"""Drawing code is testable: render to a surface and read the pixels back."""

import pygame
import pytest

from ceilidh.display import (
    arrow_surface,
    burst_surface,
    draw_bar,
    mine_surface,
    quant_colour,
    receptor_scaled,
    receptor_surface,
    scale_cover,
    vertical_gradient,
)
from ceilidh.display.theme import ACCENT, BG_BOTTOM, BG_TOP

pytestmark = pytest.mark.usefixtures("display")


def opaque_pixels(surface):
    return sum(1 for x in range(surface.get_width()) for y in range(surface.get_height())
               if surface.get_at((x, y)).a > 0)


@pytest.mark.parametrize("beat, expected", [
    (0.0, "4th"), (1.0, "4th"), (0.5, "8th"), (1.0 / 3, "12th"), (0.25, "16th"),
])
def test_quantisation_colours_differ_per_subdivision(beat, expected):
    quarter = quant_colour(0.0)
    colour = quant_colour(beat)
    assert (colour == quarter) is (expected == "4th")


def test_an_arrow_is_drawn_and_mostly_solid():
    arrow = arrow_surface(64, (255, 0, 0), 0)
    assert arrow.get_size() == (64, 64)
    assert arrow.get_at((32, 32)).a == 255          # the shaft is filled
    assert arrow.get_at((0, 0)).a == 0              # the corners are not
    assert opaque_pixels(arrow) > 64 * 64 * 0.3


def test_the_four_directions_are_genuinely_different_shapes():
    rendered = [pygame.image.tobytes(arrow_surface(64, (255, 0, 0), d), "RGBA")
                for d in range(4)]
    assert len(set(rendered)) == 4


def test_arrow_surfaces_are_cached_rather_than_redrawn():
    assert arrow_surface(64, (1, 2, 3), 0) is arrow_surface(64, (1, 2, 3), 0)
    assert arrow_surface(64, (1, 2, 3), 0) is not arrow_surface(65, (1, 2, 3), 0)


def test_a_lit_receptor_is_brighter_than_a_dark_one():
    dark = receptor_surface(64, 0, False)
    lit = receptor_surface(64, 0, True)
    assert opaque_pixels(lit) > opaque_pixels(dark)


def test_scaling_a_receptor_keeps_it_square_and_cached():
    grown = receptor_scaled(64, 0, False, 80)
    assert grown.get_size() == (80, 80)
    assert receptor_scaled(64, 0, False, 80) is receptor_scaled(64, 0, False, 80)
    assert receptor_scaled(64, 0, False, 64) is receptor_surface(64, 0, False)


def test_a_burst_carries_the_alpha_it_was_asked_for():
    assert burst_surface(64, (255, 255, 255), 0, 64, 128).get_alpha() == 128


def test_a_mine_is_round_and_fills_its_box():
    mine = mine_surface(64)
    assert mine.get_size() == (64, 64)
    assert mine.get_at((32, 32)).a == 255
    assert mine.get_at((1, 1)).a == 0


def test_a_progress_bar_fills_from_the_left():
    surface = pygame.Surface((200, 20))
    rect = pygame.Rect(0, 0, 200, 20)
    draw_bar(surface, rect, 0.5, ACCENT)
    assert surface.get_at((40, 10))[:3] == ACCENT          # filled
    assert surface.get_at((160, 10))[:3] != ACCENT         # empty


@pytest.mark.parametrize("fraction", [0.0, 1.0, -5.0, 5.0])
def test_a_progress_bar_copes_with_silly_fractions(fraction):
    surface = pygame.Surface((100, 10))
    draw_bar(surface, pygame.Rect(0, 0, 100, 10), fraction, ACCENT)
    filled = surface.get_at((50, 5))[:3] == ACCENT
    assert filled is (fraction >= 0.5)


def test_the_background_gradient_runs_from_top_colour_to_bottom():
    gradient = vertical_gradient((10, 100), BG_TOP, BG_BOTTOM)
    assert gradient.get_at((5, 0))[:3] == BG_TOP
    assert gradient.get_at((5, 99))[:3] == BG_BOTTOM
    assert gradient.get_at((5, 50))[:3] not in (BG_TOP, BG_BOTTOM)


def test_cover_scaling_fills_the_target_exactly_and_crops_the_rest():
    wide = pygame.Surface((400, 100))
    wide.fill((10, 20, 30))
    pygame.draw.rect(wide, (200, 0, 0), pygame.Rect(0, 0, 20, 100))   # a stripe at the far left
    covered = scale_cover(wide, (200, 200))
    assert covered.get_size() == (200, 200)
    assert covered.get_at((100, 100))[:3] == (10, 20, 30)             # centre survives
    assert covered.get_at((100, 100))[:3] != (200, 0, 0)              # the edge stripe is cropped away
