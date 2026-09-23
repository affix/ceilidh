from __future__ import annotations

from bisect import bisect_right
from dataclasses import dataclass


@dataclass
class Segment:
    beat: float
    t_in: float   # time at which this beat is reached
    t_out: float  # time at which movement resumes (t_in + stop length)
    bpm: float    # bpm in effect from this beat onwards


class TimingData:
    """Beat <-> time conversion for a StepMania style BPM/stop map."""

    def __init__(
        self,
        offset: float = 0.0,
        bpms: list[tuple[float, float]] | None = None,
        stops: list[tuple[float, float]] | None = None,
    ) -> None:
        self.offset = offset
        self.bpms = sorted(bpms or [(0.0, 120.0)])
        self.stops = sorted(stops or [])
        self._build()

    def _build(self) -> None:
        bpms = [b for b in self.bpms if b[1] > 0] or [(0.0, 120.0)]
        if bpms[0][0] > 0:
            bpms.insert(0, (0.0, bpms[0][1]))

        events: list[tuple[float, int, float]] = []
        for beat, value in bpms[1:]:
            events.append((beat, 1, value))
        for beat, value in self.stops:
            events.append((beat, 0, value))
        events.sort(key=lambda e: (e[0], e[1]))

        start = -self.offset
        segments = [Segment(0.0, start, start, bpms[0][1])]
        cur = segments[0]
        for beat, kind, value in events:
            if beat < cur.beat:
                continue
            if beat == cur.beat:
                seg = cur
            else:
                dt = (beat - cur.beat) * 60.0 / cur.bpm
                seg = Segment(beat, cur.t_out + dt, cur.t_out + dt, cur.bpm)
                segments.append(seg)
            if kind == 0:
                seg.t_out += value
            else:
                seg.bpm = value
            cur = seg

        self.segments = segments
        self._beats = [s.beat for s in segments]
        self._times = [s.t_in for s in segments]

    def beat_to_time(self, beat: float) -> float:
        i = max(bisect_right(self._beats, beat) - 1, 0)
        seg = self.segments[i]
        if beat <= seg.beat:
            return seg.t_in + (beat - seg.beat) * 60.0 / seg.bpm
        return seg.t_out + (beat - seg.beat) * 60.0 / seg.bpm

    def time_to_beat(self, t: float) -> float:
        i = bisect_right(self._times, t) - 1
        if i < 0:
            seg = self.segments[0]
            return seg.beat + (t - seg.t_in) * seg.bpm / 60.0
        seg = self.segments[i]
        if t <= seg.t_out:
            return seg.beat
        return seg.beat + (t - seg.t_out) * seg.bpm / 60.0

    def bpm_at(self, beat: float) -> float:
        i = max(bisect_right(self._beats, beat) - 1, 0)
        return self.segments[i].bpm

    def bpm_range(self) -> tuple[float, float]:
        values = [b for _, b in self.bpms if b > 0] or [120.0]
        return min(values), max(values)

    def display_bpm(self) -> str:
        lo, hi = self.bpm_range()
        return f"{lo:.0f}" if abs(hi - lo) < 1 else f"{lo:.0f}-{hi:.0f}"
