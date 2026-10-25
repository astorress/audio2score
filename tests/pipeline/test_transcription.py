import pytest

from src.pipeline import transcription
from src.pipeline.notes import Note


def test_assign_notes_by_range_and_tessitura():
    notes = [Note(36, 0, 1), Note(52, 0, 1), Note(76, 0, 1)]
    assigned = transcription.assign_notes(notes,
                                          ["flute", "cello", "contrabass"])
    assert [n.pitch for n in assigned["contrabass"]] == [36]
    assert [n.pitch for n in assigned["cello"]] == [52]
    assert [n.pitch for n in assigned["flute"]] == [76]


def test_monophonic_instrument_gets_a_penalty_when_busy():
    notes = [Note(72, 0, 2), Note(74, 0.5, 1)]
    assigned = transcription.assign_notes(notes, ["flute", "violin"])
    assert len(assigned["flute"]) == 1 and len(assigned["violin"]) == 1


def test_out_of_range_notes_are_not_assigned():
    assigned = transcription.assign_notes([Note(20, 0, 1)], ["flute"])
    assert assigned == {
        "flute": []
    }


@pytest.mark.parametrize("backend", ["muscriptor", "yourmt3", "nope"])
def test_unverified_backends_fail_clearly(backend, tmp_path):
    with pytest.raises(transcription.BackendUnavailable):
        transcription.transcribe_mix(tmp_path / "x.wav", ["violin"], backend)


def test_midi_to_hz():
    assert transcription.midi_to_hz(69) == 440.0


def test_basic_pitch_clamps_to_the_model_range(monkeypatch, tmp_path):
    import sys
    import types

    calls = {}

    def predict(path, model, **kwargs):
        calls.update(kwargs)
        import pretty_midi
        return None, pretty_midi.PrettyMIDI(), None

    inference = types.ModuleType("basic_pitch.inference")
    inference.predict = predict
    monkeypatch.setitem(sys.modules, "basic_pitch.inference", inference)
    monkeypatch.setattr(transcription, "basic_pitch_model", lambda: None)
    transcription.basic_pitch(tmp_path / "a.wav", 9, 120)
    assert calls["minimum_frequency"] == pytest.approx(
        transcription.midi_to_hz(20.5))
    assert calls["maximum_frequency"] == pytest.approx(
        transcription.midi_to_hz(108.5))
