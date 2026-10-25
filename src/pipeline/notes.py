"""Note events, the common currency between transcription and engraving.

Times are in seconds until quantization (`rhythm.quantize`), which returns
the same dataclass with times in quarter notes.
"""
from dataclasses import (
    dataclass,
    replace,
)

import pretty_midi

DRUM_CHANNEL = 9


@dataclass(frozen=True)
class Note:
    pitch: int
    start: float
    end: float
    velocity: int = 80

    @property
    def duration(self) -> float:
        return self.end - self.start

    def with_times(self, start: float, end: float) -> "Note":
        return replace(self, start=start, end=end)


def from_pretty_midi(midi: pretty_midi.PrettyMIDI) -> list:
    """All notes of every instrument of a PrettyMIDI, sorted by onset."""
    return sort_notes(
        Note(note.pitch, float(note.start), float(note.end), note.velocity)
        for instrument in midi.instruments
        for note in instrument.notes)


def sort_notes(notes) -> list:
    return sorted(notes, key=lambda note: (note.start, note.pitch, note.end))


def to_instrument(notes,
                  program: int = 0,
                  is_drum: bool = False,
                  name: str = "") -> pretty_midi.Instrument:
    instrument = pretty_midi.Instrument(program=program,
                                        is_drum=is_drum,
                                        name=name)
    for note in sort_notes(notes):
        instrument.notes.append(
            pretty_midi.Note(velocity=int(max(1, min(127, note.velocity))),
                             pitch=int(note.pitch),
                             start=float(note.start),
                             end=float(note.end)))
    return instrument


def to_pretty_midi(tracks: dict,
                   tempo: float = 120.0) -> pretty_midi.PrettyMIDI:
    """{name: (notes, program, is_drum)} → PrettyMIDI (times in seconds)."""
    midi = pretty_midi.PrettyMIDI(initial_tempo=tempo)
    for name, (notes, program, is_drum) in tracks.items():
        midi.instruments.append(to_instrument(notes, program, is_drum, name))
    return midi
