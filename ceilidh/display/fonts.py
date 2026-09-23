"""Font loading and text caching.

Two roles: the UI face for labels and menus, and the display face for
judgements, combos and anything that wants to shout. Either falls back to
pygame's built in font when its file is not bundled.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pygame

from ..paths import bundle_root

UI = "ui"
DISPLAY = "display"


#: FreeType reads both, so take whichever build of a face we were given
EXTENSIONS = (".otf", ".ttf", ".ttc")


@dataclass(frozen=True)
class Face:
    stem: str
    #: the bundled faces run larger than the built in one at the same point size
    scale: float = 1.0
    #: whether asking for bold should embolden synthetically
    synthetic_bold: bool = False


FACES = {
    UI: Face("Cinzel-Bold", scale=0.92),
    DISPLAY: Face("LuckiestGuy-Regular", scale=0.86),
}


def face_file(face: Face, directory: Path | None = None) -> Path | None:
    """The first build of this face we can find, or None."""
    directory = directory or font_dir()
    for extension in EXTENSIONS:
        candidate = directory / f"{face.stem}{extension}"
        if candidate.is_file():
            return candidate
    return None


def font_dir() -> Path:
    root = bundle_root()
    if root is not None:
        packaged = root / "ceilidh" / "assets" / "fonts"
        if packaged.is_dir():
            return packaged
    return Path(__file__).resolve().parent.parent / "assets" / "fonts"


class FontBank:
    def __init__(self) -> None:
        self._fonts: dict[tuple, pygame.font.Font] = {}
        self._text: dict[tuple, pygame.Surface] = {}
        self._missing: set[str] = set()

    def font(self, size: int, bold: bool = False, role: str = UI) -> pygame.font.Font:
        key = (size, bold, role)
        font = self._fonts.get(key)
        if font is not None:
            return font

        face = FACES.get(role)
        path = face_file(face) if face is not None else None
        if path is not None:
            font = pygame.font.Font(str(path), max(1, int(size * face.scale)))
            if bold and face.synthetic_bold:
                font.set_bold(True)
        else:
            if face is not None:
                self._missing.add(face.stem)
            font = pygame.font.Font(None, size)
            font.set_bold(bold)

        self._fonts[key] = font
        return font

    def missing_faces(self) -> set[str]:
        """Bundled faces we asked for and did not find."""
        return set(self._missing)

    def render(
        self,
        text: str,
        size: int,
        colour: tuple[int, int, int] = (235, 235, 245),
        bold: bool = False,
        role: str = UI,
    ) -> pygame.Surface:
        key = (text, size, colour, bold, role)
        surface = self._text.get(key)
        if surface is None:
            surface = self.font(size, bold, role).render(text, True, colour)
            if len(self._text) > 900:
                self._text.clear()
            self._text[key] = surface
        return surface

    def draw(
        self,
        target: pygame.Surface,
        text: str,
        pos: tuple[int, int],
        size: int,
        colour: tuple[int, int, int] = (235, 235, 245),
        bold: bool = False,
        anchor: str = "topleft",
        role: str = UI,
    ) -> pygame.Rect:
        surface = self.render(text, size, colour, bold, role)
        rect = surface.get_rect(**{anchor: pos})
        target.blit(surface, rect)
        return rect
