"""Note cleanup before engraving (docs/PLAN.md §4.1, steps 1-2): removes the
typical AMT noise (very short or weak notes, re-triggered repeats), keeps
notes inside the instrument's range and reduces monophonic instruments to a
single line.
"""
from src.pipeline.notes import (
    Note,
    sort_notes,
)


def clean_notes(notes,
                min_duration: float = 0.05,
                min_velocity: int = 20,
                merge_gap: float = 0.03,
                fragment: float = 0.12) -> list:
    """Drops notes shorter than `min_duration` s or softer than
    `min_velocity`, and merges same-pitch notes separated by less than
    `merge_gap` s when one of them is a fragment shorter than `fragment` s
    (one sustained note split by the transcriber). Two long notes back to
    back are a re-articulation (a bass playing quarter notes) and stay."""
    kept = [
        note for note in notes
        if note.duration >= min_duration and note.velocity >= min_velocity
    ]
    merged = []
    last_by_pitch = {}
    for note in sort_notes(kept):
        index = last_by_pitch.get(note.pitch)
        if index is not None:
            previous = merged[index]
            split = min(previous.duration, note.duration) < fragment
            if note.start - previous.end < merge_gap and split:
                merged[index] = Note(previous.pitch, previous.start,
                                     max(previous.end, note.end),
                                     max(previous.velocity, note.velocity))
                continue
        last_by_pitch[note.pitch] = len(merged)
        merged.append(note)
    return sort_notes(merged)


def filter_range(notes, low: int, high: int, fold: bool = True) -> list:
    """Keeps notes in [low, high]. With `fold`, a note at most one octave
    outside is moved an octave into range (octave errors are the most common
    pitch error of AMT); anything farther is dropped."""
    result = []
    for note in notes:
        pitch = note.pitch
        if fold and low - 12 <= pitch < low:
            pitch += 12
        elif fold and high < pitch <= high + 12:
            pitch -= 12
        if low <= pitch <= high:
            result.append(Note(pitch, note.start, note.end, note.velocity))
    return sort_notes(result)


def to_monophonic(notes) -> list:
    """One note at a time: when notes overlap, the louder one wins (ties go
    to the higher pitch, the usual melody) and the other is cut or dropped.
    """
    ordered = sorted(notes,
                     key=lambda note: (note.start, -note.velocity, -note.pitch))
    line = []
    for note in ordered:
        if not line or note.start >= line[-1].end:
            line.append(note)
            continue
        current = line[-1]
        if note.start == current.start:
            continue  # simultaneous onset: the louder/higher one is kept
        louder = (note.velocity, note.pitch) > (current.velocity, current.pitch)
        if louder:
            line[-1] = current.with_times(current.start, note.start)
            line.append(note)
        elif note.end > current.end:
            line.append(note.with_times(current.end, note.end))
    return [note for note in line if note.duration > 0]


def prepare(notes,
            instrument,
            min_duration: float = 0.05,
            min_velocity: int = 20) -> list:
    """Full cleanup for one instrument (`contract.instruments.Instrument`).
    """
    notes = clean_notes(notes,
                        min_duration=min_duration,
                        min_velocity=min_velocity)
    if instrument.is_drum:
        return notes
    notes = filter_range(notes, instrument.low, instrument.high)
    if instrument.monophonic:
        notes = to_monophonic(notes)
    return notes
