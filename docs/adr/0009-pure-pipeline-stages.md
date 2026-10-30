# ADR 0009: Pipeline stages are pure functions; the worker owns persistence (AD-2)

**Status:** Accepted (2026-10-30)

## Context

Gate 2 measures pipeline quality on a labelled set; the product must run the same code.

## Decision

parse, extract, align, compare, verify and report are pure functions with no database or storage access. The worker loads inputs and persists outputs.

## Consequences

The prototype and the product share one implementation, so Gate 2 results apply to production.

## Links

03 §9.3, §9.6 AD-2. Process for changing this record: `docs/SOP.md`.
