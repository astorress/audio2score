"""POST /jobs: validates the request, counts it against the caller's daily
quota, stores the job (PENDING) and returns a presigned POST to upload the
audio straight to S3 (the Dispatch Lambda takes over from the upload)."""
import hashlib
import os
import uuid

from src.contract import jobs
from src.services import (
    dynamodb,
    s3,
)
from src.utilities.clock import (
    after,
    epoch,
    iso,
    now,
)
from src.utilities.http import (
    json_response,
    parse_body,
    source_ip,
)
from src.utilities.logger import get_logger

logger = get_logger(__name__)

BUCKET_NAME = os.environ.get("BUCKET_NAME", "")
DAILY_QUOTA = int(os.environ.get("DAILY_QUOTA", "20"))
JOB_TTL_HOURS = float(os.environ.get("JOB_TTL_HOURS", "24"))
UPLOAD_EXPIRES_SEC = int(os.environ.get("UPLOAD_EXPIRES_SEC", "600"))


def caller_id(event: dict) -> str:
    """The quota is per source IP, stored hashed (no raw IPs at rest)."""
    return hashlib.sha256(source_ip(event).encode()).hexdigest()[:32]


def handler(event, context):
    payload = parse_body(event)
    if payload is None:
        return json_response(400, {
            "message": "Invalid JSON body"
        })
    try:
        settings = jobs.validate_create_request(payload)
    except jobs.ContractError as error:
        return json_response(400, {
            "message": str(error)
        })

    created = now()
    expires = after(created, JOB_TTL_HOURS)
    if not dynamodb.consume_quota(caller_id(event),
                                  created.date().isoformat(), DAILY_QUOTA,
                                  epoch(after(created, 48))):
        return json_response(
            429, {
                "message":
                    f"Daily limit of {DAILY_QUOTA} jobs reached, try again "
                    "tomorrow"
            })

    job_id = str(uuid.uuid4())
    key = jobs.upload_key(job_id, settings["extension"])
    dynamodb.put_job({
        "jobId": job_id,
        "status": jobs.PENDING,
        "mode": settings["mode"],
        "instruments": settings["instruments"],
        "options": settings["options"],
        "fileName": settings["fileName"],
        "contentType": settings["contentType"],
        "sizeBytes": settings["sizeBytes"],
        "durationSec": settings["durationSec"],
        "inputKey": key,
        "stages": {},
        "warnings": [],
        "createdAt": iso(created),
        "updatedAt": iso(created),
        "expiresAt": iso(expires),
        "ttl": epoch(expires),
    })
    upload = s3.presigned_post(BUCKET_NAME, key, settings["contentType"],
                               jobs.MAX_UPLOAD_BYTES, UPLOAD_EXPIRES_SEC)
    logger.info("Created job %s (%s)", job_id, settings["mode"])
    return json_response(
        201, {
            "jobId": job_id,
            "status": jobs.PENDING,
            "upload": upload,
            "expiresInSec": UPLOAD_EXPIRES_SEC,
        })
