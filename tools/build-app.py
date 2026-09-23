#!/usr/bin/env python3
"""Build a standalone Ceilidh for this machine.

    uv run --group package python3 tools/build-app.py

PyInstaller cannot cross compile, so a Windows .exe has to be built on Windows
and a macOS .app on macOS. Whichever we are on is what comes out.
"""

from __future__ import annotations

import argparse
import os
import shutil
import struct
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
SOURCE_ICON = REPO / "ceilidh" / "assets" / "icon.png"
BUILD = REPO / "build"
DIST = REPO / "dist"

# the sizes Windows expects inside an .ico
ICO_SIZES = (16, 24, 32, 48, 64, 128, 256)
# name, pixel size: what iconutil wants to find in an .iconset
ICNS_SIZES = (
    ("icon_16x16.png", 16), ("icon_16x16@2x.png", 32),
    ("icon_32x32.png", 32), ("icon_32x32@2x.png", 64),
    ("icon_128x128.png", 128), ("icon_128x128@2x.png", 256),
    ("icon_256x256.png", 256), ("icon_256x256@2x.png", 512),
    ("icon_512x512.png", 512), ("icon_512x512@2x.png", 1024),
)


def scaled_png(size: int, into: Path) -> Path:
    """One square PNG at the given size, scaled from the source icon."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    if not pygame.get_init():
        pygame.init()
        pygame.display.set_mode((1, 1))
    source = pygame.image.load(str(SOURCE_ICON))
    target = into / f"{size}.png"
    pygame.image.save(pygame.transform.smoothscale(source, (size, size)), str(target))
    return target


def write_ico(destination: Path) -> Path:
    """A multi size .ico, built by hand so we do not need Pillow."""
    with tempfile.TemporaryDirectory() as temp:
        images = [scaled_png(size, Path(temp)).read_bytes() for size in ICO_SIZES]

    header = struct.pack("<HHH", 0, 1, len(images))
    offset = len(header) + 16 * len(images)
    entries, payload = b"", b""
    for size, data in zip(ICO_SIZES, images):
        entries += struct.pack(
            "<BBBBHHII",
            0 if size >= 256 else size,      # 0 means 256 in an icon directory
            0 if size >= 256 else size,
            0, 0, 1, 32, len(data), offset,
        )
        payload += data
        offset += len(data)

    destination.write_bytes(header + entries + payload)
    return destination


def write_icns(destination: Path) -> Path:
    """An .icns, via the iconutil that ships with macOS."""
    iconset = destination.with_suffix(".iconset")
    if iconset.exists():
        shutil.rmtree(iconset)
    iconset.mkdir(parents=True)
    with tempfile.TemporaryDirectory() as temp:
        for name, size in ICNS_SIZES:
            shutil.copy(scaled_png(size, Path(temp)), iconset / name)
    subprocess.run(["iconutil", "--convert", "icns", str(iconset),
                    "--output", str(destination)], check=True)
    shutil.rmtree(iconset)
    return destination


def build(onefile: bool, keep_console: bool) -> int:
    if not SOURCE_ICON.is_file():
        print(f"no icon at {SOURCE_ICON}", file=sys.stderr)
        return 1
    BUILD.mkdir(exist_ok=True)

    command = [
        sys.executable, "-m", "PyInstaller",
        "--noconfirm", "--clean",
        "--name", "Ceilidh",
        "--distpath", str(DIST),
        "--workpath", str(BUILD / "pyinstaller"),
        "--specpath", str(BUILD),
        "--paths", str(REPO),
        "--add-data", f"{SOURCE_ICON}{os.pathsep}ceilidh/assets",
        "--noconsole" if not keep_console else "--console",
    ]

    if sys.platform == "win32":
        command += ["--icon", str(write_ico(BUILD / "ceilidh.ico"))]
        if onefile:
            command.append("--onefile")
    elif sys.platform == "darwin":
        command += [
            "--icon", str(write_icns(BUILD / "ceilidh.icns")),
            "--windowed",
            "--osx-bundle-identifier", "scot.keiran.ceilidh",
        ]
    else:
        if onefile:
            command.append("--onefile")

    command.append(str(REPO / "packaging" / "launcher.py"))
    print(" ".join(command))
    result = subprocess.run(command, cwd=REPO)
    if result.returncode:
        return result.returncode

    for path in sorted(DIST.iterdir()):
        if path.name.startswith("Ceilidh"):
            size = sum(f.stat().st_size for f in path.rglob("*")) if path.is_dir() \
                else path.stat().st_size
            print(f"built {path.name}  {size / 1048576:.0f} MB")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a standalone Ceilidh")
    parser.add_argument("--onedir", action="store_true",
                        help="a folder rather than a single file (starts faster)")
    parser.add_argument("--console", action="store_true",
                        help="keep a console window, for debugging a build")
    args = parser.parse_args()
    return build(onefile=not args.onedir, keep_console=args.console)


if __name__ == "__main__":
    raise SystemExit(main())
