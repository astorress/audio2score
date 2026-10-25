import os

import numpy as np
import pytest

# The services read their configuration at import time.
os.environ.setdefault("AWS_DEFAULT_REGION", "us-east-1")
os.environ.setdefault("AWS_ACCESS_KEY_ID", "testing")
os.environ.setdefault("AWS_SECRET_ACCESS_KEY", "testing")
os.environ.setdefault("JOBS_TABLE_NAME", "audio2score-jobs-test")
os.environ.setdefault("BUCKET_NAME", "audio2score-files-test")
os.environ.setdefault("ENDPOINT_NAME", "audio2score-worker-test")

TABLE = os.environ["JOBS_TABLE_NAME"]
BUCKET = os.environ["BUCKET_NAME"]


@pytest.fixture
def aws():
    """Mocked S3 bucket + jobs table (moto)."""
    import boto3
    from moto import mock_aws

    from src.services import (
        dynamodb,
        s3,
        sagemaker_runtime,
    )

    with mock_aws():
        for cached in (dynamodb.table, s3.client, sagemaker_runtime.client):
            cached.cache_clear()
        boto3.client("s3").create_bucket(Bucket=BUCKET)
        boto3.client("dynamodb").create_table(
            TableName=TABLE,
            KeySchema=[{
                "AttributeName": "pk",
                "KeyType": "HASH"
            }],
            AttributeDefinitions=[{
                "AttributeName": "pk",
                "AttributeType": "S"
            }],
            BillingMode="PAY_PER_REQUEST",
        )
        yield boto3.client("s3")
        for cached in (dynamodb.table, s3.client, sagemaker_runtime.client):
            cached.cache_clear()


@pytest.fixture
def melody():
    """C major scale, quarter notes at 120 BPM (0.5 s), slightly humanized.
    """
    from src.pipeline.notes import Note

    rng = np.random.default_rng(0)
    pitches = [60, 62, 64, 65, 67, 69, 71, 72]
    return [
        Note(pitch, 0.5 * index + rng.uniform(-0.02, 0.02), 0.5 * index + 0.45,
             90) for index, pitch in enumerate(pitches)
    ]


@pytest.fixture
def grid120():
    from src.pipeline.rhythm import regular_grid

    return regular_grid(10.0, 120.0)
