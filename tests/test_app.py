"""The app shell: screen stack, shortcut handling and the attract loop."""

import time

import pygame
import pytest

from ceilidh.screen import Repeater, Screen


def keydown(code, mod=0):
    return pygame.event.Event(pygame.KEYDOWN, key=code, mod=mod)


class Spy(Screen):
    allows_attract = True

    def __init__(self, app):
        super().__init__(app)
        self.entered = self.exited = self.resized = 0

    def on_enter(self):
        self.entered += 1

    def on_exit(self):
        self.exited += 1

    def on_resize(self):
        self.resized += 1


def test_pushing_and_popping_runs_the_lifecycle_hooks(app):
    first, second = Spy(app), Spy(app)
    app.push(first)
    assert first.entered == 1
    app.push(second)
    assert first.exited == 1 and second.entered == 1
    app.pop()
    assert second.exited == 1 and first.entered == 2


def test_replacing_swaps_the_top_without_touching_what_is_below(app):
    bottom, top, replacement = Spy(app), Spy(app), Spy(app)
    app.push(bottom)
    app.push(top)
    app.replace(replacement)
    assert app.screens == [bottom, replacement]
    assert bottom.entered == 1      # never re-entered


def test_popping_the_last_screen_stops_the_app(app):
    app.push(Spy(app))
    app.pop()
    assert not app.running


@pytest.mark.parametrize("event, expected", [
    (keydown(pygame.K_F11), True),
    (keydown(pygame.K_RETURN, pygame.KMOD_LALT), True),
    (keydown(pygame.K_f, pygame.KMOD_LMETA), True),
    (keydown(pygame.K_f), False),
    (keydown(pygame.K_RETURN), False),
    (pygame.event.Event(pygame.KEYUP, key=pygame.K_F11, mod=0), False),
])
def test_the_fullscreen_shortcuts(app, event, expected):
    assert app.is_fullscreen_shortcut(event) is expected


def test_the_fullscreen_shortcut_never_reaches_the_game(app):
    screen = Spy(app)
    seen = []
    screen.handle_events = seen.append
    app.push(screen)
    app._dispatch([keydown(pygame.K_F11), keydown(pygame.K_SPACE)])
    delivered = [e for batch in seen for e in batch]
    assert [e.key for e in delivered] == [pygame.K_SPACE]


def test_changing_the_display_tells_every_screen_to_re_measure(app):
    screen = Spy(app)
    app.push(screen)
    app.set_resolution("960x540")
    assert screen.resized == 1
    assert app.size == (960, 540)


def test_the_attract_loop_only_runs_in_kiosk_mode(app):
    screen = Spy(app)
    app.push(screen)
    app.last_input = time.perf_counter() - 999

    app.cfg.kiosk = False
    app._maybe_attract(screen, time.perf_counter())
    assert len(app.screens) == 1

    app.cfg.kiosk = True
    app._maybe_attract(screen, time.perf_counter())
    assert len(app.screens) == 2
    assert app.screens[-1].demo


def test_a_busy_menu_is_left_alone(app):
    screen = Spy(app)
    app.push(screen)
    app.cfg.kiosk = True
    app.last_input = time.perf_counter()
    app._maybe_attract(screen, time.perf_counter())
    assert len(app.screens) == 1


def test_screens_that_opt_out_never_attract(app):
    screen = Spy(app)
    screen.allows_attract = False
    app.push(screen)
    app.cfg.kiosk = True
    app.last_input = time.perf_counter() - 999
    app._maybe_attract(screen, time.perf_counter())
    assert len(app.screens) == 1


def test_input_resets_the_attract_timer(app):
    app.push(Spy(app))
    app.last_input = 0.0
    app._dispatch([keydown(pygame.K_SPACE)])
    assert app.last_input > time.perf_counter() - 1


def test_menu_repeat_waits_before_it_starts_repeating():
    repeat = Repeater(delay=0.3, interval=0.1)
    repeat.press(0, "down")
    assert repeat.update(0.2) == []
    assert repeat.update(0.2) == [(0, "down")]
    assert repeat.update(0.25) == [(0, "down")] * 2
    repeat.release(0, "down")
    assert repeat.update(1.0) == []
