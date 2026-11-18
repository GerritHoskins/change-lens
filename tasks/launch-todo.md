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

**Description:** One sitting on the iPhone and the Fairphone against the IONOS server, with synthetic documents only. It closes every device check the audit found open. The iPhone half has a step-by-step checklist with a result line per step: [`docs/device-sitting-1.md`](../docs/device-sitting-1.md).

**Acceptance criteria:**
- [ ] Sign-in: Apple on the iPhone, Google on both, an email code on both, a completed `link_required` link, and MFA as in AC-26
- [ ] One PDF comparison started from screen P2 completes on the server on each phone (this also proves the worker's egress allow-list); on the iPhone the PDF comes from the picker
- [ ] Account deletion works on both phones and the Logto user is gone; the consent screen (build with `CHANGELENS_CONSENT=true`) shows once and the Settings switch withdraws

**Verification:**
- [ ] Each result has a dated line in runbook section E or in 06; the M1b and M2 exit rows exist in 06
- [ ] Every fault found becomes its own task in this file

**Dependencies:** L10; a signed build from `ios-device-check` and a debug APK, both built with `CHANGELENS_CONSENT=true` (`ios-device-check` passes it since 2026-11-18; the debug APK is built on the PC with the same define); L27 and L28 first, so one sitting sees the final screens (device-first order in `tasks/launch-plan.md`) · **Files likely touched:** `deploy/ionos/README.md`, `docs/06-decision-log.md` (private), `tasks/todo.md` (Task 2 manual check) · **Estimated scope:** M (half a day)

## Task L17: Outside uptime check and patch reminder (owner)

**Description:** `monitor.sh` runs on the server it watches. Add an outside check on both domains
(runbook D3) and the weekly patch calendar entry (D4). The uptime service is a new processor that sees URLs only.

**Acceptance criteria:**
- [ ] Both `https://api.pixeltronic.dev/projects` (expects 401) and the Logto OpenID configuration (expects 200) are checked from outside, with an alert to the owner
- [ ] `docs/data-inventory.md` lists the service; the "Still open" line in runbook section D is removed
- [ ] The weekly calendar entry exists

**Verification:**
- [ ] Manual: stop `caddy` for 10 minutes and receive the outside alert

**Built 2026-11-17, not yet live.** Owner's choices: the check is a scheduled GitHub Actions workflow (`.github/workflows/uptime.yml`, every 10 minutes, three tries per URL), not a separate uptime service, so no new processor; the owner adds the calendar entry. The check script passed against the live server and failed on a wrong expected status. The data inventory and runbook section D describe it. Open: the workflow runs only from `main`, so it starts after the next merge; then the alert test (stop `caddy` for 20 minutes, not 10, because GitHub starts scheduled runs late), the owner's GitHub setting for failed-workflow mails, and the calendar entry. The "Still open" line in section D goes when those are done.

**Dependencies:** None · **Files likely touched:** `docs/data-inventory.md`, `deploy/ionos/README.md` · **Estimated scope:** XS

### Checkpoint B: M2 exit
- [ ] A new user signs up, compares and deletes the account on both platforms
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
- [ ] README status, stack and roadmap say that sign-in and the IONOS deployment exist; SOP and verification rows for I-8, I-18, AC-22 and AC-26 match 06
- [ ] The data inventory lists IONOS SMTP, Logto's database and audit logs, and the backup bucket
- [ ] `evidence/*.txt` is regenerated by `./scripts/ci.ps1`, and the logo decision gets its own O-number (it collides with O-25)

**Verification:**
- [ ] `./scripts/ci.ps1` passes

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
- [ ] A findings list with severities; no high-severity finding is open
- [ ] `docs/incident-runbook.md` exists and names who is notified, by when, and where the evidence is kept
- [ ] D-9's dependency on I-16 and I-19 in 05 is rewritten for the launch scope

**Verification:**
- [ ] Owner sign-off recorded in 06; `./scripts/ci.ps1` passes

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

**Built 2026-11-18, not yet on a device.** A failed import from the project screen reopens its sheet with
the label, the pasted text and the reason; a failed PDF import keeps the label and the PDF is picked again.
The draft lives in memory for that one import only. Each sheet is a Flutter `Form`: the main button shows a
message at every blank required field, and Flutter announces the first one. Two things the tests found: with
re-checking set on the whole form the message was announced twice and again on every keystroke, so it is set
per field; and at 2x text on a 320-wide screen a message was cut after one line, so messages now wrap. Open
for the L13 sitting: hear the messages with VoiceOver or TalkBack, and look at the label field's message at
large text, where it shares its row with the character counter. Tests: `app/test/drafts_and_required_fields_test.dart`.

**Dependencies:** None · **Files likely touched:** `app/lib/screens/project_screen.dart`, `compare_screen.dart`, `projects_screen.dart`, `finding_screen.dart`, `app/lib/l10n/app_*.arb`, `app/test/` · **Estimated scope:** M

## Task L28: Remaining P2 UI findings: tablets, polling, spoken evidence location (audit A5, A6, A8)

**Description:** Three findings are fixed in part. Each part below can also be declined by the owner with a
line in 06; A5 depends on whether iPad is a target at launch.

**Acceptance criteria:**
- [x] A5: iPad is either removed as a target, or its orientations match the portrait lock and wide screens get a reading-width limit (removed 2026-11-18, the owner's decision: `TARGETED_DEVICE_FAMILY = 1` and no iPad orientations; not yet built on Codemagic)
- [x] A6: polling pauses while the app is in the background, and every request has a time limit with a plain message
- [ ] A8: the marked passage has a spoken label in the text view and a spoken page description in the PDF view, checked once with VoiceOver or TalkBack (built 2026-11-18; the screen-reader check is open)

**Verification:**
- [ ] App command passes (no analyzer issues, 300 tests); the screen-reader check is recorded in `docs/ui-ux-audit.md` (open, L13 sitting)

**Built 2026-11-18, not yet on a device.** A6: the project list, the project and the status screen skip
their timer ticks unless the app is in front, and poll again on the first tick after it returns. Every API
request ends after 30 seconds without a complete answer (5 minutes when it carries a file), and the screens
then show their usual "can't be reached" message with Retry. The limit ends the wait and doesn't cancel the
request, so an upload that the server finishes later can exist twice after a retry. A8: the text view names
the marked passage before the page text, and the PDF view is one described image ("PDF page 2. Marked
passage: …", or that the passage is not marked). The PDF view can't be drawn in widget tests, so only its
wording is tested. Tests: `app/test/polling_and_spoken_evidence_test.dart`.

**Dependencies:** L27 first (same screens); built before the L13 device build, so the screen-reader check joins that sitting · **Files likely touched:** `app/lib/screens/comparison_screen.dart`, `project_screen.dart`, `evidence_screen.dart`, `app/lib/api.dart`, `app/ios/Runner/Info.plist` · **Estimated scope:** M

## Task L25: Release-build inspection and store declarations (I-17; owner, both phones)

**Description:** Build the signed artefacts, install them on both phones, and record the receipts that
`scripts/release/README.md` defines. Fill the App Store privacy labels and the Play data-safety form from the data inventory.

**Acceptance criteria:**
- [ ] `check_acceptance.py` passes for the Android and the iOS artefact with the owner's receipts
- [ ] The store declarations, the privacy texts and the data inventory describe the same records
- [ ] The build signs in against production and shows no developer settings

**Verification:**
- [ ] `python scripts/release/check_acceptance.py --platform android --artifact <release.apk> --receipt <receipt.json>` and the same for `ios`

**Dependencies:** L7, L13, L23, L3 (Android) · **Files likely touched:** none in Git (receipts stay outside) · **Estimated scope:** M

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
