from functools import lru_cache

import boto3


@lru_cache(maxsize=1)
def client():
    return boto3.client("sagemaker-runtime")


def invoke_endpoint_async(endpoint_name: str, input_location: str,
                          inference_id: str, timeout_seconds: int) -> dict:
    """Queues one job on the async endpoint (the request body is read by
    SageMaker from `input_location`)."""
    return client().invoke_endpoint_async(
        EndpointName=endpoint_name,
        ContentType="application/json",
        Accept="application/json",
        InputLocation=input_location,
        InferenceId=inference_id,
        InvocationTimeoutSeconds=timeout_seconds,
    )
