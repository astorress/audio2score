"""SNS notification of the async endpoint (success and error topics):
copies the worker manifest into the job (DONE) or records the failure."""
import json

from src.contract import jobs
from src.services import (
    dynamodb,
    s3,
)
from src.utilities.clock import (
    iso,
    now,
)
from src.utilities.logger import get_logger

logger = get_logger(__name__)

FINAL = (jobs.DONE, jobs.FAILED)
OPEN = (jobs.PENDING, jobs.QUEUED, jobs.RUNNING)


def complete(job_id: str, output_location: str) -> None:
    manifest = s3.read_json(output_location)
    dynamodb.update_job(
        job_id, {
            "status": jobs.DONE,
            "stage": None,
            "resolvedMode": manifest.get("resolvedMode"),
            "instruments": manifest.get("instruments"),
            "stages": manifest.get("stages") or {},
            "warnings": manifest.get("warnings") or [],
            "result": manifest.get("result"),
            "updatedAt": iso(now()),
        }, OPEN)


def fail(job_id: str, reason: str) -> None:
    job = dynamodb.get_job(job_id)
    if not job:
        return
    error = job.get("error") or f"El procesamiento falló: {reason}"[:500]
    dynamodb.update_job(
        job_id, {
            "status": jobs.FAILED,
            "stage": None,
            "error": error,
            "updatedAt": iso(now()),
        }, OPEN)


def handle_message(message: dict) -> str | None:
    try:
        job_id = jobs.validate_job_id(message.get("inferenceId"))
    except jobs.ContractError:
        logger.warning("Notification without a job id: %s", message)
        return None
    status = message.get("invocationStatus")
    output = (message.get("responseParameters") or {}).get("outputLocation")
    if status == "Completed" and output:
        complete(job_id, output)
    else:
        fail(job_id, message.get("failureReason") or status or "unknown")
    logger.info("Job %s: %s", job_id, status)
    return job_id


def handler(event, context):
    return {
        "jobs": [
            handle_message(json.loads(record["Sns"]["Message"]))
            for record in event.get("Records", [])
        ]
    }
