import pygame
import pytest

from ceilidh.display.fonts import DISPLAY, FACES, UI, Face, FontBank, face_file

pytestmark = pytest.mark.usefixtures("display")


def test_both_roles_are_defined():
    assert set(FACES) == {UI, DISPLAY}


@pytest.mark.parametrize("extension", [".otf", ".ttf", ".ttc"])
def test_any_build_of_a_face_is_accepted(tmp_path, extension):
    face = Face("Some-Face")
    (tmp_path / f"Some-Face{extension}").write_bytes(b"not really a font")
    assert face_file(face, tmp_path).suffix == extension


def test_a_face_we_do_not_have_is_simply_absent(tmp_path):
    assert face_file(Face("Nothing-Here"), tmp_path) is None


def test_the_display_face_is_bundled_and_renders():
    bank = FontBank()
    surface = bank.render("FANTASTIC", 48, role=DISPLAY)
    assert surface.get_width() > 0
    assert FACES[DISPLAY].stem not in bank.missing_faces()


def test_a_missing_face_falls_back_instead_of_failing():
    bank = FontBank()
    surface = bank.render("Play", 32, role="no-such-role")
    assert surface.get_width() > 0


def test_text_is_cached_per_role():
    bank = FontBank()
    first = bank.render("Play", 32, role=UI)
    assert bank.render("Play", 32, role=UI) is first
    assert bank.render("Play", 32, role=DISPLAY) is not first
