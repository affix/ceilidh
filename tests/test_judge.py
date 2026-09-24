import pytest

from ceilidh.gameplay.judge import (
    DECENT,
    EXCELLENT,
    FANTASTIC,
    GREAT,
    HOLD_NG,
    HOLD_OK,
    MISS,
    WAYOFF,
    PlayerScore,
    grade,
    judge_for,
    windows,
)


@pytest.mark.parametrize("error, expected", [
    (0.0, FANTASTIC),
    (0.0215, FANTASTIC),
    (-0.0215, FANTASTIC),
    (0.022, EXCELLENT),
    (0.043, EXCELLENT),
    (0.06, GREAT),
    (0.102, GREAT),
    (0.12, DECENT),
    (0.16, WAYOFF),
    (0.180, WAYOFF),
])
def test_windows_are_symmetrical_and_inclusive(error, expected):
    assert judge_for(error) == expected


def test_outside_the_last_window_is_not_a_judgement():
    assert judge_for(0.181) is None
    assert judge_for(-5.0) is None


def test_timing_scale_widens_and_narrows_every_window():
    assert judge_for(0.03, scale=2.0) == FANTASTIC
    assert judge_for(0.03, scale=0.5) == GREAT
    assert judge_for(0.2, scale=0.5) is None
    assert [w for _, w in windows(2.0)] == pytest.approx([0.043, 0.086, 0.204, 0.27, 0.36])


def test_points_follow_the_judgement():
    score = PlayerScore()
    score.possible_points = 20.0
    for judgement in (FANTASTIC, EXCELLENT, GREAT, DECENT):
        score.add(judgement)
    assert score.dance_points == pytest.approx(5 + 4 + 2 + 0)
    assert score.percent == pytest.approx(55.0)


def test_a_bad_run_cannot_report_a_negative_percentage():
    score = PlayerScore()
    score.possible_points = 10.0
    score.add(MISS)
    assert score.dance_points < 0
    assert score.percent == 0.0


def test_combo_grows_and_breaks_on_the_right_judgements():
    score = PlayerScore()
    for _ in range(3):
        score.add(FANTASTIC)
    assert score.combo == 3
    score.add(GREAT)
    assert score.combo == 4
    score.add(DECENT)          # decent and worse break the combo
    assert score.combo == 0
    assert score.max_combo == 4


def test_completing_a_hold_scores_but_does_not_inflate_the_combo():
    score = PlayerScore()
    score.add(FANTASTIC)
    score.add(HOLD_OK)
    assert score.combo == 1
    assert score.holds_ok == 1
    assert score.dance_points == pytest.approx(10.0)


def test_life_moves_in_the_right_direction_and_stays_in_range():
    score = PlayerScore()
    start = score.life
    score.add(FANTASTIC)
    assert score.life > start
    for _ in range(50):
        score.add(MISS)
    assert score.life == 0.0
    for _ in range(500):
        score.add(FANTASTIC)
    assert score.life == 1.0


def test_mines_cost_points_and_life_without_touching_the_combo():
    score = PlayerScore()
    score.possible_points = 100.0
    score.add(FANTASTIC)
    before = score.life
    score.add_mine()
    assert score.mines_hit == 1
    assert score.dance_points == pytest.approx(5 - 6)
    assert score.life < before
    assert score.combo == 1


@pytest.mark.parametrize("percent, expected", [
    (100.0, "★★★"), (99.5, "★★"), (98.0, "★"), (96.0, "S+"),
    (94.0, "S"), (89.0, "A+"), (80.0, "B+"), (61.0, "C-"), (0.0, "D"),
])
def test_grade_thresholds(percent, expected):
    assert grade(percent) == expected


def test_a_failed_run_grades_f_whatever_the_score():
    score = PlayerScore()
    score.possible_points = 10.0
    score.add(FANTASTIC)
    score.add(FANTASTIC)
    assert score.grade == "★★★"
    score.failed = True
    assert score.grade == "F"


def test_full_combo_needs_no_decents_misses_or_dropped_holds():
    score = PlayerScore()
    score.add(FANTASTIC)
    score.add(GREAT)
    assert score.full_combo
    score.add(HOLD_NG)
    assert not score.full_combo


def test_mean_error_reports_in_milliseconds_and_ignores_misses():
    score = PlayerScore()
    score.add(FANTASTIC, 0.010)
    score.add(EXCELLENT, 0.030)
    score.add(MISS)
    assert score.mean_error_ms == pytest.approx(20.0)


def test_casual_scoring_never_takes_points_away():
    score = PlayerScore(casual=True, possible_points=20.0)
    score.add(FANTASTIC)
    score.add(MISS)
    score.add(WAYOFF)
    score.add_mine()
    assert score.dance_points == 5.0
    assert score.percent == 25.0
    assert score.counts[MISS] == 1
    assert score.mines_hit == 1


def test_arcade_scoring_still_punishes_misses():
    score = PlayerScore(possible_points=20.0)
    score.add(FANTASTIC)
    score.add(MISS)
    assert score.dance_points == -7.0
    assert score.percent == 0.0
