# ADR 0004: PostgreSQL with row-level security and a Postgres-backed job queue

**Status:** Accepted (2026-10-30)

## Context

Tenant isolation must hold for the API and the worker (AC-19). A separate queue system adds another store to secure.

## Decision

Every table has `tenant_id`; RLS is enforced with `SET LOCAL app.tenant_id` per request and per job; the worker never uses an RLS-bypassing role. Jobs use a Postgres-backed queue with ID-only payloads.

## Consequences

Isolation has a second layer below application code. Queue throughput is bounded by Postgres, which is ample at pilot scale.

## Links

03 §5, §9.1; AC-19, AC-23. Process for changing this record: `docs/SOP.md`.
