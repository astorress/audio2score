# Testing

- `npm test` (pytest, `-m "not slow"`, coverage to `htmlcov/`): no network, no model weights.
  AWS is mocked with moto through the `aws` fixture (`tests/conftest.py`: bucket + jobs table); the
  SageMaker runtime is a `MagicMock` patched on the handler module.
- The neural models are replaced in `tests/pipeline/test_run.py` by the ground truth of
  `src/scripts/synth_demo.py`, so loading, routing, cleanup, beat tracking, quantization, key, music21 and
  every export run for real.
- `npm run test:slow` runs Demucs and Basic Pitch on the synthetic demos and checks onset F1 against
  their MIDI ground truth (downloads Demucs weights the first time).
- `web/`: `npm --prefix web test` (Vitest).
- New pipeline behaviour → a test with synthetic notes or synthetic audio; never commit real recordings.
