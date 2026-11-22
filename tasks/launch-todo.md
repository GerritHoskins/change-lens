# Tasks: from the 2026-11-17 audit to a free public launch

Plan: [`tasks/launch-plan.md`](launch-plan.md). Tasks T1–T15 live in [`tasks/todo.md`](todo.md) and are
not repeated here. "Owner" tasks need the owner's hands, devices or accounts; the rest can be done by an agent.

Verification commands used below (PowerShell, from the repository root):

- Backend unit: `cd backend; .venv\Scripts\python -m pytest tests/unit -q`
- Backend integration: `cd backend; docker compose up -d --wait; .venv\Scripts\python -m pytest tests/integration -q`
- App: `cd app; flutter analyze --no-pub; flutter test`
- Plan checks: `./scripts/ci.ps1`
- Release config: `python scripts/release/check_config.py; python -m unittest discover -s scripts/release -p "test_*.py"`
- Release gate: `cd backend; .venv\Scripts\python -m tools.release_gate`

---

## Phase 0: owner decisions and lead-time items

## Task L1: Decide what to do about the private documents in public history (owner)

**Description:** Seven git-ignored files were deleted in `f27ccfa` but are readable in every earlier
commit on GitHub (`git show f27ccfa^:docs/06-decision-log.md`). Choose: rewrite (route A: force-push plus a
GitHub support request to purge pull-request refs; route B: delete and recreate the repository), or accept.

**Acceptance criteria:**
- [x] The choice and, for a rewrite, the route are written in 06 with the date
- [x] If accepted: the reason is recorded, and L6 is struck out (not applicable: the choice is a rewrite)

**Verification:**
- [x] Manual: the 06 row exists

**Decided 2026-11-17: rewrite, route A** (force-push plus a GitHub support request to purge the pull-request refs). L6 stays and runs after L8 and L9.

**Dependencies:** None · **Files likely touched:** `docs/06-decision-log.md` (private) · **Estimated scope:** XS

## Task L2: Decide the way forward for I-7b (owner)

**Description:** The held-out receipt of 2026-11-13 fails one gate: 4 fabricated scope changes against a
limit of 0. The fresh cohort is spent. Choose: fix and re-evaluate on new pairs (L14–L16), or record a
second deviation and change the launch rule in 05.

**Acceptance criteria:**
- [ ] The decision is written in 06; a deviation also rewrites the launch rule in 05 and the gate in `backend/tools/release_gate.py`
- [ ] For a fix: the owner agrees to review a new cohort (about 1–2 hours)

**Verification:**
- [ ] Manual: the 06 row exists

**Dependencies:** None · **Files likely touched:** `docs/06-decision-log.md`, `docs/05-backlog.md` (private) · **Estimated scope:** XS

## Task L3: Choose and start the Google Play account route (owner)

**Description:** O-21. Either an organisation account (needs a D-U-N-S number, up to 30 days) or a new
personal account (a closed test with 12 opted-in testers for 14 continuous days, then a production review).

**Acceptance criteria:**
- [ ] The route is written in 06
- [ ] The first external step is started: the D-U-N-S request, or the account plus a tester list of at least 12 names

**Verification:**
- [ ] Manual: confirmation mail or Play Console screenshot kept outside Git

**Dependencies:** None · **Files likely touched:** `docs/06-decision-log.md` (private) · **Estimated scope:** XS (2–6 calendar weeks)

## Task L4: Book the legal review (owner)

**Description:** Send the five drafts in `docs/legal/` and the review points in `docs/legal/README.md`
(tier-A balancing test, liability wording, change by notice, supervisory authority, email-provider DPA) to a lawyer.

**Acceptance criteria:**
- [ ] A reviewer and a return date are agreed
- [ ] The reviewer has the texts, `docs/data-inventory.md` and the consent design

**Verification:**
- [ ] Manual: the date is noted in 06

**Dependencies:** None · **Files likely touched:** none · **Estimated scope:** XS (lead time)

## Task L5: Sign off the contract draft and the build order (owner)

**Description:** `docs/api-contracts-draft.md` says its operational details are "specified for review";
`tasks/plan.md` still lists them as open D1–D4. Approve or change them, confirm that the allowance
(T8–T11) is built before feedback (T3–T4), and record Gate 0.

**Acceptance criteria:**
- [ ] Each of D1–D4 is marked approved or changed in `tasks/plan.md` and `tasks/todo.md`
- [ ] Gate 0 and the order have a dated 06 row
- [ ] The stale "not committed" and "migration `0007` untracked" lines in both files are removed

**Verification:**
- [ ] `./scripts/ci.ps1` passes (links and sizes)

**Dependencies:** None · **Files likely touched:** `tasks/plan.md`, `tasks/todo.md`, `docs/api-contracts-draft.md` · **Estimated scope:** S

---

## Phase 1: secure what exists

## Task L7: Release builds carry the sign-in define

**Description:** `app-android-release` and `ios-testflight` in `codemagic.yaml` build without
`CHANGELENS_LOGTO_APP_ID`, which yields a build with no sign-in and the developer settings in the menu.
Pass the define in both, and make the offline check fail when a release workflow lacks it.

**Acceptance criteria:**
- [x] Both workflows pass `--dart-define=CHANGELENS_LOGTO_APP_ID=…` on every `flutter build` line and fail when the value is empty
- [x] `check_config.py` reports a failure for a release workflow without the define
- [x] `ios-device-check` keeps its documented empty-value option

**Verification:**
- [x] Release config command passes; a new case in `test_release.py` removes the define and expects `FAIL`
- [x] Manual: none (the device proof is L25)

**Built 2026-11-17 (not yet run on Codemagic).** The ID is defined once as `logto_app` in `codemagic.yaml`; 11 release tests and `./scripts/ci.ps1` pass.

**Dependencies:** None · **Files likely touched:** `codemagic.yaml`, `scripts/release/check_config.py`, `scripts/release/test_release.py`, `scripts/release/README.md` · **Estimated scope:** S

## Task L8: Merge `m1-iphone` into `main` (owner approves the merge)

**Description:** `m1-iphone` is pushed at `94bfaee` with CI green and is 10 commits ahead of `origin/main`.
Open the pull request and merge it. The uncommitted app edits of the second session are not part of it.

**Acceptance criteria:**
- [x] The pull request is merged with a merge commit, as PRs 10–33 were
- [x] `plan-checks` and `backend-integration` are green on `main`

**Verification:**
- [x] `gh run list --branch main --limit 2` shows two successes

**Done 2026-11-17.** Pull request 34 (16 commits, head `12f8319`, with L7, L11 and L12) was merged by the owner as merge commit `7ee8667` (`f7fb186` after the L6 rewrite); both workflows are green on it.

**Dependencies:** None · **Files likely touched:** none · **Estimated scope:** XS

## Task L9: Delete merged branches and extra worktrees (owner)

**Description:** Nine branches have nothing that `origin/main` lacks, and four extra worktrees exist. Remove
them so L6 has fewer refs to rewrite. `git worktree remove` refuses a worktree with uncommitted work; never add `--force`.

**Acceptance criteria:**
- [x] `git worktree list` shows only the main checkout (or worktrees the owner chose to keep)
- [x] Local and remote branches are `main` and `m1-iphone` only
- [x] Nothing unmerged was deleted: `git branch -d` (lower-case) succeeded for every branch

**Verification:**
- [x] `git branch -a` and `git worktree list`

**Done 2026-11-17.** Four worktrees removed without `--force`, nine local and eight remote branches deleted; every
tip was contained in `origin/main` first. Differences from the planned commands:
- Local `main` was fast-forwarded with `git fetch origin main:main`, not `git switch main`, because other sessions share this checkout on `m1-iphone`.
- `i7-eval` was 5 commits ahead of its own remote branch, so `-d` refused it until the remote branch was deleted; its tip `ad72bbc` is in `main`.
- Windows stopped `git worktree remove` on the Claude worktree at an over-long path after unregistering it; the leftover folder (tracked files and build output only) was deleted with `rd /s /q` on its `\\?\` path.
- The paseo worktree's three git-ignored run records were copied to this checkout's `.paseo/plugins/playbooks/runs/t14-preparation/` before removal.

**Dependencies:** L8 · **Files likely touched:** none · **Estimated scope:** XS

## Task L6: Rewrite the public history (owner; only if L1 = rewrite)

**Description:** Remove the seven private paths from every commit with `git filter-repo`, in a fresh mirror
clone, and force-push. This is irreversible and changes every commit ID. Check the commands against the
`git-filter-repo` manual and GitHub's "Removing sensitive data from a repository" before running them.

**Acceptance criteria:**
- [x] The seven files are copied outside the repository before anything else
- [x] A fresh clone has no commit touching the seven paths: `git log --all --oneline -- PRODUCT.md docs/06-decision-log.md` prints nothing
- [ ] ~~Old commits are unreachable on GitHub: support confirmed the purge (route A), or the repository was recreated (route B)~~ Not met, accepted by the owner on 2026-11-17 (see below)

**Verification:**
- [x] `git ls-remote origin` shows only rewritten branch heads; CI is green on the new `main`
- [ ] Manual: `https://github.com/GerritHoskins/change-lens/commit/a8280b9` returns 404

```powershell
New-Item -ItemType Directory -Force C:\Users\Gerrit\changelens-private-backup
Copy-Item PRODUCT.md, ChangeLens_Planning_Agent_Handoff.md, ChangeLens_Planning_Agent_Handoff_v2.md, docs\01-product-decision.md, docs\04-validation-plan.md, docs\05-backlog.md, docs\06-decision-log.md C:\Users\Gerrit\changelens-private-backup\
py -m pip install git-filter-repo
git clone --mirror https://github.com/GerritHoskins/change-lens.git C:\Users\Gerrit\change-lens-rewrite.git
cd C:\Users\Gerrit\change-lens-rewrite.git
git filter-repo --invert-paths --path PRODUCT.md --path ChangeLens_Planning_Agent_Handoff.md --path ChangeLens_Planning_Agent_Handoff_v2.md --path docs/01-product-decision.md --path docs/04-validation-plan.md --path docs/05-backlog.md --path docs/06-decision-log.md
git log --all --oneline -- PRODUCT.md docs/06-decision-log.md
git remote add origin https://github.com/GerritHoskins/change-lens.git
git push --force origin "refs/heads/*:refs/heads/*"
```

Then, in the working checkout, with a clean tree (ignored files such as `backend/.env` stay in place):

```powershell
cd C:\Users\Gerrit\job-search\POCs\change-lens
git status --short
git fetch origin --prune
git switch main
git reset --hard origin/main
git switch m1-iphone
git reset --hard origin/m1-iphone
```

**Closed 2026-11-17: rewritten and force-pushed; the purge will not happen and the rest is accepted.** GitHub
Support closed the request because the account's plan has self-service support only. The owner declined route B
(it loses the pull requests, the star, the Actions history and the repository settings) and accepted that the
old commits stay readable by ID and through old pull requests' file views; the reason is in 06. Route B stays
possible later. What follows describes the rewrite as it was done.

**Rewritten and force-pushed 2026-11-17.** 215 commits became 195 (20 touched only the
private paths); `main` is `f7fb186` and `m1-iphone` is `68578c8`, with the same file trees as before. Every commit
ID changed, so IDs quoted in older text (such as `f27ccfa` and `a8280b9`) are the old ones; the old-to-new list is
`filter-repo/commit-map` in `C:\Users\Gerrit\change-lens-rewrite.git`. The old commits stay readable by ID on
GitHub, and the pull-request refs still point at them. Other clones must be reset, never merged or pulled (the IONOS server: see L10).

**Dependencies:** L1, L8, L9 · **Files likely touched:** none (history only) · **Estimated scope:** S

### Checkpoint A: after L6–L9
- [ ] `main` holds all work and CI is green on it
- [x] The private paths are gone from `origin`, or the acceptance is in 06 (branches are clean; the old commits and pull-request refs are accepted in 06, 2026-11-17)
- [ ] Owner review before server and device work

---

## Phase 2: M2 exit on the server and on devices

## Task L10: Migrate the server to head and repeat the restore test (owner, on the server)

**Description:** The last restore test ran at schema `0005_limits`; head is `0008_consent_events`. Deploy
the merged `main` as in the runbook's section F, then repeat the restore test of section D2.

**Acceptance criteria:**
- [x] The `migrate` run ends at `0008_consent_events`; `api` answers 401 without a token and `auth` answers 200
- [x] A new `RESTORE OK` line is recorded in section E with the date and schema `0008_consent_events`
- [x] The private key file is shredded after the test

**Verification:**
- [x] `docker compose ps` shows every service running; the monitor sends no alert within 20 minutes

```bash
cd /opt/changelens && git pull && cd deploy/ionos && docker compose build && docker compose --profile tools run --rm migrate && docker compose up -d
install -m 600 -o 70 /dev/null /etc/changelens/backup-identity.txt && nano /etc/changelens/backup-identity.txt
docker compose --profile tools run --rm restore-test
shred -u /etc/changelens/backup-identity.txt
```

**Done 2026-11-17.** The server clone moved from the old `e191ad5` (branch
`m1-iphone`) to the rewritten `main` at `6a90bb5`; its `git@github.com` remote has no key in a non-interactive
session, so the fetch ran over HTTPS (`git fetch https://github.com/GerritHoskins/change-lens.git
"+refs/heads/main:refs/remotes/origin/main"`, then `git checkout -B main origin/main`). The schema went from
`0006_social_sign_in` to `0008_consent_events`; all eight services run, `api` 401, `auth` 200, and `/docs`,
`/redoc` and `/openapi.json` answer 404 (L12's manual check). The previous images are kept as
`changelens-backend:pre-l10` and `changelens-backup:pre-l10`. The owner then ran the
restore test with the private backup key: `RESTORE OK` at 18:47:58Z from base `20261117T074427Z`, schema
`0008_consent_events` (runbook section E), and the key file was shredded. The monitor ran five times in the 45
minutes after the deploy and recorded no alert (`/var/lib/changelens-monitor` has no `last` file).

**Dependencies:** L8 (and L6 if chosen: the server clone then needs `git fetch && git reset --hard origin/main` instead of `git pull`) · **Files likely touched:** `deploy/ionos/README.md` · **Estimated scope:** S

## Task L11: Deployed configuration fails closed

**Description:** In `logto` mode `Settings.from_env` falls back to development defaults when a variable is
missing: `CHANGELENS_LLM` becomes `fake`, and the S3 endpoint, keys and bucket become the local MinIO values.
Make each a start-up error in `logto` mode; `dev` mode keeps its defaults.

**Acceptance criteria:**
- [x] In `logto` mode a missing `CHANGELENS_LLM`, `CHANGELENS_S3_ENDPOINT`, `_ACCESS_KEY`, `_SECRET_KEY` or `_BUCKET` raises at start with the variable's name and no value
- [x] `CHANGELENS_LLM=fake` is refused in `logto` mode
- [x] Every newly required name is present in the env example files that the `api` and the `worker` load (`deploy/ionos/env/`)

**Verification:**
- [x] Backend unit: one new test per variable in `tests/unit/test_guard_logto.py` (or a new `test_settings_deployed.py`)
- [ ] Backend integration suite still green

**Built 2026-11-17.** `CHANGELENS_DATABASE_URL` is required too (six names, `DEPLOYED_REQUIRED` in `config.py`). Unit suite 884 passed. Not done: the integration suite (Docker was off; CI runs it on push). Before the next deploy, check that `/etc/changelens/changelens.env` sets all six.

**Dependencies:** None · **Files likely touched:** `backend/changelens/config.py`, `backend/tests/unit/test_guard_logto.py`, `deploy/ionos/env/*.example`, `deploy/ionos/README.md` · **Estimated scope:** S

## Task L12: Interactive API docs off in deployed mode

**Description:** `create_app` uses FastAPI's defaults, so `/docs`, `/redoc` and `/openapi.json` are served
without a token and Caddy proxies them. Turn all three off in `logto` mode and name the app without "dev API".

**Acceptance criteria:**
- [x] In `logto` mode the three paths return the same `not_found` problem body as any unknown path
- [x] In `dev` mode they still work

**Verification:**
- [x] Backend unit: a new case for each mode (in `tests/unit/test_guard_logto.py`, which has both modes' helpers)
- [ ] Manual after L10: `curl -s -o /dev/null -w '%{http_code}' https://api.pixeltronic.dev/openapi.json` prints 404

**Built 2026-11-17 (not deployed).**

**Dependencies:** None (deploy with L10 or the next release) · **Files likely touched:** `backend/changelens/api/app.py`, `backend/tests/unit/test_api_unit.py` · **Estimated scope:** XS

## Task L13: Device session for the M2 and M1b exits (owner, both phones)

**Description:** One sitting on the iPhone and the Fairphone against the IONOS server, with synthetic documents only. It closes every device check the audit found open. The iPhone half has a step-by-step checklist with a result line per step: [`docs/device-sitting-1.md`](../docs/device-sitting-1.md). The Fairphone half follows it, with its own checklist: [`docs/device-sitting-1-android.md`](../docs/device-sitting-1-android.md).

**Acceptance criteria:**
- [x] Sign-in: Apple on the iPhone, Google on both, an email code on both, a completed `link_required` link, and MFA as in AC-26 (iPhone 2026-11-20: all five; Fairphone 2026-11-18: all but MFA; MFA with email and with Google on 2026-11-20, task L30)
- [x] One PDF comparison started from screen P2 completes on the server on each phone (this also proves the worker's egress allow-list); on the iPhone the PDF comes from the picker (Fairphone 2026-11-18, iPhone 2026-11-20)
- [x] Account deletion works on both phones and the Logto user is gone; the consent screen (build with `CHANGELENS_CONSENT=true`) shows once and the Settings switch withdraws (Fairphone 2026-11-18, iPhone 2026-11-20; on the iPhone the Logto check is the owner's report)

**Verification:**
- [ ] Each result has a dated line in runbook section E or in 06; the M1b and M2 exit rows exist in 06
- [x] Every fault found becomes its own task in this file (L30 from the Fairphone, L35 from the iPhone)

**Dependencies:** L10; a signed build from `ios-device-check` and a debug APK, both built with `CHANGELENS_CONSENT=true` (`ios-device-check` passes it since 2026-11-18; the debug APK is built on the PC with the same define); L27 and L28 first, so one sitting sees the final screens (device-first order in `tasks/launch-plan.md`) · **Files likely touched:** `deploy/ionos/README.md`, `docs/06-decision-log.md` (private), `tasks/todo.md` (Task 2 manual check) · **Estimated scope:** M (half a day)

## Task L17: Outside uptime check and patch reminder (owner)

**Description:** `monitor.sh` runs on the server it watches. Add an outside check on both domains
(runbook D3) and the weekly patch calendar entry (D4). The uptime service is a new processor that sees URLs only.

**Acceptance criteria:**
- [x] Both `https://api.pixeltronic.dev/projects` (expects 401) and the Logto OpenID configuration (expects 200) are checked from outside, with an alert to the owner
- [x] `docs/data-inventory.md` lists the service; the "Still open" line in runbook section D is removed
- [x] The weekly calendar entry exists (owner's statement, 2026-11-18)

**Verification:**
- [x] Manual: stop `caddy` for 10 minutes and receive the outside alert (2026-11-18: the owner received HetrixTools' "down" and "recovered" mails)

**Done 2026-11-18.** The check is two website monitors in the owner's HetrixTools account (free plan, every minute, alert after three failed checks), set up by the owner from the values in runbook D3; the owner received the "down" and "recovered" mails in the `caddy` test and confirmed the calendar entry. The monitor settings themselves were not inspected from this repository. First attempt, dropped: a scheduled GitHub Actions workflow (`.github/workflows/uptime.yml`, on `main` from 2026-11-18 06:56Z) never started a scheduled run in four hours, also after disabling and re-enabling it, and its one manual failed run produced no mail; the file is removed. UptimeRobot's free plan was ruled out because it can't accept a 401 as healthy. HetrixTools is a new processor for operations (data inventory); its free plan needs a dashboard login every 90 days, which the weekly patch check now includes.

**Dependencies:** None · **Files likely touched:** `docs/data-inventory.md`, `deploy/ionos/README.md` · **Estimated scope:** XS

### Checkpoint B: M2 exit
- [ ] A new user signs up, compares and deletes the account on both platforms (iPhone: sections 1 and 5 of [`docs/device-sitting-2.md`](../docs/device-sitting-2.md), not yet run)
- [ ] Runbook section E has no unticked line; the S7 evidence row exists in 06
- [ ] Owner review before feature work

---

## Phase 3: quality gate (I-7b), needs L2 = fix

## Task L14: Reproduce the fabricated scope changes on the development split

**Description:** Find a development-split pair (reordered or unchanged) on which the current pipeline
reports a scope change, and name the stage that produces it. First suspect: the align contradiction rule
sending a sentence that is read twice to the model aligner. No fix in this task.

**Acceptance criteria:**
- [ ] At least one failing development pair is pinned as a unit test that fails for the right reason
- [ ] The cause is written in 06 with the stage and rule; held-out pairs are not inspected

**Verification:**
- [ ] Backend unit: the new test in `tests/unit/test_align_compare.py` fails before L15

**Dependencies:** L2 · **Files likely touched:** `backend/tests/unit/test_align_compare.py`, `docs/06-decision-log.md` (private) · **Estimated scope:** S

## Task L15: Fix the cause

**Description:** Change the stage L14 named so reordered and unchanged pairs produce no scope finding,
without lowering recall on real changes.

**Acceptance criteria:**
- [ ] The L14 test passes; zero fabricated scope changes on the development split over 2 runs
- [ ] Every other I-7 gate still holds on the development split (precision and recall ≥ 0.90, zero false removals)

**Verification:**
- [ ] Backend unit suite green; development run with `python -m tools.i7_run` recorded in 06

**Dependencies:** L14 · **Files likely touched:** `backend/changelens/pipeline/align.py`, `backend/changelens/pipeline/compare.py`, `backend/tests/unit/test_align_compare.py` · **Estimated scope:** M

## Task L16: Fresh held-out cohort and gate run (owner reviews the cohort)

**Description:** Build new pairs from bases never used in development (`scripts/eval/FRESH_COHORT.md`),
have the owner review them, freeze the split, run the gates once and commit the receipt.

**Acceptance criteria:**
- [ ] The cohort uses new bases only, and the owner's review is recorded before the run
- [ ] All gates in `scripts/eval/i7_receipt.json` pass, including `fabricated_scope_changes == 0`
- [ ] The receipt matches the frozen split and the pipeline fingerprint

**Verification:**
- [ ] Release gate command no longer prints `I-7 RELEASE BLOCKED`; `./scripts/ci.ps1` passes

**Dependencies:** L15 · **Files likely touched:** `scripts/eval/fresh_bases.py`, `scripts/eval/split.json`, `scripts/eval/i7_receipt.json`, `docs/06-decision-log.md` (private) · **Estimated scope:** M

### Checkpoint C: release gate
- [ ] The release gate passes; the receipt and the 06 row are recorded

---

## Phase 4: remaining launch scope

Built from [`tasks/todo.md`](todo.md) after L5, in this order: T8–T11 and T12 (allowance), T3–T4
(feedback), T5, T6, T13 and T7 (timeline, retraction, version cap), T14–T15 (survey). The checkpoints of
[`tasks/plan.md`](plan.md) apply.

---

## Phase 5: launch gates

## Task L18: Bring the documents in line with the code

**Description:** The README, `docs/SOP.md`, `docs/verification.md`, `docs/data-inventory.md` and
`docs/i8/` still describe a dev-token backend with nothing deployed; `evidence/ci.txt` is from 2026-10-30.

**Acceptance criteria:**
- [x] README status, stack and roadmap say that sign-in and the IONOS deployment exist; SOP and verification rows for I-8, I-18, AC-22 and AC-26 match 06
- [x] The data inventory lists IONOS SMTP, Logto's database and audit logs, and the backup bucket (written with L17, 2026-11-18)
- [x] `evidence/*.txt` is regenerated by `./scripts/ci.ps1`, and the logo decision gets its own O-number (it collides with O-25)

**Verification:**
- [x] `./scripts/ci.ps1` passes

**Done 2026-11-18, before L13.** The rows state what 06 records: built and deployed, live on Android on 2026-11-16, and the phone checks of L13 open. L13 updates the same rows with its results, so nothing here claims a check that hasn't run. Also changed: the SOP's status table is dated 2026-11-18, `docs/i8/README.md` has a status line, and the README's repository table lists `deploy/`. The logo decision is O-29 (06 and `docs/logto-branding-plan.md`). `evidence/ci.txt`, `check-trace.txt` and `check-verification.txt` are regenerated by hand from the scripts' output, because `scripts/ci.ps1` doesn't write them; `cost-model.txt` came out unchanged. `evidence/test-suite.txt` and `check-verification-baseline.txt` are records of 2026-10-30 and stay as they are.

**Dependencies:** L13 (so the records describe checked behaviour) · **Files likely touched:** `README.md`, `docs/SOP.md`, `docs/verification.md`, `docs/data-inventory.md`, `docs/logto-branding-plan.md` · **Estimated scope:** M

## Task L19: Run every existing test in CI

**Description:** `scripts/eval/test_fresh_cohort.py`, `scripts/release/test_release.py` and the
`.paseo/plugins/playbooks/tests` are never run by CI. (`backend/tests/dataset` stays out by design: it needs
the private constructed dataset and skips without it.)

**Acceptance criteria:**
- [x] `scripts/ci.ps1` runs the three suites and fails when one fails
- [x] The size check also covers hand-written `backend/**/*.py` and `app/lib/**/*.dart` (generated l10n excluded)

**Verification:**
- [x] `./scripts/ci.ps1` passes locally
- [x] `plan-checks` passes on GitHub (commit `49a7bb7`; its log shows the three new stages)

**Built 2026-11-17.** 66 more tests run in CI (21 fresh-cohort, 11 release, 34 playbook), and 182 code files are size-checked. A temporary failing test produced `CI FAIL` with exit 1 and was removed.

**Dependencies:** None · **Files likely touched:** `scripts/ci.ps1`, `docs/SOP.md` · **Estimated scope:** S

## Task L20: Secret scan and dependency audit in CI

**Description:** Add a dependency audit of the hash-pinned Python requirements and an update bot for the
pinned GitHub Actions and container images. Secret scanning needs no new workflow: the GitGuardian app
already checks every push (the audit of 2026-11-17 missed it).

**Acceptance criteria:**
- [x] Every push is scanned for secrets and a finding fails the check (GitGuardian, already installed)
- [x] `pip-audit` runs against `backend/requirements.txt` and fails on a finding; the other pinned files are audited report-only, and their findings are listed below for the owner
- [x] Dependabot proposes updates for GitHub Actions and the pinned image digests

**Verification:**
- [x] The `dependency-audit` workflow is green on GitHub (commit `2245bc7`: production pins clean, the report-only step lists the 42, 42 and 17 advisories)
- [ ] Dependabot's first run on `main` finds `changelens.Dockerfile` and `compose.yaml` (not checkable before the merge)

**Built 2026-11-17.** The audit tool is hash-pinned in `scripts/ci/requirements-audit.txt` (pip-audit 2.10.1, 29 wheels).
Findings on 2026-11-17:
- `backend/requirements.txt` (the production image): none.
- `backend/requirements-test.txt` and `scripts/eval/requirements-render.txt`: pillow 12.3.0, 42 advisories, fixed in 13.0.0.
- `scripts/ci/requirements-audit.txt`: filelock 4.1.0, 17 advisories, fixed in 4.2.1.
- Neither fixed release installs on Python 3.10, so both wait for L21; until then that step reports without failing.
Dependabot ignores Logto (upgraded by hand, runbook F), Postgres majors and Python minor or major versions.

**Dependencies:** None · **Files likely touched:** `.github/workflows/dependency-audit.yml` (new), `.github/dependabot.yml` (new), `scripts/ci/requirements-audit.txt` (new), `docs/SOP.md` · **Estimated scope:** S

## Task L21: Move off Python 3.10

**Description:** Python 3.10 reached end of life in October 2026. Regenerate the hashed requirements for the
target version, and change CI and the production image together. The owner chose **3.14.10** (2026-11-17): it is
the only candidate with one exact release for the Windows runner, the Linux runner, the image and a Windows PC,
and it is supported until October 2030. 3.11 to 3.13 are security-only, so Windows gets no new builds of them.

**Acceptance criteria:**
- [x] `backend/requirements.txt`, `requirements-test.txt` and `scripts/eval/requirements-render.txt` install with `--require-hashes` on the new version
- [x] All three workflows and `deploy/ionos/changelens.Dockerfile` (tag and digest) use the same version
- [x] Unit, integration and eval suites are green; the "Known gaps" line in the runbook is removed

**Verification:**
- [x] All three workflows green on GitHub on 3.14.10 (commit `f6d9571`: 884 backend unit tests, the integration suite on Linux, 185 evaluation, release and playbook tests, and a clean audit of all four pin files)
- [x] The owner's PC: Python 3.14.10 installed, `.venv` and `backend/.venv` recreated, `./scripts/ci.ps1` reports `CI PASS` (2026-11-17, checkout at `main` `430414f`: 884 backend unit tests, 185 evaluation, release and playbook tests)
- [x] The owner's PC: the integration command (`cd backend; docker compose up -d --wait; .venv\Scripts\python -m pytest tests/integration -q -rs`): 175 passed, none skipped (2026-11-17, Postgres 16.15 and MinIO from the development compose file)
- [x] The server: redeployed 2026-11-17 as in runbook F; `docker compose exec api python --version` prints `Python 3.14.10` and all eight services are up. From outside at 21:28Z: `api` 401 without a token, `auth` 200, and `/docs`, `/redoc` and `/openapi.json` 404. The monitor recorded no alert: `/var/lib/changelens-monitor` is empty on 2026-11-18, last changed 2026-11-17 07:50, before the redeploy (that the cron job itself ran was not checked). Not repeated: the restore test (no schema change since L10)

**Built 2026-11-17 on branch `l21-python`.** Run on the owner's PC the same day, after the merge.
- Version changes: numpy 2.2.6 to 2.5.5 (3.14 wheels), pillow 12.3.0 to 13.0.0 and filelock 4.1.0 to 4.2.11 (the 59 advisories of L20). The audit now fails on a finding in any file.
- `scripts/ci/pin_hashes.py` rewrites a pin file's hashes from PyPI; for 3.10 it reproduced 53 of the 54 old pins exactly (cffi gains one macOS wheel).
- Two tests held only on 3.10 and were made independent of it: one forced a parser error with deeply nested JSON, which 3.14 parses; one hashed raw PDF bytes, which differ with the interpreter's compression library. The canonical digest is the same on 3.10, 3.11 and 3.14, so the fixtures did not change.
- Unit tests still run only on Windows in CI; on Linux, the production platform, only the integration suite runs.

**Dependencies:** None (its own pull request; no other backend task in flight) · **Files likely touched:** `backend/requirements*.txt`, `scripts/eval/requirements-render.txt`, `.github/workflows/*.yml`, `deploy/ionos/changelens.Dockerfile` · **Estimated scope:** M

## Task L22: Security review and incident runbook (D-9)

**Description:** Review tenancy, injection, logging, the provider data flow and the mobile client against
the deployed system, and write the incident-response runbook with the 72-hour Art. 33 notification.

**Acceptance criteria:**
- [x] A findings list with severities; no high-severity finding is open (2026-11-18, for the scope built that day; Phase 4 features are reviewed when they exist)
- [ ] `docs/incident-runbook.md` exists and names who is notified, by when, and where the evidence is kept (drafted 2026-11-18; the authority's name and the contact address come with L23, and it is not rehearsed)
- [ ] D-9's dependency on I-16 and I-19 in 05 is rewritten for the launch scope

**Verification:**
- [ ] Owner sign-off recorded in 06; `./scripts/ci.ps1` passes

Review of 2026-11-18: [`docs/security-review.md`](../docs/security-review.md). Fixed: 1 high, 6 medium (LR-2, LR-3 in L31, LR-4 in L32, LR-12 on 2026-11-19, LR-10 in L33 on 2026-11-21, LR-13 with the key split of 2026-11-19 and the backup job's internet access, on the server since 2026-11-21; the first daily base backup through the proxy was uploaded on 2026-11-22), 5 low. Open: 1 medium (L34) and 20 low to fix, schedule or accept.

**Dependencies:** L13, L11, L12, and Phase 4 (the review covers the launch scope) · **Files likely touched:** `docs/incident-runbook.md` (new), `docs/review-ledger.md`, `docs/05-backlog.md` (private) · **Estimated scope:** M

## Task L23: Legal texts: fill, apply the review, publish, link (I-20)

**Description:** Fill the `[SQUARE BRACKET]` placeholders, apply the lawyer's changes, publish the five
texts on a web page, and link them in the app. Then the consent flag can be turned on.

**Acceptance criteria:**
- [ ] No placeholder is left in `docs/legal/*.md`; the texts match `docs/data-inventory.md`
- [ ] The published URLs open in both languages and are linked from the app's settings and sign-in screens
- [ ] `consent_policy_version` matches the published privacy text's version

**Verification:**
- [ ] `git grep -n "\[[A-Z ]\{4,\}\]" -- docs/legal` prints nothing; App command passes
- [ ] Manual: the links open on a device

**Dependencies:** L4 · **Files likely touched:** `docs/legal/*.md`, `app/lib/screens/settings_screen.dart`, `app/lib/screens/sign_in_screen.dart`, `app/lib/l10n/app_*.arb`, `backend/changelens/config.py` · **Estimated scope:** M

## Task L24: Close or schedule the open UI findings

**Description:** `docs/ui-ux-audit.md` (3 P1, 6 P2) and the timeline critique of 2026-11-16 (3 P2, 1 P3) have
no recorded outcome. Check each against the current screens and mark it fixed, scheduled or declined.

**Acceptance criteria:**
- [x] Every finding has a status with a commit or task reference
- [x] Each still-open P1 becomes its own task in this file

**Verification:**
- [x] App command passes (no analyzer issues, 285 tests); `./scripts/ci.ps1` passes in `plan-checks` on GitHub for the branch `l24-ui-findings`

**Done 2026-11-18** against `main` at `4e3df10`, by reading source and tests; nothing was checked on a device.
Of the 13 findings, 9 are fixed (A1, A3, A4, A7, A9 and all four timeline items) and 4 are partly open: A2
(P1) is task L27; A5, A6 and A8 (P2) are task L28. Nothing was declined: that is the owner's call. The
statuses, commits and remaining gaps are in a table at the top of `docs/ui-ux-audit.md`. The app files in the
main checkout differed from `main` only in line endings, so no uncommitted app work was pending.

**Dependencies:** the second session's app edits are committed · **Files likely touched:** `docs/ui-ux-audit.md` · **Estimated scope:** S

## Task L27: Imports keep their draft, and empty fields say why (audit A2, P1)

**Description:** An import from the project screen closes its sheet before the upload, so a failed upload
loses the label and the pasted text. Blank required fields refuse without a message, and an empty project
name closes the sheet. Keep drafts in memory only (AC-25: nothing on disk).

**Acceptance criteria:**
- [x] After a failed import, the sheet is open or reopens with the label and pasted text intact; a success or Cancel clears them
- [x] A blank required field shows an error at the field and is announced: import label and text, note, approval, project name
- [x] An empty project name keeps the sheet open

**Verification:**
- [x] App command passes, with new widget tests for a failed import and for each blank field (no analyzer issues, 293 tests)

**Built 2026-11-18; checked on the Fairphone 2026-11-18 and the iPhone 2026-11-20.** A failed import from the project screen reopens its sheet with the label, the pasted text and the reason; a failed PDF import keeps the label and the PDF is picked again. The draft lives in memory for that one import only. Each sheet is a Flutter `Form`: the main button shows a message at every blank required field, and Flutter announces the first one. Two things the tests found: with re-checking set on the whole form the message was announced twice and again on every keystroke, so it is set per field; and at 2x text on a 320-wide screen a message was cut after one line, so messages now wrap. iPhone, 2026-11-20 (`docs/device-sitting-1.md` sections 4 and 5): VoiceOver spoke the first field message once, and at the largest text size the Label message was readable next to the character counter. Not heard with TalkBack. Tests: `app/test/drafts_and_required_fields_test.dart`.

**Dependencies:** None · **Files likely touched:** `app/lib/screens/project_screen.dart`, `compare_screen.dart`, `projects_screen.dart`, `finding_screen.dart`, `app/lib/l10n/app_*.arb`, `app/test/` · **Estimated scope:** M

## Task L28: Remaining P2 UI findings: tablets, polling, spoken evidence location (audit A5, A6, A8)

**Description:** Three findings are fixed in part. Each part below can also be declined by the owner with a
line in 06; A5 depends on whether iPad is a target at launch.

**Acceptance criteria:**
- [x] A5: iPad is either removed as a target, or its orientations match the portrait lock and wide screens get a reading-width limit (removed 2026-11-18, the owner's decision: `TARGETED_DEVICE_FAMILY = 1` and no iPad orientations; built on Codemagic 2026-11-20, `ios-device-check` build 5)
- [x] A6: polling pauses while the app is in the background, and every request has a time limit with a plain message
- [x] A8: the marked passage has a spoken label in the text view and a spoken page description in the PDF view, checked once with VoiceOver or TalkBack (built 2026-11-18; heard with TalkBack on the Fairphone 2026-11-18 and with VoiceOver on the iPhone 2026-11-20, L13 sittings)

**Verification:**
- [x] App command passes (no analyzer issues, 300 tests); the screen-reader check is recorded in `docs/ui-ux-audit.md` (TalkBack 2026-11-18, VoiceOver 2026-11-20)

**Built 2026-11-18; checked on the Fairphone 2026-11-18 and the iPhone 2026-11-20.** A6: the project list, the project and the status screen skip their timer ticks unless the app is in front, and poll again on the first tick after it returns. Every API request ends after 30 seconds without a complete answer (5 minutes when it carries a file), and the screens then show their usual "can't be reached" message with Retry. The limit ends the wait and doesn't cancel the request, so an upload that the server finishes later can exist twice after a retry. A8: the text view names the marked passage before the page text, and the PDF view is one described image ("PDF page 2. Marked passage: …", or that the passage is not marked). The PDF view can't be drawn in widget tests, so only its wording is tested. On both phones the status screen caught up within a few seconds after a minute in the background; that polling stops there can't be seen on a phone. Tests: `app/test/polling_and_spoken_evidence_test.dart`.

**Dependencies:** L27 first (same screens); built before the L13 device build, so the screen-reader check joins that sitting · **Files likely touched:** `app/lib/screens/comparison_screen.dart`, `project_screen.dart`, `evidence_screen.dart`, `app/lib/api.dart`, `app/ios/Runner/Info.plist` · **Estimated scope:** M

## Task L29: iOS Keychain: clear it on a fresh install and show its effective protection (03a P10, for L25)

**Description:** Two of L25's iOS checks can't pass today (`scripts/release/README.md`, "Observing the
iOS-only checks"). iOS keeps Keychain items when the app is deleted, and nothing clears them, so a reinstall
starts signed in. And the protection of the stored items can only be observed if the app reads it back.

**Acceptance criteria:**
- [x] On the first launch after an install, the app deletes Keychain items left by an earlier install before it restores a session. It waits until protected data is available, so a launch before the first unlock never deletes a valid session (iPhone 2026-11-20: build 5, deleted while signed in and reinstalled, opened on the sign-in screen; the wait for protected data is not something a sitting shows)
- [x] The app reads the protection class and the sync setting of its own Keychain items and shows them in plain words (the owner picks the place: a line in Settings, or hidden) (iPhone 2026-11-20: the Settings line read as intended, word for word)
- [ ] The readback is in the store build too, because the L25 receipt binds to the inspected artefact (in every build by the code; seen in the ad hoc build 5, not yet in an `ios-testflight` build: L25)

Built 2026-11-18 and merged the same day (PR 55), before any iOS build had compiled it. The compile
check passed afterwards, and the iPhone check on 2026-11-20 (`docs/device-sitting-1.md`, section 6).

- The cleanup runs in `AppDelegate.swift` before the Flutter engine starts. An empty marker file in
  Application Support marks an install as seen; iOS deletes the app's files with the app, but not the
  Keychain. Without the marker the app deletes its Keychain items of every class, then writes the marker.
  If a delete fails, or protected data is unavailable, that launch decides nothing and the next one tries
  again. The marker is a file and not a preference, because preferences would need a privacy manifest.
- The readback is one line in Settings, under "Signed in with" (owner's choice, 2026-11-18), on iOS only and
  in every build. As intended it reads "Your sign-in is stored on this iPhone only. It can be read once the
  iPhone has been unlocked after a restart, and it is not synchronised with iCloud." Otherwise it names
  what iOS reported. No line means no observation: nothing is stored yet, or the readback failed.
- The readback covers every generic-password item the app can see, not only the plugin's.

**Verification:**
- [x] The iOS build compiles: the change is native Swift and can't be built on the PC. Passed 2026-11-18 in the GitHub job `ios-compile` (PR 59, run 44358870196: Xcode 16.4, Flutter 3.47.9, `flutter build ios --release --no-codesign`), after the merge and not before it as planned. Codemagic's `app-ios-compile-check` did not run: its queue did not move that day
- [x] App command passes, with tests for the Dart side (2026-11-18: analyzer clean, 309 tests)
- [x] Manual on the iPhone: sign in, delete the app, reinstall and open it: the sign-in screen. Signed in again, Settings shows the sentence above (2026-11-20, build 5: both seen; the sentence was read word for word before the reinstall and confirmed after it)

**Known effect:** the first launch after updating to this version looks like a fresh install and signs out
once. Before launch that affects the owner's phones only.

**Dependencies:** None; before L25 · **Files likely touched:** `app/ios/Runner/AppDelegate.swift`, `app/lib/services.dart`, `app/lib/screens/settings_screen.dart`, `app/lib/l10n/app_*.arb`, `app/test/` · **Estimated scope:** M

## Task L30: MFA and onboarding findings from the L13 Fairphone sitting (owner, iPhone first)

**Description:** The Fairphone sitting (2026-11-18, `docs/device-sitting-1-android.md`) found two fails. Account A never had MFA set up: no authenticator entry existed, so Logto asked for no code with email or Google. And account A arrived on the Fairphone with its onboarding unfinished, although onboarding state is stored on the server. That account A was deleted. iPhone sitting of 2026-11-20 (`docs/device-sitting-1.md`): a new account A has two-step verification (authenticator and backup codes) and Google linked, and Logto asked for the code with email and with Google. Logto let another test user skip the MFA offer, which is how C4 step 4 sets it (offered, not forced); whether to force it is the owner's call. Before the Fairphone repeat, delete the one older test user with a Google link that is still in Logto: the link step goes to whichever user holds the same verified address, and in the iPhone sitting it once went to a leftover test user.

**Acceptance criteria:**
- [x] The iPhone sitting's results are written into `docs/device-sitting-1.md`, including whether Logto offered MFA setup and whether the onboarding was finished there (2026-11-20: offered after the email code and set up; the onboarding was finished)
- [x] With a new test account, MFA is set up with an authenticator, and Logto asks for its code with email and with Google, on both phones (C4 step 4 says MFA is offered, not forced) (iPhone 2026-11-20: yes for both; Fairphone 2026-11-20: yes with email, by the owner's report, sign-in completed 22:10:16 UTC in the api log; with Google the same evening: asked, then the project list, and Settings said "Signed in with Google", by the owner's report; in the api log the one-time token is at 22:46:57 and the completing `POST /session 200` at 22:47:27 UTC, with no `link_required`, no new user and no `PUT /me/onboarding`; a first attempt at 22:42:58 was not carried through)
- [x] Onboarding finished on one phone does not show again on the other; if it does, the cause is found and fixed (2026-11-20: account A finished the onboarding on the iPhone, and the Fairphone opened the project list after the email sign-in, by the owner's report, and the api log has no `PUT /me/onboarding` since the install; the 2026-11-18 case was an account that had not finished it)

**Verification:**
- [ ] Results recorded in runbook section E (MFA line) and a dated 06 row (section E: done for both phones 2026-11-20; the 06 row is the owner's)

**Dependencies:** None · **Files likely touched:** `docs/device-sitting-1.md`, `deploy/ionos/README.md`, possibly `app/lib/auth/session.dart` · **Estimated scope:** S

## Task L31: A deleted account can't be re-created by a token that is still valid (L22, LR-3)

**Description:** `DELETE /me` clears the sign-in subject at once, but a token from another device stays valid
for up to 15 minutes, and `POST /session` with it creates a fresh account under the deleted subject.

**Acceptance criteria:**
- [x] After a completed deletion, `POST /session` with a token issued before it returns 401 and creates no row (built 2026-11-18: before a first sign-in creates an account, the api asks Logto whether the user still exists; Logto unreachable gives 503 and creates nothing)
- [x] The tombstone still ends up without personal data (ID and timestamps only) (deletion itself is unchanged)
- [x] The app's notice after deletion matches what the server did (204 or 202) (unchanged: `DELETE /me` answers as before)

**Verification:** backend unit and integration tests pass in CI, with a test for the first criterion (891 unit tests pass locally; the four new ones fail without the check; the integration test runs in CI only).

**Dependencies:** None · **Files likely touched:** `backend/changelens/domain/accounts.py`, a migration or `0004`'s functions, `backend/tests/integration/test_account_deletion_db.py` · **Estimated scope:** S

## Task L32: The worker holds no Logto credential and has no route to Logto; parser hardening (L22, LR-4, LR-13)

**Description:** Bring the deployment in line with 03 §6: the Management credential only in the api and
retention, and a compromised parser unable to read the worker's secrets.

**Acceptance criteria:**
- [x] The worker starts without the Logto Management credential and the rate-limit key, from its own env file (built 2026-11-18: `worker.env` is the only file it reads, and it stops at start when it is given one of them)
- [x] Logto is not on a network the worker is on (built 2026-11-18: Logto and Postgres share the new `authdb` network; in a local start the worker couldn't resolve `logto`)
- [x] The parse child can't read its parent's environment or start processes; the worker drops capabilities (built 2026-11-18; with both protections switched off, the same probes read the environment and forked)
- [x] The backup job uses a role with replication rights only, not the superuser (built 2026-11-18: `changelens_backup`, plus the right to call one function that prunes Logto's audit log; every other attempt was refused locally)

**Verification:** backend tests pass in CI; the compose file starts locally in Docker (done 2026-11-18 with test values: Postgres, Logto and the proxy started; the worker's settings, database connection and a parse, and the backup role, were checked in their containers; the worker loop needs the storage and wasn't run). Manual on the server: the release steps in runbook F ran on 2026-11-19; every service is up, the worker can't resolve `logto`, and the backup role connects for a base backup and may prune the audit log. The base backup of 2026-11-20 was uploaded, and a comparison from the iPhone completed that day (two parse jobs, four model calls, 1 finding; `docs/device-sitting-1.md`, step 3).

**Dependencies:** None; a deployment with a new server file (owner) · **Files likely touched:** `backend/changelens/config.py`, `backend/changelens/pipeline/sandbox.py`, `deploy/ionos/compose.yaml`, `deploy/ionos/env/`, `deploy/ionos/README.md` · **Estimated scope:** M

## Task L33: Per-account bounds on uploads and queued work (L22, LR-10)

**Description:** One account must not keep the single worker busy for everyone or fill the storage. The fair-use allowance (T8 to T12) counts comparisons, not uploads or waiting jobs. Built 2026-11-21, on the server since the release of the same day; the limits are settings with defaults, so the server's env file needs no change. Not covered: how long one upload may take (a slow upload holds its slot), and the app shows its general "not accepted" message for the new refusal.

**Acceptance criteria:**
- [x] An upload or comparison is refused with 429 when the account already has N unparsed versions or N unfinished comparisons (numbers: owner, with L5) (built 2026-11-21: `429 account_limit_reached` with the bound's name, checked in the transaction that would add the rows, both upload routes; a replay of an accepted request is still answered; defaults 8 unparsed versions and 3 unfinished comparisons; the owner kept all four defaults on 2026-11-21)
- [x] Stored bytes per account have a ceiling (built 2026-11-21: default 1 GiB, counted over every original the account still has a row for, deleted projects included)
- [x] Concurrent uploads are bounded so the api stays within its memory limit (built 2026-11-21: 4 upload requests at once per api process, 2 of them for one account, taken after sign-in is checked and before the body is read; over that `429 rate_limited` with `Retry-After`. Sizing estimated, not measured: a request with two 10 MB PDFs peaks near 60 MB, and the api has 1 GB)

**Verification:** backend unit and integration tests pass in CI. (2026-11-21 locally: 921 unit tests, 20 new in `tests/unit/test_account_bounds.py`, 8 of which fail with the check switched off; 181 integration tests against Postgres and MinIO in Docker, 5 new in `tests/integration/test_account_bounds_db.py`, the 4 Linux-only tests skipped. In CI the same day: the pull request's checks and the three workflows on `main` passed. Released on the server 2026-11-21 with the app release command (runbook F): the api, the worker, retention and Caddy were recreated and every service is up; the running api reads the four limits as 8, 3, 1073741824 and 4; afterwards the api log shows a comparison from the app accepted (`POST /projects/{project_id}/comparisons 202`) and opened three seconds later. Not checked on the server: the refusal itself.)

**Dependencies:** L5 for the numbers · **Files likely touched:** `backend/changelens/api/routes.py`, `backend/changelens/api/comparisons.py`, `backend/changelens/api/app.py`, `backend/changelens/config.py` · **Estimated scope:** M

## Task L34: Android sign-out ends the browser session on every browser (L22, LR-11; owner decision)

**Description:** Add `login` to the sign-in request's `prompt`, so Logto asks again even when the browser kept its session. It touches all three sign-in methods and can only be confirmed on a phone.

**Acceptance criteria:**
- [ ] After sign-out, Continue with email asks for the address and the code again, on Android and iOS
- [ ] Google and Apple sign-in still complete without an extra step

**Verification:** App command passes. Manual on both phones: the two criteria. Before the change, the first one on the Fairphone shows whether its browser already honours the private tab. Fairphone, 2026-11-20, before any change (debug build from `main` at `b4cbea6`; Android 15, default browser Chrome 157, both read over adb): after Settings → Sign out, Continue with email asked for the address and the mail code again, by the owner's report, one run. The api log since the install has one `POST /session 200` (22:10:16 UTC), the sign-in before the sign-out, and none after it: the owner stopped the second attempt once Logto asked again, and what Logto's page asked is not in the api log. So Chrome on this phone honours the private tab. Other browsers and other Chrome versions are not covered by this check. Owner's decision, 2026-11-20: the task stays open and is not built now.

**Dependencies:** A device sitting · **Files likely touched:** `app/lib/auth/logto.dart`, `app/test/auth_session_test.dart`, `docs/device-sitting-1*.md` · **Estimated scope:** S

## Task L35: Google sign-in on the iPhone opens the sign-in page every time, with one Google sheet (L13)

**Description:** iPhone sitting, 2026-11-20 (`docs/device-sitting-1.md`, section 6, `ios-device-check` build 5). Three of five Google sign-ins in a row ended in "Sign-in didn't work. Try again, or choose another method." The api had issued the one-time token each time, and the app never requested Logto's page (10:18:53 UTC: token issued, no `GET /oidc/auth`). The two later Google sign-ins that went through Logto's page (15:58 and 16:08 UTC) worked, so the fault is intermittent. Google's own sheet also appears twice per sign-in; three were counted once. Not verified, from reading the code: `app/lib/auth/providers.dart` calls `authenticate` and then `authorizeServer`, which may be the two sheets, and the sign-in browser may start while the second sheet is still closing.

**Acceptance criteria:**
- [x] The cause of the failed sign-ins is found and written down; if it can't be reproduced, the app records which browser error it got (`browser_<code>`), without personal data (2026-11-20: a likely cause is written down below, not reproduced; the failure message now shows the code)
- [x] After a Google code exchange the sign-in browser opens every time, and a Google sign-in shows Google's sheet once, or the second sheet is explained as needed (iPhone, 2026-11-20, build 6: 12 of 12, one sheet each)

**Verification:**
- [x] App command passes, with a test for the changed path (2026-11-20: analyzer clean, 320 tests; `app/test/sign_in_browser_and_google_test.dart` and two tests in `session_settings_test.dart`)
- [x] Manual on the iPhone: ten Google sign-ins in a row with the linked account all sign in, and the sheet count is noted (2026-11-20, `ios-device-check` build 6 from `main` at `ea3b8a7`: twelve in a row, some as fast as possible, all signed in after the authenticator code, Google's sheet once each by the owner's count; the api log of that hour has 12 "one-time token issued" and 24 `POST /session 200`, two per completed sign-in)

**Built 2026-11-20 and passed on the iPhone the same day (build 6).** Twelve sign-ins without a failure don't prove the cause named below, since the fault was intermittent (three of five on build 5); if it returns, the message now names its code. Read from the sources of `google_sign_in_ios` 6.4.0, `flutter_web_auth_2` 5.1.0 and Google's SDK 9.0.0 (`GIDSignIn.m`). The second sheet, cause found: the app asked for the server code with the scopes `openid` and `email`; the SDK shows its sheet again unless every requested scope is literally among the granted ones, and Google grants `email` under its long name. The sign-in itself already returns the code and the plugin keeps it, so on iOS the app now asks for no further scope first and falls back to the old request if that yields nothing; Android is unchanged. The failed sign-ins, likely cause, not proven: the browser plugin answers `ACQUIRE_ROOT_VIEW_CONTROLLER_FAILED` at once while another view controller is still presented, which fits a Google sheet that is still closing and the log (no request to Logto). The app now opens the browser again after 0.4 and 0.8 seconds when it failed within one second; a cancellation or a later failure is not retried. Which error code the phone got on 2026-11-20 is not known, because the app showed none. Since this change the sign-in failure message has a line "Code: …" under it with the event code (owner's decision, 2026-11-20; English and German; only letters, digits and `_ . : -`, at most 60 characters), so a failed attempt on the next build names its cause.

**Dependencies:** A new `ios-device-check` build for the manual check (paid; the owner starts it) · **Files likely touched:** `app/lib/auth/providers.dart`, `app/lib/auth/logto.dart`, `app/lib/auth/session.dart`, `app/test/` · **Estimated scope:** S to M

## Task L25: Release-build inspection and store declarations (I-17; owner, both phones)

**Description:** Build the signed artefacts, install them on both phones, and record the receipts that
`scripts/release/README.md` defines. Fill the App Store privacy labels and the Play data-safety form from the data inventory.

**Acceptance criteria:**
- [ ] `check_acceptance.py` passes for the Android and the iOS artefact with the owner's receipts
- [ ] The store declarations, the privacy texts and the data inventory describe the same records
- [ ] The build signs in against production and shows no developer settings

**Verification:**
- [ ] `python scripts/release/check_acceptance.py --platform android --artifact <release.apk> --receipt <receipt.json>` and the same for `ios`

**Dependencies:** L7, L13, L23, L3 (Android), L29 (the two iOS checks; `handoff_file_protection` is not required before I-16, owner's decision 2026-11-18) · **Files likely touched:** none in Git (receipts stay outside) · **Estimated scope:** M

## Task L26: Usability test with 5 users (D-10; owner)

**Description:** Five people from the target audience, in person, on the owner's phones, with synthetic briefs.

**Acceptance criteria:**
- [ ] 5 users complete import → report → review without help, or each failure is logged
- [ ] The main issues are fixed or have tasks

**Verification:**
- [ ] A dated 06 row with the five outcomes

**Dependencies:** L13, L25 · **Files likely touched:** `docs/06-decision-log.md` (private) · **Estimated scope:** M

### Checkpoint D: launch
- [ ] D-9 has no open high-severity finding, the D-10 users completed the flow, and the release gate passes
- [ ] Store declarations, privacy texts and the data inventory agree
- [ ] Owner decision to submit
