# I-8 S7: IONOS deployment

Part of [I-8 in slices](README.md). This slice is the **owner's**: it creates servers, accounts, domains and
keys, which only the owner can do. An agent can write the configuration and scripts (§6), but never logs
in to IONOS, Apple, Google or an email provider, and never deploys.

## 1. Goal

Run Logto, the API, the worker and the retention process on IONOS in Germany (ADR-0020, ADR-0006), in a
state fit for real sign-ups:

- reachable only over TLS, with the Logto admin console closed to the internet;
- Postgres with daily backups, a retention of at most 30 days and a restore test;
- transactional email for one-time codes;
- token lifetimes, MFA and audit-log retention set as decided;
- a patch routine for Logto and PDFium within 7 days (03 §6).

Nothing in this slice makes the service public. Sign-ups open only after S1–S6 are merged and the
release gates in 05 (I-13, I-17, I-20) allow it.

## 2. Before starting

| Item | Status | Needed for |
|---|---|---|
| D-8's open IONOS checks: server, PITR, encryption at rest, DPA coverage (06, D-8 row) | Open | Everything |
| Domain names for the API and for Logto | Owner to choose | TLS, Apple, Google |
| Transactional email provider, in the EU, with a DPA | Owner to choose | One-time codes. It's a new sub-processor: add it to the data inventory and I-20's list |
| Apple developer account: Services ID, Sign in with Apple key (`.p8`), domain verification | Owner | S4's live Apple check |
| Google Cloud OAuth clients for iOS, Android and the server | Owner | S4 |

## 3. Setup checklist

1. **Server.** One IONOS server in Germany, sized per 03 §1.2. OS updates on; SSH by key only and from the
   owner's addresses; firewall open for 443 (and 80 only for certificate renewal).
2. **TLS and proxy.** A reverse proxy terminates TLS for the API and Logto's sign-in endpoints. The Logto
   admin console listens on localhost only (reach it through an SSH tunnel). The proxy's address is S6's
   trusted proxy; access logs record no query strings or bodies.
3. **Postgres.** Separate databases for Logto and ChangeLens. ChangeLens uses S3's two roles: migrations run
   as `changelens_owner`, the processes as `changelens_app`. Daily backups and PITR kept at most 30 days
   (03 §6 Retention). Run a restore into a scratch database and record the date and result. A restored
   database must not serve traffic before pending deletions are replayed (data inventory).
4. **Object storage.** A private bucket in Germany with versioning off (03a P8). Record whether the
   provider encrypts at rest.
5. **Logto.** Pin the image by digest at 1.45.0 or later (later than 1.37.1 is required; D-8 tested 1.45.0).
   Configure: email one-time code as the identifier and verification; Google and Apple on S4's path; the
   API resource with a 900-second access token (D-8 C5 found 1 hour by default); refresh tokens with
   rotation; MFA (TOTP and backup codes) offered to users, not forced (03a P1); automatic account linking
   off. Watch for the SMTP connector gotcha in D-8 (an empty `auth: {}` saved as no field).
6. **Logto audit logs.** The open-source build never prunes them, and each entry holds an IP and a user
   agent (D-8 C5). Schedule a deletion of entries older than 30 days, and add this store to the data
   inventory (I-13).
7. **ChangeLens processes.** `api`, `worker` and `retention` with `CHANGELENS_AUTH=logto`, the issuer,
   audience and JWKS URL from S1, and secrets from files readable only by the service user: database
   passwords, S3 keys, the IONOS model key, the Apple `.p8` key and token keyring, the Google client secret
   and the Logto Management API credential (03 §6 Secrets). The worker's outbound network is limited to the
   model API and storage (03 §6).
8. **Monitoring.** Uptime checks for the API and Logto, an alert on S6's global-cap event, disk and backup
   failure alerts, and a calendar reminder for the 7-day patch rule.

## 4. Evidence to record

One decision-log row (06) with what was set up and verified, with dates: the D-8 IONOS answers; the
restore test; the token lifetime as observed in a real token's `exp - iat`; MFA working with a test
account; a one-time code delivered by the provider; Google and Apple sign-in on S4's path; the admin
console unreachable from outside; the audit-log pruning job's first run. Update `docs/data-inventory.md`
for the email provider, Logto's database and audit logs, backups and PITR.

## 5. Out of scope

Opening sign-ups, store releases (I-17), the privacy policy and terms (I-20), and the fair-use allowance
(I-14).

## 6. What an agent can do for this slice

Only when the owner asks, and without any credentials:

- write the deployment configuration under `deploy/ionos/` (compose or service files, proxy config, backup
  and restore scripts, the audit-log pruning job), with every secret read from a file path and none in the
  repository;
- write the runbook steps for the checklist above, in the format of `scripts/d8-logto/CHECKLIST.md`;
- review the owner's recorded evidence against §4.

> Work in the ChangeLens checkout on `m1-iphone`. Verify `git status` and HEAD. Read `docs/i8/README.md`
> and `docs/i8/s7-ionos-deployment.md`, then ADR-0006 and ADR-0020, 03 §1.2 and §6, the D-8 rows in 06,
> `docs/data-inventory.md` and `scripts/d8-logto/`. Write the deployment configuration and runbook in §6,
> with no secrets and no network access to IONOS or any provider. Don't deploy, don't create accounts,
> don't commit or push. Run `./scripts/ci.ps1` and return the files with a diff stat and anything that
> needs the owner.
