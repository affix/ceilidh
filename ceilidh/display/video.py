"""Background video playback by piping raw frames out of ffmpeg.

SDL has no video decoder, and pulling in a decoding library would be a heavy
dependency for something purely decorative, so we let ffmpeg do the work and
read RGB frames off a pipe. If ffmpeg is missing the game falls back to the
song's background image and nothing else changes.
"""

from __future__ import annotations

import queue
import shutil
import subprocess
import threading
from pathlib import Path

import pygame

VIDEO_EXT = (".mpg", ".mpeg", ".avi", ".mp4", ".m4v", ".mkv", ".webm", ".ogv", ".wmv", ".m2v")

_binary: str | None | bool = False
_usable: bool | None = None


def ffmpeg_path() -> str | None:
    global _binary
    if _binary is False:
        _binary = shutil.which("ffmpeg")
    return _binary  # type: ignore[return-value]


def available() -> bool:
    """On PATH *and* able to run. A half broken install is common enough."""
    global _usable
    if _usable is None:
        binary = ffmpeg_path()
        if binary is None:
            _usable = False
        else:
            try:
                probe = subprocess.run([binary, "-version"], capture_output=True, timeout=5)
                _usable = probe.returncode == 0
            except (OSError, subprocess.SubprocessError):
                _usable = False
    return _usable


def find_video(song) -> Path | None:
    """The song's declared background video, or any video sitting next to it."""
    for candidate in (song.background, song.banner):
        if candidate is not None and candidate.suffix.lower() in VIDEO_EXT:
            return candidate
    folder = song.folder
    if folder is None or not folder.is_dir():
        return None
    videos = [p for p in sorted(folder.iterdir()) if p.suffix.lower() in VIDEO_EXT]
    if not videos:
        return None
    for hint in ("bg", "background", "movie", "bga"):
        for path in videos:
            if hint in path.stem.lower():
                return path
    return videos[0]


class VideoBackground:
    """Decodes a video to the exact size we blit at, cropped to fill."""

    def __init__(self, path: Path, size: tuple[int, int], fps: int = 24,
                 loop: bool = True, start: float = 0.0) -> None:
        self.path = path
        self.start_at = max(0.0, start)
        self.width, self.height = size
        self.fps = max(1, fps)
        self.loop = loop
        self.frame_bytes = self.width * self.height * 3
        self.queue: queue.Queue[bytes] = queue.Queue(maxsize=4)
        self.process: subprocess.Popen | None = None
        self.thread: threading.Thread | None = None
        self.stopped = threading.Event()
        self.failed = False
        self._surface: pygame.Surface | None = None
        self._index = int(self.start_at * self.fps) - 1
        self._resyncs = 0

    def _spawn(self) -> subprocess.Popen | None:
        binary = ffmpeg_path()
        if binary is None:
            return None
        command = [
            binary, "-hide_banner", "-loglevel", "error", "-nostdin",
        ]
        if self.start_at > 0.05:
            command += ["-ss", f"{self.start_at:.3f}"]
        command += [
            "-i", str(self.path),
            "-an", "-sn",
            "-vf", (f"scale={self.width}:{self.height}:force_original_aspect_ratio=increase,"
                    f"crop={self.width}:{self.height},fps={self.fps}"),
            "-f", "rawvideo", "-pix_fmt", "rgb24", "-",
        ]
        try:
            return subprocess.Popen(command, stdout=subprocess.PIPE,
                                    stderr=subprocess.DEVNULL, bufsize=self.frame_bytes)
        except OSError:
            return None

    def _read_loop(self) -> None:
        passes = 0
        while not self.stopped.is_set() and passes < 64:
            passes += 1
            process = self._spawn()
            if process is None or process.stdout is None:
                self.failed = True
                return
            self.process = process
            produced = 0
            while not self.stopped.is_set():
                chunk = process.stdout.read(self.frame_bytes)
                if not chunk or len(chunk) < self.frame_bytes:
                    break
                produced += 1
                while not self.stopped.is_set():
                    try:
                        self.queue.put(chunk, timeout=0.2)
                        break
                    except queue.Full:
                        continue
            try:
                process.kill()
                process.wait(timeout=1)
            except OSError:
                pass
            if produced == 0:
                # ffmpeg could not decode this file; do not spin on it
                self.failed = True
                return
            if not self.loop or self.stopped.is_set():
                return
            self.start_at = 0.0

    def start(self) -> bool:
        if not available():
            self.failed = True
            return False
        self.thread = threading.Thread(target=self._read_loop, daemon=True)
        self.thread.start()
        return True

    def stop(self) -> None:
        self.stopped.set()
        process = self.process
        if process is not None:
            try:
                process.kill()
            except OSError:
                pass
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
            except queue.Empty:
                break

    def frame(self, song_time: float) -> pygame.Surface | None:
        """The frame for this point in the song, or the newest one decoded."""
        if self.failed:
            return None
        target = int(max(0.0, song_time) * self.fps)

        # decoding cannot always keep up, and walking frame by frame would never
        # close a large gap, so jump the decoder instead
        if target - self._index > self.fps * 3 and self._resyncs < 8 and self.queue.empty():
            self._resyncs += 1
            self.resync(song_time)
            return self._surface

        guard = 0
        while self._index < target and guard < 8:
            try:
                raw = self.queue.get_nowait()
            except queue.Empty:
                break
            guard += 1
            self._index += 1
            surface = pygame.image.frombuffer(raw, (self.width, self.height), "RGB")
            self._surface = surface.convert()
        return self._surface

    def resync(self, song_time: float) -> None:
        """Restart the decoder at a given point in the song."""
        keep = self._surface
        self.stop()
        self.stopped.clear()
        self.start_at = max(0.0, song_time)
        self._index = int(self.start_at * self.fps) - 1
        self._surface = keep
        self.start()
