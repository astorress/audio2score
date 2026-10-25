"""Synthetic test audio with a known ground truth, for smoke tests and
notebooks without copyrighted recordings:

    python3 -m src.scripts.synth_demo            → data/audio/demo_rock.wav
                                                   data/audio/demo_orquesta.wav

Rock: drum loop (kick/snare/hi-hat) + bass line + chord stabs at 110 BPM.
Orchestra: a slow chorale of sustained, vibrato-free voices at 72 BPM. Each
audio file comes with its MIDI ground truth (*.mid).
"""
import argparse
from pathlib import Path

import numpy as np

from src.pipeline import audio as audio_io
from src.pipeline.notes import (
    Note,
    to_pretty_midi,
)

SR = 44100


def tone(pitch: int,
         length: float,
         harmonics=(1.0, 0.5, 0.25),
         decay: float = 3.0) -> np.ndarray:
    t = np.arange(int(length * SR)) / SR
    freq = 440.0 * 2**((pitch - 69) / 12)
    wave = sum(amp * np.sin(2 * np.pi * freq * (k + 1) * t)
               for k, amp in enumerate(harmonics))
    envelope = np.minimum(1.0, t / 0.01) * np.exp(-decay * t)
    release = np.minimum(1.0, (length - t) / 0.02)
    return (wave * envelope * release).astype(np.float32)


def kick(length=0.25):
    t = np.arange(int(length * SR)) / SR
    freq = 50 + 100 * np.exp(-30 * t)
    return (np.sin(2 * np.pi * np.cumsum(freq) / SR) * np.exp(-12 * t))


def snare(length=0.2, rng=None):
    t = np.arange(int(length * SR)) / SR
    noise = rng.standard_normal(len(t))
    return (0.6 * noise + 0.4 * np.sin(2 * np.pi * 190 * t)) * np.exp(-25 * t)


def hihat(length=0.05, rng=None):
    t = np.arange(int(length * SR)) / SR
    noise = np.diff(rng.standard_normal(len(t) + 1))  # high-passed noise
    return 0.3 * noise * np.exp(-80 * t)


def mix_in(buffer, signal, start):
    begin = int(start * SR)
    end = min(len(buffer), begin + len(signal))
    buffer[begin:end] += signal[:end - begin]


def rock(seconds: float = 20.0, bpm: float = 110.0) -> tuple:
    rng = np.random.default_rng(0)
    beat = 60.0 / bpm
    out = np.zeros(int(seconds * SR) + SR, dtype=np.float32)
    truth = {
        "drums": [],
        "bass": [],
        "piano": []
    }
    bass_line = [40, 40, 43, 45]  # E2 E2 G2 A2
    chords = [[64, 67, 71], [64, 67, 71], [67, 71, 74], [69, 72, 76]]
    measures = int(seconds / (4 * beat))
    for measure in range(measures):
        for step in range(8):  # eighth notes
            time = (measure * 4 + step / 2) * beat
            mix_in(out, hihat(rng=rng), time)
            truth["drums"].append(Note(42, time, time + 0.1, 80))
            if step in (0, 4):
                mix_in(out, kick(), time)
                truth["drums"].append(Note(36, time, time + 0.1, 100))
            if step in (2, 6):
                mix_in(out, 0.7 * snare(rng=rng), time)
                truth["drums"].append(Note(38, time, time + 0.1, 100))
        pitch = bass_line[measure % 4]
        for quarter in range(4):
            time = (measure * 4 + quarter) * beat
            mix_in(out, 0.5 * tone(pitch, beat * 0.9, decay=1.5), time)
            truth["bass"].append(Note(pitch, time, time + beat * 0.9, 90))
        for pitch in chords[measure % 4]:
            time = measure * 4 * beat
            mix_in(out, 0.15 * tone(pitch, beat * 1.8, decay=1.0), time)
            truth["piano"].append(Note(pitch, time, time + beat * 1.8, 70))
    return out[:int(seconds * SR)], truth


def chorale(seconds: float = 20.0, bpm: float = 72.0) -> tuple:
    beat = 60.0 / bpm
    out = np.zeros(int(seconds * SR) + SR, dtype=np.float32)
    # Soprano / alto / tenor / bass of I-IV-V-I in C major, half notes.
    voices = {
        "flute": [72, 72, 74, 72],
        "clarinet": [67, 69, 67, 64],
        "cello": [52, 53, 55, 48],
        "contrabass": [36, 41, 43, 36],
    }
    truth = {
        name: []
        for name in voices
    }
    chords = int(seconds / (2 * beat))
    for index in range(chords):
        time = index * 2 * beat
        for name, line in voices.items():
            pitch = line[index % 4]
            mix_in(
                out,
                0.2 * tone(pitch, 2 * beat * 0.95,
                           (1.0, 0.3, 0.1), decay=0.3), time)
            truth[name].append(Note(pitch, time, time + 2 * beat * 0.95, 80))
    return out[:int(seconds * SR)], truth


PROGRAMS = {
    "drums": (0, True),
    "bass": (33, False),
    "piano": (0, False),
    "flute": (73, False),
    "clarinet": (71, False),
    "cello": (42, False),
    "contrabass": (43, False)
}


def write(name: str, signal: np.ndarray, truth: dict, out_dir: Path) -> Path:
    signal = 0.9 * signal / (np.abs(signal).max() + 1e-9)
    path = audio_io.write(out_dir / f"{name}.wav", signal[None, :], SR)
    to_pretty_midi({
        part: (notes, *PROGRAMS[part])
        for part, notes in truth.items()
    }).write(str(out_dir / f"{name}.mid"))
    return path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=Path("data/audio"))
    parser.add_argument("--seconds", type=float, default=20.0)
    args = parser.parse_args()
    print(write("demo_rock", *rock(args.seconds), args.out))
    print(write("demo_orquesta", *chorale(args.seconds), args.out))


if __name__ == "__main__":
    main()
