"""Parser for StepMania .sm and .ssc simfiles."""

from __future__ import annotations

import re
from pathlib import Path

from ..chart import HOLD, MINE, ROLL, TAP, Chart, Note, Song
from ..gameplay.timing import TimingData
from .errors import SimfileError
from .files import AUDIO_EXT, IMAGE_EXT, guess_file, resolve

MODE_COLUMNS = {
    "dance-single": ("single", 4),
    "dance-double": ("double", 8),
    "dance-couple": ("double", 8),
    "dance-solo": ("solo", 6),
    "pump-single": ("pump", 5),
    "single": ("single", 4),
    "double": ("double", 8),
}

_COMMENT = re.compile(r"//[^\n]*")
_ATTRS = re.compile(r"\{[^}]*\}")


def tokens(text: str):
    """Yield (KEY, value) for every #KEY:value; in the file."""
    text = _COMMENT.sub("", text.replace("\r\n", "\n").replace("\r", "\n"))
    for raw in text.split(";"):
        raw = raw.strip()
        if not raw.startswith("#"):
            continue
        key, _, value = raw[1:].partition(":")
        yield key.strip().upper(), value


def parse_pairs(value: str) -> list[tuple[float, float]]:
    """beat=value,beat=value lists, as used by BPMS and STOPS."""
    out: list[tuple[float, float]] = []
    for item in value.replace("\n", "").split(","):
        item = item.strip()
        if not item or "=" not in item:
            continue
        beat, _, val = item.partition("=")
        try:
            out.append((float(beat), float(val)))
        except ValueError:
            continue
    out.sort()
    return out


def to_float(value: str, default: float = 0.0) -> float:
    try:
        return float(value.strip())
    except (ValueError, AttributeError):
        return default


def to_int(value: str, default: int = 0) -> int:
    try:
        return int(float(value.strip()))
    except (ValueError, AttributeError):
        return default


def parse_note_data(data: str, columns: int, timing: TimingData) -> list[Note]:
    """Measures of rows into notes, resolving hold and roll tails as we go."""
    data = _ATTRS.sub("", data)
    notes: list[Note] = []
    pending: dict[int, Note] = {}

    for measure_index, measure in enumerate(data.split(",")):
        rows = [r.strip() for r in measure.split("\n")]
        rows = [r for r in rows if r and not r.startswith("//")]
        if not rows:
            continue
        count = len(rows)
        for row_index, row in enumerate(rows):
            beat = (measure_index + row_index / count) * 4.0
            for column, char in enumerate(row[:columns]):
                if char in ("0", "F", " "):
                    continue
                if char == "3":
                    head = pending.pop(column, None)
                    if head is not None:
                        head.end_beat = beat
                        head.end_time = timing.beat_to_time(beat)
                    continue
                kind = {"1": TAP, "L": TAP, "2": HOLD, "4": ROLL, "M": MINE}.get(char)
                if kind is None:
                    continue
                note = Note(beat=beat, time=timing.beat_to_time(beat), column=column, kind=kind)
                notes.append(note)
                if kind in (HOLD, ROLL):
                    pending[column] = note

    for note in pending.values():   # unterminated holds become taps
        note.kind = TAP
    notes.sort(key=lambda n: (n.beat, n.column))
    return notes


def _chart_from_fields(stepstype: str, difficulty: str, meter: int, description: str,
                       note_data: str, timing: TimingData) -> Chart | None:
    mode, columns = MODE_COLUMNS.get(stepstype.strip().lower(), (None, 0))
    if mode not in ("single", "double"):
        return None
    notes = parse_note_data(note_data, columns, timing)
    if not notes:
        return None
    return Chart(
        columns=columns,
        mode=mode,
        difficulty=difficulty.strip() or "Edit",
        meter=meter,
        notes=notes,
        description=description.strip(),
    )


def _split_blocks(text: str) -> tuple[dict[str, str], list[tuple[dict[str, str], str]]]:
    """Header fields, plus (fields, note data) for each chart in the file."""
    header: dict[str, str] = {}
    current: dict[str, str] | None = None
    charts: list[tuple[dict[str, str], str]] = []

    for key, value in tokens(text):
        if key == "NOTEDATA":          # .ssc starts each chart with this
            current = {}
            continue
        if key in ("NOTES", "NOTES2"):
            if current is not None:
                current["NOTES"] = value
                charts.append((current, value))
            else:                      # .sm packs the fields into the value
                parts = value.split(":")
                if len(parts) >= 6:
                    charts.append(({
                        "STEPSTYPE": parts[0],
                        "DESCRIPTION": parts[1],
                        "DIFFICULTY": parts[2],
                        "METER": parts[3],
                    }, parts[5]))
            continue
        target = current if current is not None else header
        target[key] = value
    return header, charts


def load(path: Path) -> Song:
    text = path.read_text(encoding="utf-8", errors="replace")
    folder = path.parent
    header, raw_charts = _split_blocks(text)

    timing = TimingData(
        offset=to_float(header.get("OFFSET", "0")),
        bpms=parse_pairs(header.get("BPMS", "0=120")),
        stops=parse_pairs(header.get("STOPS", "") or header.get("FREEZES", "")),
    )

    song = Song(
        title=header.get("TITLE", path.stem).strip() or path.stem,
        subtitle=header.get("SUBTITLE", "").strip(),
        artist=header.get("ARTIST", "").strip(),
        folder=folder,
        source=path,
        timing=timing,
        sample_start=to_float(header.get("SAMPLESTART", "0")),
        sample_length=to_float(header.get("SAMPLELENGTH", "12"), 12.0),
    )
    song.music = resolve(folder, header.get("MUSIC", ""), AUDIO_EXT) or \
        guess_file(folder, AUDIO_EXT)
    song.banner = resolve(folder, header.get("BANNER", ""), IMAGE_EXT) or \
        guess_file(folder, IMAGE_EXT, ("banner", "bn", "jacket"))
    song.background = resolve(folder, header.get("BACKGROUND", ""), IMAGE_EXT) or \
        guess_file(folder, IMAGE_EXT, ("-bg", "background"))

    for fields, note_data in raw_charts:
        chart_timing = timing
        if fields.get("BPMS", "").strip():      # .ssc charts may retime themselves
            chart_timing = TimingData(
                offset=to_float(fields.get("OFFSET", header.get("OFFSET", "0"))),
                bpms=parse_pairs(fields["BPMS"]),
                stops=parse_pairs(fields.get("STOPS", "")),
            )
        chart = _chart_from_fields(
            fields.get("STEPSTYPE", "dance-single"),
            fields.get("DIFFICULTY", "Edit"),
            to_int(fields.get("METER", "1"), 1),
            fields.get("DESCRIPTION", "") or fields.get("CHARTNAME", ""),
            note_data,
            chart_timing,
        )
        if chart is None:
            continue
        if chart_timing is not timing:
            chart.timing = chart_timing
        song.charts.append(chart)

    if not song.charts:
        raise SimfileError(f"no usable dance charts in {path}")
    return song
