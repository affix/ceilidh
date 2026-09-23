import json

import pytest

from ceilidh import simfile
from ceilidh.chart import HOLD, MINE, ROLL, TAP
from ceilidh.simfile import SimfileError

SM = """\
// a comment that should never reach the parser
#TITLE:Test Song;
#SUBTITLE:Remix;
#ARTIST:Nobody;
#MUSIC:track.ogg;
#BANNER:banner.png;
#OFFSET:-0.040;
#SAMPLESTART:32.000;
#BPMS:0.000=120.000,16.000=150.000;
#STOPS:8.000=0.500;
#NOTES:
     dance-single:
     :
     Easy:
     3:
     0,0,0,0,0:
1000
0100
0010
0001
,
2000
0000
3000
0000
,
M000
0000
4000
0000
;
#NOTES:
     dance-double:
     :
     Hard:
     9:
     0,0,0,0,0:
10000000
00000001
;
"""


@pytest.fixture
def song_dir(tmp_path):
    folder = tmp_path / "Test Song"
    folder.mkdir()
    (folder / "song.sm").write_text(SM)
    (folder / "track.ogg").write_bytes(b"OggS")
    (folder / "banner.png").write_bytes(b"\x89PNG")
    return folder


def test_header_fields_are_read(song_dir):
    song = simfile.load(song_dir / "song.sm")
    assert song.title == "Test Song"
    assert song.subtitle == "Remix"
    assert song.artist == "Nobody"
    assert song.display_title == "Test Song Remix"
    assert song.sample_start == pytest.approx(32.0)


def test_audio_and_artwork_are_resolved(song_dir):
    song = simfile.load(song_dir / "song.sm")
    assert song.music.name == "track.ogg"
    assert song.banner.name == "banner.png"


def test_timing_comes_from_the_header(song_dir):
    song = simfile.load(song_dir / "song.sm")
    assert song.timing.offset == pytest.approx(-0.040)
    assert song.timing.bpms == [(0.0, 120.0), (16.0, 150.0)]
    assert song.timing.stops == [(8.0, 0.5)]
    assert song.timing.beat_to_time(0.0) == pytest.approx(0.04)


def test_rows_become_notes_on_the_right_beats(song_dir):
    chart = simfile.load(song_dir / "song.sm").charts_for("single")[0]
    taps = [n for n in chart.notes if n.kind == TAP]
    assert [(n.beat, n.column) for n in taps[:4]] == [(0.0, 0), (1.0, 1), (2.0, 2), (3.0, 3)]


def test_a_hold_spans_from_its_head_to_its_tail(song_dir):
    chart = simfile.load(song_dir / "song.sm").charts_for("single")[0]
    hold = next(n for n in chart.notes if n.kind == HOLD)
    assert (hold.beat, hold.end_beat) == (4.0, 6.0)
    assert hold.end_time == pytest.approx(chart_time(chart, 6.0))


def chart_time(chart, beat):
    from ceilidh.gameplay.timing import TimingData
    return TimingData(offset=-0.04, bpms=[(0.0, 120.0), (16.0, 150.0)],
                      stops=[(8.0, 0.5)]).beat_to_time(beat)


def test_mines_are_kept_and_unterminated_rolls_become_taps(song_dir):
    chart = simfile.load(song_dir / "song.sm").charts_for("single")[0]
    assert any(n.kind == MINE and n.beat == 8.0 for n in chart.notes)
    assert not any(n.kind == ROLL for n in chart.notes)   # the roll never closed
    assert any(n.kind == TAP and n.beat == 10.0 for n in chart.notes)


def test_difficulty_and_meter_survive(song_dir):
    chart = simfile.load(song_dir / "song.sm").charts_for("single")[0]
    assert (chart.difficulty, chart.meter, chart.columns, chart.mode) == ("Easy", 3, 4, "single")


def test_doubles_charts_are_read_separately(song_dir):
    song = simfile.load(song_dir / "song.sm")
    doubles = song.charts_for("double")
    assert len(doubles) == 1
    assert doubles[0].columns == 8 and doubles[0].meter == 9
    assert {n.column for n in doubles[0].notes} == {0, 7}


def test_mines_do_not_count_as_steps(song_dir):
    chart = simfile.load(song_dir / "song.sm").charts_for("single")[0]
    assert chart.tap_count() == sum(1 for n in chart.notes if n.kind != MINE)


def test_a_chart_can_retime_itself_in_an_ssc(tmp_path):
    folder = tmp_path / "SSC"
    folder.mkdir()
    (folder / "a.ogg").write_bytes(b"OggS")
    (folder / "a.ssc").write_text(
        "#TITLE:SSC;\n#BPMS:0.000=100.000;\n#OFFSET:0.000;\n"
        "#NOTEDATA:;\n#STEPSTYPE:dance-single;\n#DIFFICULTY:Challenge;\n#METER:11;\n"
        "#BPMS:0.000=200.000;\n#NOTES:\n1000\n0000\n0000\n0000\n;\n")
    song = simfile.load(folder / "a.ssc")
    chart = song.charts[0]
    assert chart.difficulty == "Challenge" and chart.meter == 11
    assert chart.timing is not None and chart.timing.bpm_at(0.0) == 200.0
    assert song.chart_timing(chart).bpm_at(0.0) == 200.0


def test_a_simfile_with_no_usable_charts_is_rejected(tmp_path):
    (tmp_path / "empty.sm").write_text("#TITLE:Nothing;\n#BPMS:0=120;\n")
    with pytest.raises(SimfileError):
        simfile.load(tmp_path / "empty.sm")


def test_unknown_extensions_are_rejected(tmp_path):
    (tmp_path / "song.txt").write_text("hello")
    with pytest.raises(SimfileError):
        simfile.load(tmp_path / "song.txt")


def test_json_charts_load_with_compact_and_verbose_notes(tmp_path):
    folder = tmp_path / "JSON"
    folder.mkdir()
    (folder / "beep.ogg").write_bytes(b"OggS")
    (folder / "chart.json").write_text(json.dumps({
        "title": "JSON Song", "artist": "Tester", "music": "beep.ogg",
        "offset": -0.1, "bpms": [[0, 120]],
        "charts": [{
            "mode": "single", "difficulty": "Medium", "meter": 5,
            "notes": [[0, 0, "tap"], [1, 2, "hold", 3], [4, 1, "mine"],
                      {"beat": 5, "column": 3, "type": "tap"}],
        }],
    }))
    song = simfile.load(folder / "chart.json")
    chart = song.charts[0]
    assert song.title == "JSON Song" and chart.meter == 5
    assert song.timing.beat_to_time(0.0) == pytest.approx(0.1)
    kinds = {(n.beat, n.kind) for n in chart.notes}
    assert kinds == {(0.0, TAP), (1.0, HOLD), (4.0, MINE), (5.0, TAP)}
    hold = next(n for n in chart.notes if n.kind == HOLD)
    assert hold.end_beat == 3.0 and hold.end_time == pytest.approx(song.timing.beat_to_time(3.0))


def test_a_json_hold_without_an_end_falls_back_to_a_tap(tmp_path):
    (tmp_path / "chart.json").write_text(json.dumps({
        "title": "T", "bpms": [[0, 120]],
        "charts": [{"mode": "single", "notes": [[0, 0, "hold"]]}],
    }))
    chart = simfile.load(tmp_path / "chart.json").charts[0]
    assert chart.notes[0].kind == TAP


def test_json_without_charts_is_rejected(tmp_path):
    (tmp_path / "chart.json").write_text(json.dumps({"title": "T", "charts": []}))
    with pytest.raises(SimfileError):
        simfile.load(tmp_path / "chart.json")
