"""The note graphics, drawn once and cached.

Everything here is procedural, so there are no image assets to ship and the
arrows stay sharp at any resolution.
"""

from __future__ import annotations

import math
from functools import lru_cache

import pygame

ARROW_POLY = [
    (0.50, 0.04), (0.96, 0.46), (0.74, 0.46), (0.74, 0.96),
    (0.26, 0.96), (0.26, 0.46), (0.04, 0.46),
]

# direction -> rotation (pygame rotates counter-clockwise)
ROTATION = (90, 180, 0, 270)  # left, down, up, right

QUANT_COLOURS: tuple[tuple[int, tuple[int, int, int]], ...] = (
    (1, (235, 60, 70)),       # 4th
    (2, (70, 130, 255)),      # 8th
    (3, (150, 80, 235)),      # 12th
    (4, (245, 205, 60)),      # 16th
    (6, (235, 110, 200)),     # 24th
    (8, (245, 140, 60)),      # 32nd
    (12, (90, 220, 220)),     # 48th
    (16, (110, 230, 130)),    # 64th
)
QUANT_DEFAULT = (180, 180, 190)

OUTLINE = (12, 12, 18)


def quant_colour(beat: float) -> tuple[int, int, int]:
    for divisor, colour in QUANT_COLOURS:
        scaled = beat * divisor
        if abs(scaled - round(scaled)) < 1e-3:
            return colour
    return QUANT_DEFAULT


def _shade(colour: tuple[int, int, int], factor: float) -> tuple[int, int, int]:
    return tuple(max(0, min(255, int(c * factor))) for c in colour)  # type: ignore[return-value]


@lru_cache(maxsize=256)
def arrow_surface(size: int, colour: tuple[int, int, int], direction: int) -> pygame.Surface:
    surface = pygame.Surface((size, size), pygame.SRCALPHA)
    points = [(x * size, y * size) for x, y in ARROW_POLY]
    inner = [(size * 0.5 + (x - size * 0.5) * 0.66, size * 0.5 + (y - size * 0.5) * 0.66) for x, y in points]
    pygame.draw.polygon(surface, _shade(colour, 0.65), points)
    pygame.draw.polygon(surface, colour, inner)
    pygame.draw.polygon(surface, OUTLINE, points, max(2, size // 22))
    return pygame.transform.rotate(surface, ROTATION[direction % 4])


@lru_cache(maxsize=64)
def receptor_surface(size: int, direction: int, bright: bool = False) -> pygame.Surface:
    surface = pygame.Surface((size, size), pygame.SRCALPHA)
    points = [(x * size, y * size) for x, y in ARROW_POLY]
    colour = (235, 235, 245) if bright else (105, 105, 125)
    if bright:
        pygame.draw.polygon(surface, (255, 255, 255, 60), points)
    pygame.draw.polygon(surface, colour, points, max(3, size // 16))
    return pygame.transform.rotate(surface, ROTATION[direction % 4])


@lru_cache(maxsize=256)
def receptor_scaled(size: int, direction: int, bright: bool, grown: int) -> pygame.Surface:
    base = receptor_surface(size, direction, bright)
    if grown == base.get_width():
        return base
    return pygame.transform.smoothscale(base, (grown, grown))


@lru_cache(maxsize=512)
def burst_surface(size: int, colour: tuple[int, int, int], direction: int, grown: int,
                  alpha: int) -> pygame.Surface:
    burst = arrow_surface(size, colour, direction).copy()
    burst.set_alpha(alpha)
    if grown != burst.get_width():
        burst = pygame.transform.smoothscale(burst, (grown, grown))
    return burst


@lru_cache(maxsize=64)
def mine_surface(size: int) -> pygame.Surface:
    surface = pygame.Surface((size, size), pygame.SRCALPHA)
    centre = size / 2
    pygame.draw.circle(surface, (40, 20, 24), (centre, centre), size * 0.44)
    pygame.draw.circle(surface, (215, 60, 60), (centre, centre), size * 0.44, max(2, size // 16))
    for i in range(8):
        angle = math.radians(i * 45)
        start = (centre + math.cos(angle) * size * 0.16, centre + math.sin(angle) * size * 0.16)
        end = (centre + math.cos(angle) * size * 0.40, centre + math.sin(angle) * size * 0.40)
        pygame.draw.line(surface, (245, 120, 90), start, end, max(2, size // 20))
    return surface
