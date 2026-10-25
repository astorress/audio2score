# Integrations

| From                          | To                                             | How                                                                                           |
| ----------------------------- | ---------------------------------------------- | --------------------------------------------------------------------------------------------- |
| SPA                           | HTTP API                                       | `VITE_API_URL`, contract `docs/api.md` (CORS `*`, anonymous)                                  |
| SPA                           | S3 files bucket                                | presigned POST (upload) / GET (results); bucket CORS `*` (the signature is the authorization) |
| S3 `uploads/`                 | Dispatch                                       | S3 event (`existing: true` custom resource)                                                   |
| Dispatch                      | SageMaker async endpoint `audio2score-worker`  | `InvokeEndpointAsync`, InputLocation `requests/<jobId>.json`                                  |
| Worker                        | DynamoDB jobs table                            | `UpdateItem` (status RUNNING, stage, stages; FAILED on error)                                 |
| Worker                        | S3                                             | reads `uploads/`, `requests/`; writes `results/<jobId>/`, `async-output/`, `async-failures/`  |
| SageMaker                     | SNS `audio2score-inference-success` / `-error` | async NotificationConfig → OnComplete                                                         |
| CloudWatch alarms, AWS Budget | SNS `audio2score-notifications`                | email subscription (`NOTIFICATION_EMAIL`)                                                     |

SSM parameters: `/audio2score-storage/{FilesBucketName, JobsTableName, JobsTableArn,
InferenceSuccessTopicArn, InferenceErrorTopicArn, NotificationsTopicArn}`,
`/audio2score-image/{RepositoryName, RepositoryArn, RepositoryUri}`,
`/audio2score-worker/{EndpointName, DeployedImageTag}`, `/audio2score-api/ApiUrl`, `/audio2score-web/WebUrl`.
