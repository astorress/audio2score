"""Evaluation metrics (docs/PLAN.md §2.1, §2.2, §8 Phase 3).

- SDR of a separated stem.
- Note F1 (mir_eval): onset only (±50 ms) or onset + offset.
- Multi-instrument F1: a note counts only if pitch, onset *and* instrument
  match (micro-average over all notes, as in MT3).
- Engraving: share of measures whose content adds up to the time signature.
"""
import numpy as np

ONSET_TOLERANCE = 0.05


def sdr(reference: np.ndarray, estimate: np.ndarray) -> float:
    """10·log10(‖s‖² / ‖s − ŝ‖²) in dB (signals trimmed to equal length)."""
    length = min(reference.shape[-1], estimate.shape[-1])
    reference = np.asarray(reference)[..., :length]
    estimate = np.asarray(estimate)[..., :length]
    signal = np.sum(reference**2)
    error = np.sum((reference - estimate)**2)
    return float(10 * np.log10((signal + 1e-12) / (error + 1e-12)))


def note_arrays(notes) -> tuple:
    """Notes → (intervals [n, 2] in s, pitches in Hz) for mir_eval."""
    if not notes:
        return np.zeros((0, 2)), np.zeros(0)
    intervals = np.array([[note.start,
                           max(note.end, note.start + 1e-3)] for note in notes])
    pitches = 440.0 * 2**((np.array([note.pitch for note in notes]) - 69) / 12)
    return intervals, pitches


def match_count(reference,
                estimate,
                onset_tolerance: float = ONSET_TOLERANCE,
                with_offset: bool = False) -> int:
    from mir_eval.transcription import match_notes

    if not reference or not estimate:
        return 0
    ref_intervals, ref_pitches = note_arrays(reference)
    est_intervals, est_pitches = note_arrays(estimate)
    matches = match_notes(ref_intervals,
                          ref_pitches,
                          est_intervals,
                          est_pitches,
                          onset_tolerance=onset_tolerance,
                          offset_ratio=0.2 if with_offset else None)
    return len(matches)


def prf(matches: int, reference_count: int, estimate_count: int) -> dict:
    precision = matches / estimate_count if estimate_count else 0.0
    recall = matches / reference_count if reference_count else 0.0
    f1 = (2 * precision * recall / (precision + recall) if precision +
          recall else 0.0)
    return {
        "precision": precision,
        "recall": recall,
        "f1": f1
    }


def note_f1(reference, estimate, with_offset: bool = False) -> dict:
    return prf(match_count(reference, estimate, with_offset=with_offset),
               len(reference), len(estimate))


def multi_instrument_f1(reference: dict, estimate: dict) -> dict:
    """{instrument: notes} vs {instrument: notes}: notes only match within
    the same instrument."""
    matches = sum(
        match_count(notes, estimate.get(name, []))
        for name, notes in reference.items())
    return prf(matches, sum(map(len, reference.values())),
               sum(map(len, estimate.values())))


def measure_accuracy(score) -> float:
    """Share of measures (all parts, first and last excluded: pickup and
    final bar) whose duration equals the bar duration."""
    from music21 import stream

    total = correct = 0
    for part in score.parts:
        measures = list(part.getElementsByClass(stream.Measure))
        for measure in measures[1:-1]:
            total += 1
            expected = measure.barDuration.quarterLength
            correct += abs(measure.duration.quarterLength - expected) < 1e-6
    return correct / total if total else 1.0
