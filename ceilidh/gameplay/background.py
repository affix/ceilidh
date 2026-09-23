"""What sits behind the arrows: the song's video, its image, or the gradient."""

from __future__ import annotations

import pygame

from ..chart import Song
from ..config import Config
from ..display import scale_cover
from ..display import video


class Background:
    """Picks the best backdrop the song can offer and keeps it fed."""

    def __init__(self, song: Song, cfg: Config, size: tuple[int, int],
                 fallback: pygame.Surface) -> None:
        self.song = song
        self.cfg = cfg
        self.fallback = fallback
        self.player: video.VideoBackground | None = None
        self.still: pygame.Surface | None = None
        self.dim: pygame.Surface | None = None
        self.build(size)

    def build(self, size: tuple[int, int]) -> None:
        self.stop()
        self.still = None
        self.dim = pygame.Surface(size, pygame.SRCALPHA)
        self.dim.fill((0, 0, 0, int(255 * max(0.0, min(0.95, self.cfg.background_dim)))))

        if self._start_video(size):
            return
        self._load_still(size)

    def _start_video(self, size: tuple[int, int]) -> bool:
        if not self.cfg.background_video or not video.available():
            return False
        path = video.find_video(self.song)
        if path is None:
            return False
        height = (self.cfg.video_height or size[1]) // 2 * 2
        width = max(2, int(height * size[0] / size[1])) // 2 * 2
        player = video.VideoBackground(path, (width, height), fps=max(1, self.cfg.video_fps))
        if not player.start():
            return False
        self.player = player
        return True

    def _load_still(self, size: tuple[int, int]) -> None:
        image_path = self.song.background
        if image_path is None or image_path.suffix.lower() in video.VIDEO_EXT:
            return
        try:
            self.still = scale_cover(pygame.image.load(str(image_path)), size)
        except (pygame.error, FileNotFoundError, OSError):
            self.still = None

    def draw(self, surface: pygame.Surface, song_time: float) -> None:
        frame = self.player.frame(song_time) if self.player is not None else None
        if frame is not None:
            if frame.get_size() != surface.get_size():
                frame = pygame.transform.scale(frame, surface.get_size())
            surface.blit(frame, (0, 0))
        elif self.still is not None:
            surface.blit(self.still, (0, 0))
        else:
            surface.blit(self.fallback, (0, 0))
        if self.dim is not None:
            surface.blit(self.dim, (0, 0))

    def stop(self) -> None:
        if self.player is not None:
            self.player.stop()
            self.player = None
