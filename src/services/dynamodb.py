"""Jobs table: one item per job (pk JOB#<jobId>) plus daily quota counters
(pk QUOTA#<hashed ip>#<date>). Both expire through the `ttl` attribute."""
import json
import os
from decimal import Decimal
from functools import lru_cache

import boto3
from boto3.dynamodb.conditions import Attr

TABLE_NAME = os.environ.get("JOBS_TABLE_NAME", "")


@lru_cache(maxsize=1)
def table():
    return boto3.resource("dynamodb").Table(TABLE_NAME)


def to_dynamo(value):
    """Floats → Decimal (DynamoDB has no float type)."""
    return json.loads(json.dumps(value), parse_float=Decimal)


def from_dynamo(value):
    if isinstance(value, list):
        return [from_dynamo(item) for item in value]
    if isinstance(value, dict):
        return {
            key: from_dynamo(item)
            for key, item in value.items()
        }
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(
            value)
    return value


def job_key(job_id: str) -> dict:
    return {
        "pk": f"JOB#{job_id}"
    }


def put_job(job: dict) -> None:
    table().put_item(Item=to_dynamo({
        **job_key(job["jobId"]),
        **job
    }),
                     ConditionExpression=Attr("pk").not_exists())


def get_job(job_id: str) -> dict | None:
    item = table().get_item(Key=job_key(job_id),
                            ConsistentRead=True).get("Item")
    if not item:
        return None
    item = from_dynamo(item)
    item.pop("pk", None)
    return item


def update_job(job_id: str,
               fields: dict,
               expected_statuses: tuple | None = None) -> bool:
    """SETs `fields` (None values are removed). With `expected_statuses`,
    only when the job is in one of them; returns whether it was updated.

    Placeholders use #u/:u prefixes: boto3's condition builder generates its
    own #n0/:v0 and would silently overwrite ours."""
    sets, removes = [], []
    names, values = {}, {}
    for index, (name, value) in enumerate(fields.items()):
        names[f"#u{index}"] = name
        if value is None:
            removes.append(f"#u{index}")
        else:
            values[f":u{index}"] = to_dynamo(value)
            sets.append(f"#u{index} = :u{index}")
    expression = ""
    if sets:
        expression += "SET " + ", ".join(sets)
    if removes:
        expression += " REMOVE " + ", ".join(removes)
    arguments = {
        "Key": job_key(job_id),
        "UpdateExpression": expression.strip(),
        "ExpressionAttributeNames": names,
    }
    if values:
        arguments["ExpressionAttributeValues"] = values
    condition = Attr("pk").exists()
    if expected_statuses:
        condition = condition & Attr("status").is_in(list(expected_statuses))
    arguments["ConditionExpression"] = condition
    try:
        table().update_item(**arguments)
    except table().meta.client.exceptions.ConditionalCheckFailedException:
        return False
    return True


def consume_quota(caller: str, day: str, limit: int, expires_at: int) -> bool:
    """Atomically counts one job for `caller` today; False once the daily
    `limit` is reached."""
    try:
        table().update_item(
            Key={
                "pk": f"QUOTA#{caller}#{day}"
            },
            UpdateExpression="ADD #count :one SET #ttl = :ttl",
            ConditionExpression=(Attr("count").not_exists()
                                 | Attr("count").lt(limit)),
            ExpressionAttributeNames={
                "#count": "count",
                "#ttl": "ttl",
            },
            ExpressionAttributeValues={
                ":one": 1,
                ":ttl": expires_at,
            },
        )
    except table().meta.client.exceptions.ConditionalCheckFailedException:
        return False
    return True
