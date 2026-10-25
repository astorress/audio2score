"""CLI: `python3 -m src.pipeline.cli song.wav --mode rock` → a folder with
stems, MIDI, MusicXML (full score and parts), PDF and manifest.json."""
import argparse
import json
from pathlib import Path

from src.contract import instruments as catalog
from src.contract import jobs
from src.pipeline.run import run


def parse_args(argv=None):
    parser = argparse.ArgumentParser(prog="audio2score", description=__doc__)
    parser.add_argument("audio", type=Path)
    parser.add_argument("--mode", choices=jobs.MODES, default="auto")
    parser.add_argument(
        "--instruments",
        nargs="+",
        choices=sorted(catalog.BY_ID),
        help="default: the mode's defaults (contract/instruments.py)")
    parser.add_argument("--quantization",
                        choices=list(jobs.QUANTIZATIONS),
                        default=jobs.DEFAULT_OPTIONS["quantization"])
    parser.add_argument("--triplets", action="store_true")
    parser.add_argument("--no-pdf", action="store_true")
    parser.add_argument("--max-duration",
                        type=float,
                        default=jobs.MAX_DURATION_SEC)
    parser.add_argument("--out",
                        type=Path,
                        help="default: outputs/<audio name>")
    return parser.parse_args(argv)


def main(argv=None) -> None:
    args = parse_args(argv)
    out_dir = args.out or Path("outputs") / args.audio.stem

    def on_stage(stage, stages):
        print(f"→ {stage} {json.dumps(stages)}", flush=True)

    manifest = run(args.audio,
                   out_dir,
                   args.mode,
                   args.instruments, {
                       "quantization": args.quantization,
                       "allowTriplets": args.triplets,
                       "exportPdf": not args.no_pdf,
                   },
                   max_duration=args.max_duration,
                   on_stage=on_stage)
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False))
    result = manifest["result"]
    print(f"\nRuta: {manifest['resolvedMode']} · {result['key']} · "
          f"{result['tempo']:g} BPM · {result['timeSignature']}")
    print(f"Etapas (s): {manifest['stages']}")
    for warning in manifest["warnings"]:
        print(f"! {warning}")
    print(f"Resultados en {out_dir}/")


if __name__ == "__main__":
    main()
