"""Errors raised while reading a simfile."""

from __future__ import annotations


class SimfileError(Exception):
    """A simfile exists but nothing playable could be read out of it."""
