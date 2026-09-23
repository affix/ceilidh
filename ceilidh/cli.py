"""Command line entry point: parse arguments, build the config, start the game."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from .config import Config, config_path
from . import library


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ceilidh", description="Ceilidh, a two pad dance mat game")

    songs = parser.add_argument_group("songs")
    songs.add_argument("--songs", action="append", default=[], metavar="DIR",
                       help="extra song directory (repeatable)")
    songs.add_argument("--only-songs", action="store_true",
                       help="use only the directories given with --songs")

    display = parser.add_argument_group("display")
    display.add_argument("--resolution", metavar="WxH",
                         help='render resolution, or "native" for the desktop size')
    display.add_argument("--fullscreen", action="store_true")
    display.add_argument("--windowed", action="store_true")
    display.add_argument("--width", type=int)
    display.add_argument("--height", type=int)
    display.add_argument("--fps", type=int)
    display.add_argument("--no-vsync", action="store_true")

    audio = parser.add_argument_group("audio")
    audio.add_argument("--audio-buffer", type=int,
                       help="mixer buffer in samples (512 default, 1024 on a Pi)")
    audio.add_argument("--offset", type=float, metavar="MS",
                       help="global audio offset in ms")

    modes = parser.add_argument_group("modes")
    modes.add_argument("--bind", action="store_true",
                       help="open the pad binding screen on launch")
    modes.add_argument("--demo", action="store_true",
                       help="start in demo mode (autoplay attract loop)")
    modes.add_argument("--kiosk", action="store_true",
                       help="appliance mode: fullscreen, no Quit item, attract loop when idle")
    modes.add_argument("--attract-seconds", type=float, metavar="N",
                       help="idle seconds before the attract loop starts in kiosk mode")

    info = parser.add_argument_group("information")
    info.add_argument("--list-pads", action="store_true",
                      help="print detected controllers and exit")
    info.add_argument("--list-songs", action="store_true",
                      help="print the song library and exit")
    info.add_argument("--reset-config", action="store_true")
    return parser


def list_pads() -> int:
    os.environ.setdefault("SDL_JOYSTICK_HIDAPI", "1")
    os.environ.setdefault("SDL_JOYSTICK_HIDAPI_XBOX", "1")
    os.environ.setdefault("SDL_VIDEODRIVER", os.environ.get("SDL_VIDEODRIVER", "dummy"))
    import pygame

    pygame.init()
    pygame.joystick.init()
    count = pygame.joystick.get_count()
    print(f"{count} controller(s)")
    for index in range(count):
        joy = pygame.joystick.Joystick(index)
        joy.init()
        print(f"[{index}] {joy.get_name()}")
        print(f"     guid    : {joy.get_guid()}")
        print(f"     buttons : {joy.get_numbuttons()}  hats: {joy.get_numhats()}"
              f"  axes: {joy.get_numaxes()}")
    pygame.quit()
    return 0


def list_songs(paths: list[Path]) -> int:
    songs, errors = library.scan(paths)
    for song in songs:
        charts = ", ".join(f"{c.difficulty}:{c.meter}" for c in song.charts)
        pack = f"[{song.pack}] " if song.pack else ""
        print(f"{pack}{song.display_title} - {song.artist} "
              f"({song.timing.display_bpm()} BPM) {charts}")
    print(f"\n{len(songs)} song(s) from: {', '.join(str(p) for p in paths)}")
    for error in errors:
        print(f"  skipped: {error}", file=sys.stderr)
    return 0


def apply_args(cfg: Config, args: argparse.Namespace) -> None:
    """Command line wins over whatever the config file said."""
    if args.fps:
        cfg.fps = args.fps
    if args.audio_buffer:
        cfg.audio_buffer = args.audio_buffer
    if args.resolution:
        cfg.resolution = args.resolution.strip().lower()
    if args.width and args.height:
        cfg.resolution = f"{args.width}x{args.height}"
    if args.offset is not None:
        cfg.global_offset_ms = args.offset
    if args.kiosk:
        cfg.kiosk = True
        cfg.fullscreen = True
    if args.attract_seconds:
        cfg.attract_seconds = args.attract_seconds
    if args.fullscreen:
        cfg.fullscreen = True
    if args.windowed:
        cfg.fullscreen = False
    if args.no_vsync:
        cfg.vsync = False


def song_paths(cfg: Config, args: argparse.Namespace) -> list[Path]:
    paths = [Path(p).expanduser() for p in args.songs]
    paths += [Path(p).expanduser() for p in cfg.song_paths]
    if not args.only_songs:
        paths += library.default_song_paths()
    unique: list[Path] = []
    for path in paths:
        if path not in unique:
            unique.append(path)
    return unique


def start_game(cfg: Config, paths: list[Path], args: argparse.Namespace) -> int:
    from .app import App
    from .screens.menu import MainMenu

    app = App(cfg, paths)
    app.rescan()
    for error in app.scan_errors:
        print(f"skipped: {error}", file=sys.stderr)

    app.push(MainMenu(app))
    if args.bind:
        from .screens.setup import BindingScreen

        app.push(BindingScreen(app))
    elif args.demo:
        from .gameplay.demo import build_demo

        demo = build_demo(app)
        if demo is not None:
            app.push(demo)
    app.run()
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    if args.list_pads:
        return list_pads()

    if args.reset_config:
        path = config_path()
        if path.exists():
            path.unlink()
        print(f"removed {path}")

    cfg = Config.load()
    apply_args(cfg, args)
    paths = song_paths(cfg, args)

    if args.list_songs:
        return list_songs(paths)
    return start_game(cfg, paths, args)
