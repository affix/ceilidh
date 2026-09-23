from __future__ import annotations

import pygame

from ..screen import Screen
from ..display import DISPLAY, art
from ..display.theme import ACCENT, PANEL
from ..input import InputEvent
from ..gameplay.judge import JUDGEMENTS, JUDGEMENT_COLOUR



class Results(Screen):
    def __init__(self, app, song, lanes, mode: str) -> None:
        super().__init__(app)
        self.song = song
        self.lanes = lanes
        self.mode = mode
        self.ready = 0.0

    def handle_input(self, events: list[InputEvent]) -> None:
        if self.ready < 0.6:
            return
        for ev in events:
            if ev.pressed and ev.action in ("start", "back"):
                self.app.pop()
                from .select import DifficultySelect

                if self.app.screens and isinstance(self.app.screens[-1], DifficultySelect):
                    self.app.pop()
                return

    def update(self, dt: float) -> None:
        self.ready += dt

    def draw(self, surface: pygame.Surface) -> None:
        surface.blit(self.app.background, (0, 0))
        width, height = surface.get_size()
        scale = self.app.scale

        emblem = art.emblem(int(54 * scale))
        if emblem is not None:
            surface.blit(emblem, emblem.get_rect(midright=(
                width // 2 - int(158 * scale), int(40 * scale))))
        self.fonts.draw(surface, "RESULTS", (width // 2, int(40 * scale)), int(56 * scale),
                        (255, 90, 160), bold=True, anchor="center")
        self.fonts.draw(surface, self.song.display_title[:44], (width // 2, int(92 * scale)),
                        int(30 * scale), (215, 215, 235), anchor="center")

        count = len(self.lanes)
        for index, lane in enumerate(self.lanes):
            centre = width // 2 if count == 1 else int(width * (0.27 + 0.46 * index))
            panel = pygame.Rect(centre - int(250 * scale), int(130 * scale),
                                int(500 * scale), int(550 * scale))
            pygame.draw.rect(surface, PANEL, panel, border_radius=12)
            pygame.draw.rect(surface, (80, 70, 110), panel, 2, border_radius=12)

            def at(offset: int) -> int:
                return panel.top + int(offset * scale)

            score = lane.score
            label = "P1 + P2 (doubles)" if self.mode == "double" else f"PLAYER {lane.player + 1}"
            self.fonts.draw(surface, label, (centre, at(16)), int(30 * scale),
                            (235, 235, 250), bold=True, anchor="midtop")
            self.fonts.draw(surface, f"{lane.chart.difficulty} {lane.chart.meter}",
                            (centre, at(50)), int(24 * scale), lane.chart.colour, anchor="midtop")

            grade_colour = (255, 215, 90) if not score.failed else (210, 80, 80)
            self.fonts.draw(surface, score.grade, (centre, at(84)), int(80 * scale),
                            grade_colour, bold=True, anchor="midtop", role=DISPLAY)
            self.fonts.draw(surface, f"{score.percent:.2f}%", (centre, at(168)),
                            int(42 * scale), (235, 235, 250), bold=True, anchor="midtop",
                            role=DISPLAY)

            y = at(222)
            for judgement in JUDGEMENTS:
                colour = JUDGEMENT_COLOUR[judgement]
                self.fonts.draw(surface, judgement, (panel.left + int(40 * scale), y),
                                int(26 * scale), colour, anchor="midleft", role=DISPLAY)
                self.fonts.draw(surface, str(score.counts[judgement]),
                                (panel.right - int(40 * scale), y), int(26 * scale), colour,
                                bold=True, anchor="midright", role=DISPLAY)
                y += int(26 * scale)

            y += int(8 * scale)
            extras = (
                ("HOLDS OK", str(score.holds_ok)),
                ("HOLDS NG", str(score.holds_ng)),
                ("MINES HIT", str(score.mines_hit)),
                ("MAX COMBO", str(score.max_combo)),
                ("MEAN TIMING", f"{score.mean_error_ms:+.1f} ms"),
            )
            for name, value in extras:
                self.fonts.draw(surface, name, (panel.left + int(40 * scale), y), int(24 * scale),
                                (175, 175, 200), anchor="midleft")
                self.fonts.draw(surface, value, (panel.right - int(40 * scale), y),
                                int(24 * scale), (215, 215, 235), bold=True, anchor="midright")
                y += int(24 * scale)

            if score.failed:
                self.fonts.draw(surface, "FAILED", (centre, panel.bottom - int(24 * scale)),
                                int(30 * scale), (220, 80, 80), bold=True, anchor="midbottom")
            elif score.full_combo:
                self.fonts.draw(surface, "FULL COMBO", (centre, panel.bottom - int(24 * scale)),
                                int(30 * scale), (120, 235, 255), bold=True, anchor="midbottom")

        self.fonts.draw(surface, "START continue", (width // 2, height - int(18 * scale)),
                        int(26 * scale), (150, 150, 180), anchor="center")
