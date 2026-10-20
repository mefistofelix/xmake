# /// script
# requires-python = ">=3.11"
# dependencies = ["lz4>=4.3"]
# ///

# Xmake bundle extract/rebundle tool (Windows x64 and Linux x86_64)
#
# Extract the Lua/program tree directly from the XMZ embedded in the EXE:
#     uv run xmake_rebundle.py extract xmake-bundle.exe bundle-root
#
# Modify files under bundle-root, then rebuild the bundle:
#     uv run xmake_rebundle.py rebundle xmake-bundle.exe bundle-root xmake-bundle-patched.exe
#
# `extract` does not run Xmake and does not use %TEMP%: it finds the active embedded
# LZ4/XMZ frame in the executable, decompresses it, and writes the XMZ records directly.
#
# `rebundle` creates a deterministic LZ4/XMZ directly, without executing the input.
# It replaces an existing dedicated
# `.xmz` section in place, resizing it as needed; an upstream bundle without one gets a
# new read-only `.xmz` section once. Xmake's RIP-relative _binary_xmake_xmz_start/end
# references are repointed as needed. The new XMZ may be smaller or larger than the old one.
# Linux uses a dedicated read-only PT_LOAD mapping, reusing a non-property PT_NOTE
# header on the first rebundle and replacing the trailing payload on later runs.
# It also finds the native cache-token string in the executable and
# replaces it in place with an equally long SHA-256 prefix of the new XMZ. This gives each
# rebundled XMZ its own `.xmake0/<version>` extraction directory without changing C code.
#
# No compiler, linker, object files, source tree, or external PE tool is required.

import hashlib
import re
import struct
import sys
from pathlib import Path, PurePosixPath

import lz4.frame

LZ4_MAGIC = b"\x04\x22\x4d\x18"


def u16(data, off):
    return struct.unpack_from("<H", data, off)[0]


def u32(data, off):
    return struct.unpack_from("<I", data, off)[0]


def align(value, alignment):
    return (value + alignment - 1) // alignment * alignment


def parse_pe(data):
    if data[:2] != b"MZ":
        raise ValueError("not an MZ executable")

    pe = u32(data, 0x3C)
    if data[pe:pe + 4] != b"PE\0\0":
        raise ValueError("not a PE executable")

    coff = pe + 4
    machine = u16(data, coff)
    if machine != 0x8664:
        raise ValueError(f"only Windows x64 is supported (machine=0x{machine:04x})")

    section_count = u16(data, coff + 2)
    optional_size = u16(data, coff + 16)
    optional = coff + 20
    if u16(data, optional) != 0x20B:
        raise ValueError("expected PE32+ optional header")

    section_alignment = u32(data, optional + 32)
    file_alignment = u32(data, optional + 36)
    size_of_headers = u32(data, optional + 60)
    section_table = optional + optional_size

    sections = []
    for i in range(section_count):
        off = section_table + i * 40
        name = bytes(data[off:off + 8]).split(b"\0", 1)[0].decode("ascii", "replace")
        virtual_size, virtual_address, raw_size, raw_offset = struct.unpack_from("<IIII", data, off + 8)
        characteristics = u32(data, off + 36)
        sections.append({
            "header": off,
            "name": name,
            "virtual_size": virtual_size,
            "virtual_address": virtual_address,
            "raw_size": raw_size,
            "raw_offset": raw_offset,
            "characteristics": characteristics,
        })

    return {
        "format": "pe",
        "coff": coff,
        "optional": optional,
        "section_count": section_count,
        "section_table": section_table,
        "section_alignment": section_alignment,
        "file_alignment": file_alignment,
        "size_of_headers": size_of_headers,
        "sections": sections,
    }


def parse_elf(data):
    if data[:6] != b"\x7fELF\x02\x01" or u16(data, 18) != 62:
        raise ValueError("expected a little-endian Linux x86_64 ELF")
    phoff = struct.unpack_from("<Q", data, 32)[0]
    phsize, phcount = struct.unpack_from("<HH", data, 54)
    if phsize != 56:
        raise ValueError("unsupported ELF program-header size")
    sections, notes = [], []
    property_ranges = []
    for i in range(phcount):
        header = phoff + i * phsize
        kind, flags, offset, vaddr, _, filesz, memsz, alignment = struct.unpack_from("<IIQQQQQQ", data, header)
        if kind == 1:  # PT_LOAD: these are the ranges actually mapped by the loader
            sections.append({
                "header": header, "raw_offset": offset, "raw_size": filesz,
                "virtual_address": vaddr, "virtual_size": memsz,
                "characteristics": 0x20000000 if flags & 1 else 0,
                "alignment": alignment,
            })
        elif kind == 4:
            notes.append((header, offset, filesz))
        elif kind == 0x6474e553:  # preserve the GNU property note and its loader metadata
            property_ranges.append((offset, offset + filesz))
    spare = next((h for h, off, size in notes
                  if not any(off < end and off + size > start for start, end in property_ranges)), None)
    return {"format": "elf", "sections": sections, "spare_header": spare}


def parse_executable(data):
    return parse_elf(data) if data[:4] == b"\x7fELF" else parse_pe(data)


def file_offset_to_rva(pe, file_offset):
    for section in pe["sections"]:
        start = section["raw_offset"]
        end = start + section["raw_size"]
        if start <= file_offset < end:
            return section["virtual_address"] + file_offset - start
    raise ValueError(f"file offset 0x{file_offset:x} is not inside a PE section")


def find_rip_lea_refs(data, pe, target_rva):
    refs = []
    for section in pe["sections"]:
        if not (section["characteristics"] & 0x20000000):
            continue

        raw = section["raw_offset"]
        size = min(section["raw_size"], len(data) - raw)
        for i in range(max(0, size - 6)):
            off = raw + i
            rex, opcode, modrm = data[off:off + 3]
            if not (0x48 <= rex <= 0x4F and opcode == 0x8D and (modrm & 0xC7) == 0x05):
                continue

            disp = struct.unpack_from("<i", data, off + 3)[0]
            instruction_rva = section["virtual_address"] + i
            if instruction_rva + 7 + disp == target_rva:
                refs.append((off + 3, instruction_rva))
    return refs


def parse_xmz_records(raw):
    records = []
    p = 0
    size = len(raw)

    while p < size:
        if p + 2 > size:
            raise ValueError("truncated XMZ path length")
        name_size = int.from_bytes(raw[p:p + 2], "big")
        p += 2
        if not name_size or p + name_size + 4 > size:
            raise ValueError("invalid XMZ path")

        try:
            name = raw[p:p + name_size].decode("utf-8")
        except UnicodeDecodeError as e:
            raise ValueError("invalid XMZ UTF-8 path") from e
        p += name_size

        data_size = int.from_bytes(raw[p:p + 4], "big")
        p += 4
        if p + data_size > size:
            raise ValueError("truncated XMZ file data")

        records.append((name, raw[p:p + data_size]))
        p += data_size

    if not records:
        raise ValueError("empty XMZ")
    return records


def find_active_xmz(data, pe):
    candidates = []

    for section in pe["sections"]:
        raw_start = section["raw_offset"]
        raw_end = min(raw_start + section["raw_size"], len(data))
        pos = raw_start

        while True:
            pos = data.find(LZ4_MAGIC, pos, raw_end)
            if pos < 0:
                break

            try:
                unpacked, consumed = lz4.frame.decompress(data[pos:raw_end], return_bytes_read=True)
                if consumed <= 0 or pos + consumed > raw_end:
                    raise ValueError
                records = parse_xmz_records(unpacked)
            except Exception:
                pos += 1
                continue

            names = {name.replace("\\", "/") for name, _ in records}
            if "core/_xmake_main.lua" not in names:
                pos += 1
                continue

            start_rva = file_offset_to_rva(pe, pos)
            end_rva = start_rva + consumed
            start_refs = find_rip_lea_refs(data, pe, start_rva)
            end_refs = find_rip_lea_refs(data, pe, end_rva)
            candidates.append({
                "offset": pos,
                "size": consumed,
                "start_rva": start_rva,
                "end_rva": end_rva,
                "records": records,
                "start_refs": start_refs,
                "end_refs": end_refs,
            })
            pos += consumed

    active = [c for c in candidates if c["start_refs"] and c["end_refs"]]
    if len(active) != 1:
        raise ValueError(
            f"expected exactly one active embedded XMZ, found {len(active)} "
            f"({len(candidates)} valid XMZ frame(s) total)"
        )
    return active[0]


def safe_output_path(root, name):
    normalized = name.replace("\\", "/")
    path = PurePosixPath(normalized)
    if path.is_absolute() or not path.parts or any(part in ("", ".", "..") for part in path.parts):
        raise ValueError(f"unsafe XMZ path: {name!r}")
    if ":" in path.parts[0]:
        raise ValueError(f"unsafe XMZ path: {name!r}")
    return root.joinpath(*path.parts)


def extract_bundle(exe_path, output_dir):
    data = Path(exe_path).read_bytes()
    pe = parse_executable(data)
    xmz = find_active_xmz(data, pe)
    root = Path(output_dir)

    if root.exists():
        if not root.is_dir():
            raise ValueError(f"output path is not a directory: {root}")
        if any(root.iterdir()):
            raise ValueError(f"output directory is not empty: {root}")
    else:
        root.mkdir(parents=True)

    for name, file_data in xmz["records"]:
        path = safe_output_path(root, name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(file_data)

    print(f"XMZ: {xmz['size']:,} bytes @ file offset 0x{xmz['offset']:x}, RVA 0x{xmz['start_rva']:x}")
    print(f"files: {len(xmz['records']):,}")
    print(f"extracted: {root}")


def patch_disp32(data, disp_offset, instruction_rva, target_rva):
    disp = target_rva - (instruction_rva + 7)
    if not -(1 << 31) <= disp < (1 << 31):
        raise ValueError("new XMZ section is outside RIP-relative disp32 range")
    struct.pack_into("<i", data, disp_offset, disp)


def patch_cache_version(data, pe, old_xmz, new_xmz):
    # Official bundles store the abbreviated Git commit as a separate C string.
    # Restrict candidates to mapped native data, excluding the compressed payload,
    # and require a code reference. Fail closed if a future native layout differs.
    candidates = []
    build_dates = set(re.findall(rb"xmake_v\d+_\d+_\d+_(\d+)_", data))
    for section in pe["sections"]:
        start = section["raw_offset"]
        end = start + section["raw_size"]
        for match in re.finditer(rb"(?<![ -~])[0-9a-f]{7,12}\x00", data[start:end]):
            offset = start + match.start()
            token = match.group()[:-1]
            if old_xmz["offset"] <= offset < old_xmz["offset"] + old_xmz["size"]:
                continue
            if token in build_dates or token.startswith(b"0123456789"):
                continue
            if find_rip_lea_refs(data, pe, file_offset_to_rva(pe, offset)):
                candidates.append((offset, token))
    if len(candidates) != 1:
        raise ValueError(f"expected one referenced native cache token, found {candidates!r}")
    offset, old = candidates[0]
    replacement = hashlib.sha256(new_xmz).hexdigest()[:len(old)].encode("ascii")
    data[offset:offset + len(old)] = replacement
    return old.decode("ascii"), replacement.decode("ascii")


def build_xmz(source_dir):
    source = Path(source_dir).resolve()
    if not source.is_dir():
        raise ValueError(f"bundle root not found: {source}")
    raw = bytearray()
    for path in sorted(source.rglob("*"), key=lambda p: p.relative_to(source).as_posix()):
        if path.is_file():
            name = path.relative_to(source).as_posix().encode("utf-8")
            content = path.read_bytes()
            raw.extend(struct.pack(">H", len(name)) + name + struct.pack(">I", len(content)) + content)
    parse_xmz_records(raw)
    return lz4.frame.compress(raw, compression_level=9)


def append_and_repoint(exe_path, new_xmz, output_path):
    data = bytearray(Path(exe_path).read_bytes())
    pe = parse_pe(data)
    old = find_active_xmz(data, pe)

    old_section = next(
        section for section in pe["sections"]
        if section["raw_offset"] <= old["offset"] < section["raw_offset"] + section["raw_size"]
    )
    if old_section["name"] == ".xmz":
        if old["offset"] != old_section["raw_offset"]:
            raise ValueError("active XMZ does not start at the beginning of the .xmz section")
        if old_section is not pe["sections"][-1]:
            raise ValueError("active .xmz section is not the last PE section")
        old_raw_end = old_section["raw_offset"] + old_section["raw_size"]
        if old_raw_end != len(data):
            raise ValueError("active .xmz section is not at end of file")

        new_raw_size = align(len(new_xmz), pe["file_alignment"])
        data[old_section["raw_offset"]:] = new_xmz + b"\0" * (new_raw_size - len(new_xmz))
        struct.pack_into("<I", data, old_section["header"] + 8, len(new_xmz))
        struct.pack_into("<I", data, old_section["header"] + 16, new_raw_size)
        struct.pack_into(
            "<I", data, pe["optional"] + 8,
            u32(data, pe["optional"] + 8) - old_section["raw_size"] + new_raw_size,
        )
        struct.pack_into(
            "<I", data, pe["optional"] + 56,
            align(old_section["virtual_address"] + len(new_xmz), pe["section_alignment"]),
        )
        for ref in old["end_refs"]:
            patch_disp32(data, *ref, old["start_rva"] + len(new_xmz))

        old_token, new_token = patch_cache_version(data, pe, old, new_xmz)
        Path(output_path).write_bytes(data)
        print(f"old XMZ: {old['size']:,} bytes @ RVA 0x{old['start_rva']:x} ({len(old['start_refs'])} start ref(s), {len(old['end_refs'])} end ref(s))")
        print(f"new XMZ: {len(new_xmz):,} bytes @ RVA 0x{old['start_rva']:x} (replaced .xmz section)")
        print(f"cache token: {old_token} -> {new_token}")
        print(f"wrote: {output_path}")
        return

    new_header = pe["section_table"] + pe["section_count"] * 40
    first_raw = min(s["raw_offset"] for s in pe["sections"] if s["raw_offset"])
    if new_header + 40 > min(first_raw, pe["size_of_headers"]):
        raise ValueError("no room for another PE section header")

    virtual_end = max(
        s["virtual_address"] + max(s["virtual_size"], s["raw_size"])
        for s in pe["sections"]
    )
    new_rva = align(virtual_end, pe["section_alignment"])
    new_raw = align(len(data), pe["file_alignment"])
    new_raw_size = align(len(new_xmz), pe["file_alignment"])

    if len(data) < new_raw:
        data.extend(b"\0" * (new_raw - len(data)))
    data.extend(new_xmz)
    data.extend(b"\0" * (new_raw_size - len(new_xmz)))

    section_header = struct.pack(
        "<8sIIIIIIHHI",
        b".xmz\0\0\0\0",
        len(new_xmz),
        new_rva,
        new_raw_size,
        new_raw,
        0, 0, 0, 0,
        0x40000040,
    )
    data[new_header:new_header + 40] = section_header

    struct.pack_into("<H", data, pe["coff"] + 2, pe["section_count"] + 1)
    struct.pack_into("<I", data, pe["optional"] + 8, u32(data, pe["optional"] + 8) + new_raw_size)
    struct.pack_into(
        "<I", data, pe["optional"] + 56,
        align(new_rva + len(new_xmz), pe["section_alignment"]),
    )

    for ref in old["start_refs"]:
        patch_disp32(data, *ref, new_rva)
    for ref in old["end_refs"]:
        patch_disp32(data, *ref, new_rva + len(new_xmz))

    old_token, new_token = patch_cache_version(data, pe, old, new_xmz)
    Path(output_path).write_bytes(data)
    print(f"old XMZ: {old['size']:,} bytes @ RVA 0x{old['start_rva']:x} ({len(old['start_refs'])} start ref(s), {len(old['end_refs'])} end ref(s))")
    print(f"new XMZ: {len(new_xmz):,} bytes @ RVA 0x{new_rva:x}")
    print(f"cache token: {old_token} -> {new_token}")
    print(f"wrote: {output_path}")


def rebundle_elf(exe_path, new_xmz, output_path):
    data = bytearray(Path(exe_path).read_bytes())
    elf = parse_elf(data)
    old = find_active_xmz(data, elf)
    section = next((s for s in elf["sections"] if s["raw_offset"] == old["offset"]
                    and s["raw_size"] == old["size"] and s["raw_offset"] + s["raw_size"] == len(data)), None)
    old_token, new_token = patch_cache_version(data, elf, old, new_xmz)
    if section:
        offset, vaddr, header = section["raw_offset"], section["virtual_address"], section["header"]
        del data[offset:]
    else:
        header = elf["spare_header"]
        if header is None:
            raise ValueError("no spare ELF note header for the bundle mapping")
        offset = align(len(data), 0x1000)
        vaddr = align(max(s["virtual_address"] + s["virtual_size"] for s in elf["sections"]), 0x1000)
        data.extend(b"\0" * (offset - len(data)))
    data.extend(new_xmz)
    struct.pack_into("<IIQQQQQQ", data, header, 1, 4, offset, vaddr, vaddr, len(new_xmz), len(new_xmz), 0x1000)
    for ref in old["start_refs"]:
        patch_disp32(data, *ref, vaddr)
    for ref in old["end_refs"]:
        patch_disp32(data, *ref, vaddr + len(new_xmz))
    Path(output_path).write_bytes(data)
    Path(output_path).chmod(0o755)
    print(f"new XMZ: {len(new_xmz):,} bytes @ ELF address 0x{vaddr:x}")
    print(f"cache token: {old_token} -> {new_token}")
    print(f"wrote: {output_path}")


def rebundle(exe_path, source_dir, output_path):
    new_xmz = build_xmz(source_dir)
    if Path(exe_path).read_bytes()[:4] == b"\x7fELF":
        rebundle_elf(exe_path, new_xmz, output_path)
    else:
        append_and_repoint(exe_path, new_xmz, output_path)


def usage():
    name = Path(sys.argv[0]).name
    return (
        f"usage:\n"
        f"  uv run {name} extract  <bundle> <output-dir>\n"
        f"  uv run {name} rebundle <bundle> <bundle-root> <output>"
    )


def main():
    if len(sys.argv) < 2:
        raise SystemExit(usage())

    command = sys.argv[1]
    if command == "extract" and len(sys.argv) == 4:
        extract_bundle(sys.argv[2], sys.argv[3])
    elif command == "rebundle" and len(sys.argv) == 5:
        rebundle(sys.argv[2], sys.argv[3], sys.argv[4])
    else:
        raise SystemExit(usage())


if __name__ == "__main__":
    main()
