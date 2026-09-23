"""One place for the colours the screens share."""

from __future__ import annotations

Colour = tuple[int, int, int]

ACCENT: Colour = (255, 90, 160)
ACCENT_DIM: Colour = (150, 60, 100)

BG_TOP: Colour = (16, 16, 28)
BG_BOTTOM: Colour = (36, 20, 48)

PANEL: Colour = (26, 26, 42)
PANEL_FLAT: Colour = (24, 24, 38)
PANEL_SELECTED: Colour = (55, 38, 74)
BORDER: Colour = (80, 70, 110)

TEXT: Colour = (235, 235, 250)
TEXT_MUTED: Colour = (175, 175, 200)
TEXT_DIM: Colour = (140, 140, 170)

GOOD: Colour = (110, 235, 130)
WARN: Colour = (235, 205, 110)
BAD: Colour = (220, 80, 80)
INFO: Colour = (150, 200, 235)
