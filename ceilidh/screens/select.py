from __future__ import annotations

import pygame

from ..screen import Repeater, Screen
from ..display.theme import ACCENT, PANEL
from ..audio import play_preview
from ..input import InputEvent
from .menu import ListScreen



class SongSelect(ListScreen):
    allows_attract = True

    def __init__(self, app) -> None:
        super().__init__(app)
        self.items = app.songs
        self.preview_timer = 0.0
        self.preview_song = None
        self.banner_cache: dict[str, pygame.Surface | None] = {}

    def on_enter(self) -> None:
        super().on_enter()
        self.items = self.app.songs
        self.index = min(self.index, max(0, len(self.items) - 1))
        self.preview_timer = 0.4
        self.preview_song = None

    def on_exit(self) -> None:
        self.repeat.clear()

    def move(self, delta: int) -> None:
        super().move(delta)
        self.preview_timer = 0.35

    def adjust(self, delta: int, player: int) -> None:
        self.move(delta * 8)

    def activate(self, player: int) -> None:
        if not self.items:
            return
        self.app.push(DifficultySelect(self.app, self.items[self.index]))

    def cancel(self) -> None:
        pygame.mixer.music.stop()
        self.app.pop()

    def update(self, dt: float) -> None:
        super().update(dt)
        if self.preview_timer > 0:
            self.preview_timer -= dt
            if self.preview_timer <= 0 and self.items:
                song = self.items[self.index]
                if song is not self.preview_song:
                    self.preview_song = song
                    play_preview(song.music, song.sample_start, self.cfg.music_volume * 0.7)

    def banner(self, song) -> pygame.Surface | None:
        if song.banner is None:
            return None
        key = str(song.banner)
        if key not in self.banner_cache:
            try:
                image = pygame.image.load(key).convert_alpha()
            except (pygame.error, FileNotFoundError):
                image = None
            self.banner_cache[key] = image
        return self.banner_cache[key]

    def draw(self, surface: pygame.Surface) -> None:
        self.draw_background(surface)
        width, height = surface.get_size()
        scale = self.app.scale

        if not self.items:
            self.fonts.draw(surface, "No songs found", (width // 2, height // 2), int(48 * scale),
                            (220, 120, 120), anchor="center")
            for i, path in enumerate(self.app.song_paths):
                self.fonts.draw(surface, str(path), (width // 2, height // 2 + int((40 + i * 26) * scale)),
                                int(22 * scale), (150, 150, 175), anchor="center")
            return

        song = self.items[self.index]
        self.fonts.draw(surface, "SELECT SONG", (int(40 * scale), int(44 * scale)), int(44 * scale),
                        ACCENT, bold=True)
        self.fonts.draw(surface, f"{self.index + 1} / {len(self.items)}",
                        (width - int(40 * scale), int(48 * scale)), int(26 * scale),
                        (150, 150, 175), anchor="topright")

        # song wheel
        rows = 11
        centre_y = int(height * 0.52)
        row_h = int(46 * scale)
        list_x = int(width * 0.05)
        list_w = int(width * 0.52)
        for offset in range(-(rows // 2), rows // 2 + 1):
            i = self.index + offset
            if not (0 <= i < len(self.items)):
                continue
            entry = self.items[i]
            y = centre_y + offset * row_h
            selected = offset == 0
            rect = pygame.Rect(list_x, y - row_h // 2 + 2, list_w, row_h - 4)
            pygame.draw.rect(surface, (58, 40, 78) if selected else PANEL, rect, border_radius=6)
            if selected:
                pygame.draw.rect(surface, ACCENT, rect, 2, border_radius=6)
            colour = (255, 255, 255) if selected else (170, 170, 190)
            title = entry.display_title
            if len(title) > 40:
                title = title[:38] + "..."
            self.fonts.draw(surface, title, (list_x + int(14 * scale), y), int(30 * scale),
                            colour, bold=selected, anchor="midleft")
            self.fonts.draw(surface, entry.pack or "", (list_x + list_w - int(14 * scale), y),
                            int(20 * scale), (140, 140, 165), anchor="midright")

        # detail panel
        panel = pygame.Rect(int(width * 0.60), int(height * 0.16), int(width * 0.35), int(height * 0.68))
        pygame.draw.rect(surface, PANEL, panel, border_radius=10)
        pygame.draw.rect(surface, (80, 70, 110), panel, 2, border_radius=10)

        y = panel.top + int(18 * scale)
        banner = self.banner(song)
        if banner is not None:
            target_w = panel.width - int(32 * scale)
            target_h = int(target_w * banner.get_height() / max(1, banner.get_width()))
            target_h = min(target_h, int(160 * scale))
            scaled = pygame.transform.smoothscale(banner, (target_w, target_h))
            surface.blit(scaled, (panel.left + int(16 * scale), y))
            y += target_h + int(14 * scale)

        self.fonts.draw(surface, song.title[:28], (panel.centerx, y), int(34 * scale),
                        (255, 255, 255), bold=True, anchor="midtop")
        y += int(38 * scale)
        self.fonts.draw(surface, song.artist[:32], (panel.centerx, y), int(24 * scale),
                        (180, 180, 200), anchor="midtop")
        y += int(34 * scale)
        self.fonts.draw(surface, f"BPM {song.timing.display_bpm()}", (panel.centerx, y),
                        int(24 * scale), (160, 200, 255), anchor="midtop")
        y += int(36 * scale)

        for chart in song.charts_for("single"):
            self.fonts.draw(surface, chart.difficulty, (panel.left + int(20 * scale), y),
                            int(24 * scale), chart.colour)
            self.fonts.draw(surface, str(chart.meter), (panel.right - int(20 * scale), y),
                            int(24 * scale), chart.colour, bold=True, anchor="topright")
            y += int(28 * scale)
        doubles = song.charts_for("double")
        if doubles:
            y += int(6 * scale)
            self.fonts.draw(surface, f"+ {len(doubles)} doubles chart(s)",
                            (panel.left + int(20 * scale), y), int(20 * scale), (150, 220, 200))

        self.fonts.draw(surface, "UP/DOWN browse   LEFT/RIGHT jump   START pick   BACK menu",
                        (width // 2, height - int(28 * scale)), int(22 * scale),
                        (140, 140, 165), anchor="center")


class DifficultySelect(Screen):
    def __init__(self, app, song) -> None:
        super().__init__(app)
        self.song = song
        self.repeat = Repeater()
        self.mode = "versus"
        self.cursor = [0, 0]
        self.locked = [False, False]
        pads = app.input.pad_count()
        self.joined = [True, pads >= 2]
        self.message = ""

    def on_enter(self) -> None:
        self.locked = [False, False]
        self.repeat.clear()
        self.clamp()

    def charts(self) -> list:
        return self.song.charts_for("double" if self.mode == "double" else "single")

    def has_doubles(self) -> bool:
        return bool(self.song.charts_for("double"))

    def clamp(self) -> None:
        count = max(1, len(self.charts()))
        self.cursor = [min(c, count - 1) for c in self.cursor]

    def toggle_mode(self) -> None:
        if not self.has_doubles():
            self.message = "no doubles chart for this song"
            return
        self.mode = "double" if self.mode == "versus" else "versus"
        self.locked = [False, False]
        if self.mode == "double":
            self.joined = [True, False]
        else:
            self.joined = [True, self.app.input.pad_count() >= 2]
        self.clamp()

    def handle_input(self, events: list[InputEvent]) -> None:
        for ev in events:
            if not ev.pressed:
                self.repeat.release(ev.player, ev.action)
                continue
            if ev.action in ("up", "down"):
                self.repeat.press(ev.player, ev.action)
                self._move(ev.player, -1 if ev.action == "up" else 1)
            elif ev.action in ("left", "right"):
                self.toggle_mode()
            elif ev.action == "start":
                self._confirm(ev.player)
            elif ev.action == "back":
                self._cancel(ev.player)

    def _move(self, player: int, delta: int) -> None:
        if self.mode == "double" and player != 0:
            return
        if not self.joined[player] or self.locked[player]:
            return
        count = len(self.charts())
        if count:
            self.cursor[player] = (self.cursor[player] + delta) % count

    def _confirm(self, player: int) -> None:
        if self.mode == "double" and player != 0:
            return
        if not self.charts():
            return
        if not self.joined[player]:
            self.joined[player] = True
            self.cursor[player] = self.cursor[0]
            return
        self.locked[player] = True
        if all(self.locked[p] for p in range(2) if self.joined[p]):
            self._start()

    def _cancel(self, player: int) -> None:
        if self.locked[player]:
            self.locked[player] = False
            return
        if player == 1 and self.joined[1]:
            self.joined[1] = False
            return
        self.app.pop()

    def _start(self) -> None:
        from .game import Gameplay

        charts = self.charts()
        assignments: dict[int, object] = {}
        for player in range(2):
            if self.joined[player]:
                assignments[player] = charts[self.cursor[player]]
        pygame.mixer.music.stop()
        self.app.push(Gameplay(self.app, self.song, assignments, self.mode))

    def update(self, dt: float) -> None:
        for player, action in self.repeat.update(dt):
            self._move(player, -1 if action == "up" else 1)

    def draw(self, surface: pygame.Surface) -> None:
        surface.blit(self.app.background, (0, 0))
        width, height = surface.get_size()
        scale = self.app.scale
        charts = self.charts()

        self.fonts.draw(surface, self.song.display_title[:44], (width // 2, int(56 * scale)),
                        int(46 * scale), (255, 255, 255), bold=True, anchor="center")
        self.fonts.draw(surface, f"{self.song.artist}   BPM {self.song.timing.display_bpm()}",
                        (width // 2, int(96 * scale)), int(26 * scale), (170, 170, 195), anchor="center")

        mode_label = "DOUBLES (both pads, P1)" if self.mode == "double" else "VERSUS (one pad each)"
        self.fonts.draw(surface, f"< {mode_label} >", (width // 2, int(140 * scale)),
                        int(30 * scale), (140, 220, 210), bold=True, anchor="center")

        if not charts:
            self.fonts.draw(surface, "no charts in this mode", (width // 2, height // 2),
                            int(36 * scale), (220, 120, 120), anchor="center")
            return

        players = [0] if self.mode == "double" else [0, 1]
        for slot, player in enumerate(players):
            column_x = width // 2 if len(players) == 1 else int(width * (0.27 + 0.46 * slot))
            joined = self.joined[player]
            label = f"P{player + 1}"
            self.fonts.draw(surface, label, (column_x, int(196 * scale)), int(34 * scale),
                            (255, 255, 255) if joined else (110, 110, 130), bold=True, anchor="center")
            self.fonts.draw(surface, self.app.input.device_name(player)[:22],
                            (column_x, int(224 * scale)), int(18 * scale), (130, 130, 155), anchor="center")

            if not joined:
                self.fonts.draw(surface, "press START to join", (column_x, int(300 * scale)),
                                int(28 * scale), (170, 170, 190), anchor="center")
                continue

            top = int(266 * scale)
            for i, chart in enumerate(charts):
                y = top + i * int(56 * scale)
                selected = i == self.cursor[player]
                rect = pygame.Rect(column_x - int(180 * scale), y - int(24 * scale),
                                   int(360 * scale), int(48 * scale))
                pygame.draw.rect(surface, (55, 38, 74) if selected else PANEL, rect, border_radius=8)
                if selected:
                    border = (90, 230, 120) if self.locked[player] else ACCENT
                    pygame.draw.rect(surface, border, rect, 3, border_radius=8)
                # three zones across the row rather than a centred label that
                # the difficulty name can grow into
                meter_left = rect.right - int(14 * scale)
                self.fonts.draw(surface, str(chart.meter), (meter_left, y),
                                int(32 * scale), chart.colour, bold=True, anchor="midright")
                steps_right = meter_left - int(34 * scale)
                self.fonts.draw(surface, f"{chart.tap_count()} steps", (steps_right, y),
                                int(18 * scale), (160, 160, 185), anchor="midright")
                self.fonts.draw(surface, chart.difficulty, (rect.left + int(16 * scale), y),
                                int(26 * scale), chart.colour, bold=selected, anchor="midleft")

            if self.locked[player]:
                self.fonts.draw(surface, "READY", (column_x, top + len(charts) * int(56 * scale) + int(16 * scale)),
                                int(32 * scale), (110, 235, 130), bold=True, anchor="center")

        if self.message:
            self.fonts.draw(surface, self.message, (width // 2, height - int(64 * scale)),
                            int(22 * scale), (220, 150, 90), anchor="center")
        self.fonts.draw(surface, "UP/DOWN difficulty   LEFT/RIGHT mode   START ready   BACK cancel",
                        (width // 2, height - int(28 * scale)), int(22 * scale),
                        (140, 140, 165), anchor="center")
