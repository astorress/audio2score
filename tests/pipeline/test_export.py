import pretty_midi

from src.contract import instruments as catalog
from src.pipeline import export
from src.pipeline.key import KeyEstimate
from src.pipeline.notes import Note
from src.pipeline.score import (
    PartSpec,
    build_score,
)


def test_quantized_midi_is_written_at_score_tempo(tmp_path):
    path = export.write_midi({
        "bass": [Note(40, 0, 1), Note(43, 2, 4)]
    },
                             tmp_path / "bass.mid",
                             tempo=60)
    midi = pretty_midi.PrettyMIDI(str(path))
    notes = midi.instruments[0].notes
    assert [(n.start, n.end) for n in notes] == [(0, 1), (2, 4)]
    assert midi.instruments[0].program == catalog.get("bass").program


def test_drum_track_is_flagged(tmp_path):
    path = export.write_midi({
        "drums": [Note(36, 0, 0.1)]
    }, tmp_path / "drums.mid")
    assert pretty_midi.PrettyMIDI(str(path)).instruments[0].is_drum


def test_parts_are_written_per_instrument(tmp_path):
    specs = [
        PartSpec(catalog.get("violin"), [Note(67, 0, 4)]),
        PartSpec(catalog.get("piano"),
                 [Note(48, 0, 4), Note(72, 0, 4)]),
    ]
    score, parts = build_score(specs,
                               KeyEstimate(7, "major", 1.0),
                               120,
                               title="t")
    paths = export.write_parts(score, parts, tmp_path)
    assert set(paths) == {"violin", "piano"}
    piano = paths["piano"].read_text()
    # Both staves in one MusicXML part (the standard grand-staff encoding).
    assert piano.count("<part id=") == 1 and "<staves>2</staves>" in piano


def test_pdf_is_optional(tmp_path, monkeypatch):
    monkeypatch.setattr(export, "musescore_binary", lambda: None)
    assert export.render_pdf(tmp_path / "x.musicxml",
                             tmp_path / "x.pdf") is None


def test_midi_track_names_are_latin1(tmp_path):
    path = export.write_midi({
        "clarinet": [Note(60, 0, 1)]
    }, tmp_path / "cl.mid")
    assert pretty_midi.PrettyMIDI(
        str(path)).instruments[0].name == "Clarinete en Sib"
