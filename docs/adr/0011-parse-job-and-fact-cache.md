# ADR 0011: Parse is its own job; facts are cached per version (AD-4)

**Status:** Accepted (2026-10-30)

## Context

Successive revisions of one project would otherwise re-extract the same version.

## Decision

Parsing runs as a separate job when a version is uploaded. Extracted facts are cached per version and reused by later comparisons.

## Consequences

Lower cost per comparison (03 §8). Parse warnings reach the user before a comparison starts.

## Links

03 §9.6 AD-4. Process for changing this record: `docs/SOP.md`.
