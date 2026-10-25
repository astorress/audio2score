# GPU worker image (BYOC) for the SageMaker async endpoint: separation
# (Demucs), transcription (Basic Pitch + drums) and engraving (music21 +
# MuseScore for PDFs). `docker run <image> serve` → HTTP on :8080
# (/ping + /invocations). Model weights are baked into the image so a cold
# start doesn't download them.
# Build context: the project folder. Built and pushed by
# container/build-push.sh; tagged with container/image-version.js.
FROM python:3.11-slim-bookworm

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONPATH=/opt/program \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    TORCH_HOME=/opt/models/torch \
    HF_HOME=/opt/models/huggingface \
    QT_QPA_PLATFORM=offscreen

# ffmpeg/libsndfile: audio decoding. musescore3: MusicXML → PDF.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg libsndfile1 \
        musescore3 fonts-freefont-ttf \
    && rm -rf /var/lib/apt/lists/*

COPY container/requirements.txt /tmp/requirements.txt
RUN pip install -r /tmp/requirements.txt && rm /tmp/requirements.txt

# Demucs weights (Basic Pitch ships its model inside the package).
COPY container/download-models.py /tmp/download-models.py
RUN python3 /tmp/download-models.py && rm /tmp/download-models.py

# Only the worker packages (no Lambdas/scripts): /opt/program/src/...
WORKDIR /opt/program
COPY src/__init__.py src/__init__.py
COPY src/contract/ src/contract/
COPY src/pipeline/ src/pipeline/
COPY src/serving/ src/serving/
COPY src/services/__init__.py src/services/s3.py src/services/dynamodb.py src/services/
COPY src/utilities/ src/utilities/
COPY container/entrypoint.sh /usr/local/bin/entrypoint.sh
RUN chmod +x /usr/local/bin/entrypoint.sh

EXPOSE 8080
ENTRYPOINT ["entrypoint.sh"]
