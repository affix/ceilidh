from __future__ import annotations

import pygame

from ..display import art, video
from ..screen import Repeater, Screen
from ..input import InputEvent

from ..display.theme import ACCENT, PANEL, PANEL_SELECTED


class ListScreen(Screen):
    """Shared vertical-list behaviour driven by any connected pad."""

    def __init__(self, app) -> None:
        super().__init__(app)
        self.index = 0
        self.repeat = Repeater()
        self.items: list = []

    def item_count(self) -> int:
        return len(self.items)

    def move(self, delta: int) -> None:
        count = self.item_count()
        if count:
            self.index = (self.index + delta) % count

    def on_enter(self) -> None:
        self.repeat.clear()

    def activate(self, player: int) -> None:
        pass

    def adjust(self, delta: int, player: int) -> None:
        pass

    def cancel(self) -> None:
        self.app.pop()

    def handle_input(self, events: list[InputEvent]) -> None:
        for ev in events:
            if ev.pressed:
                if ev.action in ("up", "down", "left", "right"):
                    self.repeat.press(ev.player, ev.action)
                    self._fire(ev.player, ev.action)
                elif ev.action == "start":
                    self.activate(ev.player)
                elif ev.action == "back":
                    self.cancel()
            else:
                self.repeat.release(ev.player, ev.action)

    def _fire(self, player: int, action: str) -> None:
        if action == "up":
            self.move(-1)
        elif action == "down":
            self.move(1)
        elif action == "left":
            self.adjust(-1, player)
        elif action == "right":
            self.adjust(1, player)

    def update(self, dt: float) -> None:
        for player, action in self.repeat.update(dt):
            self._fire(player, action)

    def draw_background(self, surface: pygame.Surface) -> None:
        surface.blit(self.app.background, (0, 0))


class MainMenu(ListScreen):
    allows_attract = True

    HOLD_TO_QUIT = 3.0

    def __init__(self, app) -> None:
        super().__init__(app)
        self.items = [
            ("Play", self._play),
            ("Demo Mode", self._demo),
            ("Pads & Bindings", self._bindings),
            ("Calibrate Offset", self._calibrate),
            ("Options", self._options),
            ("Rescan Songs", self._rescan),
        ]
        if not self.cfg.kiosk:
            self.items.append(("Quit", self._quit))
        self.back_held = 0.0

    def on_enter(self) -> None:
        super().on_enter()
        pygame.mixer.music.stop()

    def activate(self, player: int) -> None:
        self.items[self.index][1]()

    def cancel(self) -> None:
        pass

    def _play(self) -> None:
        from .select import SongSelect

        if not self.app.songs:
            self.app.rescan()
        if not self.app.songs:
            return
        self.app.push(SongSelect(self.app))

    def _demo(self) -> None:
        from ..gameplay.demo import build_demo

        if not self.app.songs:
            self.app.rescan()
        demo = build_demo(self.app)
        if demo is not None:
            self.app.push(demo)

    def _bindings(self) -> None:
        from .setup import BindingScreen

        self.app.push(BindingScreen(self.app))

    def _calibrate(self) -> None:
        from .setup import CalibrateScreen

        self.app.push(CalibrateScreen(self.app))

    def _options(self) -> None:
        self.app.push(OptionsScreen(self.app))

    def _rescan(self) -> None:
        self.app.rescan()

    def _quit(self) -> None:
        self.app.quit()

    def update(self, dt: float) -> None:
        super().update(dt)
        if not self.cfg.kiosk:
            return
        # there is no Quit item on a kiosk, so leaving takes a deliberate hold
        if any(self.app.input.held(player, "back") for player in range(2)):
            self.back_held += dt
            if self.back_held >= self.HOLD_TO_QUIT:
                self.app.quit()
        else:
            self.back_held = 0.0

    def draw(self, surface: pygame.Surface) -> None:
        self.draw_background(surface)
        width, height = surface.get_size()
        scale = self.app.scale

        logo = art.logo(int(min(width * 0.38, 520 * scale)))
        if logo is not None:
            surface.blit(logo, logo.get_rect(midtop=(width // 2, int(24 * scale))))
            below = int(24 * scale) + logo.get_height()
        else:
            self.fonts.draw(surface, "Ceilidh", (width // 2, int(90 * scale)), int(96 * scale),
                            ACCENT, bold=True, anchor="center")
            below = int(126 * scale)

        self.fonts.draw(surface, f"{len(self.app.songs)} songs loaded",
                        (width // 2, below + int(6 * scale)), int(26 * scale),
                        (170, 170, 190), anchor="midtop")

        top = below + int(58 * scale)
        for i, (label, _) in enumerate(self.items):
            selected = i == self.index
            y = top + i * int(54 * scale)
            colour = (255, 255, 255) if selected else (165, 165, 185)
            if selected:
                rect = pygame.Rect(width // 2 - int(220 * scale), y - int(22 * scale),
                                   int(440 * scale), int(44 * scale))
                pygame.draw.rect(surface, (60, 40, 80), rect, border_radius=8)
                pygame.draw.rect(surface, ACCENT, rect, 2, border_radius=8)
            self.fonts.draw(surface, label, (width // 2, y), int(38 * scale), colour,
                            bold=selected, anchor="center")

        pads = self.app.input.pad_count()
        info = [
            f"P1 pad: {self.app.input.device_name(0)}",
            f"P2 pad: {self.app.input.device_name(1)}",
            f"{pads} controller(s) detected",
        ]
        for i, line in enumerate(info):
            self.fonts.draw(surface, line, (int(24 * scale), height - int((110 - i * 30) * scale)),
                            int(24 * scale), (150, 150, 175))

        if self.cfg.kiosk and self.back_held > 0.4:
            remaining = max(0.0, self.HOLD_TO_QUIT - self.back_held)
            self.fonts.draw(surface, f"hold to exit  {remaining:0.1f}",
                            (width // 2, height - int(70 * scale)), int(30 * scale),
                            (255, 200, 120), bold=True, anchor="center")

        if self.app.scan_errors:
            self.fonts.draw(surface, f"{len(self.app.scan_errors)} song(s) skipped - see console",
                            (width - int(24 * scale), height - int(30 * scale)), int(22 * scale),
                            (200, 140, 90), anchor="bottomright")


class OptionsScreen(ListScreen):
    def __init__(self, app) -> None:
        super().__init__(app)
        self.items = [
            "P1 Scroll Speed",
            "P2 Scroll Speed",
            "Scroll Direction",
            "Speed Mode",
            "Timing Windows",
            "No Fail",
            "Music Volume",
            "Global Offset",
            "Input Lag",
            "Resolution",
            "Fullscreen",
            "Background",
            "Background Dim",
            "Show FPS",
            "Back",
        ]

    def activate(self, player: int) -> None:
        item = self.items[self.index]
        if item == "Back":
            self.app.pop()
        elif item == "Fullscreen":
            self.app.toggle_fullscreen()
        elif item == "Resolution":
            self.adjust(1, player)

    def adjust(self, delta: int, player: int) -> None:
        cfg = self.cfg
        item = self.items[self.index]
        if item == "P1 Scroll Speed":
            cfg.players[0].scroll_speed = max(0.5, min(8.0, round(cfg.players[0].scroll_speed + delta * 0.1, 2)))
        elif item == "P2 Scroll Speed":
            cfg.players[1].scroll_speed = max(0.5, min(8.0, round(cfg.players[1].scroll_speed + delta * 0.1, 2)))
        elif item == "Scroll Direction":
            cfg.scroll_direction = "down" if cfg.scroll_direction == "up" else "up"
        elif item == "Speed Mode":
            cfg.constant_scroll = not cfg.constant_scroll
        elif item == "Timing Windows":
            cfg.timing_scale = max(0.5, min(2.0, round(cfg.timing_scale + delta * 0.1, 2)))
        elif item == "No Fail":
            cfg.no_fail = not cfg.no_fail
        elif item == "Music Volume":
            cfg.music_volume = max(0.0, min(1.0, round(cfg.music_volume + delta * 0.05, 2)))
        elif item == "Global Offset":
            cfg.global_offset_ms = round(cfg.global_offset_ms + delta * 1.0, 1)
        elif item == "Input Lag":
            cfg.input_lag_ms = max(0.0, min(250.0, round(cfg.input_lag_ms + delta * 5.0, 1)))
        elif item == "Show FPS":
            cfg.show_fps = not cfg.show_fps
        elif item == "Fullscreen":
            self.app.toggle_fullscreen()
        elif item == "Resolution":
            choices = cfg.resolution_choices(self.app.desktop)
            position = choices.index(cfg.resolution) if cfg.resolution in choices else 0
            self.app.set_resolution(choices[(position + delta) % len(choices)])
        elif item == "Background":
            cfg.background_video = not cfg.background_video
        elif item == "Background Dim":
            cfg.background_dim = max(0.0, min(0.95, round(cfg.background_dim + delta * 0.05, 2)))

    def value_for(self, item: str) -> str:
        cfg = self.cfg
        if cfg.resolution == "native":
            resolution = f"NATIVE ({self.app.desktop[0]}x{self.app.desktop[1]})"
        else:
            resolution = cfg.resolution
        return {
            "P1 Scroll Speed": f"{cfg.players[0].scroll_speed:.1f}x",
            "P2 Scroll Speed": f"{cfg.players[1].scroll_speed:.1f}x",
            "Scroll Direction": cfg.scroll_direction.upper(),
            "Speed Mode": "CONSTANT (CMod)" if cfg.constant_scroll else "BEAT (XMod)",
            "Timing Windows": f"{cfg.timing_scale:.1f}x",
            "No Fail": "ON" if cfg.no_fail else "OFF",
            "Music Volume": f"{int(cfg.music_volume * 100)}%",
            "Global Offset": f"{cfg.global_offset_ms:+.1f} ms",
            "Input Lag": f"{cfg.input_lag_ms:.0f} ms",
            "Show FPS": "ON" if cfg.show_fps else "OFF",
            "Fullscreen": "ON" if cfg.fullscreen else "OFF",
            "Resolution": resolution,
            "Background": ("IMAGE ONLY (PI 4)" if video.too_slow()
                           else "VIDEO + IMAGE" if cfg.background_video else "IMAGE ONLY"),
            "Background Dim": f"{int(cfg.background_dim * 100)}%",
            "Back": "",
        }.get(item, "")

    def on_exit(self) -> None:
        try:
            self.cfg.save()
        except OSError:
            pass

    def draw(self, surface: pygame.Surface) -> None:
        self.draw_background(surface)
        width, _ = surface.get_size()
        scale = self.app.scale
        self.fonts.draw(surface, "OPTIONS", (width // 2, int(70 * scale)), int(64 * scale),
                        ACCENT, bold=True, anchor="center")
        top = int(136 * scale)
        for i, item in enumerate(self.items):
            selected = i == self.index
            y = top + i * int(40 * scale)
            colour = (255, 255, 255) if selected else (165, 165, 185)
            if selected:
                rect = pygame.Rect(int(width * 0.18), y - int(17 * scale), int(width * 0.64), int(34 * scale))
                pygame.draw.rect(surface, (52, 36, 70), rect, border_radius=6)
            self.fonts.draw(surface, item, (int(width * 0.20), y), int(29 * scale), colour,
                            bold=selected, anchor="midleft")
            self.fonts.draw(surface, self.value_for(item), (int(width * 0.80), y), int(29 * scale),
                            ACCENT if selected else (150, 150, 175), anchor="midright")
        self.fonts.draw(surface, "LEFT/RIGHT change   START select   BACK exit",
                        (width // 2, surface.get_height() - int(40 * scale)), int(24 * scale),
                        (140, 140, 165), anchor="center")
