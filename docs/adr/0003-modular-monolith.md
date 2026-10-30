# ADR 0003: FastAPI modular monolith with api and worker processes (AD-1)

**Status:** Accepted (2026-10-30)

## Context

Pilot scale is 5–10 accounts. The pipeline needs background processing; the product needs one database to secure and back up.

## Decision

One Python package (FastAPI, Pydantic, SQLAlchemy, Alembic) deployed as two process types: `api` and `worker`.

## Consequences

Simple deployment and testing. Splitting into services is deferred until measurements require it.

## Links

03 §9.1, §9.6 AD-1. Process for changing this record: `docs/SOP.md`.
