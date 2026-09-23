"""Where things are, whether we are running from source or from a bundle."""

from __future__ import annotations

import sys
from pathlib import Path


def frozen() -> bool:
    """True inside a PyInstaller bundle."""
    return getattr(sys, "frozen", False)


def bundle_root() -> Path | None:
    """The directory our own files were unpacked into, when frozen."""
    if not frozen():
        return None
    return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))


def app_dir() -> Path:
    """The folder a user would think the game lives in.

    Next to the .exe on Windows, and beside the .app rather than buried inside
    it on macOS, so dropping a songs folder there does what people expect.
    """
    if not frozen():
        return Path(__file__).resolve().parent.parent
    executable = Path(sys.executable).resolve()
    for parent in executable.parents:
        if parent.suffix == ".app":
            return parent.parent
    return executable.parent
