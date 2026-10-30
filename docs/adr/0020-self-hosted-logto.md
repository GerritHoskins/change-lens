# ADR 0020: Self-hosted Logto on IONOS for sign-in

**Status:** Accepted (2026-10-30). Supersedes ADR-0005.

## Context

ADR-0005 chose a managed identity provider with EU residency and left the vendor to D-8. The D-8 shortlist (06, D-8 comparison) ruled out Firebase, Clerk and Stytch (US-only processing), Supabase (automatic linking by email that cannot be turned off) and Zitadel (no email-code primary login). The best managed option, Ory Network, is a US company that stores data in an unnamed EU country. The owner preferred to keep sign-in data in Germany under the existing IONOS DPA, with no new sub-processor.

## Decision

Run Logto (open source, MPL-2.0) on the existing IONOS servers in Germany, with its own Postgres database. Sign-in: email one-time code, Google, and Sign in with Apple. Apple sign-in is native: the Flutter app uses `sign_in_with_apple`, and the backend exchanges the authorization code with Apple and stores the Apple refresh token encrypted, so account deletion can revoke it (03a P1, P8). FastAPI verifies Logto-issued JWTs against Logto's JWKS, with access tokens of at most 15 minutes.

Conditions, checked in D-8 and tested in I-8:
- Logto later than 1.37.1 (CVE-2026-15611, linking with an unverified email).
- Automatic account linking off. A second identity is linked only after the user signs in with an existing method; if Logto's link prompt does not enforce this, the backend performs the link through the Logto Management API after that sign-in.
- MFA available in the open-source edition (unverified); if it is not, AC-26 needs a decision before I-8.

## Consequences

- Data stays in Germany under the IONOS DPA; no identity sub-processor is added.
- The owner operates an internet-facing login system: security updates within 7 days, backups, transactional email delivery and uptime, with no vendor SLA. I-8 grows by 1–2 days.
- Logto has an official Flutter SDK, but Apple sign-in goes through the native flow above rather than the SDK's browser flow.
- Exit: Logto Cloud EU runs the same software if self-hosting becomes too costly to operate.

## Links

03 §1.1, §5, §6; 03a P1, P8; O-4; AC-26; D-8, I-8. Process for changing this record: `docs/SOP.md`.
