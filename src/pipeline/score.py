"""Engraving: quantized notes → music21 Score (docs/PLAN.md §4.1, steps 6-8
and §4.4).

Every part is written directly at *written* pitch (transposing instruments
are transposed and get their own key signature) with `atSoundingPitch =
False` and the instrument's transposition set, so MusicXML readers play it
back at concert pitch. Overlapping notes are sliced at every onset/offset
into chords joined by ties (a manual, deterministic `chordify`); bar lines,
ties across them, beams and accidentals come from music21's `makeNotation`.
"""
import copy
import math
from dataclasses import dataclass
from fractions import Fraction

from music21 import (
    chord,
    clef,
    duration,
)
from music21 import instrument as m21instrument
from music21 import (
    interval,
    layout,
    metadata,
    meter,
)
from music21 import note as m21note
from music21 import stream
from music21 import tempo as m21tempo
from music21 import tie

from src.pipeline.key import (
    KeyEstimate,
    spell,
    spelling_map,
)
from src.pipeline.notes import (
    Note,
    sort_notes,
)

ABBREVIATIONS = {
    "flute": "Fl.",
    "oboe": "Ob.",
    "clarinet": "Cl.",
    "alto_sax": "Sx. A.",
    "bassoon": "Fg.",
    "horn": "Cor.",
    "trumpet": "Tpt.",
    "trombone": "Tbn.",
    "tuba": "Tba.",
    "timpani": "Timb.",
    "drums": "Bat.",
    "harp": "Arp.",
    "piano": "Pno.",
    "vocals": "Voz",
    "guitar": "Guit.",
    "bass": "Bajo",
    "violin": "Vln.",
    "viola": "Vla.",
    "cello": "Vc.",
    "contrabass": "Cb.",
}
# Instruments that switch to tenor clef when they play mostly high.
TENOR_CLEF = {"trombone", "bassoon", "cello"}
TENOR_CLEF_FROM = 62  # D4
TENOR_CLEF_SHARE = 0.6
GRAND_STAFF_SPLIT = 60  # middle C goes to the upper staff
# General MIDI percussion → (display step on the 5-line staff, notehead).
DRUM_DISPLAY = {
    35: ("F4", "normal"),
    36: ("F4", "normal"),
    37: ("C5", "x"),
    38: ("C5", "normal"),
    40: ("C5", "normal"),
    41: ("A4", "normal"),
    42: ("G5", "x"),
    43: ("A4", "normal"),
    44: ("D4", "x"),
    45: ("B4", "normal"),
    46: ("G5", "circle-x"),
    47: ("B4", "normal"),
    48: ("E5", "normal"),
    49: ("A5", "x"),
    50: ("E5", "normal"),
    51: ("F5", "x"),
    57: ("A5", "x"),
}
DRUM_DEFAULT = ("C5", "x")
# Gaps up to this (quarter notes) are absorbed by the previous note:
# AMT offsets are noisy and tiny rests make the part unreadable.
LEGATO_GAP = 0.25
# Drum hits last until the next hit, at most one beat.
DRUM_MAX_LENGTH = 1.0


@dataclass
class PartSpec:
    instrument: object  # contract.instruments.Instrument
    notes: list  # quantized notes (quarter notes)


def ql(value: float) -> Fraction:
    """Quarter length as an exact fraction (16ths, 32nds and triplets)."""
    return Fraction(value).limit_denominator(48)


def transposition_semitones(instrument) -> int:
    if not instrument.transposition:
        return 0
    return interval.Interval(instrument.transposition).semitones


def written_notes(notes, instrument) -> list:
    """Sounding → written pitch (a B♭ clarinet is written a 2nd higher)."""
    shift = transposition_semitones(instrument)
    return [
        Note(note.pitch - shift, note.start, note.end, note.velocity)
        for note in notes
    ]


def written_key(concert_key, instrument):
    if not instrument.transposition:
        return concert_key
    return concert_key.transpose(
        interval.Interval(instrument.transposition).reverse())


def fill_legato(notes, gap: float = LEGATO_GAP) -> list:
    """Extends each note to the next onset when the silence between them
    is at most `gap`."""
    notes = sort_notes(notes)
    onsets = sorted({note.start
                     for note in notes})
    result = []
    for note in notes:
        following = next((onset for onset in onsets if onset >= note.end), None)
        if following is not None and following - note.end <= gap:
            note = note.with_times(note.start, following)
        result.append(note)
    return result


def drum_lengths(notes, max_length: float = DRUM_MAX_LENGTH) -> list:
    onsets = sorted({note.start
                     for note in notes})
    result = []
    for note in notes:
        following = next((onset for onset in onsets if onset > note.start),
                         None)
        end = note.start + max_length
        if following is not None:
            end = min(end, following)
        result.append(note.with_times(note.start, end))
    return result


def segments(notes) -> list:
    """Slices overlapping notes at every onset/offset: a list of
    (start, end, [(note_index, pitch)]) covering only sounding time."""
    notes = list(notes)
    boundaries = sorted({note.start
                         for note in notes} | {note.end
                                               for note in notes})
    starts = sorted(range(len(notes)), key=lambda index: notes[index].start)
    active = set()
    cursor = 0
    result = []
    for begin, finish in zip(boundaries, boundaries[1:]):
        while cursor < len(starts) and notes[starts[cursor]].start <= begin:
            active.add(starts[cursor])
            cursor += 1
        active = {index
                  for index in active
                  if notes[index].end > begin}
        if active:
            sounding = sorted(((index, notes[index].pitch) for index in active),
                              key=lambda item: item[1])
            result.append((begin, finish, sounding))
    return result


def tie_type(index: int, begin: float, finish: float, notes) -> str | None:
    note = notes[index]
    starts_here = note.start == begin
    ends_here = note.end == finish
    if starts_here and ends_here:
        return None
    if starts_here:
        return "start"
    if ends_here:
        return "stop"
    return "continue"


def build_events(notes, names: dict, drum: bool = False) -> list:
    """Quantized notes → [(offset, music21 Note/Chord)] without overlaps."""
    notes = list(notes)
    events = []
    for begin, finish, sounding in segments(notes):
        members = []
        seen = set()
        for index, pitch in sounding:
            if drum:
                step, head = DRUM_DISPLAY.get(pitch, DRUM_DEFAULT)
                if step in seen:
                    continue
                seen.add(step)
                member = m21note.Note(step)
                member.notehead = head
            else:
                if pitch in seen:
                    continue
                seen.add(pitch)
                member = m21note.Note(spell(pitch, names))
            kind = tie_type(index, begin, finish, notes)
            if kind and not drum:
                member.tie = tie.Tie(kind)
            members.append(member)
        length = duration.Duration(ql(finish - begin))
        if len(members) == 1:
            element = members[0]
        else:
            element = chord.Chord(members)
        element.duration = length
        events.append((ql(begin), element))
    return events


def make_instrument(instrument):
    cls = getattr(m21instrument, instrument.music21_class)
    result = cls()
    result.partName = instrument.name
    result.instrumentName = instrument.name
    result.partAbbreviation = ABBREVIATIONS.get(instrument.id, "")
    result.instrumentAbbreviation = result.partAbbreviation
    result.midiProgram = instrument.program
    if instrument.is_drum:
        result.midiChannel = 9
    result.transposition = (interval.Interval(instrument.transposition)
                            if instrument.transposition else None)
    return result


def choose_clef(instrument, notes):
    if instrument.is_drum:
        return clef.PercussionClef()
    if instrument.id in TENOR_CLEF and notes:
        high = sum(note.pitch >= TENOR_CLEF_FROM for note in notes)
        if high / len(notes) >= TENOR_CLEF_SHARE:
            return clef.TenorClef()
    return {
        "treble": clef.TrebleClef,
        "bass": clef.BassClef,
        "alto": clef.AltoClef,
        "tenor": clef.TenorClef,
    }[instrument.clef]()


def make_part(instrument,
              notes,
              part_key,
              time_signature: str,
              total_length: Fraction,
              bpm: float,
              part_class=stream.Part,
              staff_clef=None,
              with_tempo: bool = True,
              suffix: str = ""):
    part = part_class()
    part.id = instrument.id + suffix
    part.partName = instrument.name
    part.partAbbreviation = ABBREVIATIONS.get(instrument.id, "")
    part.insert(0, make_instrument(instrument))
    part.insert(0, staff_clef or choose_clef(instrument, notes))
    if not instrument.is_drum:
        part.insert(0, copy.deepcopy(part_key))
    part.insert(0, meter.TimeSignature(time_signature))
    if with_tempo:
        part.insert(0, m21tempo.MetronomeMark(number=round(bpm)))
    if instrument.transposition:
        part.atSoundingPitch = False
    names = spelling_map(part_key)
    for offset, element in build_events(notes, names, instrument.is_drum):
        part.insert(offset, element)
    part.makeRests(fillGaps=True,
                   inPlace=True,
                   refStreamOrTimeRange=[0.0, float(total_length)])
    end = part.highestTime
    if end < total_length:
        part.insert(end, m21note.Rest(quarterLength=total_length - end))
    part.makeNotation(inPlace=True)
    return part


def total_length(specs, beats_per_measure: int) -> Fraction:
    """Common length of every part, rounded up to whole measures."""
    end = max((note.end for spec in specs for note in spec.notes), default=0.0)
    measures = max(1, math.ceil(ql(end) / beats_per_measure))
    return Fraction(measures * beats_per_measure)


def prepare_notes(spec) -> list:
    notes = spec.notes
    if spec.instrument.is_drum:
        return drum_lengths(notes)
    return fill_legato(written_notes(notes, spec.instrument))


def build_score(specs,
                key_estimate: KeyEstimate,
                bpm: float,
                beats_per_measure: int = 4,
                title: str = "audio2score"):
    """Returns (score, {instrument id: [parts]}); a grand-staff instrument
    has two PartStaff objects."""
    concert_key = key_estimate.to_music21()
    time_signature = f"{beats_per_measure}/4"
    # Lengths after preparation: drum hits and legato extend notes.
    specs = [PartSpec(spec.instrument, prepare_notes(spec)) for spec in specs]
    length = total_length(specs, beats_per_measure)

    score = stream.Score()
    score.metadata = metadata.Metadata()
    score.metadata.title = title
    score.metadata.composer = "Transcripción automática · audio2score"

    parts_by_instrument = {}
    first = True
    for spec in specs:
        instrument = spec.instrument
        notes = spec.notes
        part_key = written_key(concert_key, instrument)
        common = {
            "time_signature": time_signature,
            "total_length": length,
            "bpm": bpm,
        }
        if instrument.clef == "grand":
            upper = [n for n in notes if n.pitch >= GRAND_STAFF_SPLIT]
            lower = [n for n in notes if n.pitch < GRAND_STAFF_SPLIT]
            staves = [
                make_part(instrument,
                          upper,
                          part_key,
                          part_class=stream.PartStaff,
                          staff_clef=clef.TrebleClef(),
                          with_tempo=first,
                          suffix="-rh",
                          **common),
                make_part(instrument,
                          lower,
                          part_key,
                          part_class=stream.PartStaff,
                          staff_clef=clef.BassClef(),
                          with_tempo=False,
                          suffix="-lh",
                          **common),
            ]
            for staff in staves:
                score.insert(0, staff)
            score.insert(
                0,
                layout.StaffGroup(staves,
                                  name=instrument.name,
                                  abbreviation=ABBREVIATIONS.get(
                                      instrument.id, ""),
                                  symbol="brace",
                                  barTogether=True))
            parts_by_instrument[instrument.id] = staves
        else:
            part = make_part(instrument,
                             notes,
                             part_key,
                             with_tempo=first,
                             **common)
            score.insert(0, part)
            parts_by_instrument[instrument.id] = [part]
        first = False
    return score, parts_by_instrument


def part_score(score, parts: list, title: str):
    """A standalone score with one instrument (its part for the player)."""
    result = stream.Score()
    result.metadata = copy.deepcopy(score.metadata)
    result.metadata.title = title
    copies = [copy.deepcopy(part) for part in parts]
    for index, part in enumerate(copies):
        if index == 0 and not part.recurse().getElementsByClass(
                m21tempo.MetronomeMark):
            source = score.recurse().getElementsByClass(
                m21tempo.MetronomeMark).first()
            if source is not None:
                measure = part.getElementsByClass(stream.Measure).first()
                target = measure if measure is not None else part
                target.insert(0, copy.deepcopy(source))
        result.insert(0, part)
    if len(copies) > 1:
        result.insert(
            0, layout.StaffGroup(copies, symbol="brace", barTogether=True))
    return result
