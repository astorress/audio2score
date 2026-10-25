"""GET /instruments: instrument catalog, modes, defaults and limits."""
from src.contract import jobs
from src.utilities.http import json_response


def handler(event, context):
    return json_response(200,
                         jobs.catalog_response(),
                         cache_control="public, max-age=3600")
