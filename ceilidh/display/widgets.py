"""Small drawing helpers shared by the screens."""

from __future__ import annotations

import pygame


def scale_cover(surface: pygame.Surface, size: tuple[int, int]) -> pygame.Surface:
    """Scale to fill the target, cropping the overflow rather than stretching."""
    width, height = size
    scale = max(width / surface.get_width(), height / surface.get_height())
    scaled = pygame.transform.smoothscale(
        surface, (max(1, int(surface.get_width() * scale)), max(1, int(surface.get_height() * scale))))
    out = pygame.Surface(size).convert()
    out.blit(scaled, scaled.get_rect(center=(width // 2, height // 2)))
    return out


def vertical_gradient(
    size: tuple[int, int],
    top: tuple[int, int, int],
    bottom: tuple[int, int, int],
) -> pygame.Surface:
    width, height = size
    strip = pygame.Surface((1, height))
    for y in range(height):
        t = y / max(1, height - 1)
        strip.set_at((0, y), tuple(int(top[i] + (bottom[i] - top[i]) * t) for i in range(3)))
    return pygame.transform.scale(strip, (width, height))


def draw_bar(
    target: pygame.Surface,
    rect: pygame.Rect,
    fraction: float,
    colour: tuple[int, int, int],
    background: tuple[int, int, int] = (30, 30, 40),
    border: tuple[int, int, int] = (90, 90, 110),
) -> None:
    pygame.draw.rect(target, background, rect, border_radius=4)
    fill = rect.copy()
    fill.width = max(0, int(rect.width * max(0.0, min(1.0, fraction))))
    if fill.width:
        pygame.draw.rect(target, colour, fill, border_radius=4)
    pygame.draw.rect(target, border, rect, 2, border_radius=4)
