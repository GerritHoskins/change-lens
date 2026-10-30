# ADR 0001: iOS and Android app; no web front end

**Status:** Accepted (owner decision) (2026-10-30)

## Context

The handoff left the platform open and said not to assume native mobile (§14). The owner decided ChangeLens is a mobile app.

## Decision

ChangeLens ships as an iOS and Android app. The only web surface is the read-only page for shared reports (ADR-0015), because recipients may not have the app.

## Consequences

Share-sheet and camera import become MVP features (O-3, AC-24). Store review applies to every release. App-store billing rules must be checked before public launch (ADR-0018).

## Links

06 owner decisions; 02 §1; AC-24. Process for changing this record: `docs/SOP.md`.
