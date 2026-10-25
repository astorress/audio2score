"""The full pipeline with the neural models replaced by known notes: audio
loading, routing, cleanup, beat tracking, quantization, key, score and every
export run for real."""
import json

import pretty_midi
import pytest

from src.pipeline import run as run_module
from src.pipeline import separation, transcription
from src.pipeline.cli import main
from src.pipeline.notes import Note
from src.scripts import synth_demo


@pytest.fixture
def demo(tmp_path):
    rock_path = synth_demo.write("demo_rock", *synth_demo.rock(12), tmp_path)
    chorale_path = synth_demo.write("demo_orquesta", *synth_demo.chorale(12),
                                    tmp_path)
    return rock_path, chorale_path


def truth(path) -> dict:
    """{track name: notes} of the demo's ground-truth MIDI."""
    midi = pretty_midi.PrettyMIDI(str(path.with_suffix(".mid")))
    return {
        instrument.name: [
            Note(n.pitch, n.start, n.end, n.velocity) for n in instrument.notes
        ]
        for instrument in midi.instruments
    }


@pytest.fixture
def fake_models(monkeypatch, demo):
    rock_path, chorale_path = demo
    rock_truth = truth(rock_path)
    chorale_truth = truth(chorale_path)

    def fake_separate(mix, sr, out_dir):
        from src.pipeline import audio as audio_io

        return {
            name: audio_io.write(out_dir / f"{name}.wav", mix, sr)
            for name in ("vocals", "drums", "bass", "guitar", "piano", "other")
        }

    def fake_stem(path, instrument_id):
        return rock_truth.get(instrument_id, [])

    def fake_mix(path, instrument_ids, backend):
        return {
            item: chorale_truth.get(item, [])
            for item in instrument_ids
        }

    monkeypatch.setattr(separation, "separate", fake_separate)
    monkeypatch.setattr(transcription, "transcribe_stem", fake_stem)
    monkeypatch.setattr(transcription, "transcribe_mix", fake_mix)
    return demo


def test_rock_route_end_to_end(fake_models, tmp_path):
    rock_path, _ = fake_models
    stages = []
    manifest = run_module.run(rock_path,
                              tmp_path / "rock",
                              "rock", ["drums", "bass", "piano", "vocals"], {
                                  "exportPdf": False
                              },
                              on_stage=lambda s, _: stages.append(s))
    result = manifest["result"]
    assert stages == ["separation", "transcription", "engraving", "export"]
    assert manifest["resolvedMode"] == "rock"
    assert manifest["instruments"] == ["bass", "piano", "drums"]
    assert any("Voz" in warning for warning in manifest["warnings"])
    assert abs(result["tempo"] - 110) <= 3
    assert result["timeSignature"] == "4/4"
    assert result["key"] in ("E minor", "G major")
    assert {stem["name"]
            for stem in result["stems"]} >= {"bass", "drums"}
    out = tmp_path / "rock"
    for key in [result["midiFull"], result["score"]["musicxml"]
                ] + [item["key"] for item in result["midi"] + result["parts"]]:
        assert (out / key).exists(), key
    assert result["score"]["pdf"] is None
    assert not (out / "input.wav").exists()


def test_orchestra_route_end_to_end(fake_models, tmp_path):
    _, chorale_path = fake_models
    manifest = run_module.run(chorale_path, tmp_path / "orq", "orchestra",
                              ["flute", "clarinet", "cello", "contrabass"], {
                                  "exportPdf": False
                              })
    result = manifest["result"]
    assert result["stems"] == []
    assert manifest["instruments"] == [
        "flute", "clarinet", "cello", "contrabass"
    ]
    assert result["key"] == "C major"
    clarinet = (tmp_path / "orq" / "parts" / "clarinet.musicxml").read_text()
    assert "<transpose>" in clarinet


def test_auto_mode_and_trimming(fake_models, tmp_path):
    rock_path, _ = fake_models
    manifest = run_module.run(rock_path,
                              tmp_path / "auto",
                              "auto",
                              options={
                                  "exportPdf": False
                              },
                              max_duration=8)
    assert manifest["resolvedMode"] == "rock"
    assert manifest["route"]["probabilityRock"] >= 0.5
    assert manifest["result"]["durationSec"] == 8
    assert any("recortó" in warning for warning in manifest["warnings"])


def test_cli_writes_manifest(fake_models, tmp_path, capsys):
    rock_path, _ = fake_models
    main([
        str(rock_path), "--mode", "rock", "--no-pdf", "--out",
        str(tmp_path / "cli")
    ])
    manifest = json.loads((tmp_path / "cli" / "manifest.json").read_text())
    assert manifest["resolvedMode"] == "rock"
    assert "Resultados en" in capsys.readouterr().out
