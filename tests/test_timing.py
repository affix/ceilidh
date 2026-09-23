import pytest

from ceilidh.gameplay.timing import TimingData


def test_constant_bpm_maps_beats_to_seconds():
    timing = TimingData(offset=0.0, bpms=[(0.0, 120.0)])
    assert timing.beat_to_time(0.0) == pytest.approx(0.0)
    assert timing.beat_to_time(4.0) == pytest.approx(2.0)
    assert timing.time_to_beat(2.0) == pytest.approx(4.0)


def test_offset_shifts_the_whole_chart():
    # StepMania's #OFFSET is negated: -0.04 puts beat 0 at 40ms into the audio
    timing = TimingData(offset=-0.04, bpms=[(0.0, 171.0)])
    assert timing.beat_to_time(0.0) == pytest.approx(0.04)
    assert timing.beat_to_time(16.0) == pytest.approx(0.04 + 16 * 60 / 171)


def test_bpm_change_applies_from_its_beat_onwards():
    timing = TimingData(bpms=[(0.0, 120.0), (4.0, 240.0)])
    assert timing.beat_to_time(4.0) == pytest.approx(2.0)
    # after the change each beat takes half as long
    assert timing.beat_to_time(8.0) == pytest.approx(2.0 + 1.0)
    assert timing.bpm_at(0.0) == 120.0
    assert timing.bpm_at(4.0) == 240.0
    assert timing.bpm_at(3.999) == 120.0


def test_stop_delays_everything_after_it():
    timing = TimingData(bpms=[(0.0, 120.0)], stops=[(2.0, 1.5)])
    # a note on the stop beat is still hit before the pause
    assert timing.beat_to_time(2.0) == pytest.approx(1.0)
    assert timing.beat_to_time(3.0) == pytest.approx(1.0 + 1.5 + 0.5)


def test_beat_is_frozen_while_a_stop_runs():
    timing = TimingData(bpms=[(0.0, 120.0)], stops=[(2.0, 1.5)])
    assert timing.time_to_beat(1.0) == pytest.approx(2.0)
    assert timing.time_to_beat(2.0) == pytest.approx(2.0)   # mid stop
    assert timing.time_to_beat(2.4) == pytest.approx(2.0)   # still stopped
    assert timing.time_to_beat(3.0) == pytest.approx(3.0)   # moving again


def test_round_trip_survives_changes_and_stops():
    timing = TimingData(offset=-0.2, bpms=[(0.0, 100.0), (8.0, 180.0)], stops=[(4.0, 0.75)])
    for beat in (0.0, 1.5, 4.5, 8.0, 12.25, 40.0):
        assert timing.time_to_beat(timing.beat_to_time(beat)) == pytest.approx(beat)


def test_negative_times_extrapolate_backwards_for_the_lead_in():
    timing = TimingData(bpms=[(0.0, 120.0)])
    assert timing.time_to_beat(-1.0) == pytest.approx(-2.0)
    assert timing.beat_to_time(-2.0) == pytest.approx(-1.0)


def test_display_bpm_collapses_a_single_tempo_and_shows_a_range():
    assert TimingData(bpms=[(0.0, 160.0)]).display_bpm() == "160"
    assert TimingData(bpms=[(0.0, 100.0), (4.0, 200.0)]).display_bpm() == "100-200"


def test_zero_and_missing_bpms_fall_back_instead_of_dividing_by_zero():
    timing = TimingData(bpms=[(0.0, 0.0)])
    assert timing.bpm_at(0.0) == 120.0
    assert timing.beat_to_time(4.0) == pytest.approx(2.0)


def test_bpms_starting_after_beat_zero_are_backfilled():
    timing = TimingData(bpms=[(16.0, 150.0)])
    assert timing.bpm_at(0.0) == 150.0
