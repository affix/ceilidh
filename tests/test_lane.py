import pytest

from ceilidh.chart import HOLD, MINE, ROLL, TAP, Chart, Note
from ceilidh.gameplay.judge import FANTASTIC, GREAT, MISS
from ceilidh.gameplay.lane import Lane
from ceilidh.gameplay.timing import TimingData

TIMING = TimingData(bpms=[(0.0, 120.0)])   # one beat is half a second
LEFT, DOWN, UP, RIGHT = 0, 1, 2, 3


def note(time, column, kind=TAP, end=None):
    made = Note(beat=time * 2, time=time, column=column, kind=kind)
    if end is not None:
        made.end_beat, made.end_time = end * 2, end
    return made


def make_lane(notes, held=(), scale=1.0):
    chart = Chart(columns=4, mode="single", difficulty="Test", meter=1,
                  notes=sorted(notes, key=lambda n: (n.beat, n.column)))
    lane = Lane(0, chart, 4, TIMING, scale)
    held_set = set(held)
    lane.is_held = lambda column: column in held_set
    lane.held_set = held_set
    return lane


def test_a_note_hit_dead_on_is_fantastic_and_worth_full_marks():
    lane = make_lane([note(1.0, LEFT)])
    assert lane.press(LEFT, 1.0) == FANTASTIC
    assert lane.score.percent == pytest.approx(100.0)
    assert lane.score.combo == 1


def test_a_late_step_is_judged_by_how_late_it_was():
    lane = make_lane([note(1.0, LEFT)])
    assert lane.press(LEFT, 1.06) == GREAT
    assert lane.notes[0].error == pytest.approx(0.06)


def test_stepping_nowhere_near_a_note_does_nothing_at_all():
    lane = make_lane([note(1.0, LEFT)])
    assert lane.press(LEFT, 0.5) is None
    assert not lane.notes[0].judged
    assert lane.score.combo == 0


def test_stepping_on_the_wrong_panel_leaves_the_note_alone():
    lane = make_lane([note(1.0, LEFT)])
    assert lane.press(RIGHT, 1.0) is None
    assert not lane.notes[0].judged


def test_a_note_left_behind_becomes_a_miss_and_breaks_the_combo():
    lane = make_lane([note(1.0, LEFT), note(2.0, DOWN)])
    lane.press(LEFT, 1.0)
    lane.update(2.5)
    assert lane.notes[1].judgement == MISS
    assert lane.score.counts[MISS] == 1
    assert lane.score.combo == 0


def test_the_nearest_note_wins_when_two_are_close_together():
    lane = make_lane([note(1.00, LEFT), note(1.08, LEFT)])
    lane.press(LEFT, 1.07)
    assert lane.notes[1].judged and not lane.notes[0].judged


def test_a_hold_kept_down_to_the_end_scores_ok():
    lane = make_lane([note(1.0, LEFT, HOLD, end=2.0)], held=[LEFT])
    lane.press(LEFT, 1.0)
    assert lane.active_holds[LEFT] is lane.notes[0]
    lane.update(2.01)
    assert lane.score.holds_ok == 1
    assert lane.score.holds_ng == 0
    assert lane.score.percent == pytest.approx(100.0)


def test_letting_go_of_a_hold_for_too_long_drops_it():
    lane = make_lane([note(1.0, LEFT, HOLD, end=3.0)], held=[LEFT])
    lane.press(LEFT, 1.0)
    lane.held_set.discard(LEFT)
    lane.update(1.1)                      # inside the grace period
    assert lane.score.holds_ng == 0
    lane.update(1.1 + 0.26)               # past it
    assert lane.score.holds_ng == 1
    assert LEFT not in lane.active_holds


def test_a_stumble_shorter_than_the_grace_period_is_forgiven():
    lane = make_lane([note(1.0, LEFT, HOLD, end=3.0)], held=[LEFT])
    lane.press(LEFT, 1.0)
    lane.held_set.discard(LEFT)
    lane.update(1.10)
    lane.held_set.add(LEFT)
    lane.update(1.20)
    lane.update(3.01)
    assert lane.score.holds_ok == 1
    assert lane.score.holds_ng == 0


def test_a_roll_needs_repeated_steps_to_survive():
    lane = make_lane([note(1.0, LEFT, ROLL, end=3.0)])
    lane.press(LEFT, 1.0)
    lane.update(1.4)
    assert lane.score.holds_ng == 0
    lane.update(1.6)                      # more than the roll window since the tap
    assert lane.score.holds_ng == 1


def test_a_roll_that_keeps_being_tapped_completes():
    lane = make_lane([note(1.0, LEFT, ROLL, end=2.0)])
    lane.press(LEFT, 1.0)
    for when in (1.3, 1.6, 1.9):
        lane.press(LEFT, when)
        lane.update(when)
    lane.update(2.01)
    assert lane.score.holds_ok == 1


def test_standing_on_a_mine_costs_you_once():
    lane = make_lane([note(1.0, LEFT, MINE)], held=[LEFT])
    lane.update(1.0)
    lane.update(1.02)
    assert lane.score.mines_hit == 1


def test_a_mine_you_are_not_standing_on_passes_harmlessly():
    lane = make_lane([note(1.0, LEFT, MINE)])
    lane.update(1.0)
    lane.update(1.5)
    assert lane.score.mines_hit == 0
    assert lane.score.counts[MISS] == 0


def test_autoplay_clears_a_mixed_chart_perfectly():
    notes = [note(1.0, LEFT), note(1.5, DOWN), note(2.0, UP, HOLD, end=3.0),
             note(2.5, RIGHT), note(4.0, LEFT, MINE)]
    lane = make_lane(notes)
    lane.is_held = lambda column: column in lane.active_holds
    lane.autoplay = True
    now = 0.0
    while now < 5.0:
        lane.autoplay_step(now)
        lane.update(now)
        now += 0.01
    assert lane.score.percent == pytest.approx(100.0)
    assert lane.score.full_combo
    assert lane.score.mines_hit == 0


def test_a_failed_lane_stops_responding():
    lane = make_lane([note(1.0, LEFT)])
    lane.fail()
    assert lane.press(LEFT, 1.0) is None
    assert lane.score.failed


def test_possible_points_count_the_head_and_tail_of_every_hold():
    lane = make_lane([note(1.0, LEFT), note(2.0, DOWN, HOLD, end=3.0), note(4.0, UP, MINE)])
    assert lane.score.possible_points == pytest.approx(5 * 2 + 5 * 1)


def test_hitting_a_note_lights_the_receptor_and_the_light_fades():
    lane = make_lane([note(1.0, LEFT)])
    lane.press(LEFT, 1.0)
    assert lane.flash[LEFT] > 0
    lane.tick_timers(1.0)
    assert lane.flash[LEFT] == 0.0
    assert lane.judgement_timer == 0.0


def test_a_lane_is_only_finished_once_everything_is_resolved():
    lane = make_lane([note(1.0, LEFT, HOLD, end=2.0)], held=[LEFT])
    assert not lane.finished(0.0)
    lane.press(LEFT, 1.0)
    assert not lane.finished(1.5)
    lane.update(2.01)
    assert lane.finished(2.02)


def test_widening_the_windows_turns_a_miss_into_a_hit():
    late = 0.15
    assert make_lane([note(1.0, LEFT)], scale=0.5).press(LEFT, 1.0 + late) is None
    assert make_lane([note(1.0, LEFT)], scale=1.0).press(LEFT, 1.0 + late) is not None


def test_each_lane_gets_its_own_copy_of_the_notes():
    chart = Chart(columns=4, mode="single", difficulty="T", meter=1, notes=[note(1.0, LEFT)])
    one = Lane(0, chart, 4, TIMING)
    two = Lane(1, chart, 4, TIMING)
    one.press(LEFT, 1.0)
    assert one.notes[0].judged
    assert not two.notes[0].judged
    assert not chart.notes[0].judged
