"""Instrument catalog: the single source of truth for names, ranges, clefs
and transpositions, shared by the Lambdas (validation, GET /instruments) and
the worker (transcription, engraving). Pure Python on purpose: the Lambdas
don't ship music21.

Pitches are MIDI numbers at *sounding* pitch. `transposition` follows
music21's `Instrument.transposition`: the interval from written to sounding
pitch ("M-2" = sounds a major second below what is written).
"""
from dataclasses import (
    asdict,
    dataclass,
)

ROCK = "rock"
ORCHESTRA = "orchestra"


@dataclass(frozen=True)
class Instrument:
    id: str
    name: str
    family: str
    modes: tuple
    program: int  # General MIDI program (0-based)
    low: int  # lowest sounding MIDI pitch
    high: int  # highest sounding MIDI pitch
    clef: str  # treble | bass | alto | tenor | percussion | grand
    music21_class: str
    transposition: str | None = None
    monophonic: bool = False
    is_drum: bool = False
    # Demucs stem that carries this instrument in the rock route.
    stem: str | None = None

    def to_api(self) -> dict:
        data = asdict(self)
        return {
            "id": data["id"],
            "name": data["name"],
            "family": data["family"],
            "modes": list(data["modes"]),
            "clef": data["clef"],
            "transposition": data["transposition"],
            "range": [midi_to_name(self.low),
                      midi_to_name(self.high)],
            "monophonic": data["monophonic"],
        }


FAMILIES = {
    "woodwinds": "Maderas",
    "brass": "Metales",
    "percussion": "Percusión",
    "keyboards": "Teclados y arpa",
    "vocals": "Voz",
    "band": "Banda",
    "strings": "Cuerdas",
}

# Catalog order = score order (orchestral convention: woodwinds, brass,
# percussion, keyboards, voices, strings).
INSTRUMENTS = (
    Instrument("flute",
               "Flauta",
               "woodwinds", (ORCHESTRA, ),
               73,
               60,
               96,
               "treble",
               "Flute",
               monophonic=True),
    Instrument("oboe",
               "Oboe",
               "woodwinds", (ORCHESTRA, ),
               68,
               58,
               93,
               "treble",
               "Oboe",
               monophonic=True),
    Instrument("clarinet",
               "Clarinete en Si♭",
               "woodwinds", (ORCHESTRA, ),
               71,
               50,
               94,
               "treble",
               "Clarinet",
               "M-2",
               monophonic=True),
    Instrument("alto_sax",
               "Saxo alto en Mi♭",
               "woodwinds", (ORCHESTRA, ),
               65,
               49,
               80,
               "treble",
               "AltoSaxophone",
               "M-6",
               monophonic=True),
    Instrument("bassoon",
               "Fagot",
               "woodwinds", (ORCHESTRA, ),
               70,
               34,
               76,
               "bass",
               "Bassoon",
               monophonic=True),
    Instrument("horn",
               "Corno en Fa",
               "brass", (ORCHESTRA, ),
               60,
               35,
               77,
               "treble",
               "Horn",
               "P-5",
               monophonic=True),
    Instrument("trumpet",
               "Trompeta en Si♭",
               "brass", (ORCHESTRA, ),
               56,
               52,
               84,
               "treble",
               "Trumpet",
               "M-2",
               monophonic=True),
    Instrument("trombone",
               "Trombón",
               "brass", (ORCHESTRA, ),
               57,
               40,
               77,
               "bass",
               "Trombone",
               monophonic=True),
    Instrument("tuba",
               "Tuba",
               "brass", (ORCHESTRA, ),
               58,
               26,
               65,
               "bass",
               "Tuba",
               monophonic=True),
    Instrument("timpani", "Timbales", "percussion", (ORCHESTRA, ), 47, 38, 60,
               "bass", "Timpani"),
    Instrument("drums",
               "Batería",
               "percussion", (ROCK, ),
               0,
               35,
               81,
               "percussion",
               "UnpitchedPercussion",
               is_drum=True,
               stem="drums"),
    Instrument("harp", "Arpa", "keyboards", (ORCHESTRA, ), 46, 23, 104, "grand",
               "Harp"),
    Instrument("piano",
               "Piano",
               "keyboards", (ROCK, ORCHESTRA),
               0,
               21,
               108,
               "grand",
               "Piano",
               stem="piano"),
    Instrument("vocals",
               "Voz",
               "vocals", (ROCK, ),
               53,
               40,
               84,
               "treble",
               "Vocalist",
               monophonic=True,
               stem="vocals"),
    Instrument("guitar",
               "Guitarra",
               "band", (ROCK, ),
               27,
               40,
               88,
               "treble",
               "ElectricGuitar",
               "P-8",
               stem="guitar"),
    Instrument("bass",
               "Bajo eléctrico",
               "band", (ROCK, ),
               33,
               28,
               67,
               "bass",
               "ElectricBass",
               "P-8",
               monophonic=True,
               stem="bass"),
    Instrument("violin", "Violín", "strings", (ORCHESTRA, ), 40, 55, 105,
               "treble", "Violin"),
    Instrument("viola", "Viola", "strings", (ORCHESTRA, ), 41, 48, 88, "alto",
               "Viola"),
    Instrument("cello", "Violonchelo", "strings", (ORCHESTRA, ), 42, 36, 84,
               "bass", "Violoncello"),
    Instrument("contrabass", "Contrabajo", "strings", (ORCHESTRA, ), 43, 28, 67,
               "bass", "Contrabass", "P-8"),
)

BY_ID = {
    instrument.id: instrument
    for instrument in INSTRUMENTS
}

DEFAULTS = {
    ROCK: ["vocals", "guitar", "bass", "piano", "drums"],
    ORCHESTRA: [
        "flute",
        "oboe",
        "clarinet",
        "bassoon",
        "horn",
        "trumpet",
        "trombone",
        "tuba",
        "violin",
        "viola",
        "cello",
        "contrabass",
    ],
}

# Demucs htdemucs_6s stems that are listened to but not transcribed.
UNTRANSCRIBED_STEMS = ("other", )
STEM_LABELS = {
    "vocals": "Voz",
    "drums": "Batería",
    "bass": "Bajo",
    "guitar": "Guitarra",
    "piano": "Piano",
    "other": "Otros",
}

NOTE_NAMES = ("C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B")


def midi_to_name(pitch: int) -> str:
    return f"{NOTE_NAMES[pitch % 12]}{pitch // 12 - 1}"


def get(instrument_id: str) -> Instrument:
    return BY_ID[instrument_id]


def score_order(instrument_ids, route: str | None = None) -> list:
    """Sorts instrument ids in score order, removing duplicates: orchestral
    order (the catalog's), or the band order of DEFAULTS[ROCK] (voice,
    guitar, bass, piano, drums) for the rock route."""
    wanted = set(instrument_ids)
    order = [item.id for item in INSTRUMENTS]
    if route == ROCK:
        order = DEFAULTS[ROCK] + [
            item for item in order if item not in DEFAULTS[ROCK]
        ]
    return [item for item in order if item in wanted]
