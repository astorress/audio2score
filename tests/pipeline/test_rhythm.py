import numpy as np

from src.pipeline.notes import Note
from src.pipeline.rhythm import (
    Grid,
    candidate_subdivisions,
    choose_subdivisions,
    estimate_meter,
    measure_origin,
    quantize,
    quantize_tracks,
    regular_grid,
    track_beats,
)


def test_to_beats_interpolates_and_extrapolates():
    grid = Grid(np.array([1.0, 1.5, 2.0, 3.0]), 120.0)
    assert np.allclose(grid.to_beats([1.25, 2.5, 0.5, 4.0]),
                       [0.5, 2.5, -1.0, 4.0])


def test_quantize_humanized_quarters(melody, grid120):
    quantized = quantize(melody, grid120, origin=0)
    assert [n.start for n in quantized] == list(range(8))
    assert all(n.end - n.start == 1.0 for n in quantized)


def test_sixteenths_survive_and_eighths_stay_simple(grid120):
    # Beat 0: two 8ths (jittered); beat 1: four 16ths.
    notes = [Note(60, 0.01, 0.2), Note(62, 0.26, 0.45)]
    notes += [
        Note(64, 0.5 + 0.125 * k + 0.005, 0.5 + 0.125 * (k + 1))
        for k in range(4)
    ]
    quantized = quantize(notes, grid120, origin=0, subdivisions=4)
    assert [n.start for n in quantized] == [0, 0.5, 1, 1.25, 1.5, 1.75]


def test_triplets_only_when_allowed(grid120):
    third = 0.5 / 3
    notes = [Note(60, k * third, (k + 1) * third) for k in range(3)]
    plain = quantize(notes, grid120, 0, subdivisions=4, allow_triplets=False)
    triplets = quantize(notes, grid120, 0, subdivisions=4, allow_triplets=True)
    assert [n.start for n in triplets] == [0, round(1 / 3, 6), round(2 / 3, 6)]
    assert all((n.start * 4) % 1 == 0 for n in plain)


def test_viterbi_prefers_simple_subdivision_on_empty_or_on_beat():
    chosen = choose_subdivisions(np.array([0.0, 1.0, 2.0]), 3,
                                 candidate_subdivisions(4, True))
    assert list(chosen) == [1, 1, 1]


def test_estimate_meter():
    strong_every_three = np.tile([1.0, 0.2, 0.2], 8)
    strong_every_four = np.tile([0.2, 1.0, 0.3, 0.3], 8)
    assert estimate_meter(strong_every_three) == (3, 0)
    assert estimate_meter(strong_every_four) == (4, 1)


def test_measure_origin_with_pickup():
    grid = Grid(np.arange(20) * 0.5, 120.0, 4, downbeat_index=5)
    assert measure_origin(grid, 2.0) == 1
    assert measure_origin(grid, 9.2) == 9


def test_quantize_tracks_share_origin(grid120):
    tracks = {
        "a": [Note(60, 1.0, 1.5)],
        "b": [Note(48, 2.0, 3.0)]
    }
    quantized, origin = quantize_tracks(tracks, grid120)
    assert origin == 0
    assert quantized["a"][0].start == 2.0 and quantized["b"][0].start == 4.0


def test_track_beats_on_click_track():
    sr = 22050
    y = np.zeros(sr * 8, dtype=np.float32)
    for beat in range(16):  # 120 BPM
        start = int(beat * 0.5 * sr)
        y[start:start + 200] = np.hanning(200)
    grid = track_beats(y, sr)
    assert abs(grid.tempo - 120) < 6


def test_normalize_tempo_folds_half_and_double_time():
    from src.pipeline.rhythm import normalize_tempo

    slow = normalize_tempo(np.arange(10) * 1.6)  # 37.5 BPM → 75
    assert abs(60 / np.median(np.diff(slow)) - 75) < 1e-6
    fast = normalize_tempo(np.arange(40) * 0.25)  # 240 BPM → 120
    assert abs(60 / np.median(np.diff(fast)) - 120) < 1e-6
    normal = np.arange(10) * 0.5
    assert np.array_equal(normalize_tempo(normal), normal)


def test_chorale_tempo_is_not_halved():
    import librosa

    from src.scripts.synth_demo import chorale

    audio, _ = chorale(16)  # 72 BPM, chord changes every half note
    grid = track_beats(librosa.resample(audio, orig_sr=44100, target_sr=22050),
                       22050)
    assert 60 <= grid.tempo <= 90


def test_regular_grid_fallback():
    grid = regular_grid(4.0, 60.0)
    assert grid.tempo == 60.0 and grid.beats[1] == 1.0
