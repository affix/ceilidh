"""Reading songs off disk, whatever format they arrived in."""

from __future__ import annotations

from pathlib import Path

from ..chart import Song
from . import jsonchart, sm
from .errors import SimfileError
from .files import AUDIO_EXT, IMAGE_EXT
from .sm import parse_note_data

__all__ = [
    "AUDIO_EXT",
    "IMAGE_EXT",
    "SimfileError",
    "load",
    "parse_note_data",
]

LOADERS = {
    ".sm": sm.load,
    ".ssc": sm.load,
    ".dwi": sm.load,
    ".json": jsonchart.load,
}


def load(path: Path) -> Song:
    """Read any supported simfile into a Song."""
    loader = LOADERS.get(path.suffix.lower())
    if loader is None:
        raise SimfileError(f"unsupported simfile: {path}")
    return loader(path)
