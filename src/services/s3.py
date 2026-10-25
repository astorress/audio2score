import json
import mimetypes
from functools import lru_cache
from pathlib import Path
from urllib.parse import urlparse

import boto3
from botocore.config import Config

CONTENT_TYPES = {
    ".wav": "audio/wav",
    ".mid": "audio/midi",
    ".musicxml": "application/vnd.recordare.musicxml+xml",
    ".pdf": "application/pdf",
    ".json": "application/json",
}


@lru_cache(maxsize=1)
def client():
    # SigV4 + regional endpoint: presigned URLs work right after the bucket
    # is created (the global endpoint redirects for a while).
    return boto3.client("s3",
                        config=Config(signature_version="s3v4",
                                      s3={
                                          "addressing_style": "virtual"
                                      }))


def split_uri(uri: str) -> tuple:
    parsed = urlparse(uri)
    return parsed.netloc, parsed.path.lstrip("/")


def content_type(path) -> str:
    suffix = Path(path).suffix.lower()
    return CONTENT_TYPES.get(
        suffix,
        mimetypes.guess_type(str(path))[0] or "application/octet-stream")


def presigned_post(bucket: str, key: str, mime_type: str, max_bytes: int,
                   expires: int) -> dict:
    """Browser upload with S3's size limit (content-length-range)."""
    return client().generate_presigned_post(
        Bucket=bucket,
        Key=key,
        Fields={
            "Content-Type": mime_type,
        },
        Conditions=[
            {
                "Content-Type": mime_type
            },
            ["content-length-range", 1, max_bytes],
        ],
        ExpiresIn=expires,
    )


def presigned_get(bucket: str, key: str, expires: int) -> str:
    """Download URL; `attachment` makes the browser save the file (fetch()
    from the SPA ignores the header)."""
    return client().generate_presigned_url(
        "get_object",
        Params={
            "Bucket":
                bucket,
            "Key":
                key,
            "ResponseContentDisposition":
                f'attachment; filename="{Path(key).name}"',
        },
        ExpiresIn=expires,
    )


def put_json(bucket: str, key: str, body: dict) -> None:
    client().put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        ContentType="application/json",
    )


def read_json(uri: str) -> dict:
    bucket, key = split_uri(uri)
    response = client().get_object(Bucket=bucket, Key=key)
    return json.loads(response["Body"].read())


def download(bucket: str, key: str, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    client().download_file(bucket, key, str(path))
    return path


def upload(path: Path, bucket: str, key: str) -> None:
    client().upload_file(str(path),
                         bucket,
                         key,
                         ExtraArgs={
                             "ContentType": content_type(path)
                         })
