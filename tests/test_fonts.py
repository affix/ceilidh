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


def test_wrapping_breaks_on_words_that_do_not_fit():
    bank = FontBank()
    wide = bank.render("Five Nights at Freddy's Song", 34).get_width()
    lines = bank.wrap("Five Nights at Freddy's Song", 34, wide // 2)
    assert len(lines) > 1
    assert " ".join(lines) == "Five Nights at Freddy's Song"


def test_wrapping_leaves_short_text_alone():
    bank = FontBank()
    assert bank.wrap("YYZ", 34, 500) == ["YYZ"]


def test_a_single_overlong_word_is_broken_rather_than_overflowing():
    bank = FontBank()
    lines = bank.wrap("Supercalifragilisticexpialidocious", 34, 80)
    assert len(lines) > 1
    assert all(bank.font(34).size(line)[0] <= 80 for line in lines)


def test_wrapping_can_be_capped_with_an_ellipsis():
    bank = FontBank()
    lines = bank.wrap("one two three four five six seven eight", 30, 90, max_lines=2)
    assert len(lines) == 2
    assert lines[-1].endswith("...")


def test_wrapping_empty_text_still_gives_a_line():
    assert FontBank().wrap("", 20, 100) == [""]


def test_fit_shrinks_until_the_text_goes_on_one_line():
    bank = FontBank()
    text = "Five Nights at Freddy's Song"
    full = bank.render(text, 40).get_width()
    size = bank.fit(text, 40, full // 2)
    assert size < 40
    assert bank.font(size).size(text)[0] <= full // 2


def test_fit_leaves_text_that_already_fits():
    bank = FontBank()
    assert bank.fit("YYZ", 40, 800) == 40
