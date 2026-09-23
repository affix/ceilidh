"""Base class for everything the app can put on screen, plus menu key repeat.

This deliberately imports nothing from :mod:`ceilidh.app` at runtime, so screens
and the application can be imported in either order.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

if TYPE_CHECKING:
    from .app import App
    from .config import Config
    from .display import FontBank
    from .input import InputEvent


class Screen:
    #: kiosk mode may start the attract loop while this screen is on top
    allows_attract = False

    def __init__(self, app: App) -> None:
        self.app = app

    @property
    def cfg(self) -> Config:
        return self.app.cfg

    @property
    def fonts(self) -> FontBank:
        return self.app.fonts

    def on_enter(self) -> None:
        """Called when this screen becomes the top of the stack."""

    def on_exit(self) -> None:
        """Called when this screen stops being the top of the stack."""

    def on_resize(self) -> None:
        """Called after the display mode changes; drop any size dependent state."""

    def handle_events(self, events: list[pygame.event.Event]) -> None:
        """Raw pygame events, minus anything the app consumed."""

    def handle_input(self, events: list[InputEvent]) -> None:
        """Pad and key presses already mapped to player actions."""

    def update(self, dt: float) -> None:
        """Advance by dt seconds."""

    def draw(self, surface: pygame.Surface) -> None:
        """Paint a frame."""


class Repeater:
    """Menu key repeat for held pad directions."""

    def __init__(self, delay: float = 0.36, interval: float = 0.09) -> None:
        self.delay = delay
        self.interval = interval
        self._held: dict[tuple[int, str], float] = {}

    def press(self, player: int, action: str) -> None:
        self._held[(player, action)] = -self.delay

    def release(self, player: int, action: str) -> None:
        self._held.pop((player, action), None)

    def clear(self) -> None:
        self._held.clear()

    def update(self, dt: float) -> list[tuple[int, str]]:
        fired: list[tuple[int, str]] = []
        for key, value in list(self._held.items()):
            value += dt
            while value >= self.interval:
                value -= self.interval
                fired.append(key)
            self._held[key] = value
        return fired
