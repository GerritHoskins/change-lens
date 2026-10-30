# ADR 0002: Flutter + Riverpod for the mobile client

**Status:** Accepted, conditional on D-15 (2026-10-30)

## Context

One codebase for both platforms is needed. Candidates were Flutter, React Native + Expo and Kotlin Multiplatform; Capacitor was excluded by the owner.

## Decision

Use Flutter with Riverpod, go_router, Dio and Freezed. It becomes final only if the D-15 proof of concept passes; otherwise React Native + Expo is evaluated against the same five tests.

## Consequences

Dart on the client and Python on the backend: two languages. PDF evidence relies on `pdfrx` (ADR-0007).

## Links

03 §1.1; 05 D-15. Process for changing this record: `docs/SOP.md`.
