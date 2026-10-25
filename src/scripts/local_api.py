"""Local version of the HTTP API (docs/api.md) for development without AWS:
`python3 -m src.scripts.local_api` → http://localhost:8000.

Same routes and payloads as API Gateway + Lambdas; the upload "presigned
POST" points back to this server, jobs run one at a time in a background
thread (like MaxConcurrentInvocationsPerInstance=1) and files are served
from outputs/local-api/<jobId>/.
"""
import argparse
import json
import queue
import threading
import traceback
import uuid
from pathlib import Path

from flask import (
    Flask,
    Response,
    abort,
    request,
    send_from_directory,
)

from src.contract import jobs
from src.pipeline.run import run
from src.utilities.clock import (
    after,
    iso,
    now,
)

ROOT = Path("outputs/local-api")
JOB_TTL_HOURS = 24

app = Flask(__name__)
state = {
    "jobs": {},
    "lock": threading.Lock(),
    "queue": queue.Queue()
}


def base_url() -> str:
    return request.host_url.rstrip("/")


def save(job: dict) -> None:
    folder = ROOT / job["jobId"]
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "job.json").write_text(
        json.dumps(job, indent=2, ensure_ascii=False))


def update(job_id: str, **fields) -> None:
    with state["lock"]:
        job = state["jobs"][job_id]
        job.update(fields, updatedAt=iso(now()))
        save(job)


def reply(body, status: int = 200) -> Response:
    return Response(json.dumps(body, ensure_ascii=False),
                    status=status,
                    mimetype="application/json")


@app.after_request
def cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


@app.route("/<path:_>", methods=["OPTIONS"])
def preflight(_):
    return Response(status=204)


@app.get("/instruments")
def instruments():
    return reply(jobs.catalog_response())


@app.post("/jobs")
def create_job():
    try:
        settings = jobs.validate_create_request(request.get_json(silent=True))
    except jobs.ContractError as error:
        return reply({
            "message": str(error)
        }, 400)
    job_id = str(uuid.uuid4())
    created = now()
    job = {
        "jobId": job_id,
        "status": jobs.PENDING,
        "mode": settings["mode"],
        "instruments": settings["instruments"],
        "options": settings["options"],
        "fileName": settings["fileName"],
        "inputKey": jobs.upload_key(job_id, settings["extension"]),
        "stages": {},
        "warnings": [],
        "createdAt": iso(created),
        "updatedAt": iso(created),
        "expiresAt": iso(after(created, JOB_TTL_HOURS)),
    }
    with state["lock"]:
        state["jobs"][job_id] = job
        save(job)
    return reply(
        {
            "jobId": job_id,
            "status": jobs.PENDING,
            "upload": {
                "url": f"{base_url()}/uploads/{job_id}",
                "fields": {
                    "key": job["inputKey"],
                    "Content-Type": settings["contentType"],
                },
            },
            "expiresInSec": 600,
        }, 201)


@app.post("/uploads/<job_id>")
def upload(job_id):
    job = state["jobs"].get(job_id)
    upload_file = request.files.get("file")
    if not job or job["status"] != jobs.PENDING or upload_file is None:
        abort(400)
    path = ROOT / job_id / job["inputKey"]
    path.parent.mkdir(parents=True, exist_ok=True)
    upload_file.save(path)
    update(job_id, status=jobs.QUEUED)
    state["queue"].put(job_id)
    return Response(status=204)


@app.get("/jobs/<job_id>")
def get_job(job_id):
    job = state["jobs"].get(job_id)
    if not job:
        return reply({
            "message": "Job not found"
        }, 404)
    root = base_url()
    return reply(
        jobs.public_job(job,
                        lambda key: f"{root}/files/{job_id}/results/{key}"))


@app.get("/files/<job_id>/<path:key>")
def files(job_id, key):
    return send_from_directory((ROOT / job_id).resolve(), key)


def process(job_id: str) -> None:
    job = state["jobs"][job_id]
    update(job_id, status=jobs.RUNNING)
    try:
        manifest = run(ROOT / job_id / job["inputKey"],
                       ROOT / job_id / "results",
                       job["mode"],
                       job["instruments"],
                       job["options"],
                       title=job["fileName"].rsplit(".", 1)[0],
                       on_stage=lambda stage, stages: update(
                           job_id, stage=stage, stages=stages))
    except Exception as error:
        traceback.print_exc()
        update(job_id,
               status=jobs.FAILED,
               stage=None,
               error=f"El procesamiento falló: {error}")
        return
    update(job_id,
           status=jobs.DONE,
           stage=None,
           resolvedMode=manifest["resolvedMode"],
           instruments=manifest["instruments"],
           stages=manifest["stages"],
           warnings=manifest["warnings"],
           result=manifest["result"])


def worker() -> None:
    while True:
        process(state["queue"].get())


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    ROOT.mkdir(parents=True, exist_ok=True)
    threading.Thread(target=worker, daemon=True).start()
    app.run(host=args.host, port=args.port, threaded=True)


if __name__ == "__main__":
    main()
