"""GET /jobs/{jobId}: the job's status and, when DONE, presigned URLs of
its results (docs/api.md)."""
import os

from src.contract import jobs
from src.services import (
    dynamodb,
    s3,
)
from src.utilities.clock import (
    epoch,
    now,
)
from src.utilities.http import json_response

BUCKET_NAME = os.environ.get("BUCKET_NAME", "")
URL_EXPIRES_SEC = int(os.environ.get("URL_EXPIRES_SEC", "3600"))


def handler(event, context):
    try:
        job_id = jobs.validate_job_id((event.get("pathParameters") or
                                       {}).get("jobId"))
    except jobs.ContractError:
        return json_response(404, {
            "message": "Job not found"
        })
    job = dynamodb.get_job(job_id)
    # DynamoDB deletes expired items within hours, not instantly.
    if not job or job.get("ttl", 0) < epoch(now()):
        return json_response(404, {
            "message": "Job not found"
        })
    return json_response(
        200,
        jobs.public_job(
            job,
            lambda key: s3.presigned_get(BUCKET_NAME, key, URL_EXPIRES_SEC)))
