#!/bin/sh
# SageMaker contract: endpoints run the image with `serve`.
# One gunicorn worker (one model copy in GPU memory) with threads, so /ping
# keeps answering while a job runs for minutes. The endpoint config sets
# MaxConcurrentInvocationsPerInstance=1.
set -e

case "$1" in
  serve)
    exec gunicorn src.serving.serve:app \
      --bind "0.0.0.0:${SAGEMAKER_BIND_TO_PORT:-8080}" \
      --workers 1 \
      --threads "${MODEL_SERVER_THREADS:-4}" \
      --timeout "${MODEL_SERVER_TIMEOUT:-3600}" \
      --access-logfile -
    ;;
  *)
    exec "$@"
    ;;
esac
