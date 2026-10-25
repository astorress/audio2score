"""Evaluation datasets (docs/PLAN.md §8 Phase 3). Download them to data/
(they're not redistributed here):

- Slakh2100 (synthetic multitrack rock/pop): data/slakh2100/<split>/TrackXXXXX/
  with metadata.yaml, mix.flac, stems/Sxx.flac and MIDI/Sxx.mid.
- URMP (real chamber ensembles): data/urmp/NN_Piece_inst1_inst2/ with
  AuMix_*.wav, AuSep_k_inst_*.wav and Notes_k_inst_*.txt
  (onset, frequency, duration per line).
- TRIOS (real chamber trios, CC BY-NC-SA): data/real/trios/<piece>/ with
  mix.wav, <instrument>.wav (real recording) + <instrument>.mid (aligned
  score) and <instrument>_syn.wav (synthesized, unused).
- MUSDB18 7-s preview (real rock/pop, CC BY 4.0 excerpts): decoded by
  `src/scripts/real_audio.py` to data/real/musdb7/<split>/<song>/ with
  mixture.wav and the true stems drums/bass/other/vocals.wav (no notes).
"""
from dataclasses import (
    dataclass,
    field,
)
from pathlib import Path

import numpy as np

from src.pipeline.notes import (
    Note,
    from_pretty_midi,
)

# Slakh "inst_class" → catalog instrument (others aren't evaluated).
SLAKH_CLASSES = {
    "Guitar": "guitar",
    "Bass": "bass",
    "Piano": "piano",
    "Drums": "drums",
}
URMP_INSTRUMENTS = {
    "vn": "violin",
    "va": "viola",
    "vc": "cello",
    "db": "contrabass",
    "fl": "flute",
    "ob": "oboe",
    "cl": "clarinet",
    "bn": "bassoon",
    "sax": "alto_sax",
    "hn": "horn",
    "tpt": "trumpet",
    "tbn": "trombone",
    "tba": "tuba",
}
# TRIOS file stem → catalog instrument; drum tracks → GM drum pitch.
TRIOS_INSTRUMENTS = {
    "violin": "violin",
    "viola": "viola",
    "cello": "cello",
    "clarinet": "clarinet",
    "bassoon": "bassoon",
    "horn": "horn",
    "trumpet": "trumpet",
    "saxophone": "alto_sax",
    "piano": "piano",
}
TRIOS_DRUMS = {
    "kick": 36,
    "snare": 38,
    "ride": 51,
}
MUSDB_STEMS = ("drums", "bass", "other", "vocals")


@dataclass
class Track:
    name: str
    mix: Path
    notes: dict  # {instrument id: [Note]} ground truth
    stems: dict = field(default_factory=dict)  # {instrument id: [Path]}


def slakh_track(folder: Path) -> Track:
    import pretty_midi
    import yaml

    metadata = yaml.safe_load((folder / "metadata.yaml").read_text())
    notes, stems = {}, {}
    for stem_id, stem in metadata.get("stems", {}).items():
        instrument = SLAKH_CLASSES.get(stem.get("inst_class"))
        midi_path = folder / "MIDI" / f"{stem_id}.mid"
        if not instrument or not midi_path.exists():
            continue
        notes.setdefault(instrument, []).extend(
            from_pretty_midi(pretty_midi.PrettyMIDI(str(midi_path))))
        audio = folder / "stems" / f"{stem_id}.flac"
        if audio.exists():
            stems.setdefault(instrument, []).append(audio)
    return Track(folder.name, folder / "mix.flac", notes, stems)


def urmp_notes(path: Path) -> list:
    rows = np.loadtxt(path, ndmin=2)
    return [
        Note(int(round(69 + 12 * np.log2(freq / 440.0))), float(onset),
             float(onset + length), 80) for onset, freq, length in rows
    ]


def urmp_track(folder: Path) -> Track:
    notes, stems = {}, {}
    for path in sorted(folder.glob("Notes_*_*.txt")):
        instrument = URMP_INSTRUMENTS.get(path.stem.split("_")[2])
        if instrument:
            notes.setdefault(instrument, []).extend(urmp_notes(path))
    for path in sorted(folder.glob("AuSep_*_*.wav")):
        instrument = URMP_INSTRUMENTS.get(path.stem.split("_")[2])
        if instrument:
            stems.setdefault(instrument, []).append(path)
    return Track(folder.name, next(folder.glob("AuMix_*.wav")), notes, stems)


def trios_track(folder: Path) -> Track:
    import pretty_midi

    notes, stems = {}, {}
    for midi_path in sorted(folder.glob("*.mid")):
        name = midi_path.stem
        found = from_pretty_midi(pretty_midi.PrettyMIDI(str(midi_path)))
        if name in TRIOS_DRUMS:
            instrument = "drums"
            found = [
                Note(TRIOS_DRUMS[name], n.start, n.end, n.velocity)
                for n in found
            ]
        elif name in TRIOS_INSTRUMENTS:
            instrument = TRIOS_INSTRUMENTS[name]
        else:
            continue
        notes.setdefault(instrument, []).extend(found)
        audio = folder / f"{name}.wav"
        if audio.exists():
            stems.setdefault(instrument, []).append(audio)
    notes = {
        name: sorted(found, key=lambda n: (n.start, n.pitch))
        for name, found in notes.items()
    }
    return Track(folder.name, folder / "mix.wav", notes, stems)


def musdb_track(folder: Path) -> Track:
    stems = {
        name: [folder / f"{name}.wav"]
        for name in MUSDB_STEMS
        if (folder / f"{name}.wav").exists()
    }
    return Track(folder.name, folder / "mixture.wav", {}, stems)


def tracks(dataset: str, root: Path, limit: int | None = None) -> list:
    if dataset == "slakh":
        folders = sorted(path.parent for path in root.glob("*/metadata.yaml"))
        loader = slakh_track
    elif dataset == "urmp":
        folders = sorted(path for path in root.iterdir()
                         if path.is_dir() and any(path.glob("AuMix_*.wav")))
        loader = urmp_track
    elif dataset == "trios":
        folders = sorted(path.parent for path in root.glob("*/mix.wav"))
        loader = trios_track
    elif dataset == "musdb":
        folders = sorted(path.parent for path in root.glob("*/mixture.wav"))
        loader = musdb_track
    else:
        raise ValueError(f"Unknown dataset {dataset}")
    return [loader(folder) for folder in folders[:limit]]
