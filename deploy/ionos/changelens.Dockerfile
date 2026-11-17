# The ChangeLens backend image: api, worker, retention and the one-off database tools (I-8 S7).
# Build context: backend/. Dependencies install from hash-pinned wheels only (requirements.txt).
FROM python:3.14.10-slim-bookworm@sha256:3fe1a0b6c2d6b2ebb572906cdabeca75aeb558c0c17db5ffefbcf8094871c32b

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

# The group is fixed at 10001 too: the sign-in secrets on the host are root:10001 (README C8). Without --gid,
# useradd --system gives the user a system group (gid below 1000), which can't read them.
RUN groupadd --system --gid 10001 changelens \
    && useradd --system --uid 10001 --gid 10001 --no-create-home changelens
USER changelens
