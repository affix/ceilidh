#!/usr/bin/env python3
"""Generate a dance mat chart from any audio file.

    uv run --extra autochart python3 tools/autochart.py track.mp3 --title "My Song"

Produces songs/<name>/chart.json plus a copy of the audio. Beat detection is
librosa's; the step generator alternates feet and scales density per difficulty.
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
import subprocess
from pathlib import Path

import librosa
import numpy as np

LEFT, DOWN, UP, RIGHT = range(4)
LEFT_FOOT = (LEFT, DOWN)
RIGHT_FOOT = (UP, RIGHT)

PRESETS = {
    "beginner": dict(meter=2, step_every=2.0, density=0.30, jumps=0.0, holds=0.0, eighths=0.0),
    "easy": dict(meter=4, step_every=1.0, density=0.45, jumps=0.02, holds=0.03, eighths=0.0),
    "medium": dict(meter=7, step_every=1.0, density=0.70, jumps=0.06, holds=0.06, eighths=0.15),
    "hard": dict(meter=10, step_every=0.5, density=0.80, jumps=0.10, holds=0.05, eighths=0.55),
    "challenge": dict(meter=13, step_every=0.5, density=0.95, jumps=0.16, holds=0.04, eighths=0.85),
}


def load_audio(path: Path, sr: int = 22050):
    """librosa/soundfile first, ffmpeg as the fallback for exotic containers."""
    try:
        return librosa.load(str(path), sr=sr, mono=True)
    except Exception as exc:  # noqa: BLE001
        ffmpeg = shutil.which("ffmpeg")
        if ffmpeg is None:
            raise SystemExit(f"cannot decode {path}: {exc} (install ffmpeg for more formats)")
        proc = subprocess.run(
            [ffmpeg, "-v", "quiet", "-i", str(path), "-f", "f32le", "-ac", "1", "-ar", str(sr), "-"],
            capture_output=True,
        )
        if proc.returncode != 0 or not proc.stdout:
            raise SystemExit(f"ffmpeg could not decode {path}")
        return np.frombuffer(proc.stdout, dtype=np.float32).copy(), sr


def _search(onset: np.ndarray, frame_time: float, candidates: np.ndarray,
            phase_step: float) -> tuple[float, float, float]:
    duration = len(onset) * frame_time
    best = (-1.0, float(candidates[0]), 0.0)
    for bpm in candidates:
        spb = 60.0 / bpm
        count = max(4, int(duration / spb) - 1)
        k = np.arange(count)
        for phase in np.arange(0.0, spb, phase_step):
            frames = ((phase + k * spb) / frame_time).astype(np.int64)
            score = float(onset[np.clip(frames, 0, len(onset) - 1)].sum()) / count
            if score > best[0]:
                best = (score, float(bpm), float(phase))
    return best


def _tempo_bias(bpm: float) -> float:
    """Dance charts live around 120-180 BPM; nudge ties that way."""
    if 125.0 <= bpm <= 200.0:
        return 1.0
    if 95.0 <= bpm < 125.0 or 200.0 < bpm <= 215.0:
        return 0.94
    return 0.88


def fit_grid(onset: np.ndarray, frame_time: float, seed_bpm: float,
             tolerance: float = 0.04) -> tuple[float, float]:
    """Search BPM and phase for the grid that lands hardest on the onsets.

    Beat trackers often lock onto half, double or three-halves of the real
    tempo, so every plausible multiple is scored and the best one wins.
    """
    results = []
    for multiplier in (0.5, 2.0 / 3.0, 1.0, 1.5, 2.0):
        centre = seed_bpm * multiplier
        if not 70.0 <= centre <= 220.0:
            continue
        coarse = np.arange(centre * (1 - tolerance), centre * (1 + tolerance), 0.05)
        score, bpm, _ = _search(onset, frame_time, coarse, 0.006)
        score, bpm, phase = _search(onset, frame_time,
                                    np.arange(bpm - 0.06, bpm + 0.06, 0.005), 0.002)
        results.append((score * _tempo_bias(bpm), bpm, phase))
    if not results:
        return 60.0 / seed_bpm, 0.0
    _, bpm, phase = max(results)
    return 60.0 / bpm, phase


def analyse(path: Path, hop: int = 256) -> dict:
    y, sr = load_audio(path)
    frame_time = hop / sr
    onset = librosa.onset.onset_strength(y=y, sr=sr, hop_length=hop)
    rms = librosa.feature.rms(y=y, frame_length=hop * 4, hop_length=hop)[0]
    seed, _ = librosa.beat.beat_track(onset_envelope=onset, sr=sr, hop_length=hop, trim=False)
    seed_bpm = float(np.atleast_1d(seed)[0])
    if seed_bpm < 70:
        seed_bpm *= 2
    elif seed_bpm > 210:
        seed_bpm /= 2

    spb, phase = fit_grid(onset, frame_time, seed_bpm)
    duration = float(len(y) / sr)
    count = max(1, int((duration - phase) / spb))
    times = phase + np.arange(count) * spb
    frames = np.clip((times / frame_time).astype(np.int64), 0, len(onset) - 1)

    # take the strongest onset within a frame of the grid point
    window = np.stack([onset[np.clip(frames + d, 0, len(onset) - 1)] for d in (-1, 0, 1)])
    strength = window.max(axis=0)
    loud = rms[np.clip(frames, 0, len(rms) - 1)]
    gate = loud > 0.12 * float(np.median(rms[rms > 0])) if np.any(rms > 0) else np.ones_like(loud, bool)

    order = strength.argsort().argsort()
    ranked = order / max(1, len(order) - 1)
    ranked = np.where(gate, ranked, 0.0)
    return {
        "spb": spb,
        "t0": phase,
        "bpm": 60.0 / spb,
        "times": times,
        "strength": ranked,
        "gate": gate,
        "duration": duration,
        "seed_bpm": seed_bpm,
    }


class Feet:
    """Keeps patterns playable: alternate feet, never the same panel twice."""

    def __init__(self, seed: int) -> None:
        self.rng = random.Random(seed)
        self.foot = 0
        self.last = [LEFT, RIGHT]

    def step(self, crossover: float = 0.0) -> int:
        self.foot ^= 1
        options = list(LEFT_FOOT if self.foot == 0 else RIGHT_FOOT)
        if self.rng.random() < crossover:
            options = list(RIGHT_FOOT if self.foot == 0 else LEFT_FOOT)
        options = [c for c in options if c != self.last[self.foot]] or options
        choice = self.rng.choice(options)
        self.last[self.foot] = choice
        return choice

    def jump(self) -> list[int]:
        pairs = [(LEFT, RIGHT), (UP, DOWN), (LEFT, UP), (DOWN, RIGHT)]
        pair = self.rng.choice(pairs)
        self.last = [pair[0], pair[1]]
        return list(pair)


def regrid(analysis: dict, bpm: float, t0: float) -> dict:
    """Re-sample the onset ranks onto a user supplied BPM/offset grid."""
    spb = 60.0 / bpm
    count = max(1, int((analysis["duration"] - t0) / spb))
    old_times = analysis["times"]
    times = t0 + np.arange(count) * spb
    idx = np.clip(np.searchsorted(old_times, times), 0, len(old_times) - 1)
    out = dict(analysis)
    out.update(spb=spb, bpm=bpm, t0=t0, times=times, strength=analysis["strength"][idx])
    return out


def build_chart(analysis: dict, preset: dict, seed: int) -> list[list]:
    feet = Feet(seed)
    rng = random.Random(seed ^ 0x5EED)
    strength = analysis["strength"]
    notes: list[list] = []
    threshold = 1.0 - preset["density"]
    step_every = max(1, int(preset["step_every"])) if preset["step_every"] >= 1 else 1
    hold_until = -1.0
    occupied: set[float] = set()

    for index, value in enumerate(strength):
        beat = float(index)
        if value <= 0.0:
            continue
        if index % step_every:
            continue
        if value < threshold and rng.random() > 0.2:
            continue
        if beat < hold_until:
            continue

        if rng.random() < preset["jumps"] and value > 0.80:
            for column in feet.jump():
                notes.append([beat, column, "tap"])
            occupied.add(beat)
            continue

        column = feet.step(crossover=0.08 if preset["meter"] >= 10 else 0.0)
        if rng.random() < preset["holds"]:
            length = float(rng.choice([1, 2]))
            notes.append([beat, column, "hold", beat + length])
            hold_until = beat + length
        else:
            notes.append([beat, column, "tap"])
        occupied.add(beat)

        if preset["eighths"] and rng.random() < preset["eighths"] and value > 0.40:
            half = beat + 0.5
            if half not in occupied and half >= hold_until:
                notes.append([half, feet.step(), "tap"])
                occupied.add(half)

    notes.sort(key=lambda n: (n[0], n[1]))
    return notes


def main() -> int:
    parser = argparse.ArgumentParser(description="Auto-generate a dance chart from audio")
    parser.add_argument("audio", type=Path)
    parser.add_argument("--out", type=Path, help="song folder (default songs/<audio stem>)")
    parser.add_argument("--title")
    parser.add_argument("--artist", default="")
    parser.add_argument("--bpm", type=float, help="override detected BPM")
    parser.add_argument("--offset", type=float, help="override detected first-beat time (seconds)")
    parser.add_argument("--difficulties", default="easy,medium,hard",
                        help=f"comma separated: {','.join(PRESETS)}")
    parser.add_argument("--seed", type=int, default=1)
    parser.add_argument("--link", action="store_true", help="symlink the audio instead of copying")
    args = parser.parse_args()

    if not args.audio.is_file():
        parser.error(f"no such file: {args.audio}")

    title = args.title or args.audio.stem
    out = args.out or Path("songs") / args.audio.stem
    out.mkdir(parents=True, exist_ok=True)

    print(f"analysing {args.audio} ...")
    analysis = analyse(args.audio)
    if args.bpm or args.offset is not None:
        bpm = args.bpm or analysis["bpm"]
        t0 = analysis["t0"] if args.offset is None else args.offset
        analysis = regrid(analysis, bpm, t0)
    bpm, t0, duration = analysis["bpm"], analysis["t0"], analysis["duration"]
    if len(analysis["times"]) < 8:
        parser.error("not enough beats detected - try --bpm and --offset")
    print(f"  {duration:.1f}s, seed {analysis['seed_bpm']:.1f} BPM -> grid {bpm:.3f} BPM, "
          f"first beat {t0:.3f}s, {len(analysis['times'])} beats")

    charts = []
    for index, name in enumerate(d.strip().lower() for d in args.difficulties.split(",")):
        if name not in PRESETS:
            parser.error(f"unknown difficulty {name}")
        preset = PRESETS[name]
        notes = build_chart(analysis, preset, args.seed + index * 17)
        charts.append({
            "mode": "single",
            "difficulty": name.capitalize(),
            "meter": preset["meter"],
            "description": "auto-generated",
            "notes": notes,
        })
        print(f"  {name:10} {len(notes):5} notes")

    audio_name = args.audio.name
    target = out / audio_name
    if target.resolve() != args.audio.resolve():
        if args.link:
            if target.exists() or target.is_symlink():
                target.unlink()
            target.symlink_to(args.audio.resolve())
        else:
            shutil.copy2(args.audio, target)

    data = {
        "title": title,
        "artist": args.artist,
        "music": audio_name,
        "offset": -t0,
        "bpms": [[0, round(bpm, 3)]],
        "sample_start": round(max(0.0, duration * 0.35), 2),
        "sample_length": 14.0,
        "charts": charts,
    }
    chart_path = out / "chart.json"
    chart_path.write_text(json.dumps(data, indent=1), encoding="utf-8")
    print(f"wrote {chart_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
