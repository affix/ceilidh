"""Everything that puts pixels on the screen: the window, and what we draw in it."""

from __future__ import annotations

from . import theme, video
from .arrows import (
    arrow_surface,
    burst_surface,
    mine_surface,
    quant_colour,
    receptor_scaled,
    receptor_surface,
)
from .fonts import FontBank
from .icon import ICON_PATH, set_window_icon
from .widgets import draw_bar, scale_cover, vertical_gradient
from .window import LOW_REFRESH_HZ, Window, refresh_rate

__all__ = [
    "FontBank",
    "ICON_PATH",
    "LOW_REFRESH_HZ",
    "Window",
    "arrow_surface",
    "burst_surface",
    "draw_bar",
    "mine_surface",
    "quant_colour",
    "receptor_scaled",
    "receptor_surface",
    "refresh_rate",
    "scale_cover",
    "set_window_icon",
    "theme",
    "vertical_gradient",
    "video",
]
