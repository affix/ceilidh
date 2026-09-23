"""The painted artwork, loaded once and cached at the size we draw it.

Every lookup returns None when the file is not there, so the procedural
shapes in :mod:`ceilidh.display.arrows` can stand in.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pygame

from ..paths import bundle_root

#: column order is left, down, up, right
ARROW_FILES = ("arrow_left.png", "arrow_down.png", "arrow_up.png", "arrow_right.png")
SPARK = "hit_spark.png"
MINE = "mine_hazard.png"
LOGO = "logo.png"
EMBLEM = "thistle_emblem.png"


def art_dir() -> Path:
    root = bundle_root()
    if root is not None:
        packaged = root / "ceilidh" / "assets"
        if packaged.is_dir():
            return packaged
    return Path(__file__).resolve().parent.parent / "assets"


@lru_cache(maxsize=256)
def square(name: str, size: int) -> pygame.Surface | None:
    """One piece of square artwork at the size we need it."""
    path = art_dir() / name
    if not path.is_file():
        return None
    try:
        image = pygame.image.load(str(path)).convert_alpha()
    except pygame.error:
        return None
    return pygame.transform.smoothscale(image, (size, size))


@lru_cache(maxsize=32)
def wide(name: str, width: int) -> pygame.Surface | None:
    """Artwork scaled to a width, keeping its own proportions."""
    path = art_dir() / name
    if not path.is_file():
        return None
    try:
        image = pygame.image.load(str(path)).convert_alpha()
    except pygame.error:
        return None
    height = max(1, round(width * image.get_height() / image.get_width()))
    return pygame.transform.smoothscale(image, (width, height))


@lru_cache(maxsize=64)
def arrow(size: int, direction: int) -> pygame.Surface | None:
    return square(ARROW_FILES[direction % 4], size)


@lru_cache(maxsize=64)
def receptor(size: int, direction: int, bright: bool) -> pygame.Surface | None:
    """The same arrow, knocked back so it reads as a target rather than a note."""
    base = arrow(size, direction)
    if base is None:
        return None
    shaded = base.copy()
    shade = (170, 170, 180) if bright else (64, 64, 74)
    shaded.fill((*shade, 255), special_flags=pygame.BLEND_RGBA_MULT)
    return shaded


@lru_cache(maxsize=128)
def spark(size: int, alpha: int) -> pygame.Surface | None:
    base = square(SPARK, size)
    if base is None:
        return None
    faded = base.copy()
    faded.set_alpha(alpha)
    return faded


def mine(size: int) -> pygame.Surface | None:
    return square(MINE, size)


def logo(width: int) -> pygame.Surface | None:
    return wide(LOGO, width)


def emblem(size: int) -> pygame.Surface | None:
    return square(EMBLEM, size)
