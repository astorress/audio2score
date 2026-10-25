import io
import time

from src.scripts import local_api


def fake_run(audio, out_dir, mode, instruments, options, title, on_stage):
    on_stage("transcription", {})
    out_dir.mkdir(parents=True)
    (out_dir / "score.musicxml").write_text("<score-partwise/>")
    return {
        "resolvedMode": "orchestra",
        "instruments": ["violin"],
        "stages": {
            "transcription": 0.1
        },
        "warnings": [],
        "result": {
            "stems": [],
            "midi": [],
            "parts": [],
            "midiFull": None,
            "score": {
                "musicxml": "score.musicxml",
                "pdf": None
            },
        },
    }


def test_full_flow(tmp_path, monkeypatch):
    monkeypatch.setattr(local_api, "ROOT", tmp_path)
    monkeypatch.setattr(local_api, "run", fake_run)
    client = local_api.app.test_client()

    catalog = client.get("/instruments").json
    assert catalog["limits"]["maxDurationSec"] == 90

    created = client.post("/jobs",
                          json={
                              "mode": "orchestra",
                              "instruments": ["violin"],
                              "fileName": "a.wav",
                              "contentType": "audio/wav",
                              "sizeBytes": 4,
                              "durationSec": 1,
                          })
    assert created.status_code == 201
    job_id = created.json["jobId"]
    upload = created.json["upload"]
    assert upload["url"].endswith(f"/uploads/{job_id}")

    form = dict(upload["fields"])
    form["file"] = (io.BytesIO(b"RIFF"), "a.wav")
    response = client.post(f"/uploads/{job_id}",
                           data=form,
                           content_type="multipart/form-data")
    assert response.status_code == 204
    assert response.headers["Access-Control-Allow-Origin"] == "*"

    local_api.process(local_api.state["queue"].get(timeout=1))
    job = client.get(f"/jobs/{job_id}").json
    assert job["status"] == "DONE"
    xml = client.get(job["result"]["score"]["musicxml"].split("localhost",
                                                              1)[-1])
    assert xml.status_code == 200 and b"score-partwise" in xml.data

    assert client.post("/jobs", json={
        "mode": "x"
    }).status_code == 400
    assert client.get("/jobs/nope").status_code == 404
    time.sleep(0)
