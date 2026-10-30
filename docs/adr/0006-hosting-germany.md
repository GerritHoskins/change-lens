# ADR 0006: Host in Germany; OVHcloud or IONOS

**Status:** Proposed: region decided, vendor open (D-8) (2026-10-30)

## Context

Client briefs are confidential and pilot terms promise a processing location. The owner chose Germany and excluded Hetzner.

## Decision

Host the API, worker, managed Postgres and S3-compatible storage in Germany. D-8 prices the minimum bundle (03 §1.2) at OVHcloud and IONOS and picks the cheaper.

## Consequences

No self-managed database. Mobile CI runs elsewhere (macOS runners).

## Links

03 §1.1, §1.2; O-4. Process for changing this record: `docs/SOP.md`.
