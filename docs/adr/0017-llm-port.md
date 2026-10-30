# ADR 0017: Model provider behind an injected port (AD-9)

**Status:** Accepted (2026-10-30)

## Context

The provider is undecided (O-5), and pipeline tests must be deterministic.

## Decision

Stages receive an `llm` port that makes one structured-output call per request, with no tools and no URL fetching. The provider adapter is swappable; tests use stubs.

## Consequences

The provider choice does not touch stage code.

## Links

03 §9.1, §9.6 AD-9; AC-18. Process for changing this record: `docs/SOP.md`.
