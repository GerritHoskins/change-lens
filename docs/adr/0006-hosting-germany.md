# ADR 0006: Host in Germany on IONOS

**Status:** Accepted (2026-10-30): IONOS, chosen by the owner and already provisioned

## Context

Client briefs are confidential and pilot terms promise a processing location. The owner chose Germany and excluded Hetzner.

## Decision

Host the API, worker, managed Postgres and S3-compatible storage in Germany. The owner chose IONOS in Germany and has provisioned it. D-8 still checks the IONOS bundle against the 03 §1.2 minimum spec, the managed-Postgres PITR retention (≤ 30 days, SA-7) and the IONOS DPA and sub-processors.

## Consequences

No self-managed database. Mobile CI runs elsewhere (macOS runners).

## Links

03 §1.1, §1.2; O-4. Process for changing this record: `docs/SOP.md`.
