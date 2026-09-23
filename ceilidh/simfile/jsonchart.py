"""Parser for the game's own JSON chart format.

Simpler than a simfile and easier to generate, which is what the chart
generator writes.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..chart import HOLD, ROLL, TAP, Chart, Note, Song
from ..gameplay.timing import TimingData
from .errors import SimfileError
from .files import AUDIO_EXT, IMAGE_EXT, guess_file, resolve
from .sm import parse_note_data


def _timing(data: dict, fallback_offset: float = 0.0) -> TimingData:
    return TimingData(
        offset=float(data.get("offset", fallback_offset)),
        bpms=[(float(b), float(v)) for b, v in data.get("bpms", [[0, 120]])],
        stops=[(float(b), float(v)) for b, v in data.get("stops", [])],
    )


def _note(item, chart_timing: TimingData) -> Note:
    if isinstance(item, dict):
        beat = float(item["beat"])
        column = int(item["column"])
        kind = item.get("type", TAP)
        end_beat = item.get("end_beat")
    else:
        beat = float(item[0])
        column = int(item[1])
        kind = item[2] if len(item) > 2 else TAP
        end_beat = item[3] if len(item) > 3 else None

    note = Note(beat=beat, time=chart_timing.beat_to_time(beat), column=column, kind=kind)
    if kind in (HOLD, ROLL):
        if end_beat is None:
            note.kind = TAP
        else:
            note.end_beat = float(end_beat)
            note.end_time = chart_timing.beat_to_time(note.end_beat)
    return note


def load(path: Path) -> Song:
    data = json.loads(path.read_text(encoding="utf-8"))
    folder = path.parent
    timing = _timing(data)

    song = Song(
        title=data.get("title", path.stem),
        subtitle=data.get("subtitle", ""),
        artist=data.get("artist", ""),
        folder=folder,
        source=path,
        timing=timing,
        sample_start=float(data.get("sample_start", 0.0)),
        sample_length=float(data.get("sample_length", 12.0)),
    )
    song.music = resolve(folder, data.get("music", ""), AUDIO_EXT) or \
        guess_file(folder, AUDIO_EXT)
    song.banner = resolve(folder, data.get("banner", ""), IMAGE_EXT) or \
        guess_file(folder, IMAGE_EXT, ("banner", "bn", "jacket"))
    song.background = resolve(folder, data.get("background", ""), IMAGE_EXT) or \
        guess_file(folder, IMAGE_EXT, ("-bg", "background"))

    for entry in data.get("charts", []):
        mode = entry.get("mode", "single")
        columns = 8 if mode == "double" else 4
        chart_timing = _timing(entry, data.get("offset", 0.0)) if entry.get("bpms") else timing

        raw_notes = entry.get("notes", [])
        if isinstance(raw_notes, str):
            notes = parse_note_data(raw_notes, columns, chart_timing)
        else:
            notes = sorted((_note(item, chart_timing) for item in raw_notes),
                           key=lambda n: (n.beat, n.column))
        if not notes:
            continue

        chart = Chart(
            columns=columns,
            mode=mode,
            difficulty=entry.get("difficulty", "Edit"),
            meter=int(entry.get("meter", 1)),
            notes=notes,
            description=entry.get("description", ""),
        )
        if chart_timing is not timing:
            chart.timing = chart_timing
        song.charts.append(chart)

    if not song.charts:
        raise SimfileError(f"no charts in {path}")
    return song
