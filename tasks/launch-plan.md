# Implementation Plan: from the 2026-11-17 audit to a free public launch

Source: the repository audit of 2026-11-17 (decision matrix, items 1–16). Task list:
[`tasks/launch-todo.md`](launch-todo.md).

This plan sits **next to** [`tasks/plan.md`](plan.md) and [`tasks/todo.md`](todo.md), which stay the plan
for the timeline, allowance and D-18 contracts (T1–T15). Tasks here are numbered L1–L26, so the two lists
never collide. Where the audit names work that T3–T15 already describe, this plan points at those tasks and
doesn't repeat them.

## Overview

The audit found healthy code (869 backend unit tests, 279 Flutter tests, CI green on `94bfaee`) and a
launch that is blocked by five things: private planning documents readable in the public git history, a
failing I-7b release gate, an unmet M2 exit (device and server checks), launch scope that isn't built
(allowance, feedback, survey, timeline API), and launch gates that haven't started (legal texts, security
review, usability test, distribution). The plan first secures what exists, then closes M2 on real devices,
then fixes the quality gate, then builds the remaining scope, then runs the launch gates.

## Architecture decisions

- **No new architecture.** Every task works inside the existing design (03, ADR-0001 to ADR-0022). A task
  that needs a design change stops and goes to the owner.
- **The existing contract plan keeps its own files.** T3–T15 are built from `tasks/todo.md` in the order of
  `tasks/plan.md`, after the owner signs off the contract draft (L5).
- **Allowance before feedback.** Phase 4 runs T8–T11 before T3–T4: for a free launch the allowance is the
  cost protection, and it carries the highest technical risk, so it fails fast. This changes the phase order
  in `tasks/plan.md`; the owner confirms it at L5.
- **Deployed configuration fails closed.** In `logto` mode a missing storage, database or model setting
  stops the process at start. It never falls back to a development default (L11).
- **A release build is a signed-in build.** Store workflows always pass `CHANGELENS_LOGTO_APP_ID`, and the
  offline release check fails without it (L7).
- **History is rewritten once, after the branches are cleaned up.** Fewer refs to rewrite and force-push,
  and no half-rewritten state (L8 and L9 before L6).
- **Evidence is recorded where the project already records it:** the decision log (06, private), the
  runbook's section E, `docs/verification.md` and `docs/SOP.md`. No new evidence files.

## Dependency graph

```
Owner decisions (parallel, start now)
  L1 history: rewrite or accept ───────────────► L6 rewrite
  L2 I-7b: fix or deviation ───────────────────► L14 ── L15 ── L16
  L3 Play account route (2–6 weeks) ───────────────────────────────► L25
  L4 book the legal review (lead time) ────────► L23 ──────────────► L25
  L5 contract sign-off ────────────────────────► T8–T15, T3–T7 (tasks/todo.md)

Secure            L8 merge PR ── L9 branch clean-up ── L6 rewrite
                  L7 release define (independent)

M2 exit           L10 migrate + restore test ─┐
                  L11 config fails closed ────┼─ L13 device session ── Checkpoint B
                  L12 API docs off ───────────┘        │
                  L17 outside uptime check (independent)
                                                       ├─► L22 security review
Quality gate      L14 reproduce ── L15 fix ── L16 fresh cohort ── Checkpoint C
                                                       │
Launch gates      L18 docs  L19 CI tests  L20 CI scans  L21 Python  (independent)
                  L24 UI triage
                  L7 + L13 + L23 ── L25 release inspection ── L26 usability test ── Checkpoint D
```

## Task list

### Phase 0: owner decisions and lead-time items (start now, in parallel)
- [x] L1 Decide: rewrite the public history or accept the exposure (decided 2026-11-17: rewrite, route A)
- [ ] L2 Decide: fix I-7b and re-evaluate, or record a second deviation
- [ ] L3 Choose and start the Google Play account route
- [ ] L4 Book the legal review of the five texts
- [ ] L5 Sign off the contract draft and the Phase 4 order

### Phase 1: secure what exists (in this order)
- [x] L7 Release builds carry the sign-in define (built 2026-11-17)
- [x] L8 Merge `m1-iphone` into `main` (done 2026-11-17: pull request 34, merge commit `f7fb186` after the L6 rewrite)
- [x] L9 Delete merged branches and extra worktrees (done 2026-11-17: only `main` and `m1-iphone` remain)
- [ ] L6 Rewrite history (rewritten and force-pushed 2026-11-17; open: GitHub support purges the old commits and pull-request refs)

### Checkpoint A: after L6–L9
- [ ] `main` holds all work; CI green on `main`
- [ ] The private paths are gone from `origin` (or the acceptance is recorded in 06)
- [ ] Owner review

### Phase 2: M2 exit on the server and on devices
- [ ] L10 Migrate the server to head and repeat the restore test
- [x] L11 Deployed configuration fails closed (built 2026-11-17; integration suite runs in CI)
- [x] L12 Interactive API docs off in deployed mode (built 2026-11-17, not deployed)
- [ ] L13 Device session: sign-in, deletion, PDF picker, consent, one comparison on the server
- [ ] L17 Outside uptime check and patch reminder

### Checkpoint B: M2 exit
- [ ] A new user signs up, compares and deletes the account on both platforms (05, M2 exit)
- [ ] Runbook section E has no unticked evidence line; the 06 row for S7 exists
- [ ] Owner review

### Phase 3: quality gate (I-7b), needs L2
- [ ] L14 Reproduce the fabricated scope changes on the development split
- [ ] L15 Fix the cause
- [ ] L16 Fresh held-out cohort and gate run

### Checkpoint C: release gate
- [ ] `python -m tools.release_gate` no longer prints `I-7 RELEASE BLOCKED`
- [ ] Receipt and 06 row recorded

### Phase 4: remaining launch scope (tasks in `tasks/todo.md`), needs L5
- [ ] T8–T11, T12 Allowance (Checkpoint B of `tasks/plan.md`)
- [ ] T3, T4 Feedback
- [ ] T5, T6, T13, T7 Timeline, retraction and version cap
- [ ] T14, T15 Worth survey

### Phase 5: launch gates
- [ ] L18 Bring the documents in line with the code
- [x] L19 Run every existing test in CI (built 2026-11-17)
- [ ] L20 Secret scan and dependency audit in CI
- [ ] L21 Move off Python 3.10
- [ ] L22 Security review and incident runbook (D-9)
- [ ] L23 Legal texts: fill, apply the review, publish, link
- [ ] L24 Close or schedule the open UI findings
- [ ] L25 Release-build inspection on both platforms and store declarations (I-17)
- [ ] L26 Usability test with 5 users (D-10)

### Checkpoint D: launch
- [ ] D-9 has no open high-severity finding; the D-10 users complete the flow; I-7b passes (05, Public launch)
- [ ] Store declarations, privacy texts and the data inventory describe the same records
- [ ] Owner decision to submit

## Parallelisation

- **Owner tasks L1–L5 run in parallel with everything.** L3 and L4 have the longest lead times and block
  only L25 and L23.
- **Safe in parallel worktrees:** L7 (Codemagic and release scripts), L11 with L12 (backend config and app
  factory, one owner), L19 with L20 (CI files, one owner), L18 (documents only), L24 (triage, no code).
- **One at a time:** L14–L16 (shared pipeline and eval files), every task in `tasks/todo.md` that adds a
  migration, and L21 (it regenerates the hashed requirements every backend task depends on).
- **Never in parallel with L6:** the rewrite replaces every commit. All other work is merged and pushed
  first, and every clone and worktree is recreated after it.
- **One writer per worktree.** On 2026-11-17 a second session was editing `app/lib/` in the main checkout
  while this plan was written; app tasks wait for that work to be committed.

## Risks and mitigations

| Risk | Impact | Mitigation |
|---|---|---|
| The history rewrite loses the private files that exist only on disk | High | L6 starts with a copy of the seven files outside the repository, and works in a fresh mirror clone, never in the working checkout |
| The rewrite leaves old commits reachable through GitHub's pull-request refs | High | L6 offers two routes: a support request to purge them, or deleting and recreating the repository; the owner picks one at L1 |
| A second I-7b fix again fails on fresh pairs | High | L14 must reproduce the fault before L15 changes anything; L16 uses bases never seen in development; the gates and the split are frozen before the run |
| Device checks find sign-in or deletion faults late | High | L13 is in Phase 2, before any new feature work; each fault becomes its own task |
| The Play account takes longer than the build | Med | L3 starts in Phase 0; iOS can launch first if Android is late |
| Failing closed (L11) stops the server at the next deploy because a variable is missing | Med | L11 checks `deploy/ionos/env/*.example` for every newly required name and adds a start-up test per name |
| The Python upgrade breaks a hash-pinned wheel (`pypdfium2`, `psycopg`) | Med | L21 runs the full unit, integration and eval suites on the new version before the image changes; it is its own pull request |
| New CI checks (L20) fail on existing findings and block merges | Low | First run is report-only; the owner sees the list before it becomes required |
| Documents drift again after L18 | Low | L18 adds nothing new to maintain; `scripts/ci.ps1` keeps checking links and sizes |

## Open questions

- **L2** Fix and re-evaluate, or a recorded deviation? The launch rule in 05 needs a pass.
- **L3** Organisation account (D-U-N-S, up to 30 days) or a personal account with 12 testers for 14 days?
- **L5** Are the contract defaults in `docs/api-contracts-draft.md` approved as written (D1–D4 in
  `tasks/plan.md`), and is allowance-before-feedback the order?
- **L21** Target Python version: 3.12 or 3.13? It depends on wheel availability for every pinned package.
- **L22** D-9 lists I-16 and I-19 as dependencies, and both are deferred until after launch. The review
  scope for launch needs the owner's wording.
