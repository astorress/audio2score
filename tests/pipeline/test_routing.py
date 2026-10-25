from src.pipeline import routing
from src.scripts.synth_demo import (
    chorale,
    rock,
)


def test_synthetic_rock_and_chorale_take_different_routes():
    import librosa

    rock_audio, _ = rock(10)
    chorale_audio, _ = chorale(10)
    rock_decision = routing.classify(
        librosa.resample(rock_audio, orig_sr=44100, target_sr=22050), 22050)
    chorale_decision = routing.classify(
        librosa.resample(chorale_audio, orig_sr=44100, target_sr=22050), 22050)
    assert rock_decision.mode == "rock"
    assert chorale_decision.mode == "orchestra"
    assert rock_decision.probability_rock > chorale_decision.probability_rock
