"""Real models (Demucs, Basic Pitch) on the synthetic demos, scored against
their ground truth. Slow (minutes on CPU) and needs the model weights:
`npm run test:slow`."""
import pytest

from src.contract import instruments as catalog
from src.evaluation import metrics
from src.pipeline import run as run_module
from src.pipeline import symbolic, transcription
from src.scripts import synth_demo
from tests.pipeline.test_run import truth

pytestmark = pytest.mark.slow


def test_basic_pitch_transcribes_the_chorale(tmp_path):
    path = synth_demo.write("chorale", *synth_demo.chorale(12), tmp_path)
    reference = [note for notes in truth(path).values() for note in notes]
    estimate = transcription.basic_pitch(path, 28, 100)
    result = metrics.note_f1(reference, estimate)
    print("chorale onset F1", result)
    assert result["f1"] > 0.5


def test_rock_pipeline_with_real_models(tmp_path):
    path = synth_demo.write("demo_rock", *synth_demo.rock(12), tmp_path)
    manifest = run_module.run(path, tmp_path / "out", "rock",
                              ["drums", "bass", "piano"], {
                                  "exportPdf": True
                              })
    print(manifest["stages"], manifest["warnings"])
    assert len(manifest["result"]["stems"]) == 6
    assert (tmp_path / "out" / manifest["result"]["score"]["musicxml"]).exists()
    bass = transcription.transcribe_stem(
        tmp_path / "out" / "stems" / "bass.wav", "bass")
    result = metrics.note_f1(
        truth(path)["bass"], symbolic.prepare(bass, catalog.get("bass")))
    print("bass onset F1 after Demucs + cleanup", result)
    # Measured 2026-10-24: 0.93-0.98 (raw Basic Pitch: ~0.69).
    assert result["f1"] > 0.8
