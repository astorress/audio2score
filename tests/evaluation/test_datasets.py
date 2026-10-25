from src.evaluation import (
    ablation,
    datasets,
)


def test_urmp_loader(tmp_path):
    folder = tmp_path / "01_Jupiter_vn_tbn"
    folder.mkdir()
    (folder / "AuMix_01_Jupiter_vn_tbn.wav").write_bytes(b"")
    (folder / "Notes_1_vn_01_Jupiter.txt"
     ).write_text("0.50\t440.0\t0.25\n1.00\t493.88\t0.50\n")
    (folder / "Notes_2_tbn_01_Jupiter.txt").write_text("0.50\t116.54\t1.0\n")
    track = datasets.tracks("urmp", tmp_path)[0]
    assert [n.pitch for n in track.notes["violin"]] == [69, 71]
    assert track.notes["trombone"][0].pitch == 46
    assert ablation.evaluated_instruments(
        track, "orchestra") == ["trombone", "violin"]


def test_trios_loader(tmp_path):
    import pretty_midi

    from src.pipeline.notes import (
        Note,
        to_pretty_midi,
    )

    folder = tmp_path / "take_five"
    folder.mkdir()
    (folder / "mix.wav").write_bytes(b"")
    (folder / "saxophone.wav").write_bytes(b"")
    to_pretty_midi({
        "sax": ([Note(65, 0.5, 1.0)], 65, False)
    }).write(str(folder / "saxophone.mid"))
    to_pretty_midi({
        "kick": ([Note(60, 0.0, 0.1)], 0, False)
    }).write(str(folder / "kick.mid"))
    pretty_midi.PrettyMIDI().write(str(folder / "unknown.mid"))
    track = datasets.tracks("trios", tmp_path)[0]
    assert track.name == "take_five"
    assert [n.pitch for n in track.notes["alto_sax"]] == [65]
    assert [n.pitch for n in track.notes["drums"]] == [36]
    assert track.stems == {
        "alto_sax": [folder / "saxophone.wav"]
    }


def test_musdb_loader(tmp_path):
    folder = tmp_path / "Song"
    folder.mkdir()
    for name in ("mixture", "bass", "drums"):
        (folder / f"{name}.wav").write_bytes(b"")
    track = datasets.tracks("musdb", tmp_path)[0]
    assert track.mix == folder / "mixture.wav"
    assert set(track.stems) == {"bass", "drums"}
    assert track.notes == {}


def test_markdown_table():
    table = ablation.markdown_table([{
        "track": "t1",
        "strategy": "mix",
        "multi_f1": 0.5
    }])
    assert "| t1 | mix | 0.500 |" in table
