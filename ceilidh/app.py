"""The application: SDL setup, the screen stack, and the main loop."""

from __future__ import annotations

import os
import time
from pathlib import Path

import pygame

from .config import Config
from .display import FontBank, Window
from .input import InputManager
from .screen import Screen
from . import library


def prepare_sdl() -> None:
    """Hints that have to be set before pygame.init()."""
    os.environ.setdefault("SDL_JOYSTICK_HIDAPI", "1")
    os.environ.setdefault("SDL_JOYSTICK_HIDAPI_XBOX", "1")
    os.environ.setdefault("SDL_JOYSTICK_HIDAPI_XBOX_360", "1")
    os.environ.setdefault("SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", "1")
    # a dedicated joystick thread means pad events are queued as they arrive
    # instead of only when the main loop pumps
    os.environ.setdefault("SDL_JOYSTICK_THREAD", "1")


class App:
    def __init__(self, cfg: Config, song_paths: list[Path] | None = None) -> None:
        prepare_sdl()
        pygame.mixer.pre_init(44100, -16, 2, cfg.audio_buffer)
        pygame.init()
        try:
            pygame.mixer.init(44100, -16, 2, cfg.audio_buffer)
        except pygame.error:
            pass
        pygame.display.set_caption("Ceilidh")
        pygame.mouse.set_visible(False)

        self.cfg = cfg
        self.running = True
        self.screens: list[Screen] = []
        self.fonts = FontBank()
        self.clock = pygame.time.Clock()
        self.fps = 0.0
        self.last_input = time.perf_counter()

        self.song_paths = song_paths or library.default_song_paths()
        self.songs = []
        self.scan_errors: list[str] = []

        self.window = Window(cfg)
        self._vsync_working = True
        self._fast_frames = 0
        self.input = InputManager(cfg)

    @property
    def screen(self) -> pygame.Surface:
        return self.window.surface

    @property
    def background(self) -> pygame.Surface:
        return self.window.background

    @property
    def size(self) -> tuple[int, int]:
        return self.window.size

    @property
    def scale(self) -> float:
        return self.window.scale

    @property
    def desktop(self) -> tuple[int, int]:
        return self.window.desktop

    def apply_display(self) -> None:
        self.window.apply()
        for screen in self.screens:
            screen.on_resize()

    def toggle_fullscreen(self) -> None:
        self.cfg.fullscreen = not self.cfg.fullscreen
        self.apply_display()

    def set_resolution(self, resolution: str) -> None:
        self.cfg.resolution = resolution
        self.apply_display()

    def rescan(self) -> None:
        self.songs, self.scan_errors = library.scan(self.song_paths)

    def push(self, screen: Screen) -> None:
        if self.screens:
            self.screens[-1].on_exit()
        self.screens.append(screen)
        screen.on_enter()

    def pop(self) -> None:
        if not self.screens:
            return
        self.screens.pop().on_exit()
        if self.screens:
            self.screens[-1].on_enter()
        else:
            self.running = False

    def replace(self, screen: Screen) -> None:
        if self.screens:
            self.screens.pop().on_exit()
        self.screens.append(screen)
        screen.on_enter()

    def quit(self) -> None:
        self.running = False

    def _maybe_attract(self, top: Screen, now: float) -> None:
        """In kiosk mode an idle menu falls back into the demo loop."""
        if not self.cfg.kiosk or not top.allows_attract:
            return
        if now - self.last_input < self.cfg.attract_seconds:
            return
        from .gameplay.demo import build_demo

        demo = build_demo(self)
        if demo is not None:
            self.last_input = now
            self.push(demo)

    @staticmethod
    def is_fullscreen_shortcut(event: pygame.event.Event) -> bool:
        if event.type != pygame.KEYDOWN:
            return False
        if event.key == pygame.K_F11:
            return True
        if event.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and event.mod & pygame.KMOD_ALT:
            return True
        # cmd+F on macOS, where F11 belongs to Mission Control
        return event.key == pygame.K_f and bool(event.mod & pygame.KMOD_META)

    def _dispatch(self, events: list[pygame.event.Event]) -> None:
        passthrough = []
        for event in events:
            if event.type in (pygame.KEYDOWN, pygame.JOYBUTTONDOWN, pygame.JOYHATMOTION,
                              pygame.JOYAXISMOTION):
                self.last_input = time.perf_counter()
            if event.type == pygame.QUIT:
                self.running = False
            elif self.is_fullscreen_shortcut(event):
                self.toggle_fullscreen()
            else:
                passthrough.append(event)
        if not self.screens:
            return
        events = passthrough
        input_events = self.input.process(events)
        top = self.screens[-1]
        top.handle_events(events)
        top.handle_input(input_events)

    def _pace(self, now: float, dt: float) -> None:
        """Hold the frame rate without blunting the input sampling rate."""
        if self.cfg.vsync and self._vsync_working and not self.window.low_refresh:
            # the blocking flip is the pacer. Sleeping as well would push the
            # next flip past the vblank and halve the frame rate, so only
            # step in if the driver turns out to be ignoring vsync entirely
            if dt < 0.5 / max(1, self.cfg.fps):
                self._fast_frames += 1
                if self._fast_frames > 120:
                    self._vsync_working = False
            else:
                self._fast_frames = 0
            self.clock.tick()
            return

        if self.cfg.vsync and not self.window.low_refresh:
            self.clock.tick(self.cfg.fps)
            return

        # spend the slack polling input instead of sleeping in one lump,
        # which keeps step timestamps within a millisecond or two
        deadline = now + 1.0 / max(1, self.cfg.fps)
        current = self.screens[-1] if self.screens else None
        while (
            time.perf_counter() < deadline
            and self.running
            and self.screens
            and self.screens[-1] is current
        ):
            events = pygame.event.get()
            if events:
                self._dispatch(events)
            else:
                time.sleep(0.0008)
        self.clock.tick()

    def run(self) -> None:
        last = time.perf_counter()
        while self.running and self.screens:
            now = time.perf_counter()
            dt = min(now - last, 0.1)
            last = now

            self._dispatch(pygame.event.get())
            if not (self.running and self.screens):
                break

            top = self.screens[-1]
            top.update(dt)
            self._maybe_attract(top, now)
            top.draw(self.screen)
            if self.cfg.show_fps:
                self.fonts.draw(
                    self.screen, f"{self.fps:0.0f} fps",
                    (self.size[0] - 8, 6), 22, (140, 140, 160), anchor="topright",
                )
            pygame.display.flip()
            self._pace(now, dt)
            self.fps = self.clock.get_fps()

        try:
            self.cfg.save()
        except OSError:
            pass
        pygame.quit()
