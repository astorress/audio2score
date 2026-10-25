from src.contract import instruments as catalog


def test_catalog_ids_are_unique_and_ranges_valid():
    ids = [item.id for item in catalog.INSTRUMENTS]
    assert len(ids) == len(set(ids))
    for item in catalog.INSTRUMENTS:
        assert 0 <= item.low < item.high <= 127
        assert item.family in catalog.FAMILIES
        assert set(item.modes) <= {catalog.ROCK, catalog.ORCHESTRA}


def test_defaults_belong_to_their_mode():
    for mode, ids in catalog.DEFAULTS.items():
        for item in ids:
            assert mode in catalog.get(item).modes


def test_rock_instruments_have_a_demucs_stem():
    for item in catalog.DEFAULTS[catalog.ROCK]:
        assert catalog.get(item).stem


def test_score_order_follows_catalog_and_dedupes():
    assert catalog.score_order(["violin", "flute", "violin", "trombone"]) == [
        "flute",
        "trombone",
        "violin",
    ]


def test_rock_scores_use_band_order():
    ids = ["drums", "bass", "vocals", "piano", "guitar"]
    assert catalog.score_order(ids,
                               catalog.ROCK) == catalog.DEFAULTS[catalog.ROCK]
    assert catalog.score_order(ids)[0] == "drums"  # orchestral: percussion


def test_midi_to_name():
    assert catalog.midi_to_name(60) == "C4"
    assert catalog.midi_to_name(40) == "E2"


def test_transposing_instruments_match_plan_table():
    assert catalog.get("clarinet").transposition == "M-2"
    assert catalog.get("trumpet").transposition == "M-2"
    assert catalog.get("horn").transposition == "P-5"
    assert catalog.get("alto_sax").transposition == "M-6"
    assert catalog.get("trombone").transposition is None
    assert catalog.get("contrabass").transposition == "P-8"
    assert catalog.get("guitar").transposition == "P-8"
