import pytest
from music21 import (
    clef,
    layout,
    stream,
)

from src.contract import instruments as catalog
from src.evaluation.metrics import measure_accuracy
from src.pipeline.key import KeyEstimate
from src.pipeline.notes import Note
from src.pipeline.score import (
    PartSpec,
    build_score,
    fill_legato,
    part_score,
    segments,
    written_notes,
)

C_MAJOR = KeyEstimate(0, "major", 1.0)


def notes_of(part):
    return list(part.recurse().notes)


def test_segments_slice_overlaps_with_ties():
    notes = [Note(60, 0, 2), Note(64, 1, 3)]
    assert segments(notes) == [
        (0, 1, [(0, 60)]),
        (1, 2, [(0, 60), (1, 64)]),
        (2, 3, [(1, 64)]),
    ]


def test_fill_legato_absorbs_small_gaps_only():
    notes = [Note(60, 0, 0.75), Note(62, 1, 2), Note(64, 3, 4)]
    filled = fill_legato(notes)
    assert filled[0].end == 1  # 0.25 gap → absorbed
    assert filled[1].end == 2  # 1 beat rest kept


def test_written_pitch_of_transposing_instruments():
    clarinet = catalog.get("clarinet")
    assert written_notes([Note(58, 0, 1)], clarinet)[0].pitch == 60
    horn = catalog.get("horn")
    assert written_notes([Note(53, 0, 1)], horn)[0].pitch == 60


def test_score_has_equal_whole_measures_and_correct_key():
    specs = [
        PartSpec(
            catalog.get("flute"),
            [Note(72, 0, 1), Note(74, 1, 2.5),
             Note(76, 2.5, 5)]),
        PartSpec(catalog.get("clarinet"), [Note(70, 0, 4)]),
    ]
    score, parts = build_score(specs,
                               KeyEstimate(10, "major", 1.0),
                               96,
                               title="test")
    flute, clarinet = parts["flute"][0], parts["clarinet"][0]
    measures = [
        len(part.getElementsByClass(stream.Measure)) for part in score.parts
    ]
    assert measures == [2, 2]  # 5 quarters → 2 bars of 4/4
    assert measure_accuracy(score) == 1.0
    # Concert B♭ major; the B♭ clarinet reads in C major, a 2nd higher.
    assert flute.recurse().getElementsByClass("Key").first().sharps == -2
    assert clarinet.recurse().getElementsByClass("Key").first().sharps == 0
    assert notes_of(clarinet)[0].pitch.nameWithOctave == "C5"
    assert clarinet.atSoundingPitch is False
    # The 1.5-beat note crossing beat 2 is tied across the bar line.
    tied = [n for n in notes_of(flute) if n.tie is not None]
    assert tied


def test_drum_hits_extended_past_the_end_keep_parts_aligned():
    specs = [
        PartSpec(catalog.get("bass"), [Note(40, 0, 4)]),
        PartSpec(catalog.get("drums"), [Note(36, 3.75, 4.0)]),
    ]
    score, _ = build_score(specs, C_MAJOR, 120)
    counts = {
        len(part.getElementsByClass(stream.Measure))
        for part in score.parts
    }
    assert len(counts) == 1


def test_grand_staff_splits_at_middle_c():
    specs = [
        PartSpec(
            catalog.get("piano"),
            [Note(48, 0, 4), Note(64, 0, 4),
             Note(67, 0, 4)])
    ]
    score, parts = build_score(specs, C_MAJOR, 120)
    upper, lower = parts["piano"]
    assert isinstance(upper, stream.PartStaff)
    assert [p.midi for p in notes_of(upper)[0].pitches] == [64, 67]
    assert notes_of(lower)[0].pitch.midi == 48
    assert isinstance(lower.recurse().getElementsByClass(clef.Clef).first(),
                      clef.BassClef)
    groups = score.getElementsByClass(layout.StaffGroup)
    assert groups and groups[0].symbol == "brace"


def test_tenor_clef_for_high_trombone():
    high = [Note(67, i, i + 1) for i in range(4)]
    _, parts = build_score([PartSpec(catalog.get("trombone"), high)], C_MAJOR,
                           120)
    found = parts["trombone"][0].recurse().getElementsByClass(clef.Clef).first()
    assert isinstance(found, clef.TenorClef)


def test_drums_use_percussion_clef_and_noteheads():
    hits = [Note(36, 0, 0.25), Note(42, 0, 0.25), Note(38, 1, 1.25)]
    _, parts = build_score([PartSpec(catalog.get("drums"), hits)], C_MAJOR, 120)
    part = parts["drums"][0]
    assert isinstance(part.recurse().getElementsByClass(clef.Clef).first(),
                      clef.PercussionClef)
    first = notes_of(part)[0]
    assert {n.notehead
            for n in first.notes} == {"normal", "x"}


@pytest.mark.parametrize("triplets", [False, True])
def test_score_exports_to_musicxml(tmp_path, triplets):
    third = round(1 / 3, 6)
    notes = ([
        Note(60, 0, third),
        Note(62, third, 2 * third),
        Note(64, 2 * third, 1)
    ] if triplets else
             [Note(60, 0, 0.25),
              Note(62, 0.25, 1.75),
              Note(64, 1.75, 6)])
    score, parts = build_score([PartSpec(catalog.get("violin"), notes)],
                               C_MAJOR,
                               100,
                               title="xml")
    path = tmp_path / "score.musicxml"
    score.write("musicxml", fp=str(path))
    text = path.read_text()
    assert "<part-name>Violín</part-name>" in text
    single = part_score(score, parts["violin"], "parte")
    assert single.metadata.title == "parte"
    assert single.recurse().getElementsByClass("MetronomeMark")


def test_transposing_part_exports_transpose_element(tmp_path):
    score, _ = build_score([PartSpec(catalog.get("trumpet"), [Note(70, 0, 4)])],
                           C_MAJOR, 120)
    path = tmp_path / "trumpet.musicxml"
    score.write("musicxml", fp=str(path))
    text = path.read_text()
    assert "<transpose>" in text and "<chromatic>-2</chromatic>" in text
