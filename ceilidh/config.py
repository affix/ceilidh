from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

APP_NAME = "ceilidh"
LEGACY_APP_NAMES = ("dancemat",)

ACTIONS = ("left", "down", "up", "right", "start", "back")
LANE_ACTIONS = ("left", "down", "up", "right")

# Xbox 360 layout as exposed by SDL2: hat 0 is the d-pad, 6=Back, 7=Start.
# Konami pads report the four panels on the d-pad; generic pads often use
# buttons, so a few common indices are bound as well.
DEFAULT_PAD_BINDINGS: dict[str, list[str]] = {
    "left": ["hat:0:-1,0", "button:2", "axis:6:-"],
    "down": ["hat:0:0,-1", "button:0", "axis:7:+"],
    "up": ["hat:0:0,1", "button:3", "axis:7:-"],
    "right": ["hat:0:1,0", "button:1", "axis:6:+"],
    "start": ["button:7"],
    "back": ["button:6"],
}

DEFAULT_KEYBOARD: list[dict[str, list[str]]] = [
    {
        "left": ["key:left"],
        "down": ["key:down"],
        "up": ["key:up"],
        "right": ["key:right"],
        "start": ["key:return", "key:space"],
        "back": ["key:escape"],
    },
    {
        "left": ["key:a"],
        "down": ["key:s"],
        "up": ["key:w"],
        "right": ["key:d"],
        "start": ["key:tab"],
        "back": ["key:backspace"],
    },
]


def _base_dirs(name: str) -> list[Path]:
    """Where settings live, most idiomatic first, with ~/.config as a backstop."""
    out: list[Path] = []
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        out.append(Path(xdg) / name)
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            out.append(Path(appdata) / name)
    elif sys.platform == "darwin":
        out.append(Path.home() / "Library" / "Application Support" / name)
    out.append(Path.home() / ".config" / name)
    return out


def config_dir() -> Path:
    override = os.environ.get("CEILIDH_CONFIG_DIR") or os.environ.get("DANCEMAT_CONFIG_DIR")
    if override:
        return Path(override)
    return _base_dirs(APP_NAME)[0]


def config_path() -> Path:
    return config_dir() / "config.json"


def legacy_config_paths() -> list[Path]:
    """Where the settings lived when the game was called something else."""
    if os.environ.get("CEILIDH_CONFIG_DIR") or os.environ.get("DANCEMAT_CONFIG_DIR"):
        return []
    return [base / "config.json" for name in LEGACY_APP_NAMES for base in _base_dirs(name)]


@dataclass
class PlayerConfig:
    device_guid: str | None = None
    device_name: str = ""
    bindings: dict[str, list[str]] = field(default_factory=dict)
    keyboard: dict[str, list[str]] = field(default_factory=dict)
    scroll_speed: float = 2.2
    enabled: bool = True

    @classmethod
    def default(cls, index: int) -> "PlayerConfig":
        return cls(
            bindings={k: list(v) for k, v in DEFAULT_PAD_BINDINGS.items()},
            keyboard={k: list(v) for k, v in DEFAULT_KEYBOARD[index % 2].items()},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "device_guid": self.device_guid,
            "device_name": self.device_name,
            "bindings": self.bindings,
            "keyboard": self.keyboard,
            "scroll_speed": self.scroll_speed,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any], index: int) -> "PlayerConfig":
        base = cls.default(index)
        base.device_guid = data.get("device_guid")
        base.device_name = data.get("device_name", "")
        if data.get("bindings"):
            base.bindings = {k: list(v) for k, v in data["bindings"].items()}
        if data.get("keyboard"):
            base.keyboard = {k: list(v) for k, v in data["keyboard"].items()}
        base.scroll_speed = float(data.get("scroll_speed", base.scroll_speed))
        base.enabled = bool(data.get("enabled", True))
        return base


PRESET_RESOLUTIONS = (
    "native", "2560x1440", "1920x1080", "1600x900", "1366x768", "1280x720", "960x540",
)


@dataclass
class Config:
    resolution: str = "1280x720"   # "native" or "WIDTHxHEIGHT"
    fullscreen: bool = False
    fps: int = 60
    vsync: bool = True
    audio_buffer: int = 512
    music_volume: float = 0.85
    sfx_volume: float = 0.6
    global_offset_ms: float = 0.0
    background_video: bool = True
    background_dim: float = 0.55
    video_fps: int = 24
    video_height: int = 0          # 0 follows the render resolution
    scroll_direction: str = "up"
    constant_scroll: bool = False
    timing_scale: float = 1.0
    no_fail: bool = True
    kiosk: bool = False
    attract_seconds: float = 45.0
    show_fps: bool = False
    song_paths: list[str] = field(default_factory=list)
    players: list[PlayerConfig] = field(
        default_factory=lambda: [PlayerConfig.default(0), PlayerConfig.default(1)]
    )

    @property
    def offset(self) -> float:
        return self.global_offset_ms / 1000.0

    def surface_size(self, desktop: tuple[int, int], fullscreen: bool) -> tuple[int, int]:
        """Logical render size. SDL scales this to whatever the display is."""
        if self.resolution == "native":
            if fullscreen:
                return desktop
            # leave room for the window chrome, and keep it 16:9
            width = min(1600, int(desktop[0] * 0.9))
            return width, int(width * 9 / 16)
        try:
            width, height = (int(v) for v in self.resolution.lower().split("x"))
        except ValueError:
            return 1280, 720
        return max(640, width), max(360, height)

    def resolution_choices(self, desktop: tuple[int, int]) -> list[str]:
        """Presets that fit the display, native first."""
        out = ["native"]
        for preset in PRESET_RESOLUTIONS[1:]:
            width, height = (int(v) for v in preset.split("x"))
            if width <= desktop[0] and height <= desktop[1]:
                out.append(preset)
        if "1280x720" not in out:
            out.append("1280x720")
        if self.resolution not in out:
            out.append(self.resolution)
        return out

    def to_dict(self) -> dict[str, Any]:
        return {
            "resolution": self.resolution,
            "fullscreen": self.fullscreen,
            "fps": self.fps,
            "vsync": self.vsync,
            "audio_buffer": self.audio_buffer,
            "music_volume": self.music_volume,
            "sfx_volume": self.sfx_volume,
            "global_offset_ms": self.global_offset_ms,
            "background_video": self.background_video,
            "background_dim": self.background_dim,
            "video_fps": self.video_fps,
            "video_height": self.video_height,
            "scroll_direction": self.scroll_direction,
            "constant_scroll": self.constant_scroll,
            "timing_scale": self.timing_scale,
            "no_fail": self.no_fail,
            "kiosk": self.kiosk,
            "attract_seconds": self.attract_seconds,
            "show_fps": self.show_fps,
            "song_paths": self.song_paths,
            "players": [p.to_dict() for p in self.players],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Config":
        cfg = cls()
        if "resolution" not in data and "width" in data and "height" in data:
            # configs written before the resolution setting existed
            data = dict(data, resolution=f"{int(data['width'])}x{int(data['height'])}")
        for key in (
            "resolution", "fullscreen", "fps", "vsync", "audio_buffer",
            "background_video", "background_dim", "video_fps", "video_height",
            "music_volume", "sfx_volume", "global_offset_ms", "scroll_direction",
            "constant_scroll", "timing_scale", "no_fail", "show_fps", "song_paths",
            "kiosk", "attract_seconds",
        ):
            if key in data:
                setattr(cfg, key, data[key])
        players = data.get("players") or []
        cfg.players = [
            PlayerConfig.from_dict(players[i], i) if i < len(players) else PlayerConfig.default(i)
            for i in range(2)
        ]
        return cfg

    def save(self) -> None:
        path = config_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        tmp.replace(path)

    @classmethod
    def load(cls) -> "Config":
        path = config_path()
        if path.is_file():
            try:
                return cls.from_dict(json.loads(path.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                return cls()

        for old in legacy_config_paths():
            if not old.is_file():
                continue
            try:
                cfg = cls.from_dict(json.loads(old.read_text(encoding="utf-8")))
            except (OSError, ValueError):
                continue
            # carry the settings across but leave the old file where it is
            try:
                cfg.save()
                print(f"moved your settings from {old} to {path}")
            except OSError:
                pass
            return cfg
        return cls()
