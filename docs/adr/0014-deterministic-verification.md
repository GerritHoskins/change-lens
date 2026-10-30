# ADR 0014: Deterministic evidence verification and unexplained-difference listing

**Status:** Accepted (from security review) (2026-10-30)

## Context

The author of a newer brief can steer the model into dropping or mislabelling changes. Checking quotes alone cannot detect a missing finding.

## Decision

Every evidence quote must match the source exactly at its locator. A deterministic block diff lists every changed block no finding explains. Hidden text is flagged. Numeric, negation and modality changes are guarded deterministically.

## Consequences

The model is never the only line of defence. The pattern follows `mobile-engineering-intelligence/app/llm/citations.py`.

## Links

03 §2, §4.1, §6; AC-9, AC-10, AC-18. Process for changing this record: `docs/SOP.md`.
