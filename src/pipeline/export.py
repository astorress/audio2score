"""Exports (docs/PLAN.md §4.1 step 8, §4.3): MusicXML (full score and one
file per part), MIDI (quantized at the score's tempo, so it plays in sync
with the score cursor, plus the raw transcription aligned with the audio)
and PDF through the MuseScore CLI when it's installed."""
import os
import shutil
import subprocess
from pathlib import Path

from src.contract import instruments as catalog
from src.pipeline import rhythm
from src.pipeline.notes import (
    Note,
    to_pretty_midi,
)
from src.pipeline.score import part_score

MUSESCORE_BINARIES = ("mscore", "mscore4", "musescore4", "musescore", "mscore3",
                      "musescore3")
PDF_TIMEOUT = 180


def write_musicxml(score, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    score.write("musicxml", fp=str(path))
    return path


def write_parts(score, parts_by_instrument: dict, out_dir: Path) -> dict:
    """{instrument id: path} with one MusicXML per instrument."""
    paths = {}
    for instrument_id, parts in parts_by_instrument.items():
        title = f"{score.metadata.title} — {catalog.get(instrument_id).name}"
        paths[instrument_id] = write_musicxml(
            part_score(score, parts, title),
            out_dir / f"{instrument_id}.musicxml")
    return paths


def seconds_track(notes, tempo: float) -> list:
    """Quantized notes (quarter notes) → seconds at the score tempo."""
    return [
        Note(note.pitch, rhythm.quarters_to_seconds(note.start, tempo),
             rhythm.quarters_to_seconds(note.end, tempo), note.velocity)
        for note in notes
    ]


def midi_track_name(name: str) -> str:
    """MIDI meta text is latin-1: "Clarinete en Si♭" → "Clarinete en Sib"."""
    name = name.replace("♭", "b").replace("♯", "#")
    return name.encode("latin-1", "ignore").decode("latin-1")


def write_midi(tracks: dict, path: Path, tempo: float | None = None) -> Path:
    """{instrument id: notes} → MIDI file. With `tempo`, notes are in quarter
    notes and are written at that tempo; without it, in seconds."""
    path.parent.mkdir(parents=True, exist_ok=True)
    midi_tracks = {}
    for instrument_id, notes in tracks.items():
        instrument = catalog.get(instrument_id)
        if tempo:
            notes = seconds_track(notes, tempo)
        midi_tracks[midi_track_name(instrument.name)] = (notes,
                                                         instrument.program,
                                                         instrument.is_drum)
    to_pretty_midi(midi_tracks, tempo or 120.0).write(str(path))
    return path


def musescore_binary() -> str | None:
    configured = os.environ.get("A2S_MUSESCORE")
    if configured:
        return configured
    return next(
        (found for name in MUSESCORE_BINARIES if (found := shutil.which(name))),
        None)


def render_pdf(musicxml: Path, pdf: Path) -> Path | None:
    """MusicXML → PDF with MuseScore; None when it isn't available or
    fails (the PDF is optional)."""
    binary = musescore_binary()
    if not binary:
        return None
    env = {
        **os.environ, "QT_QPA_PLATFORM": "offscreen"
    }
    try:
        subprocess.run(
            [binary, "-o", str(pdf), str(musicxml)],
            check=True,
            capture_output=True,
            timeout=PDF_TIMEOUT,
            env=env)
    except (subprocess.SubprocessError, OSError):
        return None
    return pdf if pdf.exists() and pdf.stat().st_size > 0 else None
