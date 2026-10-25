from src.contract import instruments as catalog
from src.pipeline.notes import Note
from src.pipeline.symbolic import (
    clean_notes,
    filter_range,
    prepare,
    to_monophonic,
)


def test_clean_drops_short_and_weak_notes():
    notes = [Note(60, 0, 0.02, 90), Note(62, 0, 1, 5), Note(64, 0, 1, 90)]
    assert clean_notes(notes) == [Note(64, 0, 1, 90)]


def test_clean_merges_a_split_sustained_note():
    notes = [Note(60, 0.0, 0.9, 80), Note(60, 0.91, 1.0, 90)]
    assert clean_notes(notes) == [Note(60, 0.0, 1.0, 90)]


def test_clean_keeps_rearticulated_notes():
    # Basic Pitch output for a bass playing quarter notes (real case).
    notes = [Note(40, 0.01, 0.57, 90), Note(40, 0.58, 1.08, 92)]
    assert clean_notes(notes) == notes


def test_filter_range_folds_octave_errors_and_drops_the_rest():
    notes = [Note(35, 0, 1), Note(20, 1, 2), Note(80, 2, 3)]
    # trombone E2(40)-F5(77): 35 → 47, 80 → 68, 20 is two octaves away.
    assert [n.pitch for n in filter_range(notes, 40, 77)] == [47, 68]


def test_to_monophonic_keeps_the_louder_line():
    notes = [
        Note(60, 0.0, 1.0, 60),
        Note(67, 0.5, 1.5, 100),  # louder: cuts the first one
        Note(55, 0.6, 0.9, 30),  # quieter and inside: dropped
    ]
    line = to_monophonic(notes)
    assert line == [Note(60, 0.0, 0.5, 60), Note(67, 0.5, 1.5, 100)]


def test_simultaneous_onsets_keep_one_note():
    line = to_monophonic([Note(60, 0, 1, 80), Note(64, 0, 1, 80)])
    assert line == [Note(64, 0, 1, 80)]


def test_prepare_keeps_drums_unfiltered():
    drums = [Note(36, 0, 0.1, 100), Note(42, 0, 0.1, 80)]
    assert prepare(drums, catalog.get("drums")) == drums
