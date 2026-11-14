# I-8 S3: row-level security

Part of [I-8 in slices](README.md). Needs S1 and S2 merged. Check `git status` and HEAD first.

## 1. Goal

Make Postgres enforce tenant isolation as a second layer below the repository code (ADR-0004, 03 §6
Tenant isolation, AC-19). After this slice, a query that forgets its `tenant_id` filter still can't return
another tenant's rows, for both the api and the worker.

## 2. What exists

- Every tenant table has `tenant_id`, and `TenantRepo` filters on it. `tenant_scope()` already runs
  `set_config('app.tenant_id', …, true)` (transaction-local), so policies can read it without changing
  callers.
- One database role owns the tables and runs everything. There are no policies.
- Pre-tenant access goes through `Database.system_session()`, a plain session with no tenant:
  - the worker's queue loop (`jobs.reclaim_expired`, `claim`, `retry_or_fail`, `complete` in `worker/`);
  - `Database.pending_object_writes`;
  - `domain/retention.py` `maintenance_snapshot`;
  - S1's user and membership lookups and S2's first-sign-in creation.

## 3. Roles

Created by a migration (or a documented bootstrap script where Alembic can't create roles), with
passwords supplied by the environment, never committed:

| Role | Used by | Rights |
|---|---|---|
| `changelens_owner` | Migrations only | Owns tables and functions. Not used by any running process |
| `changelens_app` | `api`, `worker`, `retention` | `SELECT`, `INSERT`, `UPDATE`, `DELETE` on tenant tables; `EXECUTE` on the functions below. Not an owner, no `BYPASSRLS`, no direct rights on `users` |

`Settings` gains a separate migration URL; the running processes use the app role's URL. The local
`docker-compose.yml` and the integration conftest create both roles, so tests run as the app role.

## 4. Policies

On every table with `tenant_id` (today: `projects`, `source_versions`, `object_write_intents`,
`comparisons`, `comparison_cost_tombstones`, `object_purge_intents`, `project_deletions`, `findings`,
`fact_cache`, `jobs`, `review_events`, `client_approvals`, `account_onboarding`, `memberships`):

- `ENABLE` and `FORCE ROW LEVEL SECURITY`.
- One policy for all commands: `tenant_id = current_setting('app.tenant_id', true)::uuid`, in both
  `USING` and `WITH CHECK`. With no tenant set, the setting is null and the policy matches no rows.

`users` gets RLS with no policy for the app role (nothing visible directly); it's read and written only
through the functions below.

Add a CI-style test that lists every table in the schema and fails if one has `tenant_id` but no forced
policy, or is neither covered nor on an explicit exception list (`users`, Alembic's version table). A
future table then can't skip RLS silently.

## 5. Pre-tenant functions

Narrow `SECURITY DEFINER` functions owned by `changelens_owner`, with `SET search_path` pinned, taking and
returning IDs and scalar fields only (03 §6: "never the migration role"):

| Function | Replaces | Returns |
|---|---|---|
| `session_lookup(subject)` | S1's user and membership lookup | user ID, tenant ID, role, or nothing for a missing, deleted or membership-less user |
| `session_bootstrap(subject)` | S2's first-sign-in creation | the same, creating the user, tenant and membership idempotently |
| Queue: claim, reclaim expired, retry or fail, complete | `system_session()` in `worker/` and `jobs/` | job ID, tenant ID, kind and IDs, as today (payloads are already ID-only) |
| `pending_object_writes(now, limit)` | `Database.pending_object_writes` | (tenant ID, intent ID) pairs |
| `maintenance_candidates(now, limit)` | `maintenance_snapshot` | the three lists of (tenant ID, ID) it returns today |

After the IDs come back, all reads and writes run under `tenant_scope` as today. Remove
`system_session()`, or leave it only for tests that set up data as the owner role, named so that
production code can't call it by mistake.

## 6. Plan documents to update

| File | Change |
|---|---|
| `docs/03-technical-design.md` §5 and §6 | Name the two roles, the forced policies, the function list and the exception list |
| `docs/03a-pipeline-logic.md` P0 | GUARD's lookup is `session_lookup`; the `SET LOCAL` line is now enforced by policy |
| `docs/adr/0004-postgres-rls-queue.md` | Only if the queue functions change the decision as written; otherwise leave it |
| `backend/README.md` | Role setup for local development and how tests run as the app role |
| `docs/06-decision-log.md` | One change-log row |

## 7. Out of scope

Google and Apple (S4), deletion routes (S5), rate limits (S6), the IONOS database setup (S7), app code.

## 8. Tests

1. **Policy coverage**: the table-listing test in §4.
2. **Direct SQL as the app role**: with no tenant set, every tenant table returns zero rows and rejects
   inserts; with tenant A set, only A's rows come back, and an insert or update with tenant B's ID fails.
   `users` returns nothing directly.
3. **A deliberately unfiltered query** (a test-only repository call that omits the `tenant_id` filter)
   returns only the current tenant's rows.
4. **Every route**: for each route in the OpenAPI schema that takes a resource ID, tenant B's request for
   tenant A's resource returns `404 not_found` (AC-19, ADR-0013). Generate the list from the app's routes so
   a new route is covered automatically, with an explicit list of routes that take no resource ID.
5. **Every job kind**: a parse or compare job whose IDs belong to tenant A, run with tenant B set, finds
   nothing and changes nothing.
6. **Worker and retention**: the full integration suite passes with the processes running as
   `changelens_app`.
7. **Functions**: each `SECURITY DEFINER` function rejects or ignores input it shouldn't accept, and none
   returns more than the columns in §5.
8. **Gates**: backend unit and integration tests and `./scripts/ci.ps1` pass.

## 9. Receiving-agent prompt

> Work in the ChangeLens checkout on `m1-iphone`, with I-8 S1 and S2 merged. Verify `git status` and HEAD.
> Read `docs/i8/README.md` and `docs/i8/s3-row-level-security.md`, then ADR-0004 and ADR-0013, 03 §5 and §6,
> 03a P0, and `backend/changelens/domain/`, `jobs/`, `worker/`, `retention/` and the migrations. Add the
> owner and app roles, forced RLS on every tenant table, and the `SECURITY DEFINER` functions for
> pre-tenant access, as specified, with no new dependency. Don't build Google, Apple, deletion routes, rate
> limits or app code. Don't commit or push. Write the §8 tests, run the backend unit and integration tests
> and `./scripts/ci.ps1`, and return the evidence the overview lists or a precise blocker.
