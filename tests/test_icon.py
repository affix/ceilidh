import pygame
import pytest

from ceilidh.display import ICON_PATH, set_window_icon

pytestmark = pytest.mark.usefixtures("display")


def test_a_missing_icon_is_not_an_error(tmp_path):
    assert set_window_icon(tmp_path / "nothing.png") is False


def test_a_broken_file_is_not_an_error(tmp_path):
    broken = tmp_path / "icon.png"
    broken.write_bytes(b"not a png")
    assert set_window_icon(broken) is False


def test_an_icon_is_loaded_and_squared_off(tmp_path):
    source = pygame.Surface((240, 240), pygame.SRCALPHA)
    source.fill((255, 90, 160, 255))
    path = tmp_path / "icon.png"
    pygame.image.save(source, str(path))
    assert set_window_icon(path) is True


def test_the_game_looks_for_its_icon_inside_the_package():
    assert ICON_PATH.parent.name == "assets"
    assert ICON_PATH.name == "icon.png"
