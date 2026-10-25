"""Audio I/O: decoding (any format ffmpeg/libsndfile reads), resampling,
trimming to the job's maximum duration."""
from pathlib import Path

import numpy as np

SAMPLE_RATE = 44100  # Demucs' native rate


def load(path: Path,
         sr: int = SAMPLE_RATE,
         mono: bool = False,
         max_duration: float | None = None) -> tuple:
    """(audio, sr): audio is (channels, samples) unless `mono`."""
    import librosa

    audio, rate = librosa.load(str(path),
                               sr=sr,
                               mono=mono,
                               duration=max_duration)
    if not mono and audio.ndim == 1:
        audio = audio[None, :]
    return audio.astype(np.float32), rate


def to_mono(audio: np.ndarray) -> np.ndarray:
    return audio if audio.ndim == 1 else audio.mean(axis=0)


def write(path: Path, audio: np.ndarray, sr: int) -> Path:
    import soundfile

    path.parent.mkdir(parents=True, exist_ok=True)
    data = audio.T if audio.ndim == 2 else audio
    soundfile.write(str(path), data, sr, subtype="PCM_16")
    return path


def duration(audio: np.ndarray, sr: int) -> float:
    return audio.shape[-1] / sr
