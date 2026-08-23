# /// script
# requires-python = ">=3.11"
# ///

from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path


def run(exe: Path, project: Path, *args: str) -> str:
    result = subprocess.run(
        [str(exe), *args, "-P", str(project)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    return result.stdout


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: uv run PATCH/test_lazy_idl.py <xmake.exe>")
    exe = Path(sys.argv[1]).resolve()

    with tempfile.TemporaryDirectory(prefix="xmake-idl-lazy-", ignore_cleanup_errors=True) as tmp:
        project = Path(tmp)
        (project / "main.c").write_text("int value(void) { return 0; }\n", encoding="utf-8")
        (project / "xmake.lua").write_text(
            'set_project("idl-lazy-test")\n'
            'set_plat("windows")\n\n'
            'target("app")\n'
            '    set_kind("static")\n'
            '    add_files("main.c")\n'
            '    add_files("generated/*.c")\n',
            encoding="utf-8",
        )

        config_output = run(exe, project, "f", "-c")
        assert "cannot match add_files" not in config_output, "Windows IDL rule forced unrelated source-glob materialization during config"
        assert "generated\\*.c" not in config_output
        assert not (project / "generated").exists()

        (project / "xmake.lua").write_text(
            'set_project("idl-lazy-test")\n'
            'set_plat("windows")\n\n'
            'target("app")\n'
            '    set_kind("static")\n'
            '    add_files("main.c")\n'
            '    add_files("generated/*.idl")\n'
            '    on_prepare(function ()\n'
            '        local dir = path.join(os.projectdir(), "generated")\n'
            '        os.mkdir(dir)\n'
            '        io.writefile(path.join(dir, "test.idl"), "interface Test {}\\n")\n'
            '    end)\n',
            encoding="utf-8",
        )

        run(exe, project, "f", "-c")
        assert not (project / "generated").exists(), "plain config ran target preparation"

        run(exe, project, "project", "-k", "cmake")
        assert (project / "generated" / "test.idl").exists(), "on_prepare-generated IDL was not materialized"

        cmake = (project / "CMakeLists.txt").read_text(encoding="utf-8")
        include = "platform/windows/idl"
        assert cmake.count(include) == 2, "IDL autogen include was missing or duplicated"
        assert "target_include_directories(app INTERFACE" in cmake, "IDL autogen include did not remain public"

    print("lazy IDL patch tests passed")


if __name__ == "__main__":
    main()
