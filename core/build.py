"""Build the C++ algorithm library as the Python extension module `daa_core`.

Usage (from the project root):
    python core/build.py

The module is written to the project root (daa_core.cp313-win_amd64.pyd on Windows),
so `import daa_core` works for the pipeline, the API and the tests.

Compiler: a 64-bit MinGW-w64 g++ (WinLibs UCRT build). Set the CXX environment
variable to override the automatic search. Everything except python3XX.dll is linked
statically, so the module needs no extra DLLs at run time.
"""
from __future__ import annotations

import glob
import os
import shutil
import subprocess
import sys
import sysconfig
import time
from pathlib import Path

import pybind11

CORE = Path(__file__).resolve().parent
ROOT = CORE.parent
MODULE = "daa_core"


def _is_64bit_gxx(path: str) -> bool:
    try:
        out = subprocess.run([path, "-dumpmachine"], capture_output=True, text=True, timeout=30)
        return "x86_64" in out.stdout
    except (OSError, subprocess.SubprocessError):
        return False


def find_compiler() -> str:
    """Return the path of a 64-bit g++, preferring $CXX, then WinLibs, then PATH."""
    candidates: list[str] = []
    if os.environ.get("CXX"):
        candidates.append(os.environ["CXX"])
    local = os.environ.get("LOCALAPPDATA", "")
    candidates += glob.glob(
        os.path.join(local, "Microsoft", "WinGet", "Packages", "BrechtSanders.WinLibs*", "mingw64", "bin", "g++.exe")
    )
    which = shutil.which("g++")
    if which:
        candidates.append(which)
    for c in candidates:
        if _is_64bit_gxx(c):
            return c
    sys.exit("No 64-bit g++ found. Install WinLibs (winget install BrechtSanders.WinLibs.POSIX.UCRT) or set CXX.")


def python_dll() -> Path:
    name = f"python{sys.version_info.major}{sys.version_info.minor}.dll"
    dll = Path(sys.base_prefix) / name
    if not dll.exists():
        sys.exit(f"Cannot find {dll}")
    return dll


def build(debug: bool = False) -> Path:
    cxx = find_compiler()
    sources = sorted(str(p) for p in (CORE / "src").glob("*.cpp")) + sorted(
        str(p) for p in (CORE / "bindings").glob("*.cpp")
    )
    out = ROOT / f"{MODULE}{sysconfig.get_config_var('EXT_SUFFIX')}"
    cmd = [
        cxx,
        "-O0" if debug else "-O2",
        "-std=c++17",
        "-Wall",
        "-Wextra",
        "-shared",
        f"-I{CORE / 'include'}",
        f"-I{sysconfig.get_paths()['include']}",
        f"-I{pybind11.get_include()}",
        *sources,
        "-o",
        str(out),
        "-static",
        str(python_dll()),
    ]
    print(f"Compiling {len(sources)} source files with {Path(cxx).name} ...", flush=True)
    t0 = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True)
    # pyconfig.h redefines a few macros under MinGW; hide that known noise.
    noise = ("pyconfig.h", "MS_WIN64", "previous definition", "In file included from", "from ")
    msgs = [ln for ln in (result.stdout + result.stderr).splitlines() if ln.strip() and not ln.strip().startswith(noise)]
    if result.returncode != 0:
        print("\n".join(msgs))
        sys.exit(f"Build failed (exit {result.returncode}).")
    warnings = [m for m in msgs if "warning" in m]
    if warnings:
        print("\n".join(warnings[:20]))
    print(f"Built {out.name} in {time.time() - t0:.1f}s")
    return out


if __name__ == "__main__":
    build(debug="--debug" in sys.argv)
