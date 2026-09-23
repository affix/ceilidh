from __future__ import annotations

from dataclasses import dataclass, field

FANTASTIC = "FANTASTIC"
EXCELLENT = "EXCELLENT"
GREAT = "GREAT"
DECENT = "DECENT"
WAYOFF = "WAY OFF"
MISS = "MISS"
HOLD_OK = "OK"
HOLD_NG = "NG"

JUDGEMENTS = (FANTASTIC, EXCELLENT, GREAT, DECENT, WAYOFF, MISS)

# Seconds either side of the note. ITG-ish defaults, scaled by config.timing_scale.
BASE_WINDOWS: tuple[tuple[str, float], ...] = (
    (FANTASTIC, 0.0215),
    (EXCELLENT, 0.043),
    (GREAT, 0.102),
    (DECENT, 0.135),
    (WAYOFF, 0.180),
)

MINE_WINDOW = 0.070
HOLD_GRACE = 0.250       # how long a hold may be released before it drops
ROLL_WINDOW = 0.500      # how long between taps before a roll drops

POINTS = {
    FANTASTIC: 5.0,
    EXCELLENT: 4.0,
    GREAT: 2.0,
    DECENT: 0.0,
    WAYOFF: -6.0,
    MISS: -12.0,
    HOLD_OK: 5.0,
    HOLD_NG: 0.0,
}
MINE_POINTS = -6.0

LIFE = {
    FANTASTIC: 0.008,
    EXCELLENT: 0.008,
    GREAT: 0.004,
    DECENT: 0.000,
    WAYOFF: -0.040,
    MISS: -0.080,
    HOLD_OK: 0.008,
    HOLD_NG: -0.080,
}
MINE_LIFE = -0.050

COMBO_BREAK = (DECENT, WAYOFF, MISS, HOLD_NG)

JUDGEMENT_COLOUR = {
    FANTASTIC: (120, 230, 255),
    EXCELLENT: (255, 215, 80),
    GREAT: (110, 235, 130),
    DECENT: (235, 120, 220),
    WAYOFF: (220, 90, 90),
    MISS: (170, 60, 60),
    HOLD_OK: (110, 235, 130),
    HOLD_NG: (170, 60, 60),
}

GRADES = (
    (100.0, "★★★"),
    (99.0, "★★"),
    (98.0, "★"),
    (96.0, "S+"),
    (94.0, "S"),
    (92.0, "S-"),
    (89.0, "A+"),
    (86.0, "A"),
    (83.0, "A-"),
    (80.0, "B+"),
    (76.0, "B"),
    (72.0, "B-"),
    (68.0, "C+"),
    (64.0, "C"),
    (60.0, "C-"),
    (0.0, "D"),
)


def windows(scale: float = 1.0) -> tuple[tuple[str, float], ...]:
    return tuple((name, value * scale) for name, value in BASE_WINDOWS)


def judge_for(error: float, scale: float = 1.0) -> str | None:
    """error = hit_time - note_time. None when outside every window."""
    magnitude = abs(error)
    for name, window in BASE_WINDOWS:
        if magnitude <= window * scale:
            return name
    return None


def grade(percent: float) -> str:
    for threshold, name in GRADES:
        if percent >= threshold:
            return name
    return "D"


@dataclass
class PlayerScore:
    counts: dict[str, int] = field(default_factory=lambda: {j: 0 for j in JUDGEMENTS})
    holds_ok: int = 0
    holds_ng: int = 0
    mines_hit: int = 0
    combo: int = 0
    max_combo: int = 0
    dance_points: float = 0.0
    possible_points: float = 0.0
    life: float = 0.5
    failed: bool = False
    errors: list[float] = field(default_factory=list)

    def add(self, judgement: str, error: float | None = None) -> None:
        if judgement in self.counts:
            self.counts[judgement] += 1
        elif judgement == HOLD_OK:
            self.holds_ok += 1
        elif judgement == HOLD_NG:
            self.holds_ng += 1

        self.dance_points += POINTS.get(judgement, 0.0)
        if error is not None and judgement not in (MISS, HOLD_OK, HOLD_NG):
            self.errors.append(error)

        if judgement in COMBO_BREAK:
            self.combo = 0
        elif judgement != HOLD_OK:
            self.combo += 1
            self.max_combo = max(self.max_combo, self.combo)

        self.life = max(0.0, min(1.0, self.life + LIFE.get(judgement, 0.0)))

    def add_mine(self) -> None:
        self.mines_hit += 1
        self.dance_points += MINE_POINTS
        self.life = max(0.0, min(1.0, self.life + MINE_LIFE))

    @property
    def percent(self) -> float:
        if self.possible_points <= 0:
            return 0.0
        return max(0.0, self.dance_points / self.possible_points * 100.0)

    @property
    def grade(self) -> str:
        return "F" if self.failed else grade(self.percent)

    @property
    def mean_error_ms(self) -> float:
        return sum(self.errors) / len(self.errors) * 1000.0 if self.errors else 0.0

    @property
    def full_combo(self) -> bool:
        return all(self.counts[j] == 0 for j in (DECENT, WAYOFF, MISS)) and self.holds_ng == 0
