# ADR 0022: Polling in v1, push deferred until after v1 (AD-8)

**Status:** Accepted (owner decision O-18, 2026-11-06). Supersedes ADR-0016.

## Context

ADR-0016 planned a content-free push on completion, with polling as the fallback. The 2026-10-31 re-plan (2ae74c0) removed push from I-9 and gave it no other task, with no decision-log entry, so AC-25 failed re-verification on 2026-11-06.

## Decision

v1 has no push notifications. The app refreshes comparison status by polling (I-24). Push stays designed, as a content-free message with a comparison ID and generic text, and is deferred as I-27. The AC-25 clause on push notifications applies once push exists; its text does not change.

## Consequences

Users learn that a comparison finished only by opening the app. There is no device registry, no `POST /devices` route and no FCM or APNs keys in v1, so these leave the v1 data inventory until I-27. If I-27 is built, it must meet AC-25 and be added to the data inventory, the privacy policy and the store declarations.

## Links

O-18; 05 I-24, I-27; 03 §9.6 AD-8; 03a P9 NOTIFY; AC-25; ADR-0016. Process for changing this record: `docs/SOP.md`.
