"""Drawing one lane: where the arrows go and what they look like on the way."""

from __future__ import annotations

from dataclasses import dataclass

import pygame

from ..chart import HOLD, MINE, ROLL
from ..config import Config
from ..display import (
    FontBank,
    arrow_surface,
    burst_surface,
    draw_bar,
    mine_surface,
    quant_colour,
    receptor_scaled,
)
from .judge import JUDGEMENT_COLOUR
from .lane import FLASH_TIME, JUDGEMENT_TIME, COMBO_TIME, Lane

HOLD_BODY = (90, 200, 120)
ROLL_BODY = (180, 120, 230)
DROPPED_BODY = (90, 90, 100)
COMBO_COLOUR = (255, 225, 140)
LIFE_OK = (110, 235, 130)
LIFE_LOW = (235, 120, 90)


@dataclass(frozen=True)
class Geometry:
    """Where a playfield sits on a surface of a given size."""

    arrow: int
    spacing: float
    span: float
    left: int
    centre: int
    receptor_y: int
    direction: int

    def column_x(self, column: int) -> int:
        return int(self.left + column * self.spacing)


def layout(size: tuple[int, int], index: int, count: int, columns: int,
           scroll_down: bool) -> Geometry:
    """Playfields tile the whole width; the arrows size themselves to fit."""
    width, height = size
    gutter = max(4, int(width * 0.006))
    slot = (width - gutter * (count + 1)) / count
    arrow = int(min(slot * 0.22, height * 0.135))
    spacing = arrow * 1.1
    span = (columns - 1) * spacing + arrow
    centre = int(gutter * (index + 1) + slot * (index + 0.5))
    left = int(centre - (columns - 1) * spacing / 2)
    if scroll_down:
        return Geometry(arrow, spacing, span, left, centre, height - int(height * 0.17), -1)
    return Geometry(arrow, spacing, span, left, centre, int(height * 0.13), 1)


class Playfield:
    """Renders a Lane. One per lane, reused every frame."""

    def __init__(self, lane: Lane, cfg: Config, fonts: FontBank, index: int, count: int,
                 columns: int, label: str) -> None:
        self.lane = lane
        self.cfg = cfg
        self.fonts = fonts
        self.index = index
        self.count = count
        self.columns = columns
        self.label = label
        self._panels: dict[tuple, pygame.Surface] = {}

    def clear_cache(self) -> None:
        self._panels.clear()

    def _panel(self, size: tuple[int, int], colour: tuple[int, int, int, int]) -> pygame.Surface:
        panel = self._panels.get((size, colour))
        if panel is None:
            panel = pygame.Surface(size, pygame.SRCALPHA)
            panel.fill(colour)
            self._panels[(size, colour)] = panel
        return panel

    def geometry(self, size: tuple[int, int]) -> Geometry:
        return layout(size, self.index, self.count, self.columns,
                      self.cfg.scroll_direction == "down")

    def draw(self, surface: pygame.Surface, song_time: float, scale: float) -> None:
        lane = self.lane
        width, height = surface.get_size()
        geo = self.geometry((width, height))
        beat = lane.timing.time_to_beat(song_time)
        speed = self.cfg.players[lane.player].scroll_speed
        # keep the note spacing proportional to the arrows so a given scroll
        # speed feels the same at every resolution
        px_per_beat = geo.arrow * 1.75 * speed
        px_per_sec = geo.arrow * 4.7 * speed
        constant = self.cfg.constant_scroll

        def y_for(note_beat: float, note_time: float) -> float:
            if constant:
                delta = (note_time - song_time) * px_per_sec
            else:
                delta = (note_beat - beat) * px_per_beat
            return geo.receptor_y + delta * geo.direction

        pad = int(geo.arrow * 0.18)
        field = pygame.Rect(int(geo.centre - geo.span / 2) - pad, 0, int(geo.span) + pad * 2, height)
        surface.blit(self._panel(field.size, (0, 0, 0, 70)), field.topleft)

        self._draw_receptors(surface, geo, beat)
        self._draw_notes(surface, geo, y_for, height)
        self._draw_judgement(surface, geo)
        self._draw_hud(surface, geo, field, scale, height)

    def _draw_receptors(self, surface: pygame.Surface, geo: Geometry, beat: float) -> None:
        lane = self.lane
        pulse = 1.0 + 0.06 * max(0.0, 1.0 - (beat % 1.0) * 2.5)
        pulse_size = int(geo.arrow * pulse) // 2 * 2
        for column in range(self.columns):
            x = geo.column_x(column)
            bright = lane.flash[column] > 0 or lane.is_held(column)
            base = receptor_scaled(geo.arrow, column % 4, bright, pulse_size)
            surface.blit(base, base.get_rect(center=(x, geo.receptor_y)))
            if lane.flash[column] > 0:
                fade = min(1.0, lane.flash[column] / FLASH_TIME)
                grown = int(geo.arrow * (1.25 - 0.2 * fade)) // 4 * 4
                burst = burst_surface(geo.arrow, lane.flash_colour[column], column % 4, grown,
                                      int(200 * fade) // 16 * 16)
                surface.blit(burst, burst.get_rect(center=(x, geo.receptor_y)),
                             special_flags=pygame.BLEND_PREMULTIPLIED)

    def _draw_notes(self, surface: pygame.Surface, geo: Geometry, y_for, height: int) -> None:
        lane = self.lane
        limit_low, limit_high = -geo.arrow, height + geo.arrow
        notes = lane.notes

        # skip past everything that has already left the screen
        i = lane.draw_cursor
        while i < len(notes):
            note = notes[i]
            end_beat = note.end_beat if note.end_beat is not None else note.beat
            y_tail = y_for(end_beat, note.end_time or note.time)
            if (geo.direction > 0 and y_tail >= limit_low) or \
               (geo.direction < 0 and y_tail <= limit_high):
                break
            i += 1
        lane.draw_cursor = i

        while i < len(notes):
            note = notes[i]
            i += 1
            y = y_for(note.beat, note.time)
            if geo.direction > 0 and y > limit_high:
                break
            if geo.direction < 0 and y < limit_low:
                break
            if note.judged and note.kind not in (HOLD, ROLL):
                continue

            x = geo.column_x(note.column)
            if note.kind == MINE:
                mine = mine_surface(geo.arrow)
                surface.blit(mine, mine.get_rect(center=(x, y)))
            elif note.kind in (HOLD, ROLL):
                self._draw_hold(surface, geo, note, x, y, y_for)
            else:
                arrow = arrow_surface(geo.arrow, quant_colour(note.beat), note.column % 4)
                surface.blit(arrow, arrow.get_rect(center=(x, y)))

    def _draw_hold(self, surface: pygame.Surface, geo: Geometry, note, x: int, y: float,
                   y_for) -> None:
        head_y = geo.receptor_y if note.hold_active else y
        tail_y = y_for(note.end_beat, note.end_time)
        colour = HOLD_BODY if note.kind == HOLD else ROLL_BODY
        if note.hold_dropped:
            colour = DROPPED_BODY
        elif note.hold_active:
            colour = tuple(min(255, c + 45) for c in colour)

        top, bottom = min(head_y, tail_y), max(head_y, tail_y)
        body = pygame.Rect(int(x - geo.arrow * 0.28), int(top),
                           int(geo.arrow * 0.56), int(max(2, bottom - top)))
        pygame.draw.rect(surface, colour, body, border_radius=int(geo.arrow * 0.14))
        if note.hold_done:
            return
        if not note.judged or note.hold_active:
            head = arrow_surface(geo.arrow, quant_colour(note.beat), note.column % 4)
            surface.blit(head, head.get_rect(center=(x, head_y)))

    def _draw_judgement(self, surface: pygame.Surface, geo: Geometry) -> None:
        lane = self.lane
        judge_y = geo.receptor_y + int(geo.arrow * 2.1) * geo.direction
        if lane.judgement_timer > 0 and lane.judgement:
            fade = lane.judgement_timer / JUDGEMENT_TIME
            size = int(geo.arrow * (0.52 + 0.08 * fade)) // 4 * 4
            self.fonts.draw(surface, lane.judgement, (geo.centre, judge_y), size,
                            JUDGEMENT_COLOUR.get(lane.judgement, (255, 255, 255)),
                            bold=True, anchor="center")
        if lane.score.combo >= 4:
            size = int(geo.arrow * (0.68 + 0.08 * (lane.combo_timer / COMBO_TIME))) // 4 * 4
            self.fonts.draw(surface, str(lane.score.combo),
                            (geo.centre, judge_y + int(geo.arrow * 0.62)), size,
                            COMBO_COLOUR, bold=True, anchor="center")

    def _draw_hud(self, surface: pygame.Surface, geo: Geometry, field: pygame.Rect,
                  scale: float, height: int) -> None:
        lane = self.lane
        hud_y = height - int(38 * scale)
        surface.blit(self._panel((field.width, int(46 * scale)), (8, 8, 14, 205)),
                     (field.left, hud_y - int(23 * scale)))
        bar = pygame.Rect(int(geo.centre - geo.span * 0.30), hud_y - int(8 * scale),
                          int(geo.span * 0.60), int(16 * scale))
        draw_bar(surface, bar, lane.score.life, LIFE_OK if lane.score.life > 0.3 else LIFE_LOW)
        self.fonts.draw(surface, self.label, (bar.left - int(10 * scale), bar.centery),
                        int(26 * scale), (210, 210, 230), bold=True, anchor="midright")
        self.fonts.draw(surface, f"{lane.score.percent:.2f}%",
                        (bar.right + int(10 * scale), bar.centery), int(26 * scale),
                        (210, 210, 235), anchor="midleft")
        if lane.failed:
            self.fonts.draw(surface, "FAILED", (geo.centre, height // 2), int(70 * scale),
                            (220, 70, 70), bold=True, anchor="center")
