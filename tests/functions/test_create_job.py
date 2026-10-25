from src.functions.jobs import create_job
from src.services import dynamodb
from tests.functions.helpers import (
    body_of,
    http_event,
)

REQUEST = {
    "mode": "rock",
    "fileName": "tema.wav",
    "contentType": "audio/wav",
    "sizeBytes": 2048,
    "durationSec": 30.5,
}


def test_creates_pending_job_and_presigned_post(aws):
    response = create_job.handler(http_event(REQUEST), None)
    assert response["statusCode"] == 201
    body = body_of(response)
    job = dynamodb.get_job(body["jobId"])
    assert job["status"] == "PENDING"
    assert job["instruments"] == ["vocals", "guitar", "bass", "piano", "drums"]
    assert job["durationSec"] == 30.5
    assert body["upload"]["fields"]["key"] == job["inputKey"]
    assert body["upload"]["fields"]["Content-Type"] == "audio/wav"
    assert "policy" in body["upload"]["fields"]


def test_rejects_invalid_requests(aws):
    response = create_job.handler(http_event({
        **REQUEST, "mode": "x"
    }), None)
    assert response["statusCode"] == 400
    bad_json = create_job.handler({
        "body": "{",
        "requestContext": {}
    }, None)
    assert bad_json["statusCode"] == 400


def test_daily_quota_per_ip(aws, monkeypatch):
    monkeypatch.setattr(create_job, "DAILY_QUOTA", 2)
    codes = [
        create_job.handler(http_event(REQUEST), None)["statusCode"]
        for _ in range(3)
    ]
    assert codes == [201, 201, 429]
    other_ip = create_job.handler(http_event(REQUEST, ip="198.51.100.1"), None)
    assert other_ip["statusCode"] == 201
