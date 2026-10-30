# ADR 0015: Share snapshots with one-time hashed tokens and a web share page (AD-7)

**Status:** Accepted (2026-10-30)

## Context

Recipients may not have the app; a live project view would expose unrelated data.

## Decision

Shares are immutable snapshots of selected findings. The token is shown once and stored hashed. A server-rendered page reads only the snapshot, with no-store, no-referrer, no third-party resources, rate limiting and a 30-day default expiry.

## Consequences

A database leak does not expose links. Revocation takes effect on the next request.

## Links

03 §6, §9.6 AD-7; AC-16, AC-17; O-7. Process for changing this record: `docs/SOP.md`.
