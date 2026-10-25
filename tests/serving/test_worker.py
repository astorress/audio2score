import json

import pytest

from src.services import dynamodb
from src.serving import (
    serve,
    worker,
)
from tests.conftest import BUCKET
from tests.functions.helpers import (
    JOB_ID,
    stored_job,
)


def request():
    return {
        "jobId": JOB_ID,
        "input": {
            "bucket": BUCKET,
            "key": f"uploads/{JOB_ID}.wav"
        },
        "output": {
            "bucket": BUCKET,
            "prefix": f"results/{JOB_ID}/"
        },
        "mode": "rock",
        "instruments": ["bass"],
        "options": {},
        "maxDurationSec": 90,
        "title": "tema",
    }


def fake_run(audio, out_dir, mode, instruments, options, max_duration, title,
             on_stage):
    on_stage("separation", {})
    out_dir.mkdir(parents=True)
    (out_dir / "score.musicxml").write_text("<score-partwise/>")
    (out_dir / "stems").mkdir()
    (out_dir / "stems" / "bass.wav").write_bytes(b"RIFF")
    return {
        "resolvedMode": "rock",
        "instruments": ["bass"],
        "stages": {
            "separation": 1.0
        },
        "warnings": [],
        "route": None,
        "result": {
            "stems": [{
                "name": "bass",
                "label": "Bajo",
                "key": "stems/bass.wav"
            }],
            "midi": [],
            "parts": [],
            "midiFull": "score.mid",
            "score": {
                "musicxml": "score.musicxml",
                "pdf": None
            },
        },
    }


@pytest.fixture
def uploaded(aws):
    dynamodb.put_job(stored_job(status="QUEUED"))
    aws.put_object(Bucket=BUCKET, Key=f"uploads/{JOB_ID}.wav", Body=b"RIFF")
    return aws


def test_worker_uploads_outputs_and_tracks_progress(uploaded, monkeypatch):
    seen = []
    monkeypatch.setattr(worker, "run", fake_run)
    original = dynamodb.update_job
    monkeypatch.setattr(
        dynamodb, "update_job", lambda job_id, fields, *a:
        (seen.append(fields), original(job_id, fields, *a))[1])

    manifest = worker.handle(request())

    prefix = f"results/{JOB_ID}/"
    assert manifest["result"]["stems"][0]["key"] == prefix + "stems/bass.wav"
    assert manifest["result"]["score"]["pdf"] is None
    keys = {
        item["Key"]
        for item in uploaded.list_objects_v2(Bucket=BUCKET, Prefix=prefix)
        ["Contents"]
    }
    assert keys == {
        prefix + "score.musicxml", prefix + "stems/bass.wav",
        prefix + "manifest.json"
    }
    assert seen[0]["status"] == "RUNNING"
    assert seen[1]["stage"] == "separation"
    assert dynamodb.get_job(JOB_ID)["stage"] == "separation"


def test_worker_failure_marks_the_job(uploaded, monkeypatch):

    def broken(*args, **kwargs):
        raise MemoryError("CUDA out of memory")

    monkeypatch.setattr(worker, "run", broken)
    with pytest.raises(MemoryError):
        worker.handle(request())
    job = dynamodb.get_job(JOB_ID)
    assert job["status"] == "FAILED" and "CUDA" in job["error"]


def test_server_contract(uploaded, monkeypatch):
    monkeypatch.setattr(worker, "run", fake_run)
    client = serve.app.test_client()
    assert client.get("/ping").status_code == 200
    ok = client.post("/invocations", data=json.dumps(request()))
    assert ok.status_code == 200 and ok.json["jobId"] == JOB_ID
    bad = client.post("/invocations", data=json.dumps({
        "jobId": "x"
    }))
    assert bad.status_code == 400
