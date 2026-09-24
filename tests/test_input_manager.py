"""The pad mapping is testable without a pad: SDL events are just objects."""

import pygame
import pytest

from ceilidh.config import Config
from ceilidh.input import InputManager

PAD_ONE, PAD_TWO = 10, 20


@pytest.fixture
def manager(display):
    manager = InputManager(Config())
    # pretend two pads turned up, without needing any hardware
    manager.player_device[0] = PAD_ONE
    manager.player_device[1] = PAD_TWO
    manager.rebuild()
    return manager


def button(instance_id, index, down=True):
    return pygame.event.Event(pygame.JOYBUTTONDOWN if down else pygame.JOYBUTTONUP,
                              instance_id=instance_id, button=index)


def hat(instance_id, value, index=0):
    return pygame.event.Event(pygame.JOYHATMOTION, instance_id=instance_id,
                              hat=index, value=value)


def axis(instance_id, index, value):
    return pygame.event.Event(pygame.JOYAXISMOTION, instance_id=instance_id,
                              axis=index, value=value)


def key(code, down=True):
    return pygame.event.Event(pygame.KEYDOWN if down else pygame.KEYUP, key=code, mod=0)


def actions(events):
    return [(e.player, e.action, e.pressed) for e in events]


def test_a_button_press_and_release_become_one_action_each(manager):
    assert actions(manager.process([button(PAD_ONE, 7)])) == [(0, "start", True)]
    assert actions(manager.process([button(PAD_ONE, 7, down=False)])) == [(0, "start", False)]


def test_each_pad_drives_its_own_player(manager):
    assert actions(manager.process([button(PAD_TWO, 7)])) == [(1, "start", True)]


def test_an_unknown_pad_is_ignored(manager):
    assert manager.process([button(999, 7)]) == []


def test_the_dpad_maps_to_the_four_panels(manager):
    assert actions(manager.process([hat(PAD_ONE, (-1, 0))])) == [(0, "left", True)]
    assert actions(manager.process([hat(PAD_ONE, (0, 0))])) == [(0, "left", False)]
    assert actions(manager.process([hat(PAD_ONE, (0, 1))])) == [(0, "up", True)]


def test_a_diagonal_on_the_dpad_presses_both_panels(manager):
    pressed = actions(manager.process([hat(PAD_ONE, (-1, 1))]))
    assert sorted(pressed) == [(0, "left", True), (0, "up", True)]


def test_moving_between_directions_releases_the_old_one(manager):
    manager.process([hat(PAD_ONE, (-1, 0))])
    moved = actions(manager.process([hat(PAD_ONE, (1, 0))]))
    assert sorted(moved) == [(0, "left", False), (0, "right", True)]


def test_an_axis_only_fires_once_it_crosses_the_threshold(manager):
    assert manager.process([axis(PAD_ONE, 7, 0.3)]) == []
    assert actions(manager.process([axis(PAD_ONE, 7, 0.9)])) == [(0, "down", True)]
    assert actions(manager.process([axis(PAD_ONE, 7, 0.0)])) == [(0, "down", False)]


def test_an_axis_swinging_through_zero_swaps_panels(manager):
    manager.process([axis(PAD_ONE, 7, 0.9)])
    swung = actions(manager.process([axis(PAD_ONE, 7, -0.9)]))
    assert sorted(swung) == [(0, "down", False), (0, "up", True)]


def test_holding_a_panel_does_not_retrigger_it(manager):
    manager.process([button(PAD_ONE, 2)])
    assert manager.process([button(PAD_ONE, 2)]) == []
    assert manager.held(0, "left")


def test_released_panels_stop_reporting_as_held(manager):
    manager.process([button(PAD_ONE, 2)])
    manager.process([button(PAD_ONE, 2, down=False)])
    assert not manager.held(0, "left")


def test_the_keyboard_works_as_a_stand_in_for_either_player(manager):
    assert actions(manager.process([key(pygame.K_LEFT)])) == [(0, "left", True)]
    assert actions(manager.process([key(pygame.K_a)])) == [(1, "left", True)]


def test_keyboard_events_are_flagged_as_not_coming_from_a_pad(manager):
    assert manager.process([key(pygame.K_LEFT)])[0].from_pad is False
    assert manager.process([button(PAD_ONE, 7)])[0].from_pad is True


def test_a_panel_already_down_is_not_pressed_twice_by_another_input(manager):
    # the keyboard and the pad both map to player one's left panel
    assert actions(manager.process([key(pygame.K_LEFT)])) == [(0, "left", True)]
    assert manager.process([button(PAD_ONE, 2)]) == []
    assert manager.held(0, "left")


def test_events_carry_a_timestamp_for_judging(manager):
    event = manager.process([button(PAD_ONE, 2)])[0]
    assert event.time > 0


def test_binding_capture_swallows_the_event_and_reports_what_was_pressed(manager):
    captured = []
    manager.start_capture(lambda spec, iid: captured.append((spec, iid)))
    assert manager.process([button(PAD_ONE, 5)]) == []      # not delivered as gameplay
    assert captured == [("button:5", PAD_ONE)]


def test_capture_recognises_a_dpad_direction(manager):
    captured = []
    manager.start_capture(lambda spec, iid: captured.append(spec))
    manager.process([hat(PAD_ONE, (0, -1))])
    assert captured == ["hat:0:0,-1"]


def test_capture_can_be_cancelled_with_escape(manager):
    captured = []
    manager.start_capture(lambda spec, iid: captured.append((spec, iid)))
    manager.process([key(pygame.K_ESCAPE)])
    assert captured == [("", None)]


def test_capture_only_takes_one_event(manager):
    captured = []
    manager.start_capture(lambda spec, iid: captured.append(spec))
    manager.process([button(PAD_ONE, 5)])
    manager.process([button(PAD_ONE, 6)])
    assert captured == ["button:5"]


def test_rebinding_a_panel_takes_effect_immediately(manager):
    manager.cfg.players[0].bindings["left"] = ["button:9"]
    manager.rebuild()
    assert actions(manager.process([button(PAD_ONE, 9)])) == [(0, "left", True)]
    assert manager.process([button(PAD_ONE, 2)]) == []      # the old binding is gone
