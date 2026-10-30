# ADR 0013: Cross-tenant access returns not_found (AD-6)

**Status:** Accepted (2026-10-30)

## Context

A forbidden response reveals that a resource ID exists.

## Decision

Any access to another tenant's resource returns `not_found`.

## Consequences

Uniform authorisation tests: every cross-tenant case asserts the same response.

## Links

03 §9.6 AD-6; AC-19. Process for changing this record: `docs/SOP.md`.
