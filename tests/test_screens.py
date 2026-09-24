"""Screen behaviour, driven by injected player actions rather than a keyboard."""

import time

import pytest

from ceilidh.input import InputEvent
from ceilidh.screens.game import Gameplay
from ceilidh.screens.menu import MainMenu, OptionsScreen
from ceilidh.screens.results import Results
from ceilidh.screens.select import DifficultySelect, SongSelect
from ceilidh.screens.setup import CalibrateScreen


def press(player, action):
    return InputEvent(player, action, True, time.perf_counter())


def release(player, action):
    return InputEvent(player, action, False, time.perf_counter())


def labels(menu):
    return [label for label, _ in menu.items]


@pytest.fixture
def menu(app):
    screen = MainMenu(app)
    app.push(screen)
    return screen


def test_the_menu_moves_up_and_down_and_wraps(menu):
    menu.handle_input([press(0, "down")])
    assert menu.index == 1
    menu.index = len(menu.items) - 1
    menu.handle_input([press(0, "down")])
    assert menu.index == 0
    menu.handle_input([press(0, "up")])
    assert menu.index == len(menu.items) - 1


def test_either_player_can_drive_the_menu(menu):
    menu.handle_input([press(1, "down")])
    assert menu.index == 1


def test_choosing_play_opens_the_song_list(app, menu):
    menu.index = labels(menu).index("Play")
    menu.handle_input([press(0, "start")])
    assert isinstance(app.screens[-1], SongSelect)


def test_back_on_the_main_menu_does_nothing(app, menu):
    menu.handle_input([press(0, "back")])
    assert app.screens[-1] is menu
    assert app.running


def test_a_kiosk_has_no_way_to_quit_from_the_menu(app):
    app.cfg.kiosk = True
    assert "Quit" not in labels(MainMenu(app))
    app.cfg.kiosk = False
    assert "Quit" in labels(MainMenu(app))


def test_holding_back_for_long_enough_leaves_a_kiosk(app):
    app.cfg.kiosk = True
    screen = MainMenu(app)
    app.push(screen)
    app.input.state[(0, "back")] = True
    screen.update(1.0)
    assert app.running
    screen.update(2.5)
    assert not app.running


def test_letting_go_resets_the_exit_hold(app):
    app.cfg.kiosk = True
    screen = MainMenu(app)
    app.push(screen)
    app.input.state[(0, "back")] = True
    screen.update(2.0)
    app.input.state[(0, "back")] = False
    screen.update(0.1)
    assert screen.back_held == 0.0
    screen.update(2.9)
    assert app.running


def test_options_adjust_the_things_they_name(app):
    options = OptionsScreen(app)
    app.push(options)
    options.index = options.items.index("P1 Scroll Speed")
    before = app.cfg.players[0].scroll_speed
    options.handle_input([press(0, "right")])
    assert app.cfg.players[0].scroll_speed > before
    options.handle_input([press(0, "left"), press(0, "left")])
    assert app.cfg.players[0].scroll_speed < before


def test_toggles_flip(app):
    options = OptionsScreen(app)
    app.push(options)
    options.index = options.items.index("No Fail")
    before = app.cfg.no_fail
    options.handle_input([press(0, "right")])
    assert app.cfg.no_fail is not before


def test_changing_the_resolution_resizes_the_window(app):
    options = OptionsScreen(app)
    app.push(options)
    options.index = options.items.index("Resolution")
    options.adjust(1, 0)
    assert app.size == app.cfg.surface_size(app.desktop, app.cfg.fullscreen)


def test_the_song_wheel_walks_the_library(app):
    wheel = SongSelect(app)
    app.push(wheel)
    assert len(wheel.items) == 2
    wheel.handle_input([press(0, "down")])
    assert wheel.index == 1
    wheel.handle_input([press(0, "down")])
    assert wheel.index == 0


def test_picking_a_song_opens_the_difficulty_screen(app):
    wheel = SongSelect(app)
    app.push(wheel)
    wheel.handle_input([press(0, "start")])
    assert isinstance(app.screens[-1], DifficultySelect)


def test_the_difficulty_screen_lists_the_charts_easiest_first(app):
    song = next(s for s in app.songs if s.title == "Test Song")
    screen = DifficultySelect(app, song)
    assert [c.difficulty for c in screen.charts()] == ["Easy", "Hard"]


def test_up_and_down_choose_a_chart(app):
    song = next(s for s in app.songs if s.title == "Test Song")
    screen = DifficultySelect(app, song)
    app.push(screen)
    screen.handle_input([press(0, "down")])
    assert screen.cursor[0] == 1
    screen.handle_input([press(0, "down")])
    assert screen.cursor[0] == 0


def test_left_and_right_swap_between_versus_and_doubles(app):
    song = next(s for s in app.songs if s.title == "Test Song")
    screen = DifficultySelect(app, song)
    app.push(screen)
    assert screen.mode == "versus"
    screen.handle_input([press(0, "right")])
    assert screen.mode == "double"
    assert screen.charts()[0].mode == "double"


def test_a_song_with_no_doubles_chart_stays_in_versus(app):
    song = next(s for s in app.songs if s.title == "Another Song")
    screen = DifficultySelect(app, song)
    app.push(screen)
    screen.handle_input([press(0, "right")])
    assert screen.mode == "versus"
    assert "no doubles" in screen.message


def test_confirming_starts_the_song(app):
    song = next(s for s in app.songs if s.title == "Test Song")
    screen = DifficultySelect(app, song)
    app.push(screen)
    screen.handle_input([press(0, "start")])
    game = app.screens[-1]
    assert isinstance(game, Gameplay)
    assert [lane.player for lane in game.lanes] == [0]


def test_backing_out_returns_to_the_song_list(app):
    wheel = SongSelect(app)
    app.push(wheel)
    wheel.handle_input([press(0, "start")])
    app.screens[-1].handle_input([press(0, "back")])
    assert app.screens[-1] is wheel


def test_input_lag_is_taken_off_a_press_before_judging(app):
    song = next(s for s in app.songs if s.title == "Test Song")
    game = Gameplay(app, song, {0: song.charts_for("single")[0]}, "single")
    app.push(game)
    app.cfg.input_lag_ms = 80.0
    judged = []
    game.lanes[0].press = lambda column, when: judged.append(when)
    wall = time.perf_counter()
    game.handle_input([InputEvent(0, "left", True, wall)])
    assert judged[0] == pytest.approx(game.clock.time_at(wall) - 0.080)


def test_start_on_a_pad_pauses_and_resumes_a_song(app):
    song = next(s for s in app.songs if s.title == "Test Song")
    game = Gameplay(app, song, {0: song.charts_for("single")[0]}, "single")
    app.push(game)
    game.handle_input([press(0, "start")])
    assert game.paused
    game.handle_input([press(0, "start")])
    assert not game.paused


def test_back_on_a_pad_leaves_the_song_for_the_song_list(app):
    wheel = SongSelect(app)
    app.push(wheel)
    wheel.handle_input([press(0, "start")])
    app.screens[-1].handle_input([press(0, "start")])
    assert isinstance(app.screens[-1], Gameplay)
    app.screens[-1].handle_input([press(0, "back")])
    assert app.screens[-1] is wheel


def test_escape_on_the_keyboard_still_pauses(app):
    song = next(s for s in app.songs if s.title == "Test Song")
    game = Gameplay(app, song, {0: song.charts_for("single")[0]}, "single")
    app.push(game)
    game.handle_input([InputEvent(0, "back", True, time.perf_counter(), from_pad=False)])
    assert game.paused
    assert app.screens[-1] is game


def test_each_player_steps_on_their_own_playfield(app):
    song = next(s for s in app.songs if s.title == "Test Song")
    chart = song.charts_for("single")[0]
    game = Gameplay(app, song, {0: chart, 1: chart}, "versus")
    app.push(game)
    stepped = []
    for lane in game.lanes:
        lane.press = lambda column, when, p=lane.player: stepped.append((p, column))

    game.handle_input([press(0, "up"), press(1, "right")])
    assert stepped == [(0, 2), (1, 3)]


def test_in_doubles_the_second_pad_is_the_right_hand_half(app):
    song = next(s for s in app.songs if s.title == "Test Song")
    chart = song.charts_for("double")[0]
    game = Gameplay(app, song, {0: chart}, "double")
    app.push(game)
    stepped = []
    game.lanes[0].press = lambda column, when: stepped.append(column)

    game.handle_input([press(0, "left"), press(1, "left"), press(1, "right")])
    assert stepped == [0, 4, 7]


def test_releasing_a_panel_is_not_a_step(app):
    song = next(s for s in app.songs if s.title == "Test Song")
    chart = song.charts_for("single")[0]
    game = Gameplay(app, song, {0: chart}, "versus")
    app.push(game)
    stepped = []
    game.lanes[0].press = lambda column, when: stepped.append(column)

    game.handle_input([release(0, "left")])
    assert stepped == []


def test_anything_at_all_ends_a_demo(app):
    from ceilidh.gameplay.demo import build_demo

    menu = MainMenu(app)
    app.push(menu)
    demo = build_demo(app)      # as the attract loop pushes it
    app.push(demo)
    demo.handle_input([press(0, "left")])
    assert app.screens[-1] is menu


def test_results_go_back_past_the_difficulty_screen_to_the_songs(app):
    wheel = SongSelect(app)
    app.push(wheel)
    wheel.handle_input([press(0, "start")])
    chooser = app.screens[-1]
    song = chooser.song
    lanes = Gameplay(app, song, {0: song.charts[0]}, "versus").lanes
    app.replace(Results(app, song, lanes, "versus"))

    results = app.screens[-1]
    results.update(1.0)
    results.handle_input([press(0, "start")])
    assert app.screens[-1] is wheel


def test_calibrating_late_steps_moves_the_offset_so_they_judge_on_time(app):
    screen = CalibrateScreen(app)
    app.push(screen)
    for beat in range(CalibrateScreen.NEEDED):
        screen.last_click = 100.0 + beat * CalibrateScreen.INTERVAL
        screen.handle_input([InputEvent(0, "left", True, screen.last_click + 0.050)])
    screen.handle_input([press(0, "start")])
    assert app.cfg.global_offset_ms == pytest.approx(-50.0)
    # a step 50 ms after the beat is heard now lands on the note
    song = next(s for s in app.songs if s.title == "Test Song")
    game = Gameplay(app, song, {0: song.charts_for("single")[0]}, "single")
    assert game.clock.time_at(game.clock._anchor + 10.050) == pytest.approx(10.0)
