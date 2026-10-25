"""End-to-end pipeline: audio → stems → notes → score → files.

    ROCK       mix → Demucs → stem per instrument → Basic Pitch / drums
    ORCHESTRA  mix → multi-instrument transcription (no separation)
    both       → cleanup → beat grid → quantization → key → music21 → export

`run` returns the job result manifest (docs/api.md, with file keys relative
to `out_dir` instead of URLs) and reports progress through `on_stage`.
"""
import time
from contextlib import contextmanager
from pathlib import Path

from src.contract import instruments as catalog
from src.contract import jobs
from src.pipeline import audio as audio_io
from src.pipeline import export
from src.pipeline import key as key_module
from src.pipeline import rhythm, routing
from src.pipeline import score as score_module
from src.pipeline import (
    separation,
    symbolic,
    transcription,
)

ANALYSIS_RATE = 22050
APPROXIMATE_WARNING = ("Partitura aproximada: es una transcripción automática"
                       " y puede tener notas falsas o ritmos simplificados.")


class Stopwatch:
    """Accumulates seconds per stage and notifies when a stage starts."""

    def __init__(self, on_stage=None):
        self.stages = {}
        self.on_stage = on_stage

    @contextmanager
    def stage(self, name: str):
        if self.on_stage:
            self.on_stage(name, dict(self.stages))
        started = time.monotonic()
        try:
            yield
        finally:
            self.stages[name] = round(
                self.stages.get(name, 0.0) + time.monotonic() - started, 2)


def relative(path: Path, root: Path) -> str:
    return path.relative_to(root).as_posix()


def resolve_route(mode: str, mix, sr: int, warnings: list) -> tuple:
    if mode != "auto":
        return mode, None
    import librosa

    decision = routing.classify(
        librosa.resample(audio_io.to_mono(mix),
                         orig_sr=sr,
                         target_sr=ANALYSIS_RATE), ANALYSIS_RATE)
    label = jobs.MODE_LABELS[decision.mode].lower()
    warnings.append(f"Modo automático: se eligió la ruta «{label}» "
                    f"(p(rock) = {decision.probability_rock:.2f}).")
    return decision.mode, decision


def transcribe_rock(mix, sr, instrument_ids, work_dir: Path, watch,
                    warnings) -> tuple:
    with watch.stage("separation"):
        stems = separation.separate(mix, sr, work_dir / "stems")
    tracks = {}
    with watch.stage("transcription"):
        for instrument_id in instrument_ids:
            stem = catalog.get(instrument_id).stem
            if stem not in stems:
                warnings.append(
                    f"No hay stem para {catalog.get(instrument_id).name}.")
                continue
            tracks[instrument_id] = transcription.transcribe_stem(
                stems[stem], instrument_id)
    return tracks, stems


def transcribe_orchestra(input_path: Path, instrument_ids, watch,
                         warnings) -> dict:
    with watch.stage("transcription"):
        backend = transcription.MULTI_BACKEND
        if backend == "basic-pitch-assign":
            warnings.append(
                "Ruta orquestal con el modelo base (Basic Pitch + asignación"
                " por registro): los instrumentos se asignan por rango, no "
                "por timbre.")
        return transcription.transcribe_mix(input_path, instrument_ids, backend)


def engrave(tracks: dict, mix, sr, options: dict, title: str, route: str, watch,
            warnings) -> dict:
    import librosa

    with watch.stage("engraving"):
        cleaned = {
            instrument_id: symbolic.prepare(notes, catalog.get(instrument_id))
            for instrument_id, notes in tracks.items()
        }
        empty = [item for item, notes in cleaned.items() if not notes]
        for instrument_id in empty:
            warnings.append(
                f"{catalog.get(instrument_id).name}: no se detectaron notas.")
        cleaned = {
            item: notes
            for item, notes in cleaned.items()
            if notes
        }
        grid = rhythm.track_beats(
            librosa.resample(audio_io.to_mono(mix),
                             orig_sr=sr,
                             target_sr=ANALYSIS_RATE), ANALYSIS_RATE)
        pitched = [
            note for item, notes in cleaned.items()
            if not catalog.get(item).is_drum for note in notes
        ]
        estimated_key = key_module.estimate_key(pitched)
        quantized, _ = rhythm.quantize_tracks(
            cleaned, grid, jobs.QUANTIZATIONS[options["quantization"]],
            options["allowTriplets"])
        quantized = {
            item: (symbolic.to_monophonic(notes)
                   if catalog.get(item).monophonic else notes)
            for item, notes in quantized.items()
        }
        tempo = float(round(grid.tempo))
        specs = [
            score_module.PartSpec(catalog.get(item), quantized[item])
            for item in catalog.score_order(quantized, route)
        ]
        score, parts = score_module.build_score(specs, estimated_key, tempo,
                                                grid.beats_per_measure, title)
    return {
        "score": score,
        "parts": parts,
        "quantized": quantized,
        "cleaned": cleaned,
        "tempo": tempo,
        "grid": grid,
        "key": estimated_key,
        "route": route,
    }


def export_all(engraved: dict, raw_tracks: dict, stems: dict, out_dir: Path,
               options: dict, watch, warnings) -> dict:
    with watch.stage("export"):
        score_path = export.write_musicxml(engraved["score"],
                                           out_dir / "score.musicxml")
        part_paths = export.write_parts(engraved["score"], engraved["parts"],
                                        out_dir / "parts")
        quantized = engraved["quantized"]
        tempo = engraved["tempo"]
        midi_full = export.write_midi(quantized, out_dir / "score.mid", tempo)
        midi = []
        for instrument_id in catalog.score_order(quantized, engraved["route"]):
            path = export.write_midi({
                instrument_id: quantized[instrument_id]
            }, out_dir / "midi" / f"{instrument_id}.mid", tempo)
            export.write_midi({
                instrument_id: raw_tracks[instrument_id]
            }, out_dir / "midi" / "raw" / f"{instrument_id}.mid")
            midi.append({
                "instrument": instrument_id,
                "name": catalog.get(instrument_id).name,
                "key": relative(path, out_dir),
                "notes": len(quantized[instrument_id]),
            })
        pdf = None
        if options["exportPdf"]:
            pdf = export.render_pdf(score_path, out_dir / "score.pdf")
            if pdf is None:
                warnings.append("No se pudo generar el PDF (MuseScore no "
                                "está disponible en este entorno).")
    return {
        "stems": [{
            "name": name,
            "label": catalog.STEM_LABELS.get(name, name),
            "key": relative(path, out_dir),
        } for name, path in stems.items()],
        "midi":
            midi,
        "midiFull":
            relative(midi_full, out_dir),
        "score": {
            "musicxml": relative(score_path, out_dir),
            "pdf": relative(pdf, out_dir) if pdf else None,
        },
        "parts": [{
            "instrument": instrument_id,
            "name": catalog.get(instrument_id).name,
            "key": relative(path, out_dir),
        } for instrument_id, path in part_paths.items()],
    }


def run(audio_path: Path,
        out_dir: Path,
        mode: str = "auto",
        instruments=None,
        options=None,
        max_duration: float = jobs.MAX_DURATION_SEC,
        title: str | None = None,
        on_stage=None) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    options = jobs.validate_options(options)
    instrument_ids = jobs.resolve_instruments(mode, instruments)
    watch = Stopwatch(on_stage)
    warnings = [APPROXIMATE_WARNING]

    mix, sr = audio_io.load(audio_path, max_duration=max_duration + 1)
    if audio_io.duration(mix, sr) > max_duration:
        mix = mix[:, :int(max_duration * sr)]
        warnings.append(f"El audio se recortó a {max_duration:g} s.")
    input_path = audio_io.write(out_dir / "input.wav", mix, sr)

    route, decision = resolve_route(mode, mix, sr, warnings)
    instrument_ids = jobs.instruments_for_route(route, instrument_ids)

    stems = {}
    if route == catalog.ROCK:
        tracks, stems = transcribe_rock(mix, sr, instrument_ids, out_dir, watch,
                                        warnings)
    else:
        tracks = transcribe_orchestra(input_path, instrument_ids, watch,
                                      warnings)

    engraved = engrave(tracks, mix, sr, options, title or Path(audio_path).stem,
                       route, watch, warnings)
    files = export_all(engraved, tracks, stems, out_dir, options, watch,
                       warnings)
    input_path.unlink(missing_ok=True)
    return {
        "resolvedMode": route,
        "instruments": catalog.score_order(engraved["quantized"], route),
        "stages": watch.stages,
        "warnings": warnings,
        "route": {
            "probabilityRock": decision.probability_rock,
            "features": decision.features,
        } if decision else None,
        "result": {
            "durationSec": round(audio_io.duration(mix, sr), 2),
            "tempo": engraved["tempo"],
            "timeSignature": engraved["grid"].time_signature,
            "key": engraved["key"].name,
            **files,
        },
    }
