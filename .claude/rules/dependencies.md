# Dependencies

- Python 3.11 for the worker and the devcontainer: `basic-pitch==0.4.0` doesn't install on 3.12+.
  Lambdas run python3.13 and only import `src/contract`, `src/services`, `src/utilities` (boto3 from the
  runtime).
- `container/requirements.txt` is the single pinned ML runtime (worker image AND devcontainer). Resolved
  on 2026-10-24: torch 2.14.1, demucs 4.1.0, basic-pitch 0.4.0 (pulls TensorFlow 2.15, numpy 1.26),
  music21 10.5.1, librosa 0.11.0, pretty_midi 0.2.11.post0, mir_eval 0.8.2.
- `demucs 4.1.0` depends on `sphn`, which only ships x86_64 wheels: on arm64 the devcontainer compiles it
  (Rust via rustup, `build-essential`, `cmake`, `pkg-config`, system `libopus-dev` so `audiopus_sys`
  doesn't build opus with a CMake it rejects; `CMAKE_POLICY_VERSION_MINIMUM=3.5`). The worker image is
  amd64 and uses the wheel. The ML requirements install in two layers (all but demucs, then demucs) so
  torch/TensorFlow stay cached.
- Demucs weights are downloaded at image build time (`container/download-models.py`, `TORCH_HOME` /
  `HF_HOME` under `/opt/models`); Basic Pitch ships its model in the package.
- MuseScore 3 (Debian `musescore3`) renders PDFs in the worker and the devcontainer
  (`QT_QPA_PLATFORM=offscreen`).
- Node tooling (root `package.json`): Serverless plugins are never global — `serverless-deployment-bucket`,
  `@serverless/safeguards-plugin`, `serverless-s3-sync`. `web/` has its own `package.json`.
- Licenses of models and their weights: `docs/modelos.md`.
