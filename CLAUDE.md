# CLAUDE.md — audio2score

## Repository context

`audio2score` is a standalone personal project (learning + usable product): a user uploads an audio
fragment (max 90 s) and gets separated stems, MIDI per instrument and engraved scores (MusicXML/PDF),
for rock and orchestral music. The plan it implements is `docs/PLAN.md` (Spanish); the HTTP contract is
`docs/api.md`. It follows the conventions of the owner's `mlops-customer-churn` repository (Serverless v4
stacks, SSM between stacks, BYOC SageMaker image, `src/` layout, devcontainer).

Status: **implemented, not deployed**. Phases 0–6 have code; open items are under "Open items".

## Folder structure

```text
audio2score/
├── container/        # worker image (SageMaker async endpoint, GPU): Dockerfile, entrypoint.sh, requirements.txt, image-version.js, build-push.sh
├── serverless/       # stacks: storage, image, worker, api, web (one service each)
├── src/
│   ├── contract/     # instrument catalog + job contract, pure Python (Lambdas AND worker)
│   ├── pipeline/     # audio → stems → notes → score → files; CLI (python3 -m src.pipeline.cli)
│   ├── serving/      # serve.py (Flask: /ping, /invocations) + worker.py (one job)
│   ├── evaluation/   # metrics, datasets (Slakh2100, URMP), ablation
│   ├── functions/jobs/  services/  utilities/   # Lambdas, one module per AWS service, shared helpers
│   └── scripts/      # local_api, synth_demo, real_audio, evaluate
├── tests/            # pytest, mirrors src/ (+ integration/, marked slow)
├── web/              # Vue 3 + TS SPA (its own package.json, README, tests)
├── notebooks/  docs/  .docker/  .envs/  package.json  pyproject.toml  pytest.ini
```

What goes where: `.claude/rules/architecture.md`.

## Commands

Inside the devcontainer (`Audio2Score`, folder `/app`): `npm test`, `npm run test:slow` (real models),
`npm run format`, `npm run lint`, `npm run local:run -- <audio> --mode rock`, `npm run local:api`,
`npm run web:dev`. Before considering a change done: format, lint, tests, and `serverless print` /
`serverless package` in each touched `serverless/<stack>/`. Testing rules: `.claude/rules/testing.md`.

Outside the devcontainer the host has no Node or Python 3.11: run tools through the image, e.g.
`docker run --rm -v "$PWD":/app -w /app audio2score-dev python3 -m pytest`.

## Conventions

- Stages `dev`, `test`, `prod`, one AWS account per stage, `us-east-1` only. `stackName: ${app}-${service}`
  (`audio2score-storage`, …); cross-stack values through SSM `/audio2score-<service>/<Name>`.
- **Claude never deploys**: no `sls deploy`/`remove`/`invoke`, `npm run deploy-*`, `npm run image:push`,
  `aws sagemaker ...` writes or `git push`. Hand the command to the owner (`.claude/rules/deployment.md`).
  The GPU endpoint costs money while it has instances.
- `src/contract/` must stay free of third-party imports (it ships in the Lambdas). The pipeline imports
  heavy libraries lazily inside functions.
- Instrument data (ranges, clefs, transpositions, GM programs, stems) lives only in
  `src/contract/instruments.py`. Transpositions use music21's written→sounding interval ("M-2").
- Users' audio is never kept: 1-day S3 lifecycle, 24 h job TTL, no gallery (plan §9).
- Model licenses are verified before integration (`docs/modelos.md`); anything not run here is marked
  "not verified".
- User-facing docs (README, docs/, web UI) in Spanish; code, comments and `.claude/` in English.
- Document every change in `changelog.md`.

## Commit convention

One-line subject, imperative, no trailing period, followed by a body with one `- ` bullet per distinct
change. Empty folders that must exist are kept with a `.gitignore`, never `.gitkeep`. Claude only commits
when the owner asks, and never pushes.

## Open items

- MuScriptor / YourMT3 backends for the orchestra route: license + VRAM verification pending
  (`src/pipeline/transcription.py` raises `BackendUnavailable`).
- Phase 3 numbers: run `npm run local:evaluate` on Slakh2100 / URMP and fill `docs/resultados.md`.
- Phase 0 findings on real audio (`docs/resultados.md`, notebooks 01–04): `routing.py` labels every
  classical trio as rock (the low-onset rate counts piano/cello notes; use percussive share only or a
  learned classifier); register-based assignment fails with piano (multi-instrument F1 0.37 on TRIOS);
  drop near-silent stems; drum detector lacks ride.
- Never deployed: first deploy of the 5 stacks, cold start time and cost per job to be measured.

See .claude/rules/ for detailed operational context.
