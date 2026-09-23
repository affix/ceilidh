from __future__ import annotations

import os
import sys
from pathlib import Path

from .chart import Song
from .paths import app_dir, frozen
from . import simfile

SIMFILE_EXT = (".ssc", ".sm", ".json")


def default_song_paths() -> list[Path]:
    paths = [Path.cwd() / "songs"]
    if frozen():
        # a folder dropped next to the .exe or beside the .app
        paths.append(app_dir() / "songs")
    else:
        paths.append(Path(__file__).resolve().parent.parent / "songs")
    if sys.platform in ("darwin", "win32"):
        paths.append(Path.home() / "Music" / "Ceilidh")
        paths.append(Path.home() / "Music" / "DanceMat")
    if sys.platform == "win32":
        local = os.environ.get("LOCALAPPDATA")
        if local:
            paths.append(Path(local) / "ceilidh" / "songs")
    paths.append(Path.home() / "Ceilidh" / "songs")
    # where the Debian package keeps them
    paths.append(Path("/var/lib/ceilidh/songs"))
    paths.append(Path.home() / ".local" / "share" / "ceilidh" / "songs")
    # the folders this game used under its old name still count
    paths.append(Path.home() / "DanceMat" / "songs")
    paths.append(Path.home() / ".local" / "share" / "dancemat" / "songs")
    seen: list[Path] = []
    for path in paths:
        if path not in seen:
            seen.append(path)
    return seen


def _pick_simfile(folder: Path) -> Path | None:
    for ext in SIMFILE_EXT:
        matches = sorted(folder.glob(f"*{ext}"))
        if matches:
            return matches[0]
    return None


def scan(roots: list[Path], max_depth: int = 4) -> tuple[list[Song], list[str]]:
    """Walk song roots and load every simfile found. Returns (songs, errors)."""
    songs: list[Song] = []
    errors: list[str] = []
    visited: set[Path] = set()

    def walk(folder: Path, depth: int, root: Path) -> None:
        if depth > max_depth:
            return
        try:
            resolved = folder.resolve()
        except OSError:
            return
        if resolved in visited:
            return
        visited.add(resolved)
        try:
            entries = sorted(folder.iterdir())
        except (OSError, PermissionError):
            return

        simfile_path = _pick_simfile(folder)
        if simfile_path is not None:
            try:
                song = simfile.load(simfile_path)
                song.pack = "" if folder.parent == root else folder.parent.name
                if song.music is None:
                    errors.append(f"{simfile_path.name}: no audio file found")
                else:
                    songs.append(song)
            except Exception as exc:  # noqa: BLE001 - a bad pack should not kill the game
                errors.append(f"{simfile_path.name}: {exc}")
            return

        for entry in entries:
            if entry.is_dir() and not entry.name.startswith("."):
                walk(entry, depth + 1, root)

    for root in roots:
        if root.is_dir():
            walk(root, 0, root)

    songs.sort(key=lambda s: (s.pack.lower(), s.title.lower()))
    return songs, errors
