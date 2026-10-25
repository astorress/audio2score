"""Real recordings for the notebooks and the evaluation, downloaded from
Zenodo into data/real/ (never committed, see .gitignore):

    python3 -m src.scripts.real_audio

- MUSDB18 7-s preview (zenodo.org/records/3270814, CC BY 4.0): 144 real
  rock/pop excerpts with their true stems. The .stem.mp4 files are decoded
  with ffmpeg to data/real/musdb7/<split>/<song>/{mixture,drums,bass,other,
  vocals}.wav.
- TRIOS (zenodo.org/records/6797837, CC BY-NC-SA 2.0 UK): five chamber trios
  recorded track by track, with aligned MIDI scores, in
  data/real/trios/<piece>/.
"""
import argparse
import hashlib
import shutil
import subprocess
import urllib.request
import zipfile
from pathlib import Path

ROOT = Path("data/real")
MUSDB_URL = ("https://zenodo.org/api/records/3270814/files/"
             "MUSDB18-7-STEMS.zip/content")
TRIOS_URL = ("https://zenodo.org/api/records/6797837/files/"
             "TRIOS%20Dataset.zip/content")
TRIOS_MD5 = "0922b785187d655bd6f2d83265af2098"
# Stream order inside a NI .stem.mp4 file (MUSDB18).
STEM_STREAMS = ("mixture", "drums", "bass", "other", "vocals")


def download(url: str, path: Path, md5: str | None = None) -> Path:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        print(f"Descargando {path.name}...")
        with urllib.request.urlopen(url) as response, open(path, "wb") as out:
            shutil.copyfileobj(response, out)
    if md5 and hashlib.md5(path.read_bytes()).hexdigest() != md5:
        raise RuntimeError(f"{path} está corrupto: bórralo y vuelve a correr")
    return path


def decode_stems(stem_file: Path, out_dir: Path) -> None:
    """One WAV per stream of a .stem.mp4 (mixture + 4 stems)."""
    out_dir.mkdir(parents=True, exist_ok=True)
    for index, name in enumerate(STEM_STREAMS):
        target = out_dir / f"{name}.wav"
        if target.exists():
            continue
        subprocess.run([
            "ffmpeg", "-loglevel", "error", "-y", "-i",
            str(stem_file), "-map", f"0:{index}", "-ar", "44100",
            str(target)
        ],
                       check=True)


def musdb(root: Path) -> None:
    archive = download(MUSDB_URL, root / "downloads" / "musdb7.zip")
    raw = root / "musdb7-stems"
    if not raw.exists():
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(raw)
    for stem_file in sorted(raw.glob("*/*.stem.mp4")):
        song = stem_file.name.removesuffix(".stem.mp4")
        decode_stems(stem_file, root / "musdb7" / stem_file.parent.name / song)
    print(f"MUSDB18 7 s → {root / 'musdb7'}")


def trios(root: Path) -> None:
    archive = download(TRIOS_URL, root / "downloads" / "trios.zip", TRIOS_MD5)
    target = root / "trios"
    if not target.exists():
        extracted = root / "trios-raw"
        with zipfile.ZipFile(archive) as bundle:
            bundle.extractall(extracted)
        (extracted / "TRIOS Dataset").rename(target)
        shutil.rmtree(extracted)
    print(f"TRIOS → {target}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--only", choices=("musdb", "trios"))
    args = parser.parse_args()
    if args.only in (None, "trios"):
        trios(args.root)
    if args.only in (None, "musdb"):
        musdb(args.root)


if __name__ == "__main__":
    main()
