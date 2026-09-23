"""Window creation and the display mode rules that go with it."""

from __future__ import annotations

import pygame

from ..config import Config
from .widgets import vertical_gradient
from . import theme

#: below this many Hz a blocking flip samples the pads too coarsely to play on
LOW_REFRESH_HZ = 50


def refresh_rate() -> int:
    """The refresh rate of the display we are on, or 0 if SDL will not say."""
    for name in ("get_current_refresh_rate", "get_desktop_refresh_rates"):
        getter = getattr(pygame.display, name, None)
        if getter is None:
            continue
        try:
            value = getter()
        except pygame.error:
            continue
        if isinstance(value, list):
            value = value[0] if value else 0
        if value:
            return int(value)
    return 0


class Window:
    """Owns the display surface and everything that depends on its size."""

    def __init__(self, cfg: Config) -> None:
        self.cfg = cfg
        try:
            self.desktop = pygame.display.get_desktop_sizes()[0]
        except (pygame.error, IndexError):
            self.desktop = (1920, 1080)
        self.surface: pygame.Surface = None  # type: ignore[assignment]
        self.background: pygame.Surface = None  # type: ignore[assignment]
        self.refresh = 0
        self.low_refresh = False
        self.apply()

    @property
    def size(self) -> tuple[int, int]:
        return self.surface.get_size()

    @property
    def scale(self) -> float:
        """Layout multiplier, where 1.0 is 720p."""
        return self.surface.get_height() / 720.0

    def _create(self, size: tuple[int, int], flags: int, vsync: bool) -> None:
        try:
            self.surface = pygame.display.set_mode(size, flags, vsync=1 if vsync else 0)
        except pygame.error:
            try:
                self.surface = pygame.display.set_mode(size, flags)
            except pygame.error:
                self.surface = pygame.display.set_mode((1280, 720), pygame.SCALED)

    def apply(self) -> None:
        """(Re)create the window for the current resolution and fullscreen state."""
        size = self.cfg.surface_size(self.desktop, self.cfg.fullscreen)
        flags = pygame.SCALED
        if self.cfg.fullscreen:
            flags |= pygame.FULLSCREEN

        self._create(size, flags, self.cfg.vsync)
        self.refresh = refresh_rate()
        low = bool(self.refresh) and self.refresh < LOW_REFRESH_HZ
        if low and self.cfg.vsync:
            # a blocking flip on a 30 Hz panel would sample the pads every 33ms,
            # which is most of a Fantastic window, so drive the loop ourselves
            if not self.low_refresh:
                print(f"display is running at {self.refresh} Hz, so vsync is off for this "
                      "session and the loop is paced by hand to keep step timing tight")
            self._create(size, flags, False)
        self.low_refresh = low
        self.background = vertical_gradient(self.size, theme.BG_TOP, theme.BG_BOTTOM)

    def toggle_fullscreen(self) -> None:
        self.cfg.fullscreen = not self.cfg.fullscreen
        self.apply()

    def set_resolution(self, resolution: str) -> None:
        self.cfg.resolution = resolution
        self.apply()
