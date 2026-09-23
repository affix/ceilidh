"""The handful of places where the platforms genuinely differ."""

import importlib.util
import os
import sys
from pathlib import Path

import pytest

from ceilidh import app as app_module
from ceilidh import config as config_module
from ceilidh import library

HINTS = ("SDL_JOYSTICK_HIDAPI", "SDL_JOYSTICK_HIDAPI_XBOX", "SDL_JOYSTICK_HIDAPI_XBOX_360")


@pytest.fixture
def clean_env(monkeypatch):
    for name in HINTS + ("SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", "SDL_JOYSTICK_THREAD",
                         "XDG_CONFIG_HOME", "APPDATA", "LOCALAPPDATA"):
        monkeypatch.delenv(name, raising=False)


def test_windows_leaves_xbox_pads_to_xinput(clean_env, monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    app_module.prepare_sdl()
    assert not any(name in os.environ for name in HINTS)
    assert os.environ["SDL_JOYSTICK_THREAD"] == "1"


@pytest.mark.parametrize("platform", ["darwin", "linux"])
def test_the_others_ask_sdl_for_its_own_driver(clean_env, monkeypatch, platform):
    monkeypatch.setattr(sys, "platform", platform)
    app_module.prepare_sdl()
    assert all(os.environ[name] == "1" for name in HINTS)


def test_settings_go_to_appdata_on_windows(clean_env, monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
    assert config_module._base_dirs("ceilidh")[0] == tmp_path / "Roaming" / "ceilidh"


def test_settings_go_to_application_support_on_macos(clean_env, monkeypatch):
    monkeypatch.setattr(sys, "platform", "darwin")
    first = config_module._base_dirs("ceilidh")[0]
    assert first.parts[-3:] == ("Library", "Application Support", "ceilidh")


def test_settings_follow_xdg_when_it_is_set(clean_env, monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
    assert config_module._base_dirs("ceilidh")[0] == tmp_path / "ceilidh"


def test_dot_config_is_always_the_backstop(clean_env, monkeypatch):
    for platform in ("win32", "darwin", "linux"):
        monkeypatch.setattr(sys, "platform", platform)
        assert config_module._base_dirs("ceilidh")[-1].parts[-2:] == (".config", "ceilidh")


def test_windows_looks_for_songs_where_windows_keeps_them(clean_env, monkeypatch, tmp_path):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "Local"))
    paths = library.default_song_paths()
    assert Path.home() / "Music" / "Ceilidh" in paths
    assert tmp_path / "Local" / "ceilidh" / "songs" in paths


def test_every_platform_looks_next_to_the_game_first(clean_env, monkeypatch):
    for platform in ("win32", "darwin", "linux"):
        monkeypatch.setattr(sys, "platform", platform)
        assert library.default_song_paths()[0] == Path.cwd() / "songs"


def load_ziv():
    spec = importlib.util.spec_from_file_location("ziv", Path("tools") / "ziv.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_zip_entries_keep_their_names_off_windows(monkeypatch):
    ziv = load_ziv()
    monkeypatch.setattr(ziv.os, "name", "posix")
    assert str(ziv.safe_path("Pack/What? 3:00 AM/song.sm")) == "Pack/What? 3:00 AM/song.sm"


def test_zip_entries_are_made_writable_on_windows(monkeypatch):
    ziv = load_ziv()
    monkeypatch.setattr(ziv.os, "name", "nt")
    assert str(ziv.safe_path("Pack/What? 3:00 AM/song.sm")) == "Pack/What_ 3_00 AM/song.sm"
    assert str(ziv.safe_path("Pack/Trailing. /a.sm")) == "Pack/Trailing/a.sm"


def test_path_traversal_is_still_refused_on_windows(monkeypatch):
    ziv = load_ziv()
    monkeypatch.setattr(ziv.os, "name", "nt")
    assert ziv.safe_path("../../evil.txt") is None
    assert ziv.safe_path("/etc/passwd") is None
