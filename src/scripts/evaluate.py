"""Runs the Phase 3 ablation on a dataset and writes the results table:

    python3 -m src.scripts.evaluate --dataset slakh \
        --root data/slakh2100/test --limit 20
    python3 -m src.scripts.evaluate --dataset urmp --root data/urmp
    python3 -m src.scripts.evaluate --dataset trios --root data/real/trios

Results: outputs/evaluation/<dataset>.csv and a markdown table to paste in
docs/resultados.md.
"""
import argparse
import csv
from pathlib import Path

from src.evaluation import (
    ablation,
    datasets,
)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset",
                        choices=["slakh", "urmp", "trios"],
                        required=True)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--out", type=Path, default=Path("outputs/evaluation"))
    args = parser.parse_args()

    rows = []
    for track in datasets.tracks(args.dataset, args.root, args.limit):
        print(f"→ {track.name}", flush=True)
        rows.extend(ablation.evaluate_track(track))
    args.out.mkdir(parents=True, exist_ok=True)
    columns = sorted({key
                      for row in rows
                      for key in row})
    with open(args.out / f"{args.dataset}.csv",
              "w",
              newline="",
              encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    table = ablation.markdown_table(rows)
    (args.out / f"{args.dataset}.md").write_text(table + "\n")
    print(table)


if __name__ == "__main__":
    main()
