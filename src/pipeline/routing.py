"""Route selection for `mode=auto` (docs/PLAN.md §3.2).

Baseline heuristic on two features: the share of percussive energy
(harmonic/percussive separation) and the rate of low-frequency onsets (kick
drum). A drum kit pushes both up; an orchestra rarely does. The plan's
learned classifier (CLAP or PANNs embeddings + threshold) can replace
`classify` keeping the same output.
"""
from dataclasses import dataclass

import numpy as np

from src.contract.instruments import (
    ORCHESTRA,
    ROCK,
)

# Logistic score weights, set by hand on the synthetic and real fragments
# of notebooks/ (to be calibrated in the evaluation phase).
BIAS = -3.0
PERCUSSIVE_WEIGHT = 10.0
KICK_RATE_WEIGHT = 0.8


@dataclass(frozen=True)
class RouteDecision:
    mode: str
    probability_rock: float
    features: dict


def features(y: np.ndarray, sr: int) -> dict:
    import librosa

    spectrum = np.abs(librosa.stft(y, n_fft=2048, hop_length=512))
    harmonic, percussive = librosa.decompose.hpss(spectrum)
    percussive_share = float(
        (percussive**2).sum() / ((harmonic**2).sum() +
                                 (percussive**2).sum() + 1e-12))
    freqs = librosa.fft_frequencies(sr=sr, n_fft=2048)
    low = percussive[freqs < 150]
    envelope = librosa.onset.onset_strength(S=librosa.amplitude_to_db(low +
                                                                      1e-6),
                                            sr=sr)
    onsets = librosa.onset.onset_detect(onset_envelope=envelope, sr=sr)
    seconds = len(y) / sr
    return {
        "percussive_share": percussive_share,
        "kick_rate": float(len(onsets) / max(seconds, 1e-6)),
    }


def classify(y: np.ndarray, sr: int) -> RouteDecision:
    values = features(y, sr)
    score = (BIAS + PERCUSSIVE_WEIGHT * values["percussive_share"] +
             KICK_RATE_WEIGHT * values["kick_rate"])
    probability = float(1 / (1 + np.exp(-score)))
    mode = ROCK if probability >= 0.5 else ORCHESTRA
    return RouteDecision(mode, probability, values)
