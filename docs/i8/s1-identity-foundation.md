# I-8 S1: identity foundation

Part of [I-8 in slices](README.md). Read the overview's decisions and rules first. Baseline `b8e3778`;
check `git status` and HEAD before starting.

## 1. Goal

Replace the dev-token tenant lookup with the real request guard (03a P0) without changing what any route
does. After this slice:

- Requests carry a Logto access token, verified offline against Logto's JWKS.
- GUARD maps the token's subject to a user and that user's active membership, and the tenant comes from
  the membership, never from the request.
- The schema is managed by Alembic, with `users` and `memberships` tables.
- `account_onboarding.account_id` is a foreign key to `users.id`, and the onboarding routes use the user ID.

Nobody can sign up yet: users come from test fixtures and the dev seed. `POST /session` is S2.

## 2. What exists

- `api/auth.py` `current_tenant` maps a bearer dev token to a tenant (`config.py` `dev_tokens`). Every
  route takes `tenant: uuid.UUID = Depends(current_tenant)`.
- `auth/jwt_verifier.py` `JwtVerifier` verifies a token against a **static** trusted JWKS and returns
  `VerifiedIdentity(subject, …)`. It has unit tests (`tests/unit/test_jwt_verifier.py`). Nothing fetches
  or refreshes keys yet.
- `Database.create_schema()` runs `create_all` plus `DEV_COLUMNS` (`domain/__init__.py`). The integration
  conftest drops and rebuilds the schema on every run.
- `api/onboarding.py` `_account(tenant)` returns the tenant ID. `api/reviews.py` writes `actor=DEV_ACTOR`.
- `httpx`, `PyJWT[crypto]` and `cryptography` are already pinned in `backend/requirements.txt`.

## 3. Migrations

Add Alembic under `backend/` (for example `backend/migrations/`), pinned with hashes in
`requirements.txt` like every other package, with its own dependencies. No other new dependency.

1. **Baseline revision**: the current schema exactly, including every `DEV_COLUMNS` change and
   `account_onboarding`. A fresh database built by `upgrade head` must match the models: add a test that
   compares them (Alembic's autogenerate comparison returns no differences).
2. **Identity revision**: `users`, `memberships`, and the foreign key from `account_onboarding.account_id`
   to `users.id`. There are no real accounts, so the revision deletes `account_onboarding` rows that have
   no matching user (dev data only), and says so in its docstring and the 06 row.
3. `create_schema()` and `DEV_COLUMNS` go away. The api and worker don't migrate on start; a documented
   command does (`backend/README.md`). An existing dev database built by `create_all` is brought under
   Alembic by `stamp` of the baseline after a check that it matches; document both steps.
4. The integration conftest builds the test database with `upgrade head`, so every run exercises the
   migrations.

## 4. Data

| Table | Columns | Rules |
|---|---|---|
| `users` | `id` UUID PK; `idp_subject` text, unique, not null, at most 200 chars; `created_at`; `deleted_at` nullable | One Logto subject per user (overview, decision 3). No `tenant_id` (decision 4). No email (decision 5). S4 adds the Apple token column; S5 defines the tombstone |
| `memberships` | `user_id` FK `users.id`; `tenant_id` UUID; `role` `owner` / `member`; `status` `active` / `inactive`; `created_at` | PK (`user_id`, `tenant_id`). At most one active membership per user (partial unique index): v1 has one tenant per account. CHECK constraints on role and status |

Repository functions for the lookup live outside `TenantRepo`, because they run before a tenant is known:
`user_by_subject(subject)` and `active_membership(user_id)`. They read through a plain session for now;
S3 moves them into `SECURITY DEFINER` functions. Keep them in one small module so S3 has one place to change.

## 5. Authentication

**Settings.** Add `auth_mode` (`dev` or `logto`), `logto_issuer`, `logto_audience` (the API resource
indicator) and `logto_jwks_url`. `from_env` refuses `dev` unless `CHANGELENS_ENV=local`, and refuses
`logto` without issuer, audience and an `https` JWKS URL. Keep the env-var names in `backend/README.md`.

**Keys.** A small key holder fetches the JWKS from the configured URL only (never from a token header),
with a short timeout and a size cap, builds a `JwtVerifier`, and caches it. An unknown `kid` triggers at
most one refresh per 60 seconds; a failed refresh keeps the cached keys. The api refuses to start in
`logto` mode if the first fetch fails. Fetch failures are logged by exception class only.

**GUARD.** `current_principal(request) -> Principal(user_id, tenant_id, role)`:

1. Verify the bearer token (`logto` mode) or match the dev token (`dev` mode) to a subject.
2. Look up the user by subject; reject if missing or `deleted_at` is set. D-8 found that a deleted user
   stays signed in with cached tokens, so this check runs on **every** request.
3. Look up the active membership; reject if there is none.
4. Any failure is `401 unauthenticated` with `WWW-Authenticate: Bearer`, as today. The body never says
   which step failed.

`current_tenant` stays as a thin dependency returning `current_principal(...).tenant_id`, so the existing
routes don't change. `api/onboarding.py` uses `principal.user_id` as the account ID, and `api/reviews.py`
writes the user ID as `actor` instead of `DEV_ACTOR`.

**Dev mode.** Each dev token maps to a fixed subject (for example `dev:<token-name>`). A documented seed
command creates the matching user and active owner membership for the configured dev tenant. Tests seed
`TOKEN_A` and `TOKEN_B` users for `TENANT_A` and `TENANT_B` in fixtures. Dev mode goes through steps 2–4
like a real token.

## 6. Plan documents to update

| File | Change |
|---|---|
| `docs/03-technical-design.md` §5 | `User`: one `idp_subject`, no `tenant_id` (the pre-tenant exception, with the reason), no email until S4 decides. `Membership`: the one-active-membership rule. `AccountOnboarding`: the FK now exists |
| `docs/03a-pipeline-logic.md` P0 | GUARD also rejects a deleted user, checked on every request (D-8 side finding) |
| `docs/data-inventory.md` | A row for `users` and `memberships`: subject, timestamps, role and status; deleted with the account (S5) |
| `backend/README.md` | Auth settings, migration and stamp commands, the dev seed |
| `docs/06-decision-log.md` | One change-log row, including the dev-row deletion in the identity revision |

## 7. Out of scope

`POST /session` (S2), RLS and database roles (S3), Google and Apple (S4), deletion routes (S5), rate limits
and spend caps (S6), deployment (S7), and any app change.

## 8. Tests

1. **Migrations.** `upgrade head` on an empty database matches the models. Downgrade of the identity
   revision and upgrade again work. A `create_all`-built database stamped at the baseline upgrades cleanly.
2. **JWT path** (unit, with an RSA key generated in the test and the JWKS served through
   `httpx.MockTransport`): a valid token for a seeded user returns 200; expired, wrong issuer, wrong
   audience, `alg: none`, a `jku` header and a garbage token each return `401 unauthenticated`; an
   unknown `kid` triggers one refresh and then succeeds with the new key; a second unknown `kid` within 60
   seconds doesn't refetch.
3. **GUARD.** A valid token for a subject with no user, a deleted user, no membership or an inactive
   membership returns 401. No response or log line contains the token or the subject.
4. **Settings.** `dev` mode outside `CHANGELENS_ENV=local` and `logto` mode with an `http` JWKS URL fail
   at startup.
5. **Regression.** All existing unit and integration tests pass with the seeded dev users. The onboarding
   tests now key the row on the user ID, and `test_onboarding.py`'s SQLite stand-in gains the two tables.
6. **Gates.** Backend unit tests (725 today) and `./scripts/ci.ps1` pass; integration tests (67 today) run.

## 9. Receiving-agent prompt

> Work in the ChangeLens checkout on `m1-iphone`. Verify `git status` and HEAD against `b8e3778` (HEAD may
> be its child that adds `docs/i8/`). Read `docs/i8/README.md` and `docs/i8/s1-identity-foundation.md`,
> then 03 §5 and §6 (Tenant isolation), 03a P0, ADR-0020, the D-8 rows in 06, `backend/changelens/api/`,
> `auth/`, `domain/` and `config.py`. Build S1 as specified: Alembic (the only new dependency, hash-pinned),
> `users` and `memberships`, Logto JWT verification with a refreshing key holder, GUARD as
> `current_principal`, dev mode through the same path, and the onboarding FK. Don't build `POST /session`,
> RLS, Google or Apple, deletion routes or app code. Don't commit or push. Write the §8 tests, run the
> backend unit and integration tests and `./scripts/ci.ps1`, and return the evidence the overview lists or
> a precise blocker.
