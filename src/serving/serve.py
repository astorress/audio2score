"""Worker server for the SageMaker async endpoint (custom image,
`docker run <image> serve` → gunicorn serve:app on port 8080).

SageMaker's hosting contract:
    GET  /ping         200 when the container is up (models load lazily on
                       the first job, they're baked into the image)
    POST /invocations  the job request (src.contract.jobs.worker_request),
                       read by SageMaker from the async InputLocation
"""
import json

from flask import (
    Flask,
    Response,
    request,
)

from src.contract.jobs import ContractError
from src.serving.worker import handle
from src.utilities.logger import get_logger

logger = get_logger(__name__)

app = Flask(__name__)


def json_body(body: dict, status: int) -> Response:
    return Response(json.dumps(body, ensure_ascii=False),
                    status=status,
                    mimetype="application/json")


@app.get("/ping")
def ping():
    return Response(status=200)


@app.post("/invocations")
def invocations():
    try:
        payload = json.loads(request.get_data() or b"{}")
        return json_body(handle(payload), 200)
    except (ContractError, KeyError, json.JSONDecodeError) as error:
        logger.exception("Invalid job request")
        return json_body({
            "error": f"Invalid job request: {error}"
        }, 400)
    except Exception as error:
        logger.exception("Job failed")
        return json_body({
            "error": str(error)
        }, 500)
