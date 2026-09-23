"""Keep the whole suite headless and silent, whatever a test drags in.

SDL's dummy drivers give us a real display surface and a real event queue with
no window and no sound card, which is what makes the pygame layer testable.
"""

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import json

import pytest


@pytest.fixture(scope="session")
def display():
    """A real 1280x720 surface, backed by nothing."""
    import pygame

    pygame.display.init()
    pygame.font.init()
    surface = pygame.display.set_mode((1280, 720))
    yield surface


@pytest.fixture
def song_library(tmp_path):
    """A tiny but real song on disk: JSON chart plus a placeholder audio file."""
    folder = tmp_path / "songs" / "Test Pack" / "Test Song"
    folder.mkdir(parents=True)
    (folder / "track.ogg").write_bytes(b"OggS")
    (folder / "chart.json").write_text(json.dumps({
        "title": "Test Song", "artist": "Tester", "music": "track.ogg",
        "offset": 0.0, "bpms": [[0, 120]],
        "charts": [
            {"mode": "single", "difficulty": "Easy", "meter": 3,
             "notes": [[b, b % 4, "tap"] for b in range(8)]},
            {"mode": "single", "difficulty": "Hard", "meter": 9,
             "notes": [[b / 2, b % 4, "tap"] for b in range(16)]},
            {"mode": "double", "difficulty": "Hard", "meter": 10,
             "notes": [[b, b % 8, "tap"] for b in range(8)]},
        ],
    }))
    second = tmp_path / "songs" / "Test Pack" / "Another Song"
    second.mkdir(parents=True)
    (second / "track.ogg").write_bytes(b"OggS")
    (second / "chart.json").write_text(json.dumps({
        "title": "Another Song", "artist": "Tester", "music": "track.ogg",
        "bpms": [[0, 100]],
        "charts": [{"mode": "single", "difficulty": "Easy", "meter": 2,
                    "notes": [[0, 0, "tap"], [1, 1, "tap"]]}],
    }))
    return tmp_path / "songs"


@pytest.fixture
def app(song_library, tmp_path, monkeypatch, display):
    """A real App on the dummy display, with the test song library loaded."""
    monkeypatch.setenv("CEILIDH_CONFIG_DIR", str(tmp_path / "cfg"))
    monkeypatch.delenv("DANCEMAT_CONFIG_DIR", raising=False)
    from ceilidh.app import App
    from ceilidh.config import Config

    instance = App(Config(), [song_library])
    instance.rescan()
    return instance
