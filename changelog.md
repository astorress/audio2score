# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## Unreleased

- Plan v0.1 (`docs/PLAN.md`), API contract (`docs/api.md`), AWS architecture (`docs/arquitectura.md`), model registry (`docs/modelos.md`), evaluation protocol (`docs/resultados.md`)
- Phase 0: notebooks `01`–`04` (time-frequency representations, Demucs, Basic Pitch stems vs mix, orchestral AMT checklist)
- Phases 1–2: pipeline `src/pipeline/` — Demucs `htdemucs_6s` separation, Basic Pitch per stem bounded by instrument range, DSP drum transcriber, orchestra route with Basic Pitch + range/tessitura assignment (MuScriptor/YourMT3 integration points), `auto` route heuristic, note cleanup, beat tracking, Viterbi quantization, Krumhansl-Schmuckler key and spelling, music21 engraving (transposing instruments, tenor clef, grand staff, percussion), MusicXML/parts/MIDI/PDF export and CLI
- Shared instrument catalog and job contract (`src/contract/`)
- Phase 3: metrics (SDR, note F1, multi-instrument F1, measure accuracy), Slakh2100/URMP loaders, separation ablation and `evaluate` script
- Phase 4: worker image (Python 3.11, CUDA, weights baked in, MuseScore 3), SageMaker async endpoint with scale-to-zero autoscaling and alarms, HTTP API with presigned POST uploads, per-IP daily quota, Lambdas `ListInstruments`/`CreateJob`/`GetJob`/`Dispatch`/`OnComplete`, storage stack with 1-day lifecycle, 24 h job TTL and monthly budget
- Phase 5: Vue 3 + TypeScript SPA (`web/`): upload and crop, progress, stem mixer, OSMD score with synchronized cursor, piano-roll, downloads, "Cómo funciona" page
- Local API with the same contract (`src/scripts/local_api.py`) and synthetic demo audio with ground truth (`src/scripts/synth_demo.py`)
- Devcontainer (Node 24 + Python 3.11; Rust on arm64 to build `sphn`), `CLAUDE.md` and `.claude/rules/`
- Architecture diagram in draw.io (`docs/architecture.drawio`): stacks, numbered job flow, scale-to-zero and cost alerts
- Docs: `docs/pipeline.md` (every pipeline stage explained) and `docs/problemas.md` (troubleshooting: local, result quality, anticipated AWS issues)
- Devcontainer: JupyterLab published on host port 8889 (container 8888) to avoid clashing with other projects
- Notebooks: 03 reuses the cached Basic Pitch model (fixes OOM) and scores stems against the demo ground truth; 04 completed with the orchestra baseline (assignment, piano-rolls, wrong-instrument scenarios); findings written in 01–04 and `docs/resultados.md`
- Real recordings for notebooks and evaluation: `src/scripts/real_audio.py` (`npm run local:real-audio`) downloads MUSDB18 7-s preview and TRIOS to `data/real/`; `datasets.py` loads both (`trios`, `musdb`)
- Notebooks 01–04 rewritten on real audio (Demucs SDR on 50 MUSDB excerpts, stems vs mix on bass/sax/piano/drums, orchestra baseline on 4 TRIOS trios); findings in `docs/resultados.md`
- Fix: `transcription.basic_pitch()` clamps the requested range to A0–C8 (Basic Pitch silently returned no notes below A0)
- Docs: `docs/matematicas.md` (mathematical formulation of every stage), rewritten `docs/pipeline.md`, `docs/api.md`, `docs/arquitectura.md` and `docs/modelos.md` from the code, and `docs/README.md` index
