# Onboarding account fields: backend handoff

Prepared 2026-11-14 for the backend agent. Repository:
`C:\Users\Gerrit\job-search\POCs\change-lens`, branch `m1-iphone`, baseline commit `9e7037c`
(onboarding implemented, round-5 copy applied, 24 px margin asserted; no backend change since
`c33bee7`). This is a baseline, not proof that the checkout hasn't changed since: check
`git status` and HEAD first. Untracked tool folders (`.claude-flow/`, `app/.claude-flow/`,
`.playwright-mcp/`) and one older critique snapshot aren't yours: leave them alone. HEAD may be
one commit ahead of `9e7037c`: the commit that updated this handoff.

## 1. Goal

O-23 (`docs/06-decision-log.md`) decided that whether a user has seen onboarding is stored **on
the account, server-side**. Onboarding then shows once per account, not once per device, and
AC-25 ("only auth tokens stored" on the device) stays as written. O-23 also needs a second field,
the **saved step**, so that someone who leaves onboarding halfway resumes where they stopped.

Build these two fields and the routes that read and write them, so the app can gate first launch
on them once sign-in exists. Nothing in the app uses them yet: first-launch gating waits for
sign-in (I-8, I-18), and that wiring is not part of this task.

## 2. What exists today, and where this fits

- **No account or user table.** Auth is the I-22 dev token: `api/auth.py` `current_tenant` maps
  a bearer token to a tenant (`config.py` `dev_tokens`). Every route receives a tenant ID.
- **The account model is planned, not built.** 03 §5 defines `User` (id, idp_subjects, email,
  apple_refresh_token_enc, deleted_at) and `Membership`. 03 §9.4 and 03a P0/P1 define
  `POST /session` as the bootstrap route outside GUARD. All of this arrives with I-8, which
  says "one tenant per account; no teams in v1".
- **Schema bootstrap** is `Database.create_schema()` (`domain/__init__.py`): `create_all` plus
  `DEV_COLUMNS` for columns added to existing tables. There's no Alembic until I-8, and no
  Postgres RLS yet. Isolation is the tenant-scoped repository (`tenant_scope`).

So build a small slice that works under the dev token now and that I-8 adopts without
redesign:

| Concern | Now (I-22) | When I-8 lands |
|---|---|---|
| Who the account is | The tenant from the dev token. The account ID equals the tenant ID, because v1 has one tenant per account | `User.id` from GUARD. The dev stand-in goes away with the dev token |
| Where the state lives | New table `account_onboarding`, keyed by account ID, with `tenant_id` like every table (AC-19) | Same table. `account_id` gains a foreign key to `users.id`, and the table joins RLS with the rest |
| How the app reads it | `GET /me/onboarding` | The same object is also embedded in the `POST /session` response, so the app can route without a second request |

## 3. Data

New model in `domain/models.py`, created by `create_all` (it's a new table, so no `DEV_COLUMNS`
entry):

| Column | Type | Rule |
|---|---|---|
| `account_id` | UUID, primary key | The account. Now the tenant ID; with I-8, `users.id` |
| `tenant_id` | UUID, not null, indexed | Same convention as every table (`_tenant()`) |
| `onboarding_step` | small integer, nullable | The last step the user reached, 1-based. Null when not started or completed |
| `onboarding_completed_at` | timestamptz, nullable | Set once, by the server clock. Never cleared by any route |
| `updated_at` | timestamptz, not null | Server time of the last write |

- **No row means not started.** Create the row on the first write, not on read.
- **No document content and no analytics.** These are UUIDs, a small integer and timestamps
  (AC-23). Don't log them beyond the existing access log, which records only method, route
  template and status.
- **The server doesn't know how many steps the design has.** Accept 1–32 as a sanity bound and
  leave clamping to the app: if a stored step is beyond the current step count, the app resumes
  at the last step. A redesign then needs no backend change.

## 4. API

Both routes use `Depends(current_tenant)` today, swapped for GUARD with I-8 like every other
route. They follow the existing router style (`api/retention.py` is a small example). Errors
use the existing problem+json handler. Add a new code only if no existing one fits, and record
it in 03 §9.4.

### `GET /me/onboarding`

`200 {"completed": bool, "step": int | null}`

- No row: `{"completed": false, "step": null}`.
- Completed: `{"completed": true, "step": null}`.

### `PUT /me/onboarding`

The body has exactly one of `{"step": n}` (1 ≤ n ≤ 32) or `{"completed": true}`. Anything else
gets `422 invalid_request`. The response is `200` with the same object as `GET`.

| Current state | Body | Result |
|---|---|---|
| Not started or in progress | `step: n` | Store `n`. Going back to a lower step is allowed: it's the last step seen |
| Not started or in progress | `completed: true` | Set `onboarding_completed_at` to now and clear `onboarding_step`. Used by Start on the last step and by Skip |
| Completed | either | No change. Return the completed state. Completion can't be undone, so a stale second device can't reopen onboarding |

- **Idempotent.** Repeating a request leaves the same state.
- **Concurrent writes.** Last write wins for `step`. Completion wins over any step write. Use a
  row lock or an upsert with a guard, so a `step` write racing a completion can't clear it.
- **The replay never calls this.** "How ChangeLens works" from the Projects menu reads and
  writes nothing (O-23).
- **No reset route.** Re-showing onboarding after a redesign is not decided. Don't add a
  version field or an admin reset.

### `POST /session` (with I-8, not now)

Record in 03 §9.4 and 03a P1 that an active session's response includes
`"onboarding": {"completed": bool, "step": int | null}`, read in the same transaction. Don't
build `POST /session` here.

## 5. Deletion and retention

- **Account deletion** (03a P8 `DELETE_ACCOUNT`, and `DELETE_TENANT` for every member): delete
  the `account_onboarding` row. It's account data, not content. With the tombstone rule it must
  not survive under the tombstone ID.
- **Project deletion and the 30-day retention** don't touch it: it isn't project data.
- **Data inventory** (`docs/data-inventory.md`): add a row for this table, covering what it
  holds, its owning model and route, and "deleted with the account (P8)".
- Since `DELETE /me` doesn't exist yet, write the deletion as a repository function with a unit
  test, ready for I-8 to call. Don't add a route.

## 6. Plan documents to update

Keep each change to the lines this feature needs. Run `./scripts/ci.ps1` afterwards.

| File | Change |
|---|---|
| `docs/03-technical-design.md` §5 | Add an `AccountOnboarding` record row (account_id, onboarding_step, onboarding_completed_at, updated_at; "Step mutable; completion set once"). Note it belongs to `User` once I-8 exists |
| `docs/03-technical-design.md` §9.4 | Add `GET /me/onboarding` and `PUT /me/onboarding`, and the `onboarding` object in the `POST /session` row |
| `docs/03a-pipeline-logic.md` | P1: the session response carries the onboarding state. P8: `DELETE_ACCOUNT` deletes the onboarding row |
| `docs/data-inventory.md` | The new store row (§5) |
| `docs/05-backlog.md` | Add to I-8's description that `POST /session` returns the onboarding state (O-23), and to I-18's that the app gates first launch on it. Don't create a new task ID |
| `docs/06-decision-log.md` | One change-log row: what was built, which docs changed, and that no AC text changed |

Don't change AC text, O-23, or any other decision row.

## 7. Constraints

- **No document content** in the table, logs, errors or test fixtures beyond the synthetic
  helpers (AC-23). Error bodies never echo request input (existing `errors.py` rule).
- **Tenant isolation** (AC-19): every read and write goes through `tenant_scope`. Another
  tenant's row is never visible.
- **No new dependency**, no Alembic, no RLS work (that's I-8), and no change to `dev_tokens` or
  the auth dependency.
- **No app changes.** `app/lib/api.dart` gains its client call with the I-18 gating work, not here.
- **Out of scope:** analytics consent storage. D-18 tier B consent needs its own record (choice,
  time, policy version) after the I-20 legal review. Don't add a consent field here.
- **No commit, push or deploy.**

## 8. Tests

Follow the existing split: unit tests with `TestClient` in `backend/tests/unit/`, and Postgres
tests in `backend/tests/integration/`. The Postgres tests skip unless `docker compose up -d --wait`
is running in `backend/`.

1. **Unit, routes.**
   - `GET` with no row returns not started.
   - `step` writes store and return the step, including going back.
   - `completed` sets completion and clears the step.
   - After completion, both body kinds leave it completed.
   - Bad bodies get `422 invalid_request`: both fields, neither, step 0 or 33, wrong types, or
     `completed: false`.
   - A request without a token gets `401 unauthenticated`.
   - Error bodies don't echo input.
2. **Integration, isolation.** With `TOKEN_A` and `TOKEN_B` from `tests/helpers.py`:
   - A's state is invisible to B, and B's writes don't change A's.
   - Each tenant's first write creates its own row.
3. **Integration, concurrency.** A completion racing several step writes ends completed, with a
   null step.
4. **Deletion.** The repository delete function removes the row, and project deletion leaves it
   in place.
5. **Gates.** The full backend unit suite and `./scripts/ci.ps1` pass (682 backend unit tests
   today, plus yours). Run the integration suite if Postgres and MinIO are up, and say so if
   they weren't.

## 9. What to return

- The changed and added files, with a diff stat.
- Test counts before and after, plus the CI output, and whether integration tests ran or were
  skipped.
- The final request and response shapes, if they differ from §4, with the reason.
- Anything that needs the owner, as a precise blocker.

## 10. Receiving-agent prompt

> Work in the current ChangeLens checkout on `m1-iphone`. Verify `git status` and HEAD against
> `9e7037c` (HEAD may be its child that updates this handoff). Read `docs/onboarding-account-fields-handoff.md`, then the O-23 row in
> `docs/06-decision-log.md`, 03 §5 and §9.4, 03a P0, P1 and P8, and `backend/changelens/api/`
> and `domain/`. Build the `account_onboarding` table and `GET` / `PUT /me/onboarding` as the
> handoff specifies, under the existing dev-token auth, with the account ID equal to the tenant
> ID until I-8. Add the deletion function without a route. Update the plan documents in §6.
> Don't build `POST /session`, consent storage, RLS or app code. Don't add dependencies, and
> don't commit or push. Write the §8 tests, run the backend tests and `./scripts/ci.ps1`, and
> return the §9 evidence or a precise blocker.
