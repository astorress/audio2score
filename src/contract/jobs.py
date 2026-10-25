"""Job contract (docs/api.md): validation of POST /jobs, the request the
dispatcher sends to the GPU worker and the manifest the worker returns.
Pure Python, shared by the Lambdas, the worker and the local API.
"""
import re

from src.contract import instruments as catalog

MODES = ("auto", catalog.ROCK, catalog.ORCHESTRA)
MODE_LABELS = {
    "auto": "Automático",
    catalog.ROCK: "Rock / banda",
    catalog.ORCHESTRA: "Orquesta",
}

PENDING = "PENDING"
QUEUED = "QUEUED"
RUNNING = "RUNNING"
DONE = "DONE"
FAILED = "FAILED"
STATUSES = (PENDING, QUEUED, RUNNING, DONE, FAILED)

STAGES = ("separation", "transcription", "engraving", "export")

QUANTIZATIONS = {
    "1/8": 2,
    "1/16": 4,
    "1/32": 8,
}  # notation → subdivisions per quarter note
DEFAULT_OPTIONS = {
    "quantization": "1/16",
    "allowTriplets": False,
    "exportPdf": True,
}

MAX_DURATION_SEC = 90
MAX_UPLOAD_BYTES = 25 * 1024 * 1024
CONTENT_TYPES = {
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/wave": "wav",
    "audio/mpeg": "mp3",
    "audio/flac": "flac",
    "audio/ogg": "ogg",
    "audio/mp4": "m4a",
}

UUID_PATTERN = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$")


class ContractError(ValueError):
    """Invalid client input: the message is returned to the caller (400)."""


def catalog_response() -> dict:
    """Body of GET /instruments."""
    return {
        "instruments": [item.to_api() for item in catalog.INSTRUMENTS],
        "families": [{
            "id": key,
            "name": name
        } for key, name in catalog.FAMILIES.items()],
        "modes": [{
            "id": mode,
            "name": MODE_LABELS[mode]
        } for mode in MODES],
        "defaults": catalog.DEFAULTS,
        "limits": {
            "maxDurationSec": MAX_DURATION_SEC,
            "maxUploadBytes": MAX_UPLOAD_BYTES,
            "contentTypes": list(CONTENT_TYPES),
        },
        "quantizations": list(QUANTIZATIONS),
    }


def validate_options(options) -> dict:
    if options is None:
        options = {}
    if not isinstance(options, dict):
        raise ContractError("options must be an object")
    unknown = set(options) - set(DEFAULT_OPTIONS)
    if unknown:
        raise ContractError(f"Unknown options: {sorted(unknown)}")
    merged = {
        **DEFAULT_OPTIONS,
        **options
    }
    if merged["quantization"] not in QUANTIZATIONS:
        raise ContractError(
            f"quantization must be one of {list(QUANTIZATIONS)}")
    for flag in ("allowTriplets", "exportPdf"):
        if not isinstance(merged[flag], bool):
            raise ContractError(f"{flag} must be a boolean")
    return merged


def resolve_instruments(mode: str, instrument_ids) -> list:
    """Requested instruments in score order; the mode's defaults when none
    are given. `auto` accepts any instrument (the worker filters them once
    it knows the route)."""
    if not instrument_ids:
        if mode == "auto":
            return []
        return list(catalog.DEFAULTS[mode])
    if not isinstance(instrument_ids, list) or not all(
            isinstance(item, str) for item in instrument_ids):
        raise ContractError("instruments must be a list of ids")
    unknown = [item for item in instrument_ids if item not in catalog.BY_ID]
    if unknown:
        raise ContractError(f"Unknown instruments: {unknown}")
    if mode != "auto":
        invalid = [
            item for item in instrument_ids
            if mode not in catalog.get(item).modes
        ]
        if invalid:
            raise ContractError(f"Not available in {mode} mode: {invalid}")
    return catalog.score_order(instrument_ids)


def instruments_for_route(route: str, instrument_ids) -> list:
    """Once `auto` is resolved: keeps the instruments valid for the route,
    or the route's defaults if none survive."""
    valid = [
        item for item in instrument_ids or []
        if route in catalog.get(item).modes
    ]
    return catalog.score_order(valid, route) or list(catalog.DEFAULTS[route])


def validate_create_request(payload) -> dict:
    """Body of POST /jobs → normalized job settings."""
    if not isinstance(payload, dict):
        raise ContractError("Body must be a JSON object")
    mode = payload.get("mode", "auto")
    if mode not in MODES:
        raise ContractError(f"mode must be one of {list(MODES)}")
    content_type = str(payload.get("contentType",
                                   "")).split(";", maxsplit=1)[0].strip()
    if content_type not in CONTENT_TYPES:
        raise ContractError(f"contentType must be one of {list(CONTENT_TYPES)}")
    size = payload.get("sizeBytes")
    if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
        raise ContractError("sizeBytes must be a positive integer")
    if size > MAX_UPLOAD_BYTES:
        raise ContractError(
            f"File too large: at most {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")
    duration = payload.get("durationSec")
    if not isinstance(duration, (int, float)) or isinstance(
            duration, bool) or duration <= 0:
        raise ContractError("durationSec must be a positive number")
    if duration > MAX_DURATION_SEC + 0.5:
        raise ContractError(
            f"Audio too long: at most {MAX_DURATION_SEC} s per job")
    file_name = str(payload.get("fileName") or "audio")[:200]
    return {
        "mode": mode,
        "instruments": resolve_instruments(mode, payload.get("instruments")),
        "options": validate_options(payload.get("options")),
        "contentType": content_type,
        "extension": CONTENT_TYPES[content_type],
        "sizeBytes": size,
        "durationSec": float(duration),
        "fileName": file_name,
    }


def validate_job_id(job_id) -> str:
    if not isinstance(job_id, str) or not UUID_PATTERN.match(job_id):
        raise ContractError("Invalid job id")
    return job_id


def upload_key(job_id: str, extension: str) -> str:
    return f"uploads/{job_id}.{extension}"


def job_id_from_upload_key(key: str) -> str:
    """uploads/<jobId>.<ext> → jobId."""
    name = key.rsplit("/", 1)[-1]
    return validate_job_id(name.split(".", 1)[0])


def request_key(job_id: str) -> str:
    return f"requests/{job_id}.json"


def results_prefix(job_id: str) -> str:
    return f"results/{job_id}/"


def worker_request(job: dict, bucket: str) -> dict:
    """Payload of the SageMaker async invocation (stored in S3)."""
    return {
        "jobId": job["jobId"],
        "input": {
            "bucket": bucket,
            "key": job["inputKey"],
        },
        "output": {
            "bucket": bucket,
            "prefix": results_prefix(job["jobId"]),
        },
        "mode": job["mode"],
        "instruments": job.get("instruments") or [],
        "options": job.get("options") or dict(DEFAULT_OPTIONS),
        "maxDurationSec": MAX_DURATION_SEC,
        "title": str(job.get("fileName") or "audio").rsplit(".", 1)[0],
    }


def result_files(result: dict) -> list:
    """Every file key referenced by a worker result (for presigning)."""
    if not result:
        return []
    keys = [item["key"] for item in result.get("stems", [])]
    keys += [item["key"] for item in result.get("midi", [])]
    keys += [item["key"] for item in result.get("parts", [])]
    keys.append(result.get("midiFull"))
    keys += list((result.get("score") or {}).values())
    return [key for key in keys if key]


def public_result(result: dict, url_for) -> dict | None:
    """Worker result (file keys) → API result (URLs); `url_for(key)`."""
    if not result:
        return None
    score = result.get("score") or {}
    return {
        "durationSec":
            result.get("durationSec"),
        "tempo":
            result.get("tempo"),
        "timeSignature":
            result.get("timeSignature"),
        "key":
            result.get("key"),
        "stems": [{
            "name": item["name"],
            "label": item.get("label", item["name"]),
            "url": url_for(item["key"]),
        } for item in result.get("stems", [])],
        "midi": [{
            "instrument": item["instrument"],
            "name": item["name"],
            "url": url_for(item["key"]),
            "notes": item.get("notes", 0),
        } for item in result.get("midi", [])],
        "midiFull":
            url_for(result["midiFull"]) if result.get("midiFull") else None,
        "score": {
            "musicxml":
                url_for(score["musicxml"]) if score.get("musicxml") else None,
            "pdf":
                url_for(score["pdf"]) if score.get("pdf") else None,
        },
        "parts": [{
            "instrument": item["instrument"],
            "name": item["name"],
            "url": url_for(item["key"]),
        } for item in result.get("parts", [])],
    }


def public_job(job: dict, url_for) -> dict:
    """Stored job → body of GET /jobs/{jobId}."""
    return {
        "jobId":
            job["jobId"],
        "status":
            job["status"],
        "mode":
            job["mode"],
        "resolvedMode":
            job.get("resolvedMode"),
        "instruments":
            job.get("instruments") or [],
        "options":
            job.get("options") or {},
        "createdAt":
            job.get("createdAt"),
        "updatedAt":
            job.get("updatedAt"),
        "expiresAt":
            job.get("expiresAt"),
        "stage":
            job.get("stage"),
        "stages":
            job.get("stages") or {},
        "warnings":
            job.get("warnings") or [],
        "error":
            job.get("error"),
        "result":
            public_result(job.get("result"), url_for)
            if job["status"] == DONE else None,
    }
