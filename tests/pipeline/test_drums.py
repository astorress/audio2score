import numpy as np

from src.pipeline import drums
from src.scripts.synth_demo import (
    SR,
    hihat,
    kick,
    mix_in,
    snare,
)


def test_detects_kick_snare_and_hihat_on_a_synthetic_loop():
    rng = np.random.default_rng(1)
    y = np.zeros(SR * 4, dtype=np.float32)
    expected = []
    for index in range(8):
        time = 0.25 + index * 0.45
        sound, pitch = [(kick(), drums.KICK),
                        (0.7 * snare(rng=rng), drums.SNARE),
                        (hihat(rng=rng), drums.HIHAT)][index % 3]
        mix_in(y, sound, time)
        expected.append((time, pitch))
    notes = drums.transcribe_signal(y, SR)
    hits = [(note.start, note.pitch) for note in notes]
    found = 0
    for time, pitch in expected:
        found += any(
            abs(start - time) < 0.05 and hit == pitch for start, hit in hits)
    assert found >= 6  # baseline: most hits right on clean synthetic drums


def test_silence_has_no_hits():
    assert drums.transcribe_signal(np.zeros(SR, dtype=np.float32), SR) == []
