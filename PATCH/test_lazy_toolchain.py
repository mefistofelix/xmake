# /// script
# requires-python = ">=3.11"
# ///

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def marker(name: str) -> Path:
    return ROOT / f".patch-{name}"


def clean() -> None:
    for path in ROOT.glob(".patch-*"):
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    shutil.rmtree(ROOT / ".xmake", ignore_errors=True)


def run(exe: Path, *args: str, env: dict[str, str] | None = None) -> None:
    subprocess.run([str(exe), *args], cwd=ROOT, env=env, check=True)


def require(name: str) -> None:
    assert marker(name).exists(), f"missing marker: {name}"


def forbid(name: str) -> None:
    assert not marker(name).exists(), f"unexpected marker: {name}"


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: uv run PATCH/test_lazy_toolchain.py <xmake.exe>")
    exe = Path(sys.argv[1]).resolve()
    if not exe.is_file():
        raise SystemExit(f"xmake executable not found: {exe}")

    clean()
    try:
        # Build-driven configuration: selected target + direct links=false dependency only.
        # The two build jobs collide on target:tool("cc"); internal toolchain assertions
        # prove prepare -> check -> load ordering and exactly-once initialization.
        run(exe, "build", "-j", "2", "app")
        for name in ("config-dep", "config-app", "build-dep", "use-one", "use-two"):
            require(name)
        forbid("config-unused")
        assert not marker("unused-config").exists(), "unrelated configfiles were generated during selected build"

        # Standalone config deliberately keeps all-target semantics. Use the good fake as
        # the platform toolchain so this test remains independent of MSVC/Visual Studio.
        clean()
        env = os.environ.copy()
        env["PATCH_ALLOW_BAD"] = "1"
        run(exe, "f", "-c", "--toolchain=good", env=env)
        for name in ("config-dep", "config-app", "config-unused"):
            require(name)
        assert marker("unused-config").is_dir(), "standalone config did not generate unrelated configfiles"

        print("lazy toolchain patch tests passed")
    finally:
        clean()


if __name__ == "__main__":
    main()
