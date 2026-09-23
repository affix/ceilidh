"""The window and taskbar icon."""

from __future__ import annotations

from pathlib import Path

import pygame

ICON_PATH = Path(__file__).resolve().parent.parent / "assets" / "icon.png"


def set_window_icon(path: Path | None = None) -> bool:
    """Set the icon, if we have one. Must be called before the window is made."""
    icon = path or ICON_PATH
    if not icon.is_file():
        return False
    try:
        image = pygame.image.load(str(icon))
        pygame.display.set_icon(pygame.transform.smoothscale(image, (64, 64)))
    except (pygame.error, OSError):
        return False
    return True
