# /// script
# requires-python = ">=3.11"
# ///

from __future__ import annotations

import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def marker(name: str) -> Path:
    return ROOT / f".patch-{name}"


def clean(*, caches: bool = True) -> None:
    for path in ROOT.glob(".patch-*"):
        if path.is_dir():
            shutil.rmtree(path)
        else:
            path.unlink()
    if caches:
        shutil.rmtree(ROOT / ".xmake", ignore_errors=True)


def run(exe: Path, *args: str) -> None:
    subprocess.run([str(exe), *args], cwd=ROOT, check=True)


def require(name: str) -> None:
    assert marker(name).exists(), f"missing marker: {name}"


def forbid(name: str) -> None:
    assert not marker(name).exists(), f"unexpected marker: {name}"


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: uv run PATCH/test_lazy_toolchain.py <xmake.exe>")
    exe = Path(sys.argv[1]).resolve()

    clean()
    try:
        # A plain config may visit every target and load descriptors, but it must not
        # enter toolchain check/load and therefore must not run on_toolchain_prepare.
        run(exe, "f", "-c", "--toolchain=good")
        for name in ("config-dep", "config-app", "config-unused"):
            require(name)
        forbid("prepare-good")
        forbid("prepare-bad")

        # Real use of good performs prepare -> check -> load; unused bad remains inert.
        clean(caches=False)
        run(exe, "build", "app")
        for name in ("config-dep", "config-app", "config-unused", "build-dep", "use-good", "prepare-good"):
            require(name)
        forbid("prepare-bad")

        print("lazy toolchain patch tests passed")
    finally:
        clean()


if __name__ == "__main__":
    main()
