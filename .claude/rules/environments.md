# Environments

|                             | dev | test | prod |
| --------------------------- | --- | ---- | ---- |
| Worker max instances        | 1   | 1    | 1    |
| Jobs per IP per day         | 50  | 20   | 10   |
| Monthly budget (USD)        | 30  | 30   | 60   |
| Lambda log retention (days) | 1   | 3    | 7    |
| ECR images kept             | 3   | 3    | 5    |

Common: `ml.g4dn.xlarge`, scale-in cooldown 300 s, API throttling 5 rps (burst 10), files deleted after
1 day, jobs after 24 h, invocation timeout 1800 s, clips up to 90 s / 25 MB.

## Variables

- `.envs/aws.env`: `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION` (`us-east-1`),
  `AWS_DEFAULT_OUTPUT`.
- `.envs/sls.env`: `SERVERLESS_ACCESS_KEY`, `ORG`.
- `.envs/config.env`: `DEVELOPER` (dev deployment bucket name), `NOTIFICATION_EMAIL`, `SKIP_IMAGE_CHECK`.
- Worker/pipeline: `A2S_DEVICE`, `A2S_DEMUCS_MODEL`, `A2S_MULTI_BACKEND`, `A2S_MUSESCORE`,
  `JOBS_TABLE_NAME` (progress tracking; unset = no DynamoDB writes).
- Web: `VITE_API_URL`.

Only `*.example` files are committed. Meanings: README → Glosario.
