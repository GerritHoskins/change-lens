# I-8 S2: session bootstrap

Part of [I-8 in slices](README.md). Needs S1 merged. Check `git status` and HEAD, and that S1's migrations
and GUARD are in place, before starting.

## 1. Goal

Build `POST /session`, the only authenticated route outside GUARD (03 §9.4, 03a P0 and P1), for email
one-time-code sign-in. The app calls it after every Logto sign-in and on start with a stored session. It:

- creates the user, a new tenant and an active owner membership on the first call for a subject;
- returns the existing session on later calls;
- returns the account's onboarding state in the same response (O-23), so the app can route without a
  second request.

Google and Apple, with `link_required`, are S4. Invites never exist in v1 (overview, decision 6).

## 2. Request and response

`POST /session` with the Logto access token as the bearer token and an empty body (or `{}`). The token is
verified by S1's key holder, but **not** by GUARD, because the user may not exist yet.

`200`:

```json
{"status": "active", "onboarding": {"completed": false, "step": null}}
```

- `status` is `active` in this slice. S4 adds `link_required`; keep the field so the app can switch on it.
- `onboarding` is exactly the `GET /me/onboarding` object, read in the same transaction as the user lookup.
  A brand-new account returns `{"completed": false, "step": null}`.
- The response carries no IDs, subject, email or tenant. The app needs none of them.
- Errors: an invalid token is `401 unauthenticated`. A subject whose user is deleted is `401
  unauthenticated` too (no re-registration under a tombstone; S5 defines the tombstone). Any body other than
  empty or `{}` is `422 invalid_request`.

## 3. First sign-in

In one transaction:

1. Look up the user by subject. If found and not deleted, check the active membership (S1 rules) and
   return.
2. Otherwise create the user (`idp_subject` = the token subject), a new tenant ID (`uuid4`), and an
   `owner` / `active` membership.
3. **Concurrent first calls** for the same subject (the app may retry on a slow network) must end with one
   user and one membership. Use the unique `idp_subject` with an insert that tolerates the conflict (a
   savepoint and re-read, as `record_onboarding` does), not a check-then-insert.
4. A user row that exists without an active membership is an error state in v1. Return `401
   unauthenticated` and log the event code only (no subject), rather than silently creating a second tenant.

`POST /session` uses S1's pre-tenant lookup module, not `TenantRepo`. Creating the membership and reading
the onboarding row run in the same transaction; set `app.tenant_id` with `SET LOCAL` once the tenant is
known, as `tenant_scope` does, so S3's RLS can apply without changing this code.

Email isn't stored (overview, decision 5). Logto already guarantees one user per email for email
one-time-code sign-in.

## 4. What the app does with it (for I-18, not built here)

Sign in with Logto → `POST /session` → onboarding if `completed` is false (resuming at `step`) → Projects.
An expired Logto session returns to sign-in (O-22). Record this sequence in 03a P1 so I-18 has one source.

## 5. Plan documents to update

| File | Change |
|---|---|
| `docs/03-technical-design.md` §9.4 | The `POST /session` row: request (token only), the response fields above, and that this slice builds email sign-in only |
| `docs/03a-pipeline-logic.md` P1 | ON_SIGN_IN for email: idempotent creation under concurrency; invites not built in v1; the app sequence in §4 |
| `docs/06-decision-log.md` | One change-log row |

## 6. Out of scope

Google, Apple and `link_required` (S4), invites and teams (never in v1), RLS (S3), rate limits and the
sign-up cap per IP (S6; leave a clear hook where the first-sign-in branch is), app code.

## 7. Tests

1. **First call** creates exactly one user, one tenant and one owner membership, and returns `active` with
   onboarding not started.
2. **Later calls** return the same account. After `PUT /me/onboarding` with a step, and then with
   completion, `POST /session` returns that state.
3. **Concurrency** (integration): 8 parallel first calls for one subject produce one user and one membership,
   and all return 200.
4. **Isolation**: two subjects get two different tenants; neither sees the other's projects or onboarding
   state.
5. **Rejections**: invalid, expired and wrong-audience tokens; a deleted user; a user without an active
   membership; a non-empty body. Each gets the stated error, and no body or log line contains the token or
   the subject.
6. **GUARD unchanged**: every other route still rejects a valid token whose subject has no user (S1).
7. **Gates**: backend unit and integration tests and `./scripts/ci.ps1` pass.

## 8. Receiving-agent prompt

> Work in the ChangeLens checkout on `m1-iphone`, with I-8 S1 merged. Verify `git status` and HEAD. Read
> `docs/i8/README.md` and `docs/i8/s2-session-bootstrap.md`, then 03 §9.4, 03a P0 and P1, O-22 and O-23 in
> 06, and the S1 code (`api/auth.py`, the pre-tenant lookup module, migrations). Build `POST /session` for
> email one-time-code sign-in as specified, with no new dependency. Don't build Google, Apple,
> `link_required`, invites, RLS, rate limits or app code. Don't commit or push. Write the §7 tests, run the
> backend unit and integration tests and `./scripts/ci.ps1`, and return the evidence the overview lists or
> a precise blocker.
