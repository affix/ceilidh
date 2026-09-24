import json

import pytest

from ceilidh import config as config_module
from ceilidh.config import Config, PlayerConfig, config_path


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setenv("CEILIDH_CONFIG_DIR", str(tmp_path))
    monkeypatch.delenv("DANCEMAT_CONFIG_DIR", raising=False)
    return tmp_path


def test_settings_survive_a_save_and_load(isolated):
    cfg = Config()
    cfg.global_offset_ms = -12.5
    cfg.input_lag_ms = 65.0
    cfg.resolution = "1920x1080"
    cfg.kiosk = True
    cfg.players[0].scroll_speed = 3.4
    cfg.players[1].device_guid = "GUID-2"
    cfg.save()

    loaded = Config.load()
    assert loaded.global_offset_ms == -12.5
    assert loaded.input_lag_ms == 65.0
    assert loaded.resolution == "1920x1080"
    assert loaded.kiosk is True
    assert loaded.players[0].scroll_speed == 3.4
    assert loaded.players[1].device_guid == "GUID-2"


def test_a_missing_config_just_gives_the_defaults(isolated):
    cfg = Config.load()
    assert cfg.resolution == "1280x720"
    assert len(cfg.players) == 2


def test_a_corrupt_config_does_not_stop_the_game_starting(isolated):
    config_path().write_text("{ not json at all")
    assert Config.load().resolution == "1280x720"


def test_offset_is_exposed_in_seconds():
    cfg = Config()
    cfg.global_offset_ms = 25.0
    assert cfg.offset == pytest.approx(0.025)


@pytest.mark.parametrize("resolution, fullscreen, expected", [
    ("1920x1080", True, (1920, 1080)),
    ("1280x720", False, (1280, 720)),
    ("native", True, (2560, 1440)),
    ("nonsense", False, (1280, 720)),
    ("320x200", False, (640, 360)),          # clamped to something playable
])
def test_surface_size(resolution, fullscreen, expected):
    cfg = Config()
    cfg.resolution = resolution
    assert cfg.surface_size((2560, 1440), fullscreen) == expected


def test_native_in_a_window_leaves_room_for_the_chrome():
    cfg = Config()
    cfg.resolution = "native"
    width, height = cfg.surface_size((2560, 1440), fullscreen=False)
    assert width < 2560
    assert width / height == pytest.approx(16 / 9, rel=1e-2)


def test_resolution_choices_only_offer_what_the_display_can_show():
    cfg = Config()
    choices = cfg.resolution_choices((1920, 1080))
    assert choices[0] == "native"
    assert "1920x1080" in choices
    assert "2560x1440" not in choices


def test_the_current_resolution_is_always_offered_even_if_odd():
    cfg = Config()
    cfg.resolution = "800x600"
    assert "800x600" in cfg.resolution_choices((1920, 1080))


def test_players_get_their_own_keyboard_defaults():
    one, two = PlayerConfig.default(0), PlayerConfig.default(1)
    assert one.keyboard["left"] != two.keyboard["left"]
    assert one.bindings["left"] == two.bindings["left"]   # pads share a default layout


def test_an_older_config_with_width_and_height_becomes_a_resolution():
    cfg = Config.from_dict({"width": 1600, "height": 900})
    assert cfg.resolution == "1600x900"


def test_settings_are_carried_over_from_the_previous_name(tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("CEILIDH_CONFIG_DIR", raising=False)
    monkeypatch.delenv("DANCEMAT_CONFIG_DIR", raising=False)
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    for name in ("HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA"):
        monkeypatch.setenv(name, str(tmp_path))

    legacy = config_module._base_dirs("dancemat")[0] / "config.json"
    legacy.parent.mkdir(parents=True)
    legacy.write_text(json.dumps({
        "global_offset_ms": -33.0,
        "players": [{"device_guid": "OLD-PAD", "bindings": {"left": ["button:9"]}}, {}],
    }))

    cfg = Config.load()
    assert cfg.global_offset_ms == -33.0
    assert cfg.players[0].device_guid == "OLD-PAD"
    assert cfg.players[0].bindings["left"] == ["button:9"]
    assert "moved your settings" in capsys.readouterr().out

    assert config_path().is_file()      # written to the new home
    assert legacy.is_file()             # and the old one left as a backup


def test_an_override_turns_migration_off(tmp_path, monkeypatch):
    monkeypatch.setenv("CEILIDH_CONFIG_DIR", str(tmp_path))
    assert config_module.legacy_config_paths() == []
