# I-8 in slices: overview

Prepared 2026-11-14. Repository this repository, branch `m1-iphone`,
baseline commit `b8e3778` (onboarding account fields built: `account_onboarding`, `GET` / `PUT
/me/onboarding`, the 422 key-name fix). HEAD may be one commit ahead: the commit that adds these files.

I-8 (`docs/05-backlog.md`) replaces the I-22 dev token with real sign-in and is estimated at 6–10 days.
It's split here into seven slices, each with its own handoff. Each one is a working, tested state of the
backend, so the work can stop after any slice without leaving the API half-migrated.

## Slices

| # | Handoff | Builds | Depends on | Who |
|---|---|---|---|---|
| S1 | [Identity foundation](s1-identity-foundation.md) | Alembic, `users` and `memberships`, Logto JWT verification, GUARD in place of `current_tenant`, `account_onboarding.account_id` → `users.id` | — | Backend agent |
| S2 | [Session bootstrap](s2-session-bootstrap.md) | `POST /session` for email one-time code: first sign-in creates the user, the tenant and the owner membership; the response carries `onboarding` | S1 | Backend agent |
| S3 | [Row-level security](s3-row-level-security.md) | Separate owner and app roles, `FORCE`d RLS on every tenant table, `SECURITY DEFINER` functions for pre-tenant lookups and the queue, cross-tenant tests on every route and job | S1, S2 | Backend agent |
| S4 | [Google and Apple sign-in](s4-google-apple-sign-in.md) | Native Google and Apple: backend code exchange, `link_required`, backend-owned linking (O-19), encrypted Apple refresh token, parked tokens | S2, S3; starts with a check of how a native credential becomes a Logto session | Backend agent; the live Apple check needs S7's HTTPS domain |
| S5 | [Account deletion](s5-account-deletion.md) | `DELETE /me` through 03a P8: projects, onboarding row, Apple revocation, Logto user deletion, tombstone | S2, S3 (S4 for the Apple step) | Backend agent |
| S6 | [Cost and abuse controls](s6-cost-and-abuse.md) | Per-tenant monthly spend cap, global spend cap as kill switch, rate limits, sign-up cap per IP, telemetry allow-list | S1 (S2 for the sign-up cap) | Backend agent |
| S7 | [IONOS deployment](s7-ionos-deployment.md) | Logto and the API on IONOS: TLS, Postgres with backups and a restore test, transactional email, token lifetimes, MFA policy, patching | D-8's open IONOS checks | Owner, with an agent for scripts |

Order: S1 → S2 → S3 → S4 → S5. S6 can follow S1 at any point; S7 runs alongside on the owner's side
and must be done before anything is reachable from the internet. **Two writers never work in the same
files at once:** S1–S5 all touch `domain/`, migrations and `api/auth.py`, so they run one after the other.
S6 can run in parallel only in its own worktree, after S1 has landed.

The app side (sign-in screens, the `link_required` prompt, account deletion in the app, first-launch
gating on `onboarding`, replacing the stored dev token) is I-18 and is not in these slices.

## Decisions these handoffs make

The owner approves these by sending the handoffs. Veto any of them first.

1. **Alembic is added** (S1), with its dependencies, hash-pinned like the rest of `requirements.txt`.
   This is the one new backend dependency in I-8; I-22 deferred migrations to here.
2. **The dev token stays for local use and tests only**, behind an explicit setting that a deployed
   config refuses. It goes through the same GUARD path as a real token (a seeded user and membership),
   so the 700+ existing tests keep running and exercise the membership check.
3. **`users` holds one Logto subject, not a list** (03 §5 says `idp_subjects[]`). D-8 C4 showed that a
   linked Google identity signs in as the existing Logto user (same `sub`), so linked identities live in
   Logto, not in our table.
4. **`users` has no `tenant_id`.** It's the one pre-tenant table, read only through narrow lookups
   (03 §6 already names "user by subject or email" as one). Recorded in 03 §5 as the exception.
5. **No email in our database in S2.** Logto holds it. S4 decides whether `link_required` needs a local
   copy or can ask Logto's Management API; the default is not to store it (data minimisation).
6. **No invites or teams in v1** (I-8: "No teams in v1"). 03a P1's invite branch, `POST /team/*` and
   `DELETE /team` aren't built. Every first sign-in creates its own tenant, with the user as owner.
7. **The global cap is the owner's monthly EUR 50** (06, 2026-11-13), which supersedes "global daily
   kill switch" in 03 §6; S6 corrects 03. The per-tenant monthly cap starts at **EUR 5** (about 3× the
   cost of 20 typical comparisons, per 03 §8's 3× rule) as a config value; change it before S6 if you
   want another number.

## Open questions that block a slice

| Question | Blocks | Default if unanswered |
|---|---|---|
| How does a native Apple or Google credential become a Logto session (Experience API social verification, token exchange, or another path)? | S4 | S4 starts with a time-boxed check against the local Logto in `scripts/d8-logto` and stops with a written finding if there's no supported path |
| D-8's open IONOS checks: server, PITR, encryption at rest, DPA coverage | S7 | S7 doesn't start |
| Transactional email provider for one-time codes | S7 | None: the owner chooses |
| Public domain names for the API and Logto | S4 (Apple), S7 | None: the owner chooses |

## Rules for every slice

- Read the slice's handoff, then the docs it names, then the code. Verify `git status` and HEAD first.
  Untracked tool folders (`.claude-flow/`, `app/.claude-flow/`, `.playwright-mcp/`) aren't yours.
- No document content in tables, logs, errors, metric labels or test fixtures beyond the synthetic
  helpers (AC-23). Error bodies never echo request input (`api/errors.py`).
- Tokens, subjects, emails and Apple tokens never go into logs, problem bodies or test output.
- Secrets come from the environment or a file named by it, never from the repository (03 §6).
- No app changes. No dependency beyond the one named in the slice. No commit, push or deploy unless the
  owner says so.
- Run the backend unit tests, the integration tests (`docker compose up -d --wait` in `backend/`) and
  `./scripts/ci.ps1`. Say which ran and which were skipped.
- Update only the plan documents the slice names, plus one change-log row in 06. Don't change AC text or
  decision rows.
- Return the changed files with a diff stat, test counts before and after, the CI output, any deviation
  from the handoff with the reason, and precise blockers.
