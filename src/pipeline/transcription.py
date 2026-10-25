"""Automatic music transcription (docs/PLAN.md §2.2, §3).

- Melodic stems (rock route): Basic Pitch, instrument-agnostic — the stem
  says which instrument it is, and its range bounds the pitch search.
- Drums: `drums.transcribe` (onset detection + band energies).
- Full mix with several instruments (orchestra route): pluggable backends.
  `basic-pitch-assign` (default, always available) transcribes the mix with
  Basic Pitch and assigns every note to one of the requested instruments by
  range and tessitura: a baseline, not real multi-instrument AMT. MuScriptor
  and YourMT3 are integration points whose licenses and APIs are pending
  verification (docs/modelos.md).
"""
import math
import os
from functools import lru_cache
from pathlib import Path

from src.contract import instruments as catalog
from src.pipeline.notes import (
    from_pretty_midi,
    sort_notes,
)

MULTI_BACKEND = os.environ.get("A2S_MULTI_BACKEND", "basic-pitch-assign")
# Basic Pitch thresholds (its defaults: 0.5 / 0.3 / 127.70 ms).
ONSET_THRESHOLD = 0.5
FRAME_THRESHOLD = 0.3
MIN_NOTE_MS = 58.0
# Basic Pitch's pitch range (A0-C8): asked for a frequency outside it, it
# silently returns no notes at all.
MODEL_LOW, MODEL_HIGH = 21, 108


class BackendUnavailable(RuntimeError):
    """The requested transcription backend is not installed/verified."""


def midi_to_hz(pitch: float) -> float:
    return 440.0 * 2**((pitch - 69) / 12)


@lru_cache(maxsize=1)
def basic_pitch_model():
    from basic_pitch import ICASSP_2022_MODEL_PATH
    from basic_pitch.inference import Model

    return Model(ICASSP_2022_MODEL_PATH)


def basic_pitch(path: Path, low: int = 21, high: int = 108) -> list:
    """Notes of an audio file with Basic Pitch, restricted to [low, high]
    (clamped to the model's range)."""
    from basic_pitch.inference import predict

    low, high = max(low, MODEL_LOW), min(high, MODEL_HIGH)

    _, midi, _ = predict(
        str(path),
        basic_pitch_model(),
        onset_threshold=ONSET_THRESHOLD,
        frame_threshold=FRAME_THRESHOLD,
        minimum_note_length=MIN_NOTE_MS,
        minimum_frequency=midi_to_hz(low - 0.5),
        maximum_frequency=midi_to_hz(high + 0.5),
    )
    return from_pretty_midi(midi)


def transcribe_stem(path: Path, instrument_id: str) -> list:
    instrument = catalog.get(instrument_id)
    if instrument.is_drum:
        from src.pipeline import drums

        return drums.transcribe(path)
    # One octave of slack: filter_range folds octave errors back later.
    return basic_pitch(path, instrument.low - 12, instrument.high + 12)


def tessitura(instrument) -> float:
    return (instrument.low + instrument.high) / 2


# Assignment costs (in tessitura spans).
SHARED_CHORD_COST = 0.3  # two notes of one chord to one instrument
BUSY_COST = 1.0  # a monophonic instrument already sounding
CHORD_TOLERANCE = 0.05  # seconds: onsets closer than this form a chord
SKIP_COST = 2.0  # a note no requested instrument can play


def note_cost(note, instrument, busy_until: float) -> float:
    if not instrument.low <= note.pitch <= instrument.high:
        return math.inf
    cost = abs(note.pitch - tessitura(instrument)) / max(
        instrument.high - instrument.low, 1)
    if instrument.monophonic and busy_until > note.start:
        cost += BUSY_COST
    return cost


def chords(notes) -> list:
    """Groups notes whose onsets are within CHORD_TOLERANCE."""
    groups = []
    for note in sort_notes(notes):
        if groups and note.start - groups[-1][0].start <= CHORD_TOLERANCE:
            groups[-1].append(note)
        else:
            groups.append([note])
    return groups


def _offer(states: dict, state: int, cost: float, path: list) -> None:
    if state not in states or cost < states[state][0]:
        states[state] = (cost, path)


def align_chord(chord, instruments, busy_until: dict) -> list:
    """Monotonic alignment of a chord (ascending pitch) to instruments
    (ascending tessitura) by dynamic programming: voices don't cross, a
    monophonic instrument takes at most one note of the chord, sharing a
    polyphonic one is penalized and a note may stay unassigned (SKIP_COST).
    Returns [(note, instrument or None)]."""
    chord = sorted(chord, key=lambda note: note.pitch)
    # State = index of the last instrument used (-1: none yet).
    states = {
        -1: (0.0, [])
    }
    for note in chord:
        following = {}
        for last, (cost, path) in states.items():
            _offer(following, last, cost + SKIP_COST, path + [None])
            for j in range(max(last, 0), len(instruments)):
                instrument = instruments[j]
                shared = j == last
                if shared and instrument.monophonic:
                    continue
                step = note_cost(note, instrument, busy_until[instrument.id])
                if math.isinf(step):
                    continue
                _offer(following, j,
                       cost + step + (SHARED_CHORD_COST if shared else 0),
                       path + [instrument])
        states = following
    _, path = min(states.values(), key=lambda item: item[0])
    return list(zip(chord, path))


def assign_notes(notes, instrument_ids) -> dict:
    """Mix notes → {instrument: notes}, chord by chord with `align_chord`."""
    instruments = sorted((catalog.get(item)
                          for item in instrument_ids
                          if not catalog.get(item).is_drum),
                         key=tessitura)
    assigned = {
        item.id: []
        for item in instruments
    }
    busy_until = {
        item.id: -1.0
        for item in instruments
    }
    for chord in chords(notes):
        for note, instrument in align_chord(chord, instruments, busy_until):
            if instrument is None:
                continue
            assigned[instrument.id].append(note)
            busy_until[instrument.id] = max(busy_until[instrument.id], note.end)
    return assigned


def transcribe_mix(path: Path,
                   instrument_ids,
                   backend: str = MULTI_BACKEND) -> dict:
    """{instrument id: notes} for a full mix (orchestra route)."""
    if backend == "basic-pitch-assign":
        pitched = [
            catalog.get(item)
            for item in instrument_ids
            if not catalog.get(item).is_drum
        ]
        low = min((item.low for item in pitched), default=21)
        high = max((item.high for item in pitched), default=108)
        return assign_notes(basic_pitch(path, low, high), instrument_ids)
    if backend in ("muscriptor", "yourmt3", "mt3"):
        raise BackendUnavailable(
            f"The {backend} backend is not integrated yet: verify its license"
            " and VRAM first (docs/modelos.md), then implement it here.")
    raise BackendUnavailable(f"Unknown transcription backend: {backend}")
