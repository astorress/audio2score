"""Beat tracking and rhythmic quantization (docs/PLAN.md §2.3 and §4.1,
steps 3-4): continuous time (seconds) → metric time (quarter notes).

Seconds are mapped to beats by piecewise-linear interpolation through the
detected beats, so tempo drift and rubato bend the grid instead of
accumulating error. Quantization is a Viterbi pass over beats: every beat
picks one subdivision (8ths, 16ths, triplets, ...) trading off the snapping
error of its onsets against rhythmic complexity, with a small cost for
switching subdivision between neighbouring beats (notation reads better
when it doesn't).
"""
import math
from dataclasses import dataclass

import numpy as np

from src.pipeline.notes import (
    Note,
    sort_notes,
)

DEFAULT_TEMPO = 120.0
# Beat trackers lock onto half or double the pulse (a chorale's chord
# changes, a busy hi-hat): the grid is folded into this BPM range.
MIN_TEMPO = 60.0
MAX_TEMPO = 180.0
# Rhythmic complexity of each subdivision (per quarter note).
COMPLEXITY = {
    1: 0.0,
    2: 1.0,
    4: 2.0,
    8: 3.0,
    3: 2.5,
    6: 3.5,
}
# Cost weights, in beats of snapping error.
COMPLEXITY_WEIGHT = 0.03
SWITCH_WEIGHT = 0.02


@dataclass
class Grid:
    beats: np.ndarray  # beat times in seconds, increasing
    tempo: float  # BPM (median inter-beat interval)
    beats_per_measure: int = 4
    downbeat_index: int = 0  # index in `beats` of a downbeat

    @property
    def time_signature(self) -> str:
        return f"{self.beats_per_measure}/4"

    def to_beats(self, times) -> np.ndarray:
        """Seconds → fractional beat index (extrapolated at both ends with
        the first/last inter-beat interval)."""
        times = np.asarray(times, dtype=float)
        beats = self.beats
        index = np.arange(len(beats), dtype=float)
        result = np.interp(times, beats, index)
        first_period = beats[1] - beats[0]
        last_period = beats[-1] - beats[-2]
        before = times < beats[0]
        after = times > beats[-1]
        result[before] = (times[before] - beats[0]) / first_period
        result[after] = (len(beats) - 1 +
                         (times[after] - beats[-1]) / last_period)
        return result


def regular_grid(duration: float,
                 tempo: float = DEFAULT_TEMPO,
                 beats_per_measure: int = 4) -> Grid:
    period = 60.0 / tempo
    count = max(2, int(math.ceil(duration / period)) + 1)
    return Grid(np.arange(count) * period, tempo, beats_per_measure, 0)


def estimate_meter(strengths: np.ndarray) -> tuple:
    """(beats_per_measure, downbeat phase) from the onset strength at each
    beat: the meter/phase whose downbeats are most accented. 4/4 unless 3/4
    is clearly better (it's by far the most common meter in both genres)."""
    strengths = np.asarray(strengths, dtype=float)
    best = {}
    for meter in (3, 4):
        if len(strengths) < 2 * meter:
            continue
        contrasts = []
        for phase in range(meter):
            mask = np.zeros(len(strengths), dtype=bool)
            mask[phase::meter] = True
            contrasts.append(strengths[mask].mean() - strengths[~mask].mean())
        phase = int(np.argmax(contrasts))
        best[meter] = (contrasts[phase], phase)
    if not best:
        return 4, 0
    if 3 in best and 4 in best:
        if best[3][0] > 1.15 * max(best[4][0], 1e-9) and best[3][0] > 0:
            return 3, best[3][1]
        return 4, best[4][1]
    meter = next(iter(best))
    return meter, best[meter][1]


def normalize_tempo(beats: np.ndarray) -> np.ndarray:
    """Doubles (midpoints) or halves (every other beat) the beat times until
    the tempo falls in [MIN_TEMPO, MAX_TEMPO]."""
    beats = np.asarray(beats, dtype=float)
    for _ in range(4):
        if len(beats) < 2:
            break
        tempo = 60.0 / np.median(np.diff(beats))
        if tempo < MIN_TEMPO:
            middle = (beats[:-1] + beats[1:]) / 2
            beats = np.sort(np.concatenate([beats, middle]))
        elif tempo > MAX_TEMPO and len(beats) >= 8:
            beats = beats[::2]
        else:
            break
    return beats


def track_beats(y: np.ndarray, sr: int) -> Grid:
    """Beat grid of a mono signal with librosa's dynamic-programming beat
    tracker; falls back to a regular 120 BPM grid when too few beats are
    found (silence, free time)."""
    import librosa

    duration = len(y) / sr
    onset_env = librosa.onset.onset_strength(y=y, sr=sr)
    _, frames = librosa.beat.beat_track(onset_envelope=onset_env,
                                        sr=sr,
                                        units="frames")
    frames = np.asarray(frames, dtype=int)
    if len(frames) < 4:
        return regular_grid(duration)
    times = normalize_tempo(librosa.frames_to_time(frames, sr=sr))
    tempo = float(60.0 / np.median(np.diff(times)))
    beat_frames = np.clip(librosa.time_to_frames(times, sr=sr), 0,
                          len(onset_env) - 1)
    meter, phase = estimate_meter(onset_env[beat_frames])
    return Grid(times, tempo, meter, phase)


def candidate_subdivisions(subdivisions: int, allow_triplets: bool) -> list:
    """Subdivisions per beat allowed for a maximum of `subdivisions`
    (2 = 8ths, 4 = 16ths, 8 = 32nds)."""
    result = [value for value in (1, 2, 4, 8) if value <= subdivisions]
    if allow_triplets:
        result += [3] + ([6] if subdivisions >= 4 else [])
    return result


def _snap(fraction: float, subdivision: int) -> float:
    return round(fraction * subdivision) / subdivision


def choose_subdivisions(positions: np.ndarray, beat_count: int,
                        candidates: list) -> np.ndarray:
    """Viterbi over beats: the subdivision of every beat in [0, beat_count)
    for onsets at fractional beat `positions`."""
    finest = max(candidates)
    eps = 0.5 / finest
    beat_of = np.floor(positions + eps).astype(int)
    states = len(candidates)
    emission = np.zeros((beat_count, states))
    for beat in range(beat_count):
        fractions = positions[beat_of == beat] - beat
        if len(fractions) == 0:
            continue
        for state, subdivision in enumerate(candidates):
            error = sum(
                abs(fraction - _snap(fraction, subdivision))
                for fraction in fractions)
            emission[beat,
                     state] = (error +
                               COMPLEXITY_WEIGHT * COMPLEXITY[subdivision])
    switch = SWITCH_WEIGHT * (1 - np.eye(states))
    cost = emission[0].copy()
    back = np.zeros((beat_count, states), dtype=int)
    for beat in range(1, beat_count):
        total = cost[:, None] + switch
        back[beat] = np.argmin(total, axis=0)
        cost = total[back[beat], np.arange(states)] + emission[beat]
    path = np.zeros(beat_count, dtype=int)
    path[-1] = int(np.argmin(cost))
    for beat in range(beat_count - 1, 0, -1):
        path[beat - 1] = back[beat, path[beat]]
    return np.array([candidates[state] for state in path])


def measure_origin(grid: Grid, earliest_beat: float) -> int:
    """Beat index where measure 1 starts: the latest downbeat at or before
    the first note (the notes before the detected downbeat become a
    pickup filled with rests)."""
    meter = grid.beats_per_measure
    origin = grid.downbeat_index
    while origin > math.floor(earliest_beat + 1e-6):
        origin -= meter
    while origin + meter <= math.floor(earliest_beat + 1e-6):
        origin += meter
    return origin


def quantize(notes,
             grid: Grid,
             origin: int,
             subdivisions: int = 4,
             allow_triplets: bool = False) -> list:
    """Notes in seconds → notes in quarter notes from `origin`."""
    notes = sort_notes(notes)
    if not notes:
        return []
    candidates = candidate_subdivisions(subdivisions, allow_triplets)
    starts = grid.to_beats([note.start for note in notes]) - origin
    ends = grid.to_beats([note.end for note in notes]) - origin
    beat_count = int(math.floor(max(ends.max(), starts.max()))) + 2
    beat_count = max(beat_count, 1)
    chosen = choose_subdivisions(starts, beat_count, candidates)
    eps = 0.5 / max(candidates)

    def snap(position: float) -> float:
        beat = int(math.floor(position + eps))
        beat = min(max(beat, 0), beat_count - 1)
        return beat + _snap(position - beat, int(chosen[beat]))

    result = []
    for note, start, end in zip(notes, starts, ends):
        q_start = max(0.0, snap(start))
        beat = min(int(math.floor(q_start + 1e-9)), beat_count - 1)
        step = 1.0 / chosen[beat]
        q_end = max(snap(end), q_start + step)
        result.append(
            Note(note.pitch, round(q_start, 6), round(q_end, 6), note.velocity))
    return sort_notes(result)


def quantize_tracks(tracks: dict,
                    grid: Grid,
                    subdivisions: int = 4,
                    allow_triplets: bool = False) -> tuple:
    """Quantizes every instrument against the same grid and measure origin.
    Returns ({instrument: notes in quarter notes}, origin beat index)."""
    onsets = [note.start for notes in tracks.values() for note in notes]
    if not onsets:
        return {
            name: []
            for name in tracks
        }, 0
    origin = measure_origin(grid, float(grid.to_beats([min(onsets)])[0]))
    return {
        name: quantize(notes, grid, origin, subdivisions, allow_triplets)
        for name, notes in tracks.items()
    }, origin


def quarters_to_seconds(position: float, tempo: float) -> float:
    """Quarter notes → seconds at a constant tempo (the tempo written in the
    score, used for the quantized MIDI files)."""
    return position * 60.0 / tempo
