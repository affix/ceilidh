from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

from .gameplay.timing import TimingData

TAP = "tap"
HOLD = "hold"
ROLL = "roll"
MINE = "mine"

DIFFICULTY_ORDER = {
    "beginner": 0,
    "easy": 1,
    "basic": 1,
    "medium": 2,
    "another": 2,
    "hard": 3,
    "maniac": 3,
    "heavy": 3,
    "challenge": 4,
    "smaniac": 4,
    "expert": 4,
    "edit": 5,
}

DIFFICULTY_COLOUR = {
    0: (120, 220, 255),
    1: (110, 235, 140),
    2: (255, 210, 90),
    3: (255, 110, 110),
    4: (200, 130, 255),
    5: (200, 200, 200),
}


@dataclass
class Note:
    beat: float
    time: float
    column: int
    kind: str = TAP
    end_beat: float | None = None
    end_time: float | None = None

    # runtime state (per player copy)
    judged: bool = False
    judgement: str | None = None
    error: float = 0.0
    hold_active: bool = False
    hold_done: bool = False
    hold_dropped: bool = False
    release_at: float | None = None
    last_tap: float = 0.0

    def copy(self) -> "Note":
        return Note(self.beat, self.time, self.column, self.kind, self.end_beat, self.end_time)


@dataclass
class Chart:
    columns: int
    mode: str  # "single" or "double"
    difficulty: str
    meter: int
    notes: list[Note] = field(default_factory=list)
    description: str = ""
    timing: TimingData | None = None

    @property
    def rank(self) -> int:
        return DIFFICULTY_ORDER.get(self.difficulty.lower(), 5)

    @property
    def colour(self) -> tuple[int, int, int]:
        return DIFFICULTY_COLOUR.get(self.rank, (200, 200, 200))

    def tap_count(self) -> int:
        return sum(1 for n in self.notes if n.kind != MINE)

    def clone_notes(self) -> list[Note]:
        return [n.copy() for n in self.notes]


@dataclass
class Song:
    title: str
    artist: str = ""
    subtitle: str = ""
    music: Path | None = None
    banner: Path | None = None
    background: Path | None = None
    folder: Path | None = None
    pack: str = ""
    timing: TimingData = field(default_factory=TimingData)
    charts: list[Chart] = field(default_factory=list)
    sample_start: float = 0.0
    sample_length: float = 12.0
    source: Path | None = None

    def charts_for(self, mode: str) -> list[Chart]:
        out = [c for c in self.charts if c.mode == mode]
        out.sort(key=lambda c: (c.rank, c.meter))
        return out

    @property
    def display_title(self) -> str:
        return f"{self.title} {self.subtitle}".strip()

    def chart_timing(self, chart: Chart) -> TimingData:
        return chart.timing or self.timing

    def length(self) -> float:
        end = 0.0
        for chart in self.charts:
            if chart.notes:
                last = chart.notes[-1]
                end = max(end, last.end_time or last.time)
        return end
