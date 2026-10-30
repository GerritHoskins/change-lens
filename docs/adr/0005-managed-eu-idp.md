# ADR 0005: Managed identity provider with EU residency

**Status:** Superseded by ADR-0020 (2026-10-30): self-hosted Logto on IONOS instead of a managed provider

## Context

MFA, token rotation and session revocation are security-critical and costly to build. The owner chose a managed provider.

## Decision

Use a managed identity provider with EU (preferably German) data residency. Sign-in: email one-time code, Google, Sign in with Apple. FastAPI only verifies JWTs. Vendor picked in D-8.

## Consequences

Vendor dependency and DPA review. Apple requires Sign in with Apple because Google login is offered. Account linking must never merge tenants (AC-26).

## Links

03 §1.1; O-4; AC-26. Process for changing this record: `docs/SOP.md`.
