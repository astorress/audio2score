import pytest

from src.contract import jobs

VALID = {
    "mode": "orchestra",
    "instruments": ["violin", "trombone"],
    "fileName": "fragmento.wav",
    "contentType": "audio/wav",
    "sizeBytes": 1000,
    "durationSec": 30,
}


def test_valid_request_is_normalized():
    settings = jobs.validate_create_request(VALID)
    assert settings["instruments"] == ["trombone", "violin"]  # score order
    assert settings["options"] == jobs.DEFAULT_OPTIONS
    assert settings["extension"] == "wav"


def test_mode_defaults_when_no_instruments():
    settings = jobs.validate_create_request({
        **VALID, "instruments": None
    })
    assert settings["instruments"] == jobs.catalog.DEFAULTS["orchestra"]
    auto = jobs.validate_create_request({
        **VALID, "mode": "auto",
        "instruments": []
    })
    assert auto["instruments"] == []


@pytest.mark.parametrize("change, message", [
    ({
        "mode": "jazz"
    }, "mode"),
    ({
        "contentType": "video/mp4"
    }, "contentType"),
    ({
        "sizeBytes": 0
    }, "sizeBytes"),
    ({
        "sizeBytes": 26 * 1024 * 1024
    }, "too large"),
    ({
        "durationSec": 120
    }, "too long"),
    ({
        "durationSec": True
    }, "durationSec"),
    ({
        "instruments": ["kazoo"]
    }, "Unknown instruments"),
    ({
        "mode": "rock",
        "instruments": ["violin"]
    }, "Not available"),
    ({
        "options": {
            "quantization": "1/64"
        }
    }, "quantization"),
    ({
        "options": {
            "speed": 2
        }
    }, "Unknown options"),
    ({
        "options": {
            "exportPdf": "yes"
        }
    }, "exportPdf"),
])
def test_invalid_requests(change, message):
    with pytest.raises(jobs.ContractError, match=message):
        jobs.validate_create_request({
            **VALID,
            **change
        })


def test_instruments_for_route_filters_or_defaults():
    assert jobs.instruments_for_route("rock",
                                      ["violin", "guitar"]) == ["guitar"]
    assert jobs.instruments_for_route(
        "rock", ["violin"]) == jobs.catalog.DEFAULTS["rock"]


def test_upload_key_round_trip():
    job_id = "9b2f7c1e-1234-4abc-8def-0123456789ab"
    key = jobs.upload_key(job_id, "wav")
    assert key == f"uploads/{job_id}.wav"
    assert jobs.job_id_from_upload_key(key) == job_id
    with pytest.raises(jobs.ContractError):
        jobs.job_id_from_upload_key("uploads/../../etc.wav")


def test_worker_request_and_public_job():
    job = {
        "jobId": "9b2f7c1e-1234-4abc-8def-0123456789ab",
        "inputKey": "uploads/x.wav",
        "mode": "rock",
        "instruments": ["bass"],
        "fileName": "mi tema.wav",
        "status": jobs.DONE,
        "result": {
            "stems": [{
                "name": "bass",
                "label": "Bajo",
                "key": "results/a/stems/bass.wav"
            }],
            "midi": [{
                "instrument": "bass",
                "name": "Bajo",
                "key": "results/a/midi/bass.mid",
                "notes": 3
            }],
            "midiFull": "results/a/score.mid",
            "score": {
                "musicxml": "results/a/score.musicxml",
                "pdf": None
            },
            "parts": [],
            "tempo": 120.0,
        },
    }
    request = jobs.worker_request(job, "bucket")
    assert request["input"] == {
        "bucket": "bucket",
        "key": "uploads/x.wav"
    }
    assert request["output"]["prefix"] == f"results/{job['jobId']}/"
    assert request["title"] == "mi tema"

    body = jobs.public_job(job, lambda key: f"https://files/{key}")
    assert body["result"]["stems"][0]["url"].endswith("stems/bass.wav")
    assert body["result"]["score"]["pdf"] is None
    assert body["result"]["midiFull"] == "https://files/results/a/score.mid"
    assert len(jobs.result_files(job["result"])) == 4

    pending = jobs.public_job({
        **job, "status": jobs.RUNNING
    }, str)
    assert pending["result"] is None


def test_catalog_response_shape():
    body = jobs.catalog_response()
    assert {item["id"]
            for item in body["instruments"]} >= {"trombone", "guitar"}
    trombone = next(item for item in body["instruments"]
                    if item["id"] == "trombone")
    assert trombone["range"] == ["E2", "F5"]
    assert body["limits"]["maxDurationSec"] == 90
