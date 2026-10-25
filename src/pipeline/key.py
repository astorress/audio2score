"""Key estimation (Krumhansl-Schmuckler) and pitch spelling (docs/PLAN.md
§4.1, steps 5-6).

The pitch-class profile of the piece (total duration of every pitch class)
is correlated with the 24 rotated Krumhansl-Kessler probe-tone profiles;
the best correlation is the key. Spelling then picks letter names from that
key (C# vs D♭), so accidentals read naturally.
"""
from dataclasses import dataclass

import numpy as np

MAJOR_PROFILE = np.array(
    [6.35, 2.23, 3.48, 2.33, 4.38, 4.09, 2.52, 5.19, 2.39, 3.66, 2.29, 2.88])
MINOR_PROFILE = np.array(
    [6.33, 2.68, 3.52, 5.38, 2.60, 3.53, 2.54, 4.75, 3.98, 2.69, 3.34, 3.17])

# Tonic spelling (music21 names, "-" = flat): the most usual enharmonic.
MAJOR_TONICS = ("C", "D-", "D", "E-", "E", "F", "F#", "G", "A-", "A", "B-", "B")
MINOR_TONICS = ("C", "C#", "D", "E-", "E", "F", "F#", "G", "G#", "A", "B-", "B")


@dataclass(frozen=True)
class KeyEstimate:
    tonic: int  # pitch class 0-11
    mode: str  # "major" | "minor"
    correlation: float

    @property
    def tonic_name(self) -> str:
        names = MAJOR_TONICS if self.mode == "major" else MINOR_TONICS
        return names[self.tonic]

    @property
    def name(self) -> str:
        return f"{self.tonic_name.replace('-', 'b')} {self.mode}"

    def to_music21(self):
        from music21 import key

        return key.Key(self.tonic_name, self.mode)


def pitch_class_profile(notes) -> np.ndarray:
    profile = np.zeros(12)
    for note in notes:
        profile[note.pitch % 12] += max(note.duration, 0.0)
    return profile


def estimate_key(notes) -> KeyEstimate:
    """Most likely key of pitched notes (C major when there are none)."""
    profile = pitch_class_profile(notes)
    if profile.sum() == 0 or np.count_nonzero(profile) < 2:
        return KeyEstimate(0, "major", 0.0)
    best = None
    for mode, reference in (("major", MAJOR_PROFILE), ("minor", MINOR_PROFILE)):
        for tonic in range(12):
            correlation = float(
                np.corrcoef(profile, np.roll(reference, tonic))[0, 1])
            if best is None or correlation > best.correlation:
                best = KeyEstimate(tonic, mode, correlation)
    return best


def spelling_map(music21_key) -> dict:
    """Pitch class → music21 pitch name for a music21 Key: scale degrees by
    their letter, the raised 6th/7th of minor keys as alterations of their
    letter, and the remaining chromatic notes with the key's accidental
    direction."""
    from music21 import pitch

    names = {}
    for degree in music21_key.getPitches()[:7]:
        names.setdefault(degree.pitchClass, degree.name)
    if music21_key.mode == "minor":
        for index in (5, 6):  # melodic/harmonic minor: raised 6th and 7th
            raised = music21_key.getPitches()[index].transpose("A1")
            names.setdefault(raised.pitchClass, raised.name)
    sharps = music21_key.sharps
    neutral = {
        1: "C#",
        3: "E-",
        6: "F#",
        8: "A-",
        10: "B-"
    }
    for pitch_class in range(12):
        if pitch_class in names:
            continue
        if sharps == 0:
            names[pitch_class] = neutral[pitch_class]
            continue
        candidate = pitch.Pitch(midi=60 + pitch_class)
        enharmonic = candidate.getEnharmonic()
        options = [candidate, enharmonic]
        wanted = "sharp" if sharps > 0 else "flat"
        chosen = next(
            (option for option in options if option.accidental is not None and
             option.accidental.name == wanted), candidate)
        names[pitch_class] = chosen.name
    return names


def spell(midi_pitch: int, names: dict):
    """MIDI number → music21 Pitch spelled with `spelling_map` names."""
    from music21 import pitch

    result = pitch.Pitch(names[midi_pitch % 12])
    # Octave from the MIDI number (B#/C♭ cross the octave boundary).
    result.octave = 4
    result.octave += (midi_pitch - result.midi) // 12
    return result
