"""One async invocation = one job: download the audio from S3, run the
pipeline, upload every output under results/<jobId>/ and return the
manifest (SageMaker stores it in the async output location, and the
OnComplete Lambda copies it into the job). Progress is written to the jobs
table while the job runs, so the UI can show the current stage."""
import os
import tempfile
from pathlib import Path

from src.contract import jobs
from src.pipeline.run import run
from src.services import (
    dynamodb,
    s3,
)
from src.utilities.clock import (
    iso,
    now,
)
from src.utilities.logger import get_logger

logger = get_logger(__name__)


def track_progress() -> bool:
    return bool(os.environ.get("JOBS_TABLE_NAME"))


def update(job_id: str, fields: dict) -> None:
    if not track_progress():
        return
    try:
        dynamodb.update_job(job_id, {
            **fields, "updatedAt": iso(now())
        })
    except Exception:  # progress is best effort, the job goes on
        logger.exception("Could not update job %s", job_id)


def prefixed(result: dict, prefix: str) -> dict:
    """Result with file keys relative to the output folder → S3 keys."""

    def key(value):
        return prefix + value if value else value

    return {
        **result,
        "stems": [{
            **item, "key": key(item["key"])
        } for item in result["stems"]],
        "midi": [{
            **item, "key": key(item["key"])
        } for item in result["midi"]],
        "parts": [{
            **item, "key": key(item["key"])
        } for item in result["parts"]],
        "midiFull": key(result["midiFull"]),
        "score": {
            name: key(value)
            for name, value in result["score"].items()
        },
    }


def handle(request: dict) -> dict:
    job_id = jobs.validate_job_id(request.get("jobId"))
    source = request["input"]
    target = request["output"]
    update(job_id, {
        "status": jobs.RUNNING,
        "stage": None
    })
    with tempfile.TemporaryDirectory() as tmp:
        work = Path(tmp)
        audio = s3.download(source["bucket"], source["key"],
                            work / Path(source["key"]).name)
        out_dir = work / "out"

        def on_stage(stage, stages):
            logger.info("Job %s: %s %s", job_id, stage, stages)
            update(job_id, {
                "stage": stage,
                "stages": stages
            })

        try:
            manifest = run(audio,
                           out_dir,
                           request.get("mode", "auto"),
                           request.get("instruments"),
                           request.get("options"),
                           max_duration=float(
                               request.get("maxDurationSec",
                                           jobs.MAX_DURATION_SEC)),
                           title=request.get("title"),
                           on_stage=on_stage)
        except Exception as error:
            update(
                job_id, {
                    "status": jobs.FAILED,
                    "stage": None,
                    "error": f"El procesamiento falló: {error}"[:500],
                })
            raise
        for path in sorted(out_dir.rglob("*")):
            if path.is_file():
                s3.upload(
                    path, target["bucket"],
                    target["prefix"] + path.relative_to(out_dir).as_posix())
        manifest = {
            "jobId":
                job_id,
            **manifest,
            "result":
                prefixed(manifest["result"], target["prefix"]),
        }
        s3.put_json(target["bucket"], target["prefix"] + "manifest.json",
                    manifest)
    return manifest
