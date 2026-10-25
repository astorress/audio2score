import json
from unittest.mock import MagicMock

from src.functions.jobs import dispatch
from src.services import dynamodb
from tests.conftest import BUCKET
from tests.functions.helpers import (
    JOB_ID,
    stored_job,
)


def s3_event(key):
    return {
        "Records": [{
            "s3": {
                "bucket": {
                    "name": BUCKET
                },
                "object": {
                    "key": key
                }
            }
        }]
    }


def test_queues_pending_job(aws, monkeypatch):
    dynamodb.put_job(stored_job())
    runtime = MagicMock()
    runtime.invoke_endpoint_async.return_value = {
        "OutputLocation": "s3://b/async/out.out"
    }
    monkeypatch.setattr(dispatch, "sagemaker_runtime", runtime)

    result = dispatch.handler(s3_event(f"uploads/{JOB_ID}.wav"), None)

    assert result == {
        "queued": [JOB_ID]
    }
    args = runtime.invoke_endpoint_async.call_args.args
    assert args[1] == f"s3://{BUCKET}/requests/{JOB_ID}.json"
    assert args[2] == JOB_ID
    request = json.loads(
        aws.get_object(Bucket=BUCKET,
                       Key=f"requests/{JOB_ID}.json")["Body"].read())
    assert request["output"]["prefix"] == f"results/{JOB_ID}/"
    assert dynamodb.get_job(JOB_ID)["status"] == "QUEUED"


def test_duplicate_events_are_ignored(aws, monkeypatch):
    dynamodb.put_job(stored_job(status="QUEUED"))
    runtime = MagicMock()
    monkeypatch.setattr(dispatch, "sagemaker_runtime", runtime)
    assert dispatch.handler(s3_event(f"uploads/{JOB_ID}.wav"), None) == {
        "queued": []
    }
    runtime.invoke_endpoint_async.assert_not_called()


def test_unknown_keys_are_ignored(aws):
    assert dispatch.handler(s3_event("uploads/hola.wav"), None) == {
        "queued": []
    }


def test_endpoint_errors_fail_the_job(aws, monkeypatch):
    dynamodb.put_job(stored_job())
    runtime = MagicMock()
    runtime.invoke_endpoint_async.side_effect = RuntimeError("no endpoint")
    monkeypatch.setattr(dispatch, "sagemaker_runtime", runtime)
    dispatch.handler(s3_event(f"uploads/{JOB_ID}.wav"), None)
    job = dynamodb.get_job(JOB_ID)
    assert job["status"] == "FAILED" and "encolar" in job["error"]
