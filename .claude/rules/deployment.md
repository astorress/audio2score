# Deployment

**Claude never runs** `sls deploy`, `sls remove`, `sls invoke`, `npm run deploy-*`, `npm run image:push`,
`aws sagemaker` / `aws application-autoscaling` writes, or `git push`. It prepares the change, runs the
local checks and gives the owner the exact commands.

## Order (every stage)

1. `npm run deploy-storage:<stage>` — confirm the SNS email subscription afterwards.
2. `npm run deploy-image:<stage>`
3. `npm run image:push` (amd64 build; emulated and slow on Apple Silicon)
4. `npm run deploy-worker:<stage>` (fails if the image tag of `container/image-version.js` isn't in ECR)
5. `npm run deploy-api:<stage>` (reads the endpoint name from SSM)
6. `npm run deploy-web:<stage>` (builds `web/` with `/audio2score-api/ApiUrl`)

## Risks and gotchas

- The worker endpoint is created with 1 GPU instance (async endpoints can't start at 0) and scales in to 0
  after `scaleInCooldownSec` with an empty queue. Alarms `NotScalingToZero` / `BacklogStuck` /
  `InvocationFailures` + the monthly budget email the owner.
- First job after idle waits for scale-out from zero (alarm `HasBacklogWithoutCapacity` → step policy) plus
  image pull and model load: several minutes. The UI explains it in the QUEUED state.
- The worker image must be pushed with Docker v2 manifests (`build-push.sh` checks it).
- Dispatch uses an S3 `existing: true` event: Serverless adds a custom resource that edits the files
  bucket notifications. Removing the api stack removes that notification.
- The ECR repository is retained on `sls remove`.
- Not verified on AWS yet: first deploy, cold start duration, GPU memory of Demucs + Basic Pitch on
  `ml.g4dn.xlarge` (T4 16 GB), MuseScore 3 PDF rendering in the worker image.
