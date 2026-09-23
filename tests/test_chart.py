import pytest

from ceilidh.chart import MINE, TAP, Chart, Note, Song
from ceilidh.gameplay.timing import TimingData


def chart(difficulty, meter, mode="single", notes=None):
    return Chart(columns=4 if mode == "single" else 8, mode=mode, difficulty=difficulty,
                 meter=meter, notes=notes or [Note(beat=0.0, time=0.0, column=0)])


def test_difficulties_rank_in_playing_order():
    ranks = [chart(name, 1).rank for name in ("Beginner", "Easy", "Medium", "Hard", "Challenge")]
    assert ranks == sorted(ranks) == [0, 1, 2, 3, 4]


def test_an_unknown_difficulty_sorts_last_and_still_has_a_colour():
    odd = chart("Sausage", 1)
    assert odd.rank == 5
    assert len(odd.colour) == 3


def test_charts_are_offered_easiest_first_and_split_by_mode():
    song = Song(title="S")
    song.charts = [chart("Hard", 9), chart("Easy", 3), chart("Hard", 7),
                   chart("Medium", 5, mode="double")]
    singles = song.charts_for("single")
    assert [(c.difficulty, c.meter) for c in singles] == [("Easy", 3), ("Hard", 7), ("Hard", 9)]
    assert len(song.charts_for("double")) == 1


def test_display_title_only_adds_a_subtitle_when_there_is_one():
    assert Song(title="Alpha").display_title == "Alpha"
    assert Song(title="Alpha", subtitle="Beta").display_title == "Alpha Beta"


def test_song_length_is_the_last_thing_that_happens_in_any_chart():
    short = chart("Easy", 1, notes=[Note(beat=0.0, time=1.0, column=0)])
    long = chart("Hard", 9, notes=[Note(beat=0.0, time=9.0, column=0)])
    song = Song(title="S")
    song.charts = [short, long]
    assert song.length() == pytest.approx(9.0)


def test_a_hold_extends_the_song_past_its_own_head():
    held = Note(beat=0.0, time=1.0, column=0)
    held.end_time = 12.0
    song = Song(title="S")
    song.charts = [chart("Easy", 1, notes=[held])]
    assert song.length() == pytest.approx(12.0)


def test_mines_are_not_steps():
    mixed = chart("Easy", 1, notes=[Note(beat=0.0, time=0.0, column=0, kind=TAP),
                                    Note(beat=1.0, time=1.0, column=1, kind=MINE)])
    assert mixed.tap_count() == 1


def test_cloned_notes_do_not_share_state_with_the_chart():
    source = chart("Easy", 1)
    clone = source.clone_notes()
    clone[0].judged = True
    assert not source.notes[0].judged


def test_a_chart_can_override_the_song_timing():
    song = Song(title="S", timing=TimingData(bpms=[(0.0, 120.0)]))
    plain = chart("Easy", 1)
    retimed = chart("Hard", 9)
    retimed.timing = TimingData(bpms=[(0.0, 200.0)])
    song.charts = [plain, retimed]
    assert song.chart_timing(plain).bpm_at(0.0) == 120.0
    assert song.chart_timing(retimed).bpm_at(0.0) == 200.0
