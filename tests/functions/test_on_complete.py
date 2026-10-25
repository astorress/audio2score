import json

from src.functions.jobs import on_complete
from src.services import (
    dynamodb,
    s3,
)
from tests.conftest import BUCKET
from tests.functions.helpers import (
    JOB_ID,
    stored_job,
)


def sns_event(message):
    return {
        "Records": [{
            "Sns": {
                "Message": json.dumps(message)
            }
        }]
    }


def test_success_copies_manifest(aws):
    dynamodb.put_job(stored_job(status="RUNNING", stage="export"))
    s3.put_json(
        BUCKET, "async/out.out", {
            "jobId": JOB_ID,
            "resolvedMode": "rock",
            "instruments": ["bass"],
            "stages": {
                "separation": 10.5
            },
            "warnings": ["Partitura aproximada"],
            "result": {
                "tempo": 120.0,
                "stems": []
            },
        })
    on_complete.handler(
        sns_event({
            "invocationStatus": "Completed",
            "inferenceId": JOB_ID,
            "responseParameters": {
                "outputLocation": f"s3://{BUCKET}/async/out.out"
            },
        }), None)
    job = dynamodb.get_job(JOB_ID)
    assert job["status"] == "DONE"
    assert job["stages"] == {
        "separation": 10.5
    }
    assert job["result"]["tempo"] == 120
    assert "stage" not in job


def test_failure_keeps_the_worker_error(aws):
    dynamodb.put_job(
        stored_job(status="RUNNING", error="El procesamiento falló: OOM"))
    on_complete.handler(
        sns_event({
            "invocationStatus": "Failed",
            "inferenceId": JOB_ID,
            "failureReason": "ClientError: 500"
        }), None)
    job = dynamodb.get_job(JOB_ID)
    assert job["status"] == "FAILED" and job["error"].endswith("OOM")


def test_failure_without_worker_error(aws):
    dynamodb.put_job(stored_job(status="QUEUED"))
    on_complete.handler(
        sns_event({
            "invocationStatus": "Failed",
            "inferenceId": JOB_ID,
            "failureReason": "Timeout"
        }), None)
    assert "Timeout" in dynamodb.get_job(JOB_ID)["error"]


def test_final_jobs_are_not_overwritten(aws):
    dynamodb.put_job(stored_job(status="DONE"))
    on_complete.handler(
        sns_event({
            "invocationStatus": "Failed",
            "inferenceId": JOB_ID
        }), None)
    assert dynamodb.get_job(JOB_ID)["status"] == "DONE"


def test_messages_without_job_id_are_skipped(aws):
    assert on_complete.handler(sns_event({
        "invocationStatus": "Completed"
    }), None) == {
        "jobs": [None]
    }
