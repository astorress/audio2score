from src.pipeline.key import (
    estimate_key,
    spell,
    spelling_map,
)
from src.pipeline.notes import Note


def scale(tonic, steps):
    pitches = [tonic]
    for step in steps:
        pitches.append(pitches[-1] + step)
    # Tonic and dominant longer, as in real music.
    return [
        Note(p, i, i + (2.0 if (p - tonic) % 12 in (0, 7) else 1.0))
        for i, p in enumerate(pitches)
    ]


MAJOR = [2, 2, 1, 2, 2, 2, 1]
HARMONIC_MINOR = [2, 1, 2, 2, 1, 3, 1]


def test_detects_major_and_minor_keys():
    assert estimate_key(scale(62, MAJOR)).name == "D major"
    assert estimate_key(scale(64, HARMONIC_MINOR)).name == "E minor"
    assert estimate_key(scale(70, MAJOR)).name == "Bb major"


def test_empty_defaults_to_c_major():
    assert estimate_key([]).name == "C major"


def test_spelling_follows_the_key():
    from music21 import key

    flats = spelling_map(key.Key("E-", "major"))
    sharps = spelling_map(key.Key("E", "major"))
    assert spell(63, flats).nameWithOctave == "E-4"
    assert spell(63, sharps).nameWithOctave == "D#4"
    minor = spelling_map(key.Key("a", "minor"))
    assert spell(68, minor).name == "G#"  # leading tone
    assert spell(70, spelling_map(key.Key("C"))).name == "B-"


def test_spell_keeps_octave_across_b_sharp():
    from music21 import key

    names = spelling_map(key.Key("c#", "minor"))  # leading tone B#
    assert spell(60, names).nameWithOctave == "B#3"
    assert spell(60, names).midi == 60
