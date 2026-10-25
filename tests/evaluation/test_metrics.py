import numpy as np

from src.evaluation import metrics
from src.pipeline.notes import Note


def test_sdr_perfect_and_noisy():
    rng = np.random.default_rng(0)
    signal = rng.standard_normal(1000)
    assert metrics.sdr(signal, signal) > 100
    noisy = metrics.sdr(signal, signal + 0.1 * rng.standard_normal(1000))
    assert 15 < noisy < 25


def test_note_f1_onset_tolerance():
    reference = [Note(60, 0.0, 0.5), Note(62, 0.5, 1.0)]
    estimate = [Note(60, 0.03, 0.5), Note(62, 0.7, 1.0)]
    result = metrics.note_f1(reference, estimate)
    assert result["precision"] == 0.5 and result["recall"] == 0.5


def test_multi_instrument_f1_requires_the_right_instrument():
    reference = {
        "violin": [Note(67, 0, 1)],
        "cello": [Note(48, 0, 1)]
    }
    swapped = {
        "violin": [Note(48, 0, 1)],
        "cello": [Note(67, 0, 1)]
    }
    assert metrics.multi_instrument_f1(reference, reference)["f1"] == 1.0
    assert metrics.multi_instrument_f1(reference, swapped)["f1"] == 0.0


def test_empty_estimates():
    assert metrics.note_f1([Note(60, 0, 1)], [])["f1"] == 0.0
