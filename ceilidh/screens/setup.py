from __future__ import annotations

import statistics
import time

import pygame

from ..screen import Screen
from ..display.theme import ACCENT, PANEL
from ..audio import make_click
from ..config import ACTIONS, DEFAULT_PAD_BINDINGS, LANE_ACTIONS
from ..display import draw_bar
from ..input import InputEvent, describe_binding



class BindingScreen(Screen):
    """Assign pads to players and bind each panel. Driven by the keyboard so it
    still works when the pad bindings are wrong."""

    def __init__(self, app) -> None:
        super().__init__(app)
        self.rows: list[tuple[str, int, str | None]] = []
        self.index = 0
        self.capturing: tuple[int, str] | None = None
        self.message = "arrow keys move, ENTER bind, D reset, S swap pads, ESC back"
        self._build_rows()

    def _build_rows(self) -> None:
        self.rows = []
        for player in range(2):
            self.rows.append(("device", player, None))
            for action in ACTIONS:
                self.rows.append(("action", player, action))
        self.rows.append(("swap", 0, None))
        self.rows.append(("back", 0, None))

    def handle_events(self, events: list[pygame.event.Event]) -> None:
        if self.capturing is not None:
            return
        for event in events:
            if event.type != pygame.KEYDOWN:
                continue
            if event.key == pygame.K_UP:
                self.index = (self.index - 1) % len(self.rows)
            elif event.key == pygame.K_DOWN:
                self.index = (self.index + 1) % len(self.rows)
            elif event.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.activate()
            elif event.key == pygame.K_d:
                self.reset_row()
            elif event.key == pygame.K_s:
                self.swap_pads()
            elif event.key == pygame.K_ESCAPE:
                self.cfg.save()
                self.app.pop()
                return

    def handle_input(self, events: list[InputEvent]) -> None:
        if self.capturing is not None:
            return
        for ev in events:
            if not ev.pressed or not ev.from_pad:
                continue
            if ev.action == "up":
                self.index = (self.index - 1) % len(self.rows)
            elif ev.action == "down":
                self.index = (self.index + 1) % len(self.rows)
            elif ev.action == "start":
                self.activate()
            elif ev.action == "back":
                self.cfg.save()
                self.app.pop()
                return

    def activate(self) -> None:
        kind, player, action = self.rows[self.index]
        if kind == "back":
            self.cfg.save()
            self.app.pop()
        elif kind == "swap":
            self.swap_pads()
        elif kind == "device":
            self.capturing = (player, "__device__")
            self.message = f"step on any panel of P{player + 1}'s pad (ESC cancels)"
            self.app.input.start_capture(self._captured)
        elif kind == "action":
            self.capturing = (player, action)
            self.message = f"press the P{player + 1} {action.upper()} panel (ESC cancels)"
            self.app.input.start_capture(self._captured)

    def _captured(self, spec: str, instance_id: int | None) -> None:
        target = self.capturing
        self.capturing = None
        if target is None or not spec:
            self.message = "cancelled"
            return
        player, action = target
        if instance_id is not None:
            self.app.input.assign_device(player, instance_id)
        if action == "__device__":
            self.message = f"P{player + 1} pad set to {self.app.input.device_name(player)}"
        elif spec.startswith("key:"):
            self.cfg.players[player].keyboard[action] = [spec]
            self.message = f"P{player + 1} {action} -> {describe_binding(spec)} (keyboard)"
        else:
            self.cfg.players[player].bindings[action] = [spec]
            self.message = f"P{player + 1} {action} -> {describe_binding(spec)}"
        self.app.input.rebuild()
        self.cfg.save()

    def reset_row(self) -> None:
        kind, player, action = self.rows[self.index]
        if kind != "action":
            return
        self.cfg.players[player].bindings[action] = list(DEFAULT_PAD_BINDINGS[action])
        self.app.input.rebuild()
        self.message = f"P{player + 1} {action} reset to defaults"

    def swap_pads(self) -> None:
        p0 = self.app.input.player_device.get(0)
        p1 = self.app.input.player_device.get(1)
        if p0 is None or p1 is None:
            self.message = "need two pads to swap"
            return
        self.app.input.assign_device(0, p1)
        self.app.input.assign_device(1, p0)
        self.message = "pads swapped"
        self.cfg.save()

    def on_exit(self) -> None:
        self.app.input.cancel_capture()

    def draw(self, surface: pygame.Surface) -> None:
        surface.blit(self.app.background, (0, 0))
        width, height = surface.get_size()
        scale = self.app.scale

        self.fonts.draw(surface, "PADS & BINDINGS", (width // 2, int(34 * scale)),
                        int(48 * scale), ACCENT, bold=True, anchor="center")

        row_h = int(38 * scale)
        top = int(100 * scale)
        for i, (kind, player, action) in enumerate(self.rows):
            y = top + i * row_h
            selected = i == self.index
            rect = pygame.Rect(int(width * 0.06), y - row_h // 2 + 2, int(width * 0.58), row_h - 4)
            if selected:
                pygame.draw.rect(surface, (55, 38, 74), rect, border_radius=6)
                pygame.draw.rect(surface, ACCENT, rect, 2, border_radius=6)
            colour = (255, 255, 255) if selected else (175, 175, 200)

            if kind == "device":
                label = f"P{player + 1} PAD"
                value = self.app.input.device_name(player)
            elif kind == "action":
                label = f"   P{player + 1} {action}"
                pad = self.cfg.players[player].bindings.get(action, [])
                keys = self.cfg.players[player].keyboard.get(action, [])
                value = ", ".join(describe_binding(b) for b in pad[:2] + keys[:1]) or "unbound"
            elif kind == "swap":
                label = "SWAP P1/P2 PADS"
                value = ""
            else:
                label = "BACK"
                value = ""
            self.fonts.draw(surface, label, (rect.left + int(14 * scale), y), int(26 * scale),
                            colour, bold=selected, anchor="midleft")
            self.fonts.draw(surface, value, (rect.right - int(14 * scale), y), int(22 * scale),
                            (150, 200, 235) if selected else (140, 140, 170), anchor="midright")

        # live panel test
        test_x = int(width * 0.68)
        self.fonts.draw(surface, "LIVE TEST", (test_x, int(100 * scale)), int(28 * scale),
                        (235, 235, 250), bold=True)
        for player in range(2):
            base_y = int((150 + player * 190) * scale)
            self.fonts.draw(surface, f"P{player + 1}", (test_x, base_y), int(24 * scale),
                            (200, 200, 225))
            cells = {"up": (1, 0), "left": (0, 1), "down": (1, 1), "right": (2, 1)}
            size = int(44 * scale)
            for action, (cx, cy) in cells.items():
                rect = pygame.Rect(test_x + cx * (size + 6), base_y + int(26 * scale) + cy * (size + 6),
                                   size, size)
                held = self.app.input.held(player, action)
                pygame.draw.rect(surface, (110, 235, 130) if held else PANEL, rect, border_radius=6)
                pygame.draw.rect(surface, (90, 90, 120), rect, 2, border_radius=6)
            for offset, action in enumerate(("start", "back")):
                rect = pygame.Rect(test_x + 3 * (size + 6) + offset * (size + 6),
                                   base_y + int(26 * scale), size, size)
                held = self.app.input.held(player, action)
                pygame.draw.rect(surface, (235, 205, 110) if held else PANEL, rect, border_radius=6)
                pygame.draw.rect(surface, (90, 90, 120), rect, 2, border_radius=6)
                self.fonts.draw(surface, action[:2].upper(), rect.center, int(20 * scale),
                                (30, 30, 40) if held else (150, 150, 175), anchor="center")

        self.fonts.draw(surface, self.message, (width // 2, height - int(34 * scale)),
                        int(24 * scale), (200, 180, 120) if self.capturing else (150, 150, 180),
                        anchor="center")


class CalibrateScreen(Screen):
    """Step on the beat; the median error becomes the global offset."""

    INTERVAL = 0.5
    NEEDED = 16

    def __init__(self, app) -> None:
        super().__init__(app)
        self.samples: list[float] = []
        self.next_click = time.perf_counter() + 1.5
        self.last_click = 0.0
        self.flash = 0.0
        self.result: float | None = None
        try:
            self.click = make_click(volume=max(0.2, app.cfg.sfx_volume))
        except pygame.error:
            self.click = None

    def handle_input(self, events: list[InputEvent]) -> None:
        for ev in events:
            if not ev.pressed:
                continue
            if ev.action == "back":
                self.app.pop()
                return
            if ev.action == "start" and self.result is not None:
                self.cfg.global_offset_ms = self.suggested_offset_ms()
                self.cfg.save()
                self.app.pop()
                return
            if ev.action in LANE_ACTIONS and self.last_click:
                beats = [self.last_click, self.last_click + self.INTERVAL, self.last_click - self.INTERVAL]
                error = min((ev.time - b for b in beats), key=abs)
                if abs(error) < self.INTERVAL / 2:
                    self.samples.append(error)
                    self.flash = 0.2
                if len(self.samples) >= self.NEEDED:
                    trimmed = sorted(self.samples)[2:-2] or self.samples
                    self.result = statistics.median(trimmed)

    def suggested_offset_ms(self) -> float:
        # the offset is added to song time, so stepping late means the song
        # has to be read as earlier: subtract the error rather than add it
        return round(self.cfg.global_offset_ms - (self.result or 0.0) * 1000.0, 1)

    def handle_events(self, events: list[pygame.event.Event]) -> None:
        for event in events:
            if event.type == pygame.KEYDOWN and event.key == pygame.K_r:
                self.samples.clear()
                self.result = None

    def update(self, dt: float) -> None:
        now = time.perf_counter()
        self.flash = max(0.0, self.flash - dt)
        if now >= self.next_click:
            if self.click is not None:
                self.click.play()
            self.last_click = now
            self.next_click += self.INTERVAL
            if self.next_click < now:
                self.next_click = now + self.INTERVAL

    def draw(self, surface: pygame.Surface) -> None:
        surface.blit(self.app.background, (0, 0))
        width, height = surface.get_size()
        scale = self.app.scale

        self.fonts.draw(surface, "CALIBRATE OFFSET", (width // 2, int(60 * scale)),
                        int(52 * scale), ACCENT, bold=True, anchor="center")
        self.fonts.draw(surface, "step on any panel in time with the click",
                        (width // 2, int(120 * scale)), int(28 * scale), (190, 190, 215), anchor="center")

        phase = (time.perf_counter() - self.last_click) / self.INTERVAL if self.last_click else 0.0
        radius = int((70 - 26 * min(1.0, phase)) * scale)
        pygame.draw.circle(surface, (90, 70, 130), (width // 2, height // 2), int(70 * scale), 3)
        pygame.draw.circle(surface, (255, 90, 160) if self.flash <= 0 else (235, 235, 120),
                           (width // 2, height // 2), max(6, radius))

        bar = pygame.Rect(width // 2 - int(200 * scale), height // 2 + int(120 * scale),
                          int(400 * scale), int(16 * scale))
        draw_bar(surface, bar, len(self.samples) / self.NEEDED, (110, 235, 130))
        self.fonts.draw(surface, f"{len(self.samples)} / {self.NEEDED} steps",
                        (width // 2, bar.bottom + int(14 * scale)), int(24 * scale),
                        (180, 180, 205), anchor="midtop")

        self.fonts.draw(surface, f"current offset {self.cfg.global_offset_ms:+.1f} ms",
                        (width // 2, height - int(120 * scale)), int(26 * scale),
                        (170, 170, 200), anchor="center")
        if self.result is not None:
            self.fonts.draw(surface, f"suggested {self.suggested_offset_ms():+.1f} ms - START to apply",
                            (width // 2, height - int(80 * scale)), int(30 * scale),
                            (110, 235, 130), bold=True, anchor="center")
        self.fonts.draw(surface, "R restart   BACK cancel",
                        (width // 2, height - int(34 * scale)), int(22 * scale),
                        (140, 140, 170), anchor="center")
