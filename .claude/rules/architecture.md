# Architecture

## Request flow (AWS)

1. SPA (CloudFront + S3, `serverless/web`) → `POST /jobs` (HTTP API, `serverless/api`) → CreateJob:
   validates with `src/contract/jobs.py`, consumes the per-IP daily quota (DynamoDB `QUOTA#…` items, IP
   hashed), stores `JOB#<id>` as PENDING and returns a **presigned POST** (size-limited) to
   `uploads/<jobId>.<ext>` in the files bucket (`serverless/storage`).
2. Browser uploads directly to S3 → S3 event → Dispatch: writes `requests/<jobId>.json`
   (`jobs.worker_request`) and calls `InvokeEndpointAsync` (InferenceId = jobId) → QUEUED.
3. SageMaker async endpoint (`serverless/worker`, `ml.g4dn.xlarge`, autoscaling 0..N) runs the worker
   image: `serve.py` → `worker.handle` downloads the audio, runs `src.pipeline.run.run`, writes
   RUNNING/`stage`/`stages` to the job while it runs, uploads outputs to `results/<jobId>/` and returns the
   manifest (stored by SageMaker in `async-output/`).
4. SNS success/error topic → OnComplete: copies the manifest into the job (DONE) or records FAILED (keeps
   the worker's own error message if it wrote one).
5. SPA polls `GET /jobs/{jobId}` → GetJob returns the job with presigned GET URLs (1 h, attachment).

The same contract runs locally in `src/scripts/local_api.py` (Flask, one job at a time, files under
`outputs/local-api/`).

## Pipeline (`src/pipeline/run.py`)

- Route: `rock` → Demucs `htdemucs_6s` stems → Basic Pitch per melodic stem (bounded by the instrument
  range ± 1 octave) and `drums.py` for drums; `orchestra` → `transcription.transcribe_mix` (backend
  `basic-pitch-assign`: Basic Pitch on the mix + chord-by-chord monotonic DP assignment by
  range/tessitura); `auto` → `routing.classify`.
- Engraving: `symbolic.prepare` (cleanup, range folding, monophony) → `rhythm.track_beats` (librosa) →
  `rhythm.quantize_tracks` (seconds → quarter notes through beat interpolation; Viterbi over beats choosing
  one subdivision per beat) → `key.estimate_key` (Krumhansl-Schmuckler) → `score.build_score` (music21,
  parts at written pitch with `atSoundingPitch=False`, grand staff for piano/harp, tenor clef for high
  trombone/bassoon/cello, percussion clef with noteheads for drums).
- Export: `score.musicxml`, `parts/<id>.musicxml`, `midi/<id>.mid` (quantized, score tempo → in sync with
  the score cursor), `midi/raw/<id>.mid` (seconds, aligned with audio), `score.mid`, `score.pdf`
  (MuseScore CLI, optional).

## Code layout

- `src/contract/`: pure Python shared by Lambdas and worker. Changing it means redeploying both.
- `src/pipeline/`, `src/serving/`: baked into the worker image (`container/Dockerfile`,
  `.dockerignore`, `container/image-version.js` must list the same packages).
- `src/functions/jobs/<handler>.py`: one Lambda each; packaged with explicit patterns in
  `serverless/api/functions.yml`. `src/services/<aws_service>.py`: boto3 clients created lazily
  (`lru_cache`) so moto can mock them. `src/utilities/`: shared helpers.
- `src/evaluation/` + `src/scripts/evaluate.py`: Phase 3 metrics and ablation.
- `tests/` mirrors `src/`; `tests/integration/` runs the real models (marked `slow`).
