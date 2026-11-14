# I-8 S5: account deletion

Part of [I-8 in slices](README.md). Needs S2 and S3 merged; the Apple step needs S4. Check `git status`
and HEAD first.

## 1. Goal

Build `DELETE /me`, the in-app account deletion Apple requires (guideline 5.1.1(v)), following 03a P8
`DELETE_ACCOUNT` and `DELETE_TENANT`. In v1 every account is the sole owner of its own tenant (overview,
decision 6), so deleting the account deletes the tenant: every project, the onboarding row, the
membership, the Logto user and its linked identities, and the Apple authorization.

`DELETE /team`, ownership transfer and member removal aren't built: there are no teams in v1.

## 2. What exists

- Project deletion: `request_project_deletion` freezes a project and writes a `project_deletions` receipt;
  `process_project_deletion` purges rows and every object version, retried by maintenance until complete
  (`domain/retention.py`). `DELETE /projects/{id}` returns 204 when done and 202 while pending.
- `TenantRepo.delete_onboarding(account_id)`, written for this slice, with no route.
- After S4: the Apple revoke function and the encrypted token on the user.
- After S1: `users.deleted_at`. GUARD rejects a deleted user on every request.

## 3. Behaviour

`DELETE /me` under GUARD, no body. In order, so a crash at any point resumes rather than half-deletes:

1. **Freeze.** In one transaction: write an account-deletion receipt (user ID, tenant ID, status
   `pending`, attempts, next attempt, no personal data), set `users.deleted_at`, and set the membership
   `inactive`. From the next request, GUARD rejects the user, so the app's other calls stop at once.
2. **Apple** (if a token is stored): revoke with Apple first, while the row still holds the token (AR-1),
   retried with backoff until Apple confirms (AR-6). Then null the column.
3. **Projects**: `request_project_deletion` and `process_project_deletion` for every project of the
   tenant, including already frozen ones.
4. **Account rows**: `delete_onboarding`, pending links and parked tokens for this user (S4), and the
   membership.
5. **Logto**: delete the Logto user, which removes its linked identities and sessions (Management API).
   A 404 from Logto counts as done.
6. **Tombstone**: the user row keeps only its ID and `deleted_at`; `idp_subject` and any other identifying
   column are cleared. The ID stays, so `review_events.actor` and other append-only references stay valid
   without personal data (03 §5 `User`). The receipt becomes `complete`.

**Response**: `204` when every step finished in the request, `202` when something is still pending (as
project deletion does). The app treats both as signed out. A second `DELETE /me` can't authenticate,
because the user is already rejected by GUARD.

**Maintenance** retries pending account deletions from step 2 onward, through a `SECURITY DEFINER`
candidates function (S3), and never reports completion while a step is pending.

A Logto user deleted out of band (for example in the console) can't sign in again, but our user row and
the tenant's projects stay until someone runs the deletion. Don't build a sweeper for it. Note it in the
data inventory as an operator rule: delete accounts through the API, not the Logto console.

## 4. Plan documents to update

| File | Change |
|---|---|
| `docs/03-technical-design.md` §5 and §9.4 | The account-deletion receipt; the tombstone columns; `DELETE /me` responses; `DELETE /team` not in v1 |
| `docs/03a-pipeline-logic.md` P8 | The order above, if it refines the pseudocode |
| `docs/data-inventory.md` | Account rows: what's deleted, what the tombstone keeps, the console rule |
| `docs/06-decision-log.md` | One change-log row |

## 5. Out of scope

The app's deletion screen (I-18), backups and PITR expiry (I-13, S7), shares (none in v1), teams.

## 6. Tests

1. **Happy path** (integration, fakes for Apple and Logto): an account with two projects, uploads, a
   comparison, reviews, an onboarding row and an Apple token ends with no project rows or objects, no
   onboarding row, an inactive-then-deleted membership, a tombstone user, Apple revoked once, Logto user
   deleted once, and `204`.
2. **Immediate lockout**: right after step 1, every route with the same token returns `401`.
3. **Resumption**: a failure injected at each of steps 2–5 returns `202`; maintenance completes it later
   without repeating a finished external call more than its retry policy allows.
4. **Apple failure** keeps the token until Apple confirms (AR-6); the receipt stays `pending`.
5. **Isolation**: another tenant's projects, onboarding row and user are untouched.
6. **Tombstone**: `review_events.actor` still points at the user ID; no subject, email or token remains.
7. **No leaks**: no response, log line or receipt holds a subject, email or token.
8. **Gates**: backend unit and integration tests and `./scripts/ci.ps1` pass.

## 7. Receiving-agent prompt

> Work in the ChangeLens checkout on `m1-iphone`, with I-8 S1–S3 merged (and S4 for the Apple step).
> Verify `git status` and HEAD. Read `docs/i8/README.md` and `docs/i8/s5-account-deletion.md`, then 03 §5
> and §9.4, 03a P8, review-ledger items SA-6, CR-6, AR-1 and AR-6, `docs/data-inventory.md`, and
> `backend/changelens/domain/retention.py` and `api/retention.py`. Build `DELETE /me` and its maintenance
> retries as specified, with no new dependency. Don't build `DELETE /team`, app code or backup handling.
> Don't commit or push. Write the §6 tests, run the backend unit and integration tests and
> `./scripts/ci.ps1`, and return the evidence the overview lists or a precise blocker.
