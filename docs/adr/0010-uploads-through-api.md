# ADR 0010: Uploads go through the API (AD-3)

**Status:** Accepted (2026-10-30)

## Context

Presigned direct-to-storage uploads skip server-side validation until after storage.

## Decision

Uploads are multipart requests to the API, which checks limits, type and magic bytes before storing.

## Consequences

The API carries upload bandwidth; acceptable at pilot volume (≤ 10 MB per file).

## Links

03 §9.6 AD-3; AC-20. Process for changing this record: `docs/SOP.md`.
