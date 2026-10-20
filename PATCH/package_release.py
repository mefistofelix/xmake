# /// script
# requires-python = ">=3.11"
# dependencies = ["lz4>=4.3"]
# ///
"""Download an official base, rebundle, validate and package the current Lua tree."""

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import tarfile
import tempfile
import urllib.request
import zipfile
from pathlib import Path

from xmake_rebundle import find_active_xmz, parse_executable, rebundle


def download(url, api=False):
    headers = {"User-Agent": "xmake-patch-release"}
    if api and os.getenv("GH_TOKEN"):
        headers["Authorization"] = "Bearer " + os.environ["GH_TOKEN"]
    with urllib.request.urlopen(urllib.request.Request(url, headers=headers), timeout=120) as response:
        return response.read()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upstream-tag", default="latest")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if not re.fullmatch(r"latest|v\d+\.\d+\.\d+", args.upstream_tag):
        parser.error("upstream tag must be latest or vMAJOR.MINOR.PATCH")
    if platform.machine().lower() not in ("amd64", "x86_64") or platform.system() not in ("Windows", "Linux"):
        parser.error("run on Windows x64 or Linux x86_64 to validate the native bundle")
    if os.getenv("XMAKE_PROGRAM_DIR"):
        parser.error("unset XMAKE_PROGRAM_DIR before validating the bundled executable")

    patchdir = Path(__file__).resolve().parent
    root = patchdir.parent
    output = (args.output or patchdir / ".validate" / "release").resolve()
    output.mkdir(parents=True, exist_ok=True)
    endpoint = "latest" if args.upstream_tag == "latest" else "tags/" + args.upstream_tag
    release = json.loads(download("https://api.github.com/repos/xmake-io/xmake/releases/" + endpoint, api=True))
    tag = release["tag_name"]
    if not re.fullmatch(r"v\d+\.\d+\.\d+", tag) or release["prerelease"] or release["draft"]:
        raise ValueError("expected an official stable Xmake release")
    windows = platform.system() == "Windows"
    suffix = "win64.exe" if windows else "linux.x86_64"
    assetname = f"xmake-bundle-{tag}.{suffix}"
    asset = next(a for a in release["assets"] if a["name"] == assetname)
    url = f"https://github.com/xmake-io/xmake/releases/download/{tag}/{assetname}"
    if asset["browser_download_url"] != url:
        raise ValueError("unexpected official asset URL")

    with tempfile.TemporaryDirectory(prefix="xmake-release-") as tmp:
        workdir = Path(tmp)
        base = workdir / assetname
        base.write_bytes(download(url))
        digest = "sha256:" + hashlib.sha256(base.read_bytes()).hexdigest()
        if digest != asset.get("digest"):
            raise ValueError(f"official asset SHA-256 mismatch: {assetname}")
        staging = workdir / "package"
        staging.mkdir()
        exe = staging / ("xmake.exe" if windows else "xmake")
        rebundle(base, root / "xmake", exe)
        env = os.environ.copy()
        env.pop("XMAKE_PROGRAM_FILE", None)
        env["XMAKE_COLORTERM"] = "nocolor"
        subprocess.run([str(exe), "test-patches", "-P", str(patchdir)], check=True, cwd=workdir, env=env)

        data = exe.read_bytes()
        xmz = find_active_xmz(data, parse_executable(data))
        info = {
            "upstream_release": tag, "official_asset": url, "official_sha256": digest[7:],
            "lua_payload_sha256": hashlib.sha256(data[xmz["offset"]:xmz["offset"] + xmz["size"]]).hexdigest(),
            "executable_sha256": hashlib.sha256(data).hexdigest(),
            "validation": "test-patches passed without XMAKE_PROGRAM_DIR; compiler tools excluded from child PATH",
        }
        (staging / "build-info.json").write_text(json.dumps(info, indent=2) + "\n", encoding="utf-8")
        shutil.copyfile(patchdir / "README.md", staging / "README.md")
        shutil.copyfile(root / "LICENSE.md", staging / "LICENSE.md")
        # Publish the exact executable that just passed, also beside PATCH/README.md.
        shutil.copy2(exe, patchdir / ("XMake.exe" if windows else "XMake"))
        stem = f"xmake-patched-{tag}.{'win64' if windows else 'linux.x86_64'}"
        archive = output / (stem + (".zip" if windows else ".tar.gz"))
        if windows:
            with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as package:
                for path in sorted(staging.iterdir()):
                    package.write(path, path.name)
        else:
            with tarfile.open(archive, "w:gz") as package:
                for path in sorted(staging.iterdir()):
                    package.add(path, arcname=path.name)
        checksum = hashlib.sha256(archive.read_bytes()).hexdigest()
        archive.with_name(archive.name + ".sha256").write_text(f"{checksum}  {archive.name}\n", encoding="ascii")
        print(f"validated release package: {archive}")


if __name__ == "__main__":
    main()
