"""One player's chart and the judging state machine that runs it.

No pygame in here: a Lane can be stepped through headlessly, which is what
makes autoplay, demo mode and offline chart checking possible.
"""

from __future__ import annotations

from typing import Callable

from ..chart import HOLD, MINE, ROLL, Chart, Note
from .judge import (
    BASE_WINDOWS,
    HOLD_GRACE,
    HOLD_NG,
    HOLD_OK,
    JUDGEMENT_COLOUR,
    MINE_WINDOW,
    MISS,
    ROLL_WINDOW,
    PlayerScore,
    judge_for,
)
from .timing import TimingData

#: how long the receptor stays lit after a hit
FLASH_TIME = 0.18
JUDGEMENT_TIME = 0.55
COMBO_TIME = 0.25

HeldTest = Callable[[int], bool]


def _never_held(column: int) -> bool:
    return False


class Lane:
    """A chart plus everything that changes while it is being played."""

    def __init__(self, player: int, chart: Chart, columns: int, timing: TimingData,
                 scale_windows: float = 1.0, is_held: HeldTest | None = None) -> None:
        self.player = player
        self.chart = chart
        self.columns = columns
        self.timing = timing
        self.scale_windows = scale_windows
        self.is_held: HeldTest = is_held or _never_held

        self.notes: list[Note] = chart.clone_notes()
        self.by_column: list[list[Note]] = [[] for _ in range(columns)]
        for note in self.notes:
            if 0 <= note.column < columns:
                self.by_column[note.column].append(note)

        self.column_cursor = [0] * columns
        self.mine_cursor = [0] * columns
        self.cursor = 0
        self.draw_cursor = 0
        self.active_holds: dict[int, Note] = {}

        self.flash = [0.0] * columns
        self.flash_colour = [(255, 255, 255)] * columns
        self.judgement: str | None = None
        self.judgement_timer = 0.0
        self.combo_timer = 0.0

        self.score = PlayerScore()
        self.failed = False
        self.autoplay = False
        self.auto_cursor = 0

        taps = sum(1 for n in self.notes if n.kind != MINE)
        holds = sum(1 for n in self.notes if n.kind in (HOLD, ROLL))
        self.score.possible_points = 5.0 * taps + 5.0 * holds
        self.max_window = BASE_WINDOWS[-1][1] * scale_windows
        self.end_time = max((n.end_time or n.time) for n in self.notes) if self.notes else 0.0

    def note_at(self, column: int, when: float) -> Note | None:
        """The nearest unjudged note in this column within the widest window."""
        notes = self.by_column[column]
        i = self.column_cursor[column]
        while i < len(notes) and (notes[i].judged or notes[i].kind == MINE):
            i += 1
        self.column_cursor[column] = i

        best: Note | None = None
        best_error = self.max_window
        j = i
        while j < len(notes) and notes[j].time <= when + self.max_window:
            note = notes[j]
            if not note.judged and note.kind != MINE:
                error = abs(note.time - when)
                if error <= best_error:
                    best, best_error = note, error
            j += 1
        return best

    def press(self, column: int, when: float) -> str | None:
        """Step on a panel. Returns the judgement, or None if nothing was there."""
        if self.failed:
            return None
        held = self.active_holds.get(column)
        if held is not None and held.kind == ROLL:
            held.last_tap = when

        note = self.note_at(column, when)
        if note is None:
            return None
        judgement = judge_for(when - note.time, self.scale_windows)
        if judgement is None:
            return None

        note.judged = True
        note.judgement = judgement
        note.error = when - note.time
        self.score.add(judgement, note.error)
        self.set_judgement(judgement)
        self.flash[column] = FLASH_TIME
        self.flash_colour[column] = JUDGEMENT_COLOUR.get(judgement, (255, 255, 255))

        if note.kind in (HOLD, ROLL) and judgement != MISS:
            note.hold_active = True
            note.release_at = None
            note.last_tap = when
            self.active_holds[column] = note
        return judgement

    def set_judgement(self, judgement: str) -> None:
        self.judgement = judgement
        self.judgement_timer = JUDGEMENT_TIME
        self.combo_timer = COMBO_TIME

    def update(self, now: float, is_held: HeldTest | None = None) -> None:
        if self.failed:
            return
        held = is_held or self.is_held
        self._judge_misses(now)
        self._judge_mines(now, held)
        self._judge_holds(now, held)

    def _judge_misses(self, now: float) -> None:
        miss_line = now - self.max_window
        i = self.cursor
        while i < len(self.notes) and self.notes[i].time < miss_line:
            note = self.notes[i]
            if not note.judged:
                note.judged = True
                if note.kind != MINE:
                    note.judgement = MISS
                    self.score.add(MISS)
                    self.set_judgement(MISS)
                    if note.kind in (HOLD, ROLL):
                        note.hold_done = True
                        note.hold_dropped = True
                        self.score.add(HOLD_NG)
            i += 1
        while self.cursor < len(self.notes) and self.notes[self.cursor].judged:
            self.cursor += 1

    def _judge_mines(self, now: float, is_held: HeldTest) -> None:
        for column in range(self.columns):
            notes = self.by_column[column]
            j = self.mine_cursor[column]
            while j < len(notes) and notes[j].time < now - MINE_WINDOW:
                j += 1
            self.mine_cursor[column] = j
            k = j
            while k < len(notes) and notes[k].time <= now + MINE_WINDOW:
                note = notes[k]
                if note.kind == MINE and not note.judged and is_held(column):
                    note.judged = True
                    note.judgement = "MINE"
                    self.score.add_mine()
                    self.flash[column] = 0.2
                    self.flash_colour[column] = (230, 70, 70)
                k += 1

    def _judge_holds(self, now: float, is_held: HeldTest) -> None:
        for column, note in list(self.active_holds.items()):
            if note.end_time is None:
                del self.active_holds[column]
                continue
            if now >= note.end_time:
                note.hold_active = False
                note.hold_done = True
                self.score.add(HOLD_OK)
                del self.active_holds[column]
                self.flash[column] = 0.15
                self.flash_colour[column] = JUDGEMENT_COLOUR[HOLD_OK]
                continue

            if note.kind == ROLL:
                dropped = (now - note.last_tap) > ROLL_WINDOW
            else:
                dropped = False
                if is_held(column):
                    note.release_at = None
                elif note.release_at is None:
                    note.release_at = now
                elif now - note.release_at > HOLD_GRACE:
                    dropped = True

            if dropped:
                note.hold_active = False
                note.hold_done = True
                note.hold_dropped = True
                self.score.add(HOLD_NG)
                self.set_judgement(HOLD_NG)
                del self.active_holds[column]

    def autoplay_step(self, now: float) -> None:
        """Hit every note dead on its own timestamp."""
        notes = self.notes
        while self.auto_cursor < len(notes) and notes[self.auto_cursor].time <= now:
            note = notes[self.auto_cursor]
            self.auto_cursor += 1
            if note.kind == MINE or note.judged:
                continue
            self.press(note.column, note.time)
        for note in self.active_holds.values():
            if note.kind == ROLL:
                note.last_tap = now

    def tick_timers(self, dt: float) -> None:
        self.judgement_timer = max(0.0, self.judgement_timer - dt)
        self.combo_timer = max(0.0, self.combo_timer - dt)
        for column in range(self.columns):
            self.flash[column] = max(0.0, self.flash[column] - dt)

    def fail(self) -> None:
        self.failed = True
        self.score.failed = True

    def finished(self, now: float) -> bool:
        return self.cursor >= len(self.notes) and not self.active_holds and now > self.end_time
