# The ChangeLens backend image: api, worker, retention and the one-off database tools (I-8 S7).
# Build context: backend/. Dependencies install from hash-pinned wheels only (requirements.txt).
FROM python:3.10.19-slim-bookworm@sha256:23f63358922e79a794f71be8f3723c84e5ccca9638af3f74456dc73d6184499e

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app
COPY requirements.txt .
RUN pip install --require-hashes -r requirements.txt

COPY alembic.ini .
COPY migrations ./migrations
COPY changelens ./changelens

RUN useradd --system --uid 10001 --no-create-home changelens
USER changelens
