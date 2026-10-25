"""S3 ObjectCreated on uploads/: writes the worker request next to the
audio and queues it on the SageMaker async endpoint (InferenceId = jobId).
Idempotent: only PENDING jobs are dispatched."""
import os
from urllib.parse import unquote_plus

from src.contract import jobs
from src.services import (
    dynamodb,
    s3,
    sagemaker_runtime,
)
from src.utilities.clock import (
    iso,
    now,
)
from src.utilities.logger import get_logger

logger = get_logger(__name__)

ENDPOINT_NAME = os.environ.get("ENDPOINT_NAME", "")
INVOCATION_TIMEOUT_SEC = int(os.environ.get("INVOCATION_TIMEOUT_SEC", "1800"))


def dispatch(bucket: str, key: str) -> str | None:
    try:
        job_id = jobs.job_id_from_upload_key(key)
    except jobs.ContractError:
        logger.warning("Ignoring unexpected upload %s", key)
        return None
    job = dynamodb.get_job(job_id)
    if not job or job["status"] != jobs.PENDING or job["inputKey"] != key:
        logger.warning("Ignoring upload %s (job %s)", key,
                       job["status"] if job else "missing")
        return None
    request_key = jobs.request_key(job_id)
    s3.put_json(bucket, request_key, jobs.worker_request(job, bucket))
    try:
        response = sagemaker_runtime.invoke_endpoint_async(
            ENDPOINT_NAME, f"s3://{bucket}/{request_key}", job_id,
            INVOCATION_TIMEOUT_SEC)
    except Exception:
        logger.exception("Could not queue job %s", job_id)
        dynamodb.update_job(
            job_id, {
                "status": jobs.FAILED,
                "error": "No se pudo encolar el job en el worker.",
                "updatedAt": iso(now()),
            }, (jobs.PENDING, ))
        return None
    dynamodb.update_job(
        job_id, {
            "status": jobs.QUEUED,
            "outputLocation": response.get("OutputLocation"),
            "updatedAt": iso(now()),
        }, (jobs.PENDING, ))
    logger.info("Queued job %s", job_id)
    return job_id


def handler(event, context):
    queued = []
    for record in event.get("Records", []):
        bucket = record["s3"]["bucket"]["name"]
        key = unquote_plus(record["s3"]["object"]["key"])
        job_id = dispatch(bucket, key)
        if job_id:
            queued.append(job_id)
    return {
        "queued": queued
    }
