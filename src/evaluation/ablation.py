"""Phase 3 ablation: does separating before transcribing help?

For every track and its ground truth instruments:
    separated  mix → Demucs → stem → transcription (rock route)
    mix        mix → Basic Pitch + range assignment (orchestra route)
Both are scored with onset F1 per instrument and multi-instrument F1.
"""
import tempfile
from pathlib import Path

from src.contract import instruments as catalog
from src.evaluation import metrics
from src.pipeline import audio as audio_io
from src.pipeline import (
    separation,
    symbolic,
    transcription,
)


def evaluated_instruments(track, route: str) -> list:
    return [
        item for item in catalog.score_order(track.notes)
        if route in catalog.get(item).modes
    ]


def separated(track, instrument_ids, work_dir: Path) -> dict:
    mix, sr = audio_io.load(track.mix, max_duration=None)
    stems = separation.separate(mix, sr, work_dir / "stems")
    return {
        item: transcription.transcribe_stem(stems[catalog.get(item).stem], item)
        for item in instrument_ids
        if catalog.get(item).stem in stems
    }


def from_mix(track, instrument_ids) -> dict:
    return transcription.transcribe_mix(track.mix, instrument_ids,
                                        "basic-pitch-assign")


def score_estimate(track, estimate: dict) -> dict:
    estimate = {
        item: symbolic.prepare(notes, catalog.get(item))
        for item, notes in estimate.items()
    }
    reference = {
        item: track.notes[item]
        for item in estimate
    }
    row = {
        f"f1_{item}": metrics.note_f1(reference[item], notes)["f1"]
        for item, notes in estimate.items()
    }
    row["multi_f1"] = metrics.multi_instrument_f1(reference, estimate)["f1"]
    return row


def evaluate_track(track, strategies=("separated", "mix")) -> list:
    rows = []
    route = (catalog.ROCK if evaluated_instruments(track, catalog.ROCK) else
             catalog.ORCHESTRA)
    instrument_ids = evaluated_instruments(track, route)
    for strategy in strategies:
        if strategy == "separated" and route != catalog.ROCK:
            continue  # Demucs has no orchestral stems
        with tempfile.TemporaryDirectory() as tmp:
            estimate = (separated(track, instrument_ids, Path(tmp)) if strategy
                        == "separated" else from_mix(track, instrument_ids))
        rows.append({
            "track": track.name,
            "strategy": strategy,
            **score_estimate(track, estimate)
        })
    return rows


def markdown_table(rows: list) -> str:
    columns = ["track", "strategy"
               ] + sorted({key
                           for row in rows
                           for key in row} - {"track", "strategy"})
    lines = [
        "| " + " | ".join(columns) + " |",
        "|" + "|".join("---" for _ in columns) + "|",
    ]
    for row in rows:
        lines.append("| " + " | ".join(f"{row[column]:.3f}" if isinstance(
            row.get(column), float) else str(row.get(column, "—"))
                                       for column in columns) + " |")
    return "\n".join(lines)
