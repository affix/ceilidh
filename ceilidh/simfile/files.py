"""Finding the audio and artwork that belong to a simfile."""

from __future__ import annotations

from pathlib import Path

AUDIO_EXT = (".ogg", ".mp3", ".wav", ".flac", ".opus", ".oga", ".m4a")
IMAGE_EXT = (".png", ".jpg", ".jpeg", ".bmp", ".webp")


def resolve(folder: Path, name: str, exts: tuple[str, ...]) -> Path | None:
    """A file named in the header, matched case insensitively."""
    name = (name or "").strip()
    if not name:
        return None
    candidate = folder / name
    if candidate.is_file():
        return candidate
    lowered = name.lower()
    for path in folder.iterdir():
        if path.name.lower() == lowered:
            return path
    return None


def guess_file(folder: Path, exts: tuple[str, ...], hints: tuple[str, ...] = ()) -> Path | None:
    """Fall back to whatever is lying next to the simfile, preferring hints."""
    files = [p for p in sorted(folder.iterdir()) if p.suffix.lower() in exts]
    for hint in hints:
        for path in files:
            if hint in path.stem.lower():
                return path
    return files[0] if files else None
