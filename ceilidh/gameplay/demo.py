"""A song playing itself, for the attract loop or for checking a chart."""

from __future__ import annotations

import random

from ..chart import Song


def build_demo(app, exclude: Song | None = None):
    """A Gameplay screen set to autoplay, or None when the library is empty."""
    from ..screens.game import Gameplay

    songs = [song for song in app.songs if song.charts]
    if not songs:
        return None
    pool = [song for song in songs if song is not exclude] or songs
    song = random.choice(pool)
    charts = song.charts_for("single") or song.charts
    chart = charts[-1]
    if chart.mode == "double":
        return Gameplay(app, song, {0: chart}, "double", autoplay=True, demo=True)
    return Gameplay(app, song, {0: chart, 1: chart}, "versus", autoplay=True, demo=True)
