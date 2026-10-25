import base64
import json


def json_response(status_code: int,
                  body: dict,
                  cache_control: str = "no-store") -> dict:
    """API Gateway (HTTP API) proxy response. CORS headers are added by the
    HTTP API itself (serverless/api)."""
    return {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Cache-Control": cache_control,
        },
        "body": json.dumps(body, ensure_ascii=False),
    }


def parse_body(event: dict):
    """JSON body of an HTTP API event (None when it isn't valid JSON)."""
    body = event.get("body") or "{}"
    if event.get("isBase64Encoded"):
        body = base64.b64decode(body).decode("utf-8")
    try:
        return json.loads(body)
    except json.JSONDecodeError:
        return None


def source_ip(event: dict) -> str:
    return (event.get("requestContext", {}).get("http", {}).get("sourceIp") or
            "unknown")
