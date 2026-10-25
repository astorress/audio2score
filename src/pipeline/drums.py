"""Drum transcription baseline (docs/PLAN.md §3): onset detection on the
Demucs drums stem + energy in three bands right after every onset.

    kick   (36)  20-150 Hz
    snare  (38)  150-2500 Hz with a noisy 2.5-8 kHz component
    hi-hat (42)  8-16 kHz, short decay
    crash  (49)  8-16 kHz, long decay

A band "fires" when its energy at the onset stands out from that band's
typical (median) onset energy. Several instruments can fire at once (kick +
hi-hat). It's a transparent DSP baseline to compare a learned drum
transcriber (ADTOF, Omnizart) against in the evaluation phase.
"""
from pathlib import Path

import numpy as np

from src.pipeline import audio as audio_io
from src.pipeline.notes import (
    Note,
    sort_notes,
)

KICK, SNARE, HIHAT, CRASH = 36, 38, 42, 49
BANDS = {
    "low": (20, 150),
    "mid": (150, 2500),
    "noise": (2500, 8000),
    "high": (8000, 16000),
}
WINDOW = 0.05  # seconds analyzed after each onset
DECAY_WINDOW = 0.35  # crash vs hi-hat
FIRE_RATIO = 0.6  # band energy / band median needed to fire
HIT_LENGTH = 0.1  # seconds (drum notes are written by onset only)


def band_energy(spectrum: np.ndarray, freqs: np.ndarray, band) -> float:
    low, high = band
    mask = (freqs >= low) & (freqs < high)
    return float(spectrum[mask].sum()) if mask.any() else 0.0


def onset_features(y: np.ndarray, sr: int, onsets: np.ndarray) -> list:
    window = int(WINDOW * sr)
    decay = int(DECAY_WINDOW * sr)
    features = []
    for onset in onsets:
        start = int(onset * sr)
        segment = y[start:start + window]
        if len(segment) < 16:
            features.append(None)
            continue
        spectrum = np.abs(np.fft.rfft(segment * np.hanning(len(segment))))**2
        freqs = np.fft.rfftfreq(len(segment), 1 / sr)
        energies = {
            name: band_energy(spectrum, freqs, band)
            for name, band in BANDS.items()
        }
        tail = y[start + window:start + decay]
        head_rms = float(np.sqrt(np.mean(segment**2)) + 1e-12)
        tail_rms = float(np.sqrt(np.mean(tail**2))) if len(tail) else 0.0
        energies["sustain"] = tail_rms / head_rms
        energies["rms"] = head_rms
        features.append(energies)
    return features


def classify(features: list) -> list:
    """Per onset, the GM drum pitches that fire."""
    valid = [item for item in features if item]
    if not valid:
        return [[] for _ in features]
    medians = {
        name: np.median([item[name] for item in valid]) + 1e-12
        for name in BANDS
    }
    hits = []
    for item in features:
        if not item:
            hits.append([])
            continue
        total = sum(item[name] for name in BANDS) + 1e-12
        share = {
            name: item[name] / total
            for name in BANDS
        }
        ratio = {
            name: item[name] / medians[name]
            for name in BANDS
        }
        fired = []
        if share["low"] > 0.35 and ratio["low"] > FIRE_RATIO:
            fired.append(KICK)
        if (share["mid"] + share["noise"] > 0.35 and
                ratio["noise"] > FIRE_RATIO and ratio["mid"] > 0.3):
            fired.append(SNARE)
        if share["high"] > 0.08 and ratio["high"] > FIRE_RATIO:
            fired.append(CRASH if item["sustain"] > 0.5 else HIHAT)
        if not fired:
            fired.append(
                max(((KICK, share["low"]),
                     (SNARE, share["mid"] + share["noise"]),
                     (HIHAT, share["high"])),
                    key=lambda pair: pair[1])[0])
        hits.append(fired)
    return hits


def detect_onsets(y: np.ndarray, sr: int) -> tuple:
    import librosa

    envelope = librosa.onset.onset_strength(y=y, sr=sr)
    frames = librosa.onset.onset_detect(onset_envelope=envelope,
                                        sr=sr,
                                        backtrack=True,
                                        units="frames")
    times = librosa.frames_to_time(frames, sr=sr)
    strengths = envelope[np.clip(frames, 0, len(envelope) - 1)]
    return times, strengths


def transcribe_signal(y: np.ndarray, sr: int) -> list:
    times, strengths = detect_onsets(y, sr)
    if len(times) == 0:
        return []
    peak = float(np.max(strengths)) or 1.0
    notes = []
    for onset, strength, fired in zip(times, strengths,
                                      classify(onset_features(y, sr, times))):
        velocity = int(np.clip(40 + 87 * strength / peak, 1, 127))
        for pitch in fired:
            notes.append(
                Note(pitch, float(onset),
                     float(onset) + HIT_LENGTH, velocity))
    return sort_notes(notes)


def transcribe(path: Path) -> list:
    y, sr = audio_io.load(path, sr=audio_io.SAMPLE_RATE, mono=True)
    return transcribe_signal(y, sr)
