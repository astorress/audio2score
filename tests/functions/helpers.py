import json

JOB_ID = "9b2f7c1e-1234-4abc-8def-0123456789ab"


def http_event(body=None, path=None, ip="203.0.113.7"):
    return {
        "body": json.dumps(body) if body is not None else None,
        "pathParameters": path,
        "requestContext": {
            "http": {
                "sourceIp": ip
            }
        },
    }


def body_of(response):
    return json.loads(response["body"])


def stored_job(**fields):
    job = {
        "jobId": JOB_ID,
        "status": "PENDING",
        "mode": "rock",
        "instruments": ["bass"],
        "options": {
            "quantization": "1/16",
            "allowTriplets": False,
            "exportPdf": True
        },
        "fileName": "tema.wav",
        "inputKey": f"uploads/{JOB_ID}.wav",
        "stages": {},
        "warnings": [],
        "createdAt": "2026-10-24T20:00:00Z",
        "updatedAt": "2026-10-24T20:00:00Z",
        "expiresAt": "2099-01-01T00:00:00Z",
        "ttl": 4070908800,
    }
    job.update(fields)
    return job
