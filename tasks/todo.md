# Tasks: timeline, I-14 allowance, D-18 feedback

Plan: [`tasks/plan.md`](plan.md). Spec: [`docs/api-contracts-draft.md`](../docs/api-contracts-draft.md).
**Nothing starts before Gate 0 (owner authorises implementation).**

Verification commands used below:

- Backend unit: `cd backend; python -m pytest tests/unit -q`
- Backend integration: `cd backend; docker compose up -d --wait; python -m pytest tests/integration -q`
- App: `cd app; flutter analyze --no-pub; flutter test`

Every backend task also updates 03 §9.4 (route and error codes), 03 §5 (record) and
`docs/data-inventory.md` (new stored data) for what it adds.

---

## Phase 0: prerequisites

- [x] Gate 0: owner authorises implementation (Task 1 started 2026-11-16)
- [ ] Commit or shelve the `m1-iphone` working tree (migration `0007` untracked)
- [ ] D1 heavy threshold · [ ] D2 history bounding and cap way forward · [ ] D3 reservations and refund fields · [ ] D4 survey bookkeeping

---

## Task 1: Usage-events consent API (C1)

**Description:** Store tier-B consent as append-only `consent_events` and expose `GET`/`PUT /me/consent`.
`POST /session` returns the current answer next to `onboarding`. Account deletion removes the rows.

**Acceptance criteria:**
- [x] `GET` returns `granted: null` when there's no row or the newest row is for an older policy version; `PUT` returns the same shape
- [x] `PUT` with a non-current `policy_version` → `409 policy_version_stale`; extra keys or a non-bool → `422 invalid_request`
- [x] `POST /session` 200 includes `consent.usage_events`; `DELETE /me` leaves no `consent_events` rows

**Verification:**
- [x] Unit: new `tests/unit/test_consent.py` (shape, stale version, strict body); `test_session.py` extended
- [x] Integration: RLS isolation and deletion cascade in `test_identity_db.py`; `test_rls_static.py` lists the table
- [x] Manual: none

**Dependencies:** Gate 0

**Done 2026-11-16 (not committed).** Unit: `test_consent.py` (new), `test_session.py`; integration: `test_consent_db.py` (new), `test_account_deletion_db.py`, `test_rls_db.py`. Migration `0008_consent_events`. The RLS/deletion checks went into `test_rls_db.py` and `test_account_deletion_db.py`, not `test_identity_db.py`.

**Files likely touched:** `backend/migrations/versions/0008_consent_events.py`, `backend/changelens/domain/models.py`,
`backend/changelens/api/consent.py` (new), `backend/changelens/api/session.py`, `backend/changelens/api/errors.py`,
`backend/changelens/config.py` (current policy version)

**Estimated scope:** M

## Task 2: Consent screen live in the app (C1)

**Description:** Implement `UsageConsent` against the API, route sign-in → onboarding → consent → Projects
from the session response, and add the Settings switch for withdrawal. Keep it behind a flag until I-20 legal review.

**Acceptance criteria:**
- [x] With the flag on, a session with `usage_events: null` shows the consent screen once before Projects; replaying onboarding doesn't show it
- [x] Allow and Decline both persist; a save failure shows `consent-error` and doesn't advance
- [x] The Settings switch writes `false` (or `true`) in one tap; with the flag off, no route reaches the screen

**Verification:**
- [x] App: `usage_consent_test.dart` and `consent_gate_test.dart` (new), `pumpGate` gains `consentFlow`; the existing consent-screen and layout tests in `session_settings_test.dart` and `new_screens_layout_test.dart` still pass unchanged. Replay is a separate route from the Projects menu that never passes the gate (no new test)
- [ ] Manual: device build, first launch and withdrawal in Settings

**Dependencies:** Task 1

**Built 2026-11-16 (not committed).** Flag: `--dart-define=CHANGELENS_CONSENT=true` (`Services.consentFlow`). `flutter analyze` clean, `flutter test` 279 passed. Not done: the device check below.

**Files likely touched:** `app/lib/api.dart`, `app/lib/auth/session.dart`, `app/lib/screens/account_gate.dart`,
`app/lib/screens/consent_screen.dart`, `app/lib/screens/settings_screen.dart`

**Estimated scope:** M

## Task 3: Feedback API (C2)

**Description:** `POST /feedback` with codes only, an `Idempotency-Key`, and one opinion per account and
comparison or finding context (replace); `app` context appends.

**Acceptance criteria:**
- [ ] 201 `{id, created_at}`; the same key and body replays; the same key with a different body → `409 idempotency_conflict`
- [ ] A second post for the same comparison or finding replaces the first (one row counted); `app` posts accumulate
- [ ] An unknown or other-tenant context id → `not_found`; any extra field (free text) → `422`; more than 5 reasons → `422`

**Verification:**
- [ ] Unit: new `tests/unit/test_feedback.py`, including an AC-23 assertion that the schema has no string field outside enums
- [ ] Integration: RLS isolation, replace under concurrency (unique constraint on account and context), `DELETE /me` cascade

**Dependencies:** Gate 0 (sequenced after Task 1 for the migration number)

**Files likely touched:** `backend/migrations/versions/0009_feedback.py`, `domain/models.py`, `api/feedback.py` (new), `api/app.py`

**Estimated scope:** M

## Task 4: Feedback in report and finding (C2, WP-F)

**Description:** Add helpful or not-helpful plus reason chips to the report and finding screens, posting with a
retained idempotency key.

**Acceptance criteria:**
- [ ] Positive sends with one tap; negative offers the reason codes (optional) and sends
- [ ] A transport failure keeps the key and retries the same request; a 4xx shows an error with no retry loop
- [ ] Layout matrix (320×568, 390×844, EN/DE, 2× text) has no overflow

**Verification:**
- [ ] App: new widget tests and `new_screens_layout_test.dart` cases
- [ ] Manual: device build, send feedback on one finding twice and confirm one stored row

**Dependencies:** Task 3

**Files likely touched:** `app/lib/api.dart`, `app/lib/screens/report_screen.dart`, `app/lib/screens/finding_screen.dart`, `app/lib/l10n/app_*.arb`

**Estimated scope:** M

---

## Task 8: Allowance ledger and `GET /me/usage` (B)

**Description:** A per-tenant ledger of charges, refunds and reservations, keyed by the comparison's creation
month, plus the read endpoint. No enforcement yet.

**Acceptance criteria:**
- [ ] `used` = charges − refunds for the period; `remaining = max(0, limit − used)`; `weights` and `limit` come from config
- [ ] `state` is `paused` when `cap_reached` is non-null, `exhausted` when `remaining < standard`, else `available`
- [ ] Unique constraints make a second charge or refund for one comparison impossible at the database level

**Verification:**
- [ ] Unit: new `tests/unit/test_allowance.py` (month boundary on creation time, overdraw clamp)
- [ ] Integration: duplicate-insert rejection, RLS

**Dependencies:** Gate 0, D3

**Files likely touched:** `backend/migrations/versions/00xx_allowance_ledger.py`, `domain/models.py`, `domain/allowance.py` (new), `api/usage.py` (new), `config.py`

**Estimated scope:** M

## Task 9: Allowance check at comparison creation (B)

**Description:** Next to the spend-cap check in `comparisons.py`: reserve `standard` units atomically per tenant and
period, and reject with `429 allowance_exhausted`, `resets_at` and `Retry-After`. Count rejections as a tier-A D-18 event.

**Acceptance criteria:**
- [ ] Creation succeeds only if `remaining − standard × uncharged_in_flight ≥ standard`; a rejection creates nothing and reserves nothing
- [ ] An idempotent replay returns before the check (no second reservation)
- [ ] The reservation is released on charge or on a terminal state without a charge

**Verification:**
- [ ] Unit: `test_comparison_creation.py` extended
- [ ] Integration: two concurrent creations with one unit left produce exactly one 202

**Dependencies:** Task 8

**Files likely touched:** `api/comparisons.py`, `domain/allowance.py`, `api/errors.py`

**Estimated scope:** S

## Task 10: Worker charge and grace overdraw (B)

**Description:** At the first paid stage, serialised per tenant and period: check `remaining ≥ standard`, then
charge `heavy` (D1 threshold, either version) or `standard`; otherwise fail with warning `allowance_exhausted`
and no charge. `GET /comparisons/{id}` gains `allowance_units`.

**Acceptance criteria:**
- [ ] Net usage never exceeds `limit + heavy − standard` (23 at 20/1/4) under concurrent workers
- [ ] A queued run finding nothing left ends `failed` with `warnings: [{"code": "allowance_exhausted"}]`, `allowance_units: null`
- [ ] A worker retry of the same job never charges twice

**Verification:**
- [ ] Unit: `test_worker_budget.py` extended
- [ ] Integration: a concurrency test with two workers at 2 units left and two heavy runs

**Dependencies:** Task 9, D1

**Files likely touched:** `worker/__init__.py`, `domain/allowance.py`, `api/routes.py` (`_comparison_out`)

**Estimated scope:** M

## Task 11: Automatic refund on server-side failure (B)

**Description:** After a terminal failure (retries exhausted, provider, worker, internal or ceiling stop
without a usable report), insert one refund row against the original period, with the refund fields per D3.

**Acceptance criteria:**
- [ ] Exactly one refund even when failure handling runs twice; the spend meter is unchanged
- [ ] No refund for complete, usable-partial, input-rejected or retracted comparisons
- [ ] The comparison response distinguishes the charge from the refund (D3 fields)

**Verification:**
- [ ] Unit and integration: repeat-failure idempotency; a refund across a month boundary per D3

**Dependencies:** Task 10, D3

**Files likely touched:** `worker/__init__.py`, `domain/allowance.py`, `api/routes.py`

**Estimated scope:** S

### Checkpoint B (see plan)

---

## Task 5: Comparison retraction (A)

**Description:** `POST /comparisons/{id}/retraction` sets `retracted_at` once; `GET /comparisons/{id}` exposes it.

**Acceptance criteria:**
- [ ] 204 on first and repeated calls, and `retracted_at` doesn't change on repeats
- [ ] The report stays readable; no allowance change
- [ ] Another tenant's comparison → `not_found`

**Verification:**
- [ ] Unit and integration: idempotency, RLS

**Dependencies:** Gate 0

**Files likely touched:** a migration (`retracted_at` column), `domain/models.py`, `api/routes.py`

**Estimated scope:** S

## Task 6: Timeline endpoint (A)

**Description:** `GET /projects/{id}/timeline`: every version, with `rank` (longest path over non-retracted, non-rejected
edges), `in_conflict` for cycles, and relationships with `is_latest_for_pair`, bounded per D2.

**Acceptance criteria:**
- [ ] Branches share a rank; an unplaced version has `rank: null`, `in_conflict: false`; cycle members have `null`/`true`
- [ ] Retracting one edge of a cycle restores the ranks; a failed comparison with a rejected version is excluded, other failed comparisons are included
- [ ] Graph values use all relationships even when the returned history is bounded

**Verification:**
- [ ] Unit: new `tests/unit/test_timeline.py` with a pure graph function (chain, branch, cycle, self-pair, long history)
- [ ] Integration: query count stays constant with project size

**Dependencies:** Task 5, D2

**Files likely touched:** `domain/timeline.py` (new), `api/routes.py` or `api/timeline.py` (new)

**Estimated scope:** M

## Task 13: Per-project version cap (A, O-25)

**Description:** A shared slot-reservation function used by `POST /projects/{id}/versions` and inline uploads in
comparison creation; `409 version_limit_reached`, with nothing written when a request doesn't fit.

**Acceptance criteria:**
- [ ] Pending imports reserve slots, rejected ones release them; reused versions need none
- [ ] At 199 used, two concurrent single uploads produce one success and one 409; a two-version compare at 199 → 409 with nothing written
- [ ] The cap comes from config

**Verification:**
- [ ] Unit and integration on both paths plus a concurrent test

**Dependencies:** Gate 0, D2 (way forward at the cap)

**Files likely touched:** `api/uploads.py`, `api/comparisons.py`, `domain/storage_intents.py`, `api/errors.py`, `config.py`

**Estimated scope:** M

### Checkpoint C (see plan)

---

## Task 7: P6 timeline in the app (WP-D)

**Description:** Replace `project_timeline.dart`'s derivation with the endpoint: graph layout, the "not placed"
group, the conflict state with a retract action, and the Compare v2 → v3 shortcut pre-filling P2.

**Acceptance criteria:**
- [ ] No ordering from upload time, label or filename
- [ ] A conflict asks which comparison is wrong and retracts it, then refreshes
- [ ] Long, empty and branched histories pass the layout matrix

**Verification:**
- [ ] App tests; manual on device against the Calm Bold artboards

**Dependencies:** Task 6; WP-D artboards

**Files likely touched:** `app/lib/api.dart`, `app/lib/screens/project_timeline.dart`, `app/lib/screens/project_screen.dart`, `app/lib/screens/compare_screen.dart`, ARB files

**Estimated scope:** M

## Task 12: Allowance in the app (WP-E)

**Description:** Show usage and the reset date, the exhausted and paused states, and handle `429 allowance_exhausted` on Start.

**Acceptance criteria:**
- [ ] Exhausted says plainly when it resets; paused shows no amount
- [ ] No weights or limits hard-coded (all read from `/me/usage`)
- [ ] An allowance-exhausted warning on a comparison reads as no charge

**Verification:**
- [ ] App tests; manual on device

**Dependencies:** Tasks 9–10; WP-E artboards

**Files likely touched:** `app/lib/api.dart`, `app/lib/screens/compare_screen.dart`, `app/lib/screens/comparison_screen.dart`, `app/lib/screens/settings_screen.dart`, ARB files

**Estimated scope:** M

## Task 14: Worth survey API (C3)

**Description:** `GET /me/survey` eligibility (3 real completed comparisons across ≥ 2 days, per D4) and
`POST /me/survey-responses` with the 8 answer codes.

**Acceptance criteria:**
- [ ] Examples, failed runs and repeat deliveries don't count; the day boundary follows D4
- [ ] Any answer, including `not_sure` and `declined`, makes `due` false; a second answer → `409 already_answered`
- [ ] `DELETE /me` removes responses

**Verification:**
- [ ] Unit: new `tests/unit/test_survey.py`; integration for RLS and the cascade

**Dependencies:** Gate 0, D4

**Files likely touched:** a migration, `domain/models.py`, `api/survey.py` (new), `api/errors.py`

**Estimated scope:** M

## Task 15: Worth survey invitation in the app (C3)

**Description:** An unobtrusive invitation after finishing a report review or returning to Projects from one,
only when `due`.

**Acceptance criteria:**
- [ ] Never a blocking modal; never shown right at processing completion
- [ ] All 8 answers send; Skip sends `declined`
- [ ] The plan wording and VAT basis match D4

**Verification:**
- [ ] App tests; manual on device

**Dependencies:** Task 14

**Files likely touched:** `app/lib/api.dart`, `app/lib/screens/review_completion.dart`, `app/lib/screens/projects_screen.dart`, ARB files

**Estimated scope:** S

### Checkpoint D (see plan)
