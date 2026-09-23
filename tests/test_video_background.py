"""The video decoder, tested by feeding it frames instead of running ffmpeg."""

from pathlib import Path

import pytest

from ceilidh.chart import Song
from ceilidh.display import video
from ceilidh.display.video import VideoBackground

pytestmark = pytest.mark.usefixtures("display")


@pytest.fixture
def player():
    made = VideoBackground(Path("nothing.avi"), (8, 6), fps=24)
    made.failed = False          # pretend ffmpeg is running
    return made


def push(player, count=1):
    for _ in range(count):
        player.queue.put(b"\x10\x20\x30" * (player.width * player.height))


def test_a_failed_decoder_never_returns_a_frame(player):
    player.failed = True
    push(player)
    assert player.frame(1.0) is None


def test_frames_are_consumed_towards_the_current_song_position(player):
    push(player, 4)
    player.frame(0.0)
    assert player._index == 0
    player.frame(0.2)            # 0.2s at 24fps is frame 4
    assert player._index == 3    # only four frames were available


def test_the_last_frame_is_held_when_the_decoder_falls_behind(player):
    push(player, 2)
    first = player.frame(0.1)
    assert first is not None
    assert player.frame(0.5) is first


def test_a_frame_comes_back_as_a_surface_of_the_right_size(player):
    push(player)
    assert player.frame(0.0).get_size() == (8, 6)


def test_a_long_gap_makes_the_decoder_jump_rather_than_crawl(player, monkeypatch):
    restarts = []
    monkeypatch.setattr(player, "start", lambda: restarts.append(player.start_at) or True)
    player.frame(30.0)
    assert restarts == [30.0]
    assert player._index == int(30.0 * 24) - 1


def test_it_only_jumps_so_many_times_before_giving_up(player, monkeypatch):
    monkeypatch.setattr(player, "start", lambda: True)
    for second in range(1, 40):
        player.frame(second * 30.0)
    assert player._resyncs <= 8


def test_a_decoder_that_starts_mid_song_counts_from_there():
    player = VideoBackground(Path("x.avi"), (4, 4), fps=30, start=10.0)
    assert player._index == int(10.0 * 30) - 1


def test_stopping_drains_the_queue(player):
    push(player, 3)
    player.stop()
    assert player.queue.empty()
    assert player.stopped.is_set()


def test_starting_without_a_usable_ffmpeg_fails_cleanly(monkeypatch):
    monkeypatch.setattr(video, "_usable", False)
    player = VideoBackground(Path("x.avi"), (4, 4))
    assert player.start() is False
    assert player.failed


def test_a_broken_ffmpeg_counts_as_no_ffmpeg(monkeypatch):
    monkeypatch.setattr(video, "_binary", "/usr/bin/ffmpeg")
    monkeypatch.setattr(video, "_usable", None)
    monkeypatch.setattr(video.subprocess, "run",
                        lambda *a, **k: pytest.fail("should not get this far")
                        if False else _Result(1))
    assert video.available() is False


class _Result:
    def __init__(self, returncode):
        self.returncode = returncode


def test_a_song_with_a_video_beside_it_is_found(tmp_path):
    folder = tmp_path / "Song"
    folder.mkdir()
    (folder / "bg.avi").write_bytes(b"RIFF")
    assert video.find_video(Song(title="S", folder=folder)).name == "bg.avi"


def test_a_song_without_one_returns_nothing(tmp_path):
    folder = tmp_path / "Song"
    folder.mkdir()
    (folder / "track.ogg").write_bytes(b"OggS")
    assert video.find_video(Song(title="S", folder=folder)) is None


def test_a_declared_background_video_wins_over_a_stray_file(tmp_path):
    folder = tmp_path / "Song"
    folder.mkdir()
    (folder / "aaa.avi").write_bytes(b"RIFF")
    declared = folder / "declared.mpg"
    declared.write_bytes(b"\x00")
    song = Song(title="S", folder=folder, background=declared)
    assert video.find_video(song) == declared
