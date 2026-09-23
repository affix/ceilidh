from __future__ import annotations

import array
import math
import time
from pathlib import Path

import pygame

SAMPLE_RATE = 44100


class MusicClock:
    """Song clock anchored to wall time and slewed towards the mixer position."""

    def __init__(self, path: Path | None, lead_in: float = 3.0, offset: float = 0.0,
                 volume: float = 0.85) -> None:
        self.path = path
        self.lead_in = lead_in
        self.offset = offset
        self.volume = volume
        self.started = False
        self.finished = False
        self.paused = False
        self._anchor = time.perf_counter() + lead_in
        self._next_check = 0.0
        self._loaded = False
        self._drift_ok = True
        self._first_check = True
        self._paused_at = 0.0

    def load(self) -> bool:
        if self.path is None:
            return False
        try:
            pygame.mixer.music.load(str(self.path))
            pygame.mixer.music.set_volume(self.volume)
            self._loaded = True
        except pygame.error:
            self._loaded = False
        return self._loaded

    def start(self) -> None:
        self._anchor = time.perf_counter() + self.lead_in
        self.started = False
        self.finished = False

    def time_at(self, wall: float) -> float:
        return wall - self._anchor + self.offset

    @property
    def time(self) -> float:
        # while paused the anchor is stale; resume() fixes it up afterwards
        return self.time_at(self._paused_at if self.paused else time.perf_counter())

    @property
    def raw_time(self) -> float:
        wall = self._paused_at if self.paused else time.perf_counter()
        return wall - self._anchor

    def update(self) -> None:
        if self.paused:
            return
        now = time.perf_counter()
        raw = now - self._anchor
        if not self.started and raw >= 0.0:
            if self._loaded:
                pygame.mixer.music.play()
            self._anchor = time.perf_counter()
            self.started = True
            self._first_check = True
            self._next_check = now + 0.35
            return
        if self.started and self._loaded and self._drift_ok and now >= self._next_check:
            self._next_check = now + 0.25
            pos = pygame.mixer.music.get_pos()
            if pos < 0:
                self.finished = True
                return
            drift = raw - pos / 1000.0
            if abs(drift) > 0.25 or self._first_check:
                # the first reading absorbs however long the mixer took to
                # actually start the stream
                self._anchor += drift
            else:
                self._anchor += drift * 0.05
            self._first_check = False

    def pause(self) -> None:
        if self.paused:
            return
        self.paused = True
        self._paused_at = time.perf_counter()
        if self.started and self._loaded:
            pygame.mixer.music.pause()

    def resume(self) -> None:
        if not self.paused:
            return
        self._anchor += time.perf_counter() - self._paused_at
        self.paused = False
        # mixer position after a pause is not reliable across SDL builds
        self._drift_ok = False
        if self.started and self._loaded:
            pygame.mixer.music.unpause()

    def stop(self) -> None:
        if self._loaded:
            pygame.mixer.music.stop()
        self.started = False


def play_preview(path: Path | None, start: float, volume: float) -> None:
    pygame.mixer.music.stop()
    if path is None:
        return
    try:
        pygame.mixer.music.load(str(path))
        pygame.mixer.music.set_volume(volume)
        pygame.mixer.music.play(loops=-1, start=max(0.0, start))
    except pygame.error:
        try:
            pygame.mixer.music.play(loops=-1)
        except pygame.error:
            pass


def _pcm(samples: array.array) -> pygame.mixer.Sound:
    return pygame.mixer.Sound(buffer=samples.tobytes())


def make_click(frequency: float = 1400.0, length: float = 0.035, volume: float = 0.35) -> pygame.mixer.Sound:
    count = int(SAMPLE_RATE * length)
    data = array.array("h")
    channels = pygame.mixer.get_init()[2] if pygame.mixer.get_init() else 2
    for i in range(count):
        envelope = math.exp(-i / count * 6.0)
        value = int(math.sin(2 * math.pi * frequency * i / SAMPLE_RATE) * envelope * volume * 32767)
        for _ in range(channels):
            data.append(value)
    return _pcm(data)


def make_noise_tick(length: float = 0.02, volume: float = 0.25) -> pygame.mixer.Sound:
    import random

    count = int(SAMPLE_RATE * length)
    data = array.array("h")
    channels = pygame.mixer.get_init()[2] if pygame.mixer.get_init() else 2
    for i in range(count):
        envelope = math.exp(-i / count * 9.0)
        value = int(random.uniform(-1, 1) * envelope * volume * 32767)
        for _ in range(channels):
            data.append(value)
    return _pcm(data)
