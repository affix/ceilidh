"""The song clock, driven by a fake wall clock and a fake mixer."""

from pathlib import Path

import pygame
import pytest

from ceilidh import audio
from ceilidh.audio import MusicClock


class FakeClock:
    def __init__(self, now=1000.0):
        self.now = now

    def perf_counter(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class FakeMusic:
    def __init__(self):
        self.loaded = None
        self.plays = 0
        self.stopped = self.paused = self.unpaused = 0
        self.position = 0.0
        self.playing = False
        self.fail_load = False

    def load(self, path):
        if self.fail_load:
            raise pygame.error("cannot decode")
        self.loaded = path

    def set_volume(self, volume):
        self.volume = volume

    def play(self, loops=0, start=0.0):
        self.plays += 1
        self.playing = True

    def stop(self):
        self.stopped += 1
        self.playing = False

    def pause(self):
        self.paused += 1

    def unpause(self):
        self.unpaused += 1

    def get_pos(self):
        return int(self.position * 1000) if self.playing else -1


@pytest.fixture
def fake(monkeypatch):
    clock, music = FakeClock(), FakeMusic()
    monkeypatch.setattr(audio, "time", clock)
    monkeypatch.setattr(pygame.mixer, "music", music)
    return clock, music


def make_clock(lead_in=3.0, offset=0.0):
    clock = MusicClock(Path("song.ogg"), lead_in=lead_in, offset=offset)
    clock.load()
    clock.start()
    return clock


def test_the_count_in_runs_before_the_song(fake):
    wall, music = fake
    clock = make_clock()
    assert clock.time == pytest.approx(-3.0)
    wall.advance(1.0)
    assert clock.time == pytest.approx(-2.0)
    clock.update()
    assert music.plays == 0                 # nothing has started yet


def test_the_music_starts_exactly_when_the_song_does(fake):
    wall, music = fake
    clock = make_clock()
    wall.advance(3.0)
    clock.update()
    assert music.plays == 1
    assert clock.started
    assert clock.time == pytest.approx(0.0)


def test_the_clock_tracks_wall_time_once_running(fake):
    wall, _ = fake
    clock = make_clock()
    wall.advance(3.0)
    clock.update()
    wall.advance(2.5)
    assert clock.time == pytest.approx(2.5)


def test_the_offset_shifts_the_time_we_judge_against(fake):
    wall, _ = fake
    clock = make_clock(offset=0.030)
    wall.advance(3.0)
    clock.update()
    assert clock.time == pytest.approx(0.030)


def test_pausing_freezes_the_song_and_resuming_carries_on(fake):
    wall, music = fake
    clock = make_clock()
    wall.advance(3.0)
    clock.update()
    wall.advance(1.0)

    clock.pause()
    assert music.paused == 1
    frozen = clock.time
    wall.advance(10.0)
    clock.update()
    assert clock.time == pytest.approx(frozen)

    clock.resume()
    assert music.unpaused == 1
    assert clock.time == pytest.approx(frozen)
    wall.advance(0.5)
    assert clock.time == pytest.approx(frozen + 0.5)


def test_the_first_mixer_reading_absorbs_the_start_up_delay(fake):
    wall, music = fake
    clock = make_clock()
    wall.advance(3.0)
    clock.update()

    # the mixer actually began 40ms after we asked it to
    wall.advance(0.4)
    music.position = 0.36
    clock.update()
    assert clock.time == pytest.approx(0.36, abs=1e-6)


def test_later_readings_only_nudge_the_clock(fake):
    wall, music = fake
    clock = make_clock()
    wall.advance(3.0)
    clock.update()
    wall.advance(0.4)
    music.position = 0.4
    clock.update()                       # first check, snaps

    wall.advance(0.3)
    music.position = 0.69                # 10ms of drift
    before = clock.time
    clock.update()
    assert before - clock.time == pytest.approx(0.0005, abs=1e-4)


def test_a_big_jump_is_snapped_rather_than_nudged(fake):
    wall, music = fake
    clock = make_clock()
    wall.advance(3.0)
    clock.update()
    wall.advance(0.4)
    music.position = 0.4
    clock.update()

    wall.advance(0.3)
    music.position = 2.0                 # the mixer is a long way off
    clock.update()
    assert clock.time == pytest.approx(2.0, abs=1e-6)


def test_the_mixer_is_not_trusted_again_after_a_pause(fake):
    wall, music = fake
    clock = make_clock()
    wall.advance(3.0)
    clock.update()
    clock.pause()
    clock.resume()

    wall.advance(1.0)
    music.position = 99.0                # nonsense, and it must be ignored
    clock.update()
    assert clock.time == pytest.approx(1.0)


def test_a_song_that_will_not_decode_still_plays_through_silently(fake):
    wall, music = fake
    music.fail_load = True
    clock = MusicClock(Path("broken.ogg"))
    assert clock.load() is False
    clock.start()
    wall.advance(3.0)
    clock.update()
    assert music.plays == 0
    wall.advance(5.0)
    assert clock.time == pytest.approx(5.0)
    assert not clock.finished


def test_stopping_stops_the_music(fake):
    _, music = fake
    clock = make_clock()
    clock.stop()
    assert music.stopped >= 1
    assert not clock.started
