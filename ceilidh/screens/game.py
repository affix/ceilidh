"""The gameplay screen: routes input to lanes and composes the playfields."""

from __future__ import annotations

import time

import pygame

from ..audio import MusicClock, make_noise_tick
from ..chart import Chart, Song
from ..config import LANE_ACTIONS
from ..gameplay.background import Background
from ..gameplay.lane import Lane
from ..gameplay.playfield import Playfield
from ..gameplay.demo import build_demo
from ..input import InputEvent
from ..screen import Screen
from ..display import DISPLAY
from ..display.theme import ACCENT, TEXT

LEAD_IN = 3.0
END_HOLD = 1.0
ACTION_COLUMN = {action: i for i, action in enumerate(LANE_ACTIONS)}


class Gameplay(Screen):
    def __init__(self, app, song: Song, assignments: dict[int, Chart], mode: str,
                 autoplay: bool = False, demo: bool = False) -> None:
        super().__init__(app)
        self.song = song
        self.mode = mode
        self.assignments = assignments
        self.autoplay = autoplay
        self.demo = demo
        self.paused = False
        self.ending = 0.0
        self.song_time = -LEAD_IN

        self.columns = 8 if mode == "double" else 4
        self.lanes = [
            Lane(player, chart, self.columns, song.chart_timing(chart), app.cfg.timing_scale)
            for player, chart in sorted(assignments.items())
        ]
        for lane in self.lanes:
            lane.autoplay = autoplay
            lane.is_held = self._held_test(lane)

        label = "P1+P2" if mode == "double" else None
        self.playfields = [
            Playfield(lane, app.cfg, app.fonts, index, len(self.lanes), self.columns,
                      label or f"P{lane.player + 1}")
            for index, lane in enumerate(self.lanes)
        ]
        self.background: Background | None = None

        self.clock = MusicClock(song.music, lead_in=LEAD_IN, offset=app.cfg.offset,
                                volume=app.cfg.music_volume)
        self.clock.load()
        self.tick = None
        if app.cfg.sfx_volume > 0:
            try:
                self.tick = make_noise_tick(volume=app.cfg.sfx_volume * 0.35)
            except pygame.error:
                self.tick = None

    def on_enter(self) -> None:
        if self.background is None:
            self.background = Background(self.song, self.cfg, self.app.size, self.app.background)
        if not self.clock.started:
            self.clock.start()

    def on_exit(self) -> None:
        self.clock.stop()
        if self.background is not None:
            self.background.stop()
            self.background = None

    def on_resize(self) -> None:
        for field in self.playfields:
            field.clear_cache()
        if self.background is not None:
            self.background.stop()
        self.background = Background(self.song, self.cfg, self.app.size, self.app.background)

    def _held_test(self, lane: Lane):
        """Which panels are under a foot right now, for holds and mines."""
        if self.autoplay:
            return lambda column: column in lane.active_holds
        manager = self.app.input
        if self.mode == "double":
            return lambda column: manager.held(1 if column >= 4 else 0,
                                               LANE_ACTIONS[column % 4])
        player = lane.player
        return lambda column: manager.held(player, LANE_ACTIONS[column])

    def lane_for(self, player: int) -> tuple[Lane, int] | None:
        """The lane a player's steps go to, and the column offset within it."""
        if self.mode == "double":
            return self.lanes[0], 4 if player == 1 else 0
        for lane in self.lanes:
            if lane.player == player:
                return lane, 0
        return None

    def handle_input(self, events: list[InputEvent]) -> None:
        if self.demo:
            if any(ev.pressed for ev in events):
                self.quit_song()
            return
        for ev in events:
            if ev.from_pad and ev.pressed and ev.action == "back":
                # nobody on a mat can reach Q, so Back leaves outright
                self.quit_to_songs()
                return
            if ev.from_pad and ev.pressed and ev.action == "start":
                self.toggle_pause()
                continue
            if ev.action == "back" and ev.pressed:
                self.toggle_pause()
                continue
            if self.paused:
                if ev.pressed and ev.action == "start":
                    self.toggle_pause()
                continue
            if not ev.pressed or ev.action not in ACTION_COLUMN:
                continue
            target = self.lane_for(ev.player)
            if target is None:
                continue
            lane, offset = target
            # the global offset moves the arrows and the judging together, so
            # display lag has to come off the press alone
            when = self.clock.time_at(ev.time) - self.cfg.input_lag_ms / 1000.0
            judgement = lane.press(ACTION_COLUMN[ev.action] + offset, when)
            if judgement is not None and self.tick is not None:
                self.tick.play()

    def handle_events(self, events: list[pygame.event.Event]) -> None:
        for event in events:
            if event.type != pygame.KEYDOWN:
                continue
            if self.demo:
                self.quit_song()
                return
            if event.key == pygame.K_q and self.paused:
                self.quit_song()

    def toggle_pause(self) -> None:
        if self.ending:
            return
        self.paused = not self.paused
        if self.paused:
            self.clock.pause()
        else:
            self.clock.resume()

    def quit_song(self) -> None:
        self.clock.stop()
        self.app.pop()

    def quit_to_songs(self) -> None:
        """Leave past the difficulty screen, the way the results screen does."""
        from .select import DifficultySelect

        self.quit_song()
        if self.app.screens and isinstance(self.app.screens[-1], DifficultySelect):
            self.app.pop()

    def update(self, dt: float) -> None:
        if self.paused:
            return
        self.clock.update()
        self.song_time = self.clock.time_at(time.perf_counter())

        alive = False
        for lane in self.lanes:
            if lane.autoplay:
                lane.autoplay_step(self.song_time)
            lane.update(self.song_time)
            lane.tick_timers(dt)
            if not self.cfg.no_fail and lane.score.life <= 0.0 and not lane.failed:
                lane.fail()
            if not lane.failed:
                alive = True

        done = all(lane.finished(self.song_time) for lane in self.lanes)
        if not alive or done or (self.clock.started and self.clock.finished):
            self.ending += dt
            if self.ending > END_HOLD or not alive:
                self.finish()

    def finish(self) -> None:
        from .results import Results

        self.clock.stop()
        if self.demo:
            following = build_demo(self.app, exclude=self.song)
            if following is not None:
                self.app.replace(following)
            else:
                self.app.pop()
            return
        self.app.replace(Results(self.app, self.song, self.lanes, self.mode))

    def draw(self, surface: pygame.Surface) -> None:
        if self.background is not None:
            self.background.draw(surface, self.song_time)
        else:
            surface.blit(self.app.background, (0, 0))

        scale = self.app.scale
        for field in self.playfields:
            field.draw(surface, self.song_time, scale)

        self._draw_header(surface, scale)
        if self.song_time < 0:
            self._draw_countdown(surface, scale)
        if self.demo:
            self._draw_demo_badge(surface, scale)
        if self.paused:
            self._draw_pause(surface, scale)

    def _draw_header(self, surface: pygame.Surface, scale: float) -> None:
        """A hairline progress strip along the very top edge, with the title
        tucked underneath it so nothing sits in the note runway."""
        width = surface.get_width()
        end = max(1e-3, max(lane.end_time for lane in self.lanes))
        done = max(0.0, min(1.0, self.song_time / end))
        strip = max(3, int(5 * scale))
        pygame.draw.rect(surface, (20, 20, 30), (0, 0, width, strip))
        pygame.draw.rect(surface, ACCENT, (0, 0, int(width * done), strip))

        title = self.song.display_title
        size = self.fonts.fit(title, int(22 * scale), int(width * 0.6), bold=True)
        y = strip + int(4 * scale)
        self.fonts.draw(surface, title, (width // 2 + 2, y + 2), size,
                        (0, 0, 0), bold=True, anchor="midtop")
        self.fonts.draw(surface, title, (width // 2, y), size, TEXT,
                        bold=True, anchor="midtop")

    def _draw_countdown(self, surface: pygame.Surface, scale: float) -> None:
        width, height = surface.get_size()
        self.fonts.draw(surface, str(int(-self.song_time) + 1), (width // 2, height // 2),
                        int(150 * scale), (255, 255, 255), bold=True, anchor="center",
                        role=DISPLAY)

    def _draw_demo_badge(self, surface: pygame.Surface, scale: float) -> None:
        width = surface.get_width()
        badge = self.fonts.render("DEMO", int(30 * scale), (255, 210, 90), bold=True,
                                  role=DISPLAY)
        backing = pygame.Surface((badge.get_width() + int(24 * scale),
                                  badge.get_height() + int(10 * scale)), pygame.SRCALPHA)
        backing.fill((10, 10, 16, 190))
        rect = backing.get_rect(midtop=(width // 2, int(40 * scale)))
        surface.blit(backing, rect)
        surface.blit(badge, badge.get_rect(center=rect.center))
        self.fonts.draw(surface, "press anything to exit",
                        (width // 2, rect.bottom + int(6 * scale)), int(20 * scale),
                        (200, 200, 220), anchor="midtop")

    def _draw_pause(self, surface: pygame.Surface, scale: float) -> None:
        width, height = surface.get_size()
        overlay = pygame.Surface((width, height), pygame.SRCALPHA)
        overlay.fill((0, 0, 0, 170))
        surface.blit(overlay, (0, 0))
        self.fonts.draw(surface, "PAUSED", (width // 2, height // 2 - int(60 * scale)),
                        int(80 * scale), (255, 255, 255), bold=True, anchor="center")
        hint = ("START resume     BACK quit to song list" if self.app.input.pad_count()
                else "START resume     Q quit to song list")
        self.fonts.draw(surface, hint,
                        (width // 2, height // 2 + int(30 * scale)), int(30 * scale),
                        (200, 200, 220), anchor="center")
