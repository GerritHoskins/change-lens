# ADR 0012: REST + JSON with an OpenAPI-generated Dart client (AD-5)

**Status:** Accepted (2026-10-30)

## Context

The client and backend use different languages and need a typed contract.

## Decision

Expose a REST API with problem+json errors; generate the Dart client from the OpenAPI schema.

## Consequences

No GraphQL or gRPC infrastructure. Contract changes surface as client compile errors.

## Links

03 §9.4, §9.6 AD-5. Process for changing this record: `docs/SOP.md`.
