# ADR 0016: Push notification plus polling for comparison status (AD-8)

**Status:** Superseded by ADR-0022 (2026-11-06). Accepted on 2026-10-30.

## Context

Comparisons are asynchronous; users should not have to wait in the app.

## Decision

Send a content-free push (FCM / APNs) on completion; the app also polls comparison status as a fallback.

## Consequences

Works with notifications disabled. No WebSocket infrastructure.

## Links

03 §9.6 AD-8; AC-25. Process for changing this record: `docs/SOP.md`.
