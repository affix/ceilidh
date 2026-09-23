"""Font and rendered text caching."""

from __future__ import annotations

import pygame


class FontBank:
    def __init__(self) -> None:
        self._fonts: dict[tuple[int, bool], pygame.font.Font] = {}
        self._text: dict[tuple, pygame.Surface] = {}

    def font(self, size: int, bold: bool = False) -> pygame.font.Font:
        key = (size, bold)
        font = self._fonts.get(key)
        if font is None:
            font = pygame.font.Font(None, size)
            font.set_bold(bold)
            self._fonts[key] = font
        return font

    def render(
        self,
        text: str,
        size: int,
        colour: tuple[int, int, int] = (235, 235, 245),
        bold: bool = False,
    ) -> pygame.Surface:
        key = (text, size, colour, bold)
        surface = self._text.get(key)
        if surface is None:
            surface = self.font(size, bold).render(text, True, colour)
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
    ) -> pygame.Rect:
        surface = self.render(text, size, colour, bold)
        rect = surface.get_rect(**{anchor: pos})
        target.blit(surface, rect)
        return rect
