"""Source separation with HTDemucs (docs/PLAN.md §2.1, §3): the rock route
splits the mix into vocals, drums, bass, guitar, piano and other."""
import os
from functools import lru_cache
from pathlib import Path

import numpy as np

from src.pipeline import audio as audio_io

MODEL = os.environ.get("A2S_DEMUCS_MODEL", "htdemucs_6s")


def device() -> str:
    import torch

    wanted = os.environ.get("A2S_DEVICE")
    if wanted:
        return wanted
    return "cuda" if torch.cuda.is_available() else "cpu"


@lru_cache(maxsize=2)
def load_model(name: str = MODEL):
    from demucs.pretrained import get_model

    model = get_model(name)
    model.eval()
    return model


def separate(audio: np.ndarray,
             sr: int,
             out_dir: Path,
             model_name: str = MODEL) -> dict:
    """Separates a (channels, samples) mix; writes one WAV per stem and
    returns {stem name: path}."""
    import torch
    from demucs.apply import apply_model

    model = load_model(model_name)
    if sr != model.samplerate:
        import librosa

        audio = librosa.resample(audio, orig_sr=sr, target_sr=model.samplerate)
        sr = model.samplerate
    if audio.shape[0] == 1:
        audio = np.repeat(audio, model.audio_channels, axis=0)
    mix = torch.from_numpy(np.ascontiguousarray(audio[:model.audio_channels]))
    # Same normalization as demucs.separate.
    reference = mix.mean(0)
    mean, std = reference.mean(), reference.std() + 1e-8
    with torch.no_grad():
        sources = apply_model(model, ((mix - mean) / std)[None],
                              device=device(),
                              shifts=1,
                              split=True,
                              overlap=0.25,
                              progress=False)[0]
    sources = sources * std + mean
    out_dir.mkdir(parents=True, exist_ok=True)
    stems = {}
    for name, source in zip(model.sources, sources):
        stems[name] = audio_io.write(out_dir / f"{name}.wav",
                                     source.cpu().numpy(), sr)
    return stems
