from src.functions.jobs import (
    get_job,
    list_instruments,
)
from src.services import dynamodb
from tests.functions.helpers import (
    JOB_ID,
    body_of,
    http_event,
    stored_job,
)


def test_done_job_has_presigned_urls(aws):
    dynamodb.put_job(
        stored_job(status="DONE",
                   result={
                       "tempo": 100.0,
                       "stems": [{
                           "name": "bass",
                           "label": "Bajo",
                           "key": f"results/{JOB_ID}/stems/bass.wav"
                       }],
                       "midi": [],
                       "parts": [],
                       "midiFull": f"results/{JOB_ID}/score.mid",
                       "score": {
                           "musicxml": f"results/{JOB_ID}/score.musicxml",
                           "pdf": None
                       },
                   }))
    response = get_job.handler(http_event(path={
        "jobId": JOB_ID
    }), None)
    assert response["statusCode"] == 200
    body = body_of(response)
    url = body["result"]["stems"][0]["url"]
    assert "X-Amz-Signature" in url and "attachment" in url
    assert body["result"]["score"]["pdf"] is None
    assert "inputKey" not in body and "ttl" not in body


def test_running_job_has_no_result(aws):
    dynamodb.put_job(stored_job(status="RUNNING", stage="transcription"))
    body = body_of(get_job.handler(http_event(path={
        "jobId": JOB_ID
    }), None))
    assert body["stage"] == "transcription" and body["result"] is None


def test_missing_invalid_and_expired_jobs_are_404(aws):
    assert get_job.handler(http_event(path={
        "jobId": JOB_ID
    }), None)["statusCode"] == 404
    assert get_job.handler(http_event(path={
        "jobId": "../x"
    }), None)["statusCode"] == 404
    dynamodb.put_job(stored_job(ttl=1))
    assert get_job.handler(http_event(path={
        "jobId": JOB_ID
    }), None)["statusCode"] == 404


def test_list_instruments():
    response = list_instruments.handler({}, None)
    assert response["statusCode"] == 200
    assert "max-age" in response["headers"]["Cache-Control"]
    assert body_of(response)["defaults"]["rock"][0] == "vocals"
