# Implementation Plan: timeline, I-14 allowance, D-18 feedback contracts

Source spec: [`docs/api-contracts-draft.md`](../docs/api-contracts-draft.md) (owner-approved direction,
O-25 to O-28, 2026-11-16). Task list: [`tasks/todo.md`](todo.md).

**Gate 0: implementation is not authorised yet.** The draft says "Implementation is not authorised
by this update". This plan orders the work for when it is. Nothing here starts before the owner says go.

## Overview

The plan has four vertical slices, each built backend then app: **consent** (C1), **feedback** (C2),
**timeline and retraction** (A), **allowance** (B), plus the **version cap** (A, O-25) and the
**worth survey** (C3). Each slice ends in a working state: a migration, routes, tests, the 03 §9.4/§5 rows,
the data-inventory row and the app wiring. Tier-B event intake (C4) is out of scope.

## Architecture decisions (from the draft, not re-opened)

- The timeline is derived from comparisons only (A1). The only write is retraction (`retracted_at` column).
- The allowance is keyed by tenant and the month of the comparison's **creation**, the same as `domain/spend.py`.
  It is kept apart from the financial spend meter: a refund restores units, never spend.
- Charge at the worker's first paid stage. Creation reserves `standard` units per uncharged
  in-flight comparison. Grace overdraw is bounded at `heavy − standard`. A refund happens exactly once after terminal failure.
- Consent, feedback and survey rows are append-only, belong to the account and are deleted with `DELETE /me`.
- New error codes go into `errors.py` TITLES and 03 §9.4 in the same task that first returns them.
- Migrations are numbered strictly in order from `0008`. Every migration needs RLS (`ENABLE`/`FORCE`, one
  tenant policy) and must pass `test_rls_static.py`.

## Dependency graph

```
Gate 0 (authorisation) ─┬─ T1 consent API ── T2 consent app
                        ├─ T3 feedback API ── T4 feedback app
                        ├─ T5 retraction ── T6 timeline API ── T7 timeline app (needs WP-D artboards)
                        │                     └─ needs D2 (history bounding)
                        ├─ D1 heavy definition ┐
                        ├─ D3 reservations/refund fields ┴─ T8 allowance ledger + /me/usage
                        │        └─ T9 creation check ── T10 worker charge/overdraw ── T11 refunds
                        │                                   └─ T12 allowance app (needs WP-E artboards)
                        ├─ D2 ── T13 version cap
                        └─ D4 ── T14 survey API ── T15 survey app
```

## Task list

### Phase 0: prerequisites (owner)
- [ ] Gate 0: owner authorises implementation
- [ ] Commit or shelve the current `m1-iphone` working tree (migration `0007` is untracked), so `0008` has a clean base
- [ ] D1–D4 decisions (see Open questions). Each one only blocks the tasks named in it

### Phase 1: account-level D-18 (unblocked, smallest risk, sets the pattern)
- [ ] T1 Consent API · [ ] T2 Consent app
- [ ] T3 Feedback API · [ ] T4 Feedback app

### Checkpoint A: after T1–T4
- [ ] Backend unit and integration suites green; `flutter analyze` and `flutter test` green
- [ ] Sign-in → onboarding → consent → Projects works on a device build; Settings withdrawal works
- [ ] Owner review before allowance work

### Phase 2: allowance (highest risk, needs D1 + D3)
- [ ] T8 Ledger + `GET /me/usage` · [ ] T9 Creation check · [ ] T10 Worker charge and overdraw · [ ] T11 Refunds

### Checkpoint B: after T8–T11
- [ ] Concurrency tests: two workers and two creations for one tenant never exceed the bound of 23 net units at 20/1/4
- [ ] Spend meter unchanged by refunds; `verification.md` AC-21 row updated
- [ ] Owner review

### Phase 3: timeline (needs D2 for history)
- [ ] T5 Retraction · [ ] T6 Timeline API · [ ] T13 Version cap

### Checkpoint C: after T5, T6, T13
- [ ] Cycle → retract → ranked again, end-to-end through the API
- [ ] Concurrent uploads at 199/200 slots: exactly one succeeds

### Phase 4: apps and survey
- [ ] T7 Timeline app · [ ] T12 Allowance app · [ ] T14 Survey API · [ ] T15 Survey app

### Checkpoint D: complete
- [ ] Every draft section is in 03 §9.4/§5; the draft is marked superseded
- [ ] `docs/data-inventory.md`, privacy texts (`docs/legal/`) and store declarations match the new records
- [ ] Decision-log row; `traceability.md` links for AC-21 and AC-23

## Parallelisation

- Backend tasks touch shared files (`domain/models.py`, `api/errors.py`, `api/app.py`, the migration sequence),
  so they run **one at a time**.
- App tasks (T2, T4, T7, T12, T15) can run in parallel worktrees once their API task is merged. They all touch
  `app/lib/api.dart` and the ARB files, so one integration owner merges those.

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| Allowance race between workers, or between creation and the worker | High: overdraw beyond the bound or a double charge | Postgres advisory lock or `SELECT … FOR UPDATE` on a per-tenant-period row; unique constraint on `(comparison_id, kind)` in the ledger; concurrency integration tests |
| A refund applied twice when failure handling repeats | High | The ledger's unique `(comparison_id, 'refund')` is the mechanism, not a check-then-insert |
| Version-cap race on two creation paths | Med | One shared reservation function used by both routes; a test per path plus a concurrent test |
| Timeline cost on long comparison history | Med | Compute the graph from `(earlier_id, later_id)` only, with an index; bound history per D2 |
| Consent screen ships before legal review (I-20) | Med | The route stays gated behind a config flag until the privacy texts are reviewed |
| Feedback reason codes or survey answers leak content | Low | Enums only, `extra="forbid"`; an AC-23 test asserts no free-text field |
| Large uncommitted tree on `m1-iphone` | Med | Phase 0 commit before any new migration |

## Open questions (block only the tasks named)

- **D1** Heavy-document threshold (03 §8 says more than 5,000 words; O-8). Blocks T10.
- **D2** Comparison-history bounding or pagination in the timeline, and the way forward at the version cap. Blocks T6 and T13.
- **D3** Queue and reservation reconciliation when accepted runs turn out heavy, refund response fields, and refunds
  after the period ends. Blocks T8–T11.
- **D4** Survey day boundary (UTC or device), eligibility bookkeeping, plan wording and VAT basis. Blocks T14 and T15.
