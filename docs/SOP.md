# SOP — Running and Changing ChangeLens

This repository holds the plan (`docs/`), the development backend (`backend/`), the Flutter app (`app/`), the D-15 proof of concept (`poc/`) and the evaluation tools (`scripts/eval/`). In this SOP, "running" means running the checks and "changing" means editing the plan and code without losing traceability. To start the software, see [backend/README.md](../backend/README.md) and [app/README.md](../app/README.md). Nothing is deployed publicly, and the backend must not be until I-8 replaces its dev token.

## Status on 2026-11-13

| State | What | Evidence |
|---|---|---|
| Built and tested | Dev API and worker (I-22), parsing (I-1, I-1c), the fact pipeline (I-2 to I-6) and the IONOS model check (D-17) | Backend unit tests in CI (`plan-checks`); integration tests in CI (`backend-integration`) and locally (§1); a row per task in 06 |
| Built, closed with a deviation | Evaluation harness (I-7): 2 fabricated scope changes against a gate of 0 | `scripts/eval/i7_receipt.json` and 06 |
| Met on both phones (M1, 2026-11-10) | App shell and report screens (I-9, I-10) | Android (06, 2026-11-01) and iPhone (06, 2026-11-10). On the iPhone the comparison used pasted text only, so the iOS PDF picker is not yet exercised |
| Built, M1b exit not yet recorded | Finding topics and extract-v7 (I-23, `f6fb4e6`); one-screen compare (I-24) and review evidence telemetry (I-26, `f5cbea1`); the Calm Bold app screens P0–P7 with German strings (I-25, `87ae0e9`, `5f940a4`) | Unit and widget tests. The iPhone M1 build already ran this app, but the M1b exit check (05) on both phones is not in 06 |
| Open, held-out run fails one gate | I-7b: 0 fabricated scope changes over 2 development runs (2026-11-10), but 4 over 2 held-out runs of the fresh cohort (gate 0); every other gate passes (06, 2026-11-13) | `test_i7.py` passes again with the fresh receipt; `release-readiness` still blocks on its FAIL verdict. Owner decision open: fix with a new fresh cohort, or accept a deviation. Must be settled before the public release (O-21: no external testers) |
| Partly built | M2: Logto checks run locally (D-8; C2 decided as O-19, the backend owns Google linking); JWT verifier and Apple refresh-token encryption (I-8 groundwork, `f91b2f5`, not wired into the API); project deletion, 30-day retention and the data inventory (I-13). I-14: the per-comparison cost ceiling only | D-8 IONOS hosting and Apple sign-in checks not started; the dev token is still the only API authentication; account deletion waits for I-8; the fair-use allowance, spend cap and kill switch wait for I-8 and I-14 |
| Release tooling, nothing published | Release config and acceptance checks (`scripts/release/`), the manual `release-readiness` job, Codemagic ad hoc iOS and signed Android builds (I-17 prep) | `release-readiness` is expected to block on the stale I-7 receipt |
| Planned, not built | I-8 public sign-up, I-18 account screens, I-20 privacy texts, the I-14 fair-use allowance, and M5 (I-21, I-17, D-9, D-10, D-18) | 05 |
| After a free launch (O-20, 2026-11-13) | Subscriptions (I-19) and screenshots and share sheet (M3), rescheduled with the billing decision from the D-18 readout | 05, 06 |
| Not in v1 | Share links (I-12), push notifications (I-27) and teams | 05 |

`verification.md` records plan checks. Its Product evidence section says how far each AC is backed by the built product.

## 1. Run the checks

Everything at once (the same entry point `.github/workflows/plan-checks.yml` runs on push and pull request):

```powershell
powershell -NoProfile -File scripts/ci.ps1
```

It runs the build checks (tracked documents and scripts, and hand-written `backend/` Python and `app/lib/` Dart, under 500 lines; strict UTF-8 without mojibake; relative Markdown links resolve; no secrets or `.env` files), then the three checks below and separate text, visual, hidden-text and labelling-kit evaluation test stages (see 07 §3 and §5), the release-configuration and playbook tests, and exits 1 if anything fails. New files must be `git add`ed first, because it checks tracked files.

CI creates `.venv/` if necessary and reinstalls every wheel in `scripts/eval/requirements-render.txt` on each run (`pip --force-reinstall --no-deps --require-hashes`, wheels only), because pip skips hash checks for packages already installed. It never changes the global Python. It checks imports and runs `test_generate.py`, `test_render.py`, `test_render_hidden.py`, `test_label_kit.py`, `test_label_rounds.py`, `test_split.py` and `test_fresh_cohort.py` as separate stages, then `scripts/release/test_*.py` and `.paseo/plugins/playbooks/tests/test_*.py` (standard library only) with the same interpreter; an install/import failure, a failing test or zero tests in any stage fails CI. `backend/tests/dataset` is not part of CI: it needs the private constructed dataset and skips without it. `test_label_kit.py` runs the labelling page's offset code under Node.js and fails, rather than skips, when Node is missing (the Windows runner has it). The GitHub workflows pin `actions/setup-python` by SHA and Python 3.14.10 (x64), the release the server image uses too, and install the same lockfiles. Locally the two project environments must be made by the same minor version (`py -3.14 -m venv .venv`, and the same in `backend/`); `ci.ps1` says so when one is not. To change a pin, edit its version and run `python scripts/ci/pin_hashes.py --python 3.14 <file>` (`--all-wheels` for `requirements-render.txt`), which rewrites the hashes from the PyPI JSON API. Locally, use the project environment for the combined suite:

```bash
.venv/Scripts/python -m unittest discover -s scripts/eval
```

The backend stage (I-22) creates `backend/.venv/` if necessary, reinstalls `backend/requirements.txt` and `backend/requirements-test.txt` the same way (`--force-reinstall --no-deps --require-hashes`) and runs the backend unit tests (`pytest backend/tests/unit`), which need no Docker. A failing test, an install failure or zero passed tests fails CI. The backend integration tests need the compose Postgres and MinIO and are not part of CI yet; run them locally as described in [backend/README.md](../backend/README.md) §6:

```powershell
cd backend; docker compose up -d --wait; .venv\Scripts\python -m pytest tests/integration -q -rs
```

A third workflow, `.github/workflows/dependency-audit.yml`, audits every hash-pinned requirements file with `pip-audit` on push, on pull request and every Monday. A known vulnerability in any of them fails it. Its own tool is pinned in `scripts/ci/requirements-audit.txt`. `.github/dependabot.yml` proposes updates for the SHA-pinned actions and the digest-pinned images.

Run `.venv/Scripts/python scripts/eval/probe_label_rounds.py` to repeat the option A mutation probes. It first requires the full synthetic suite to pass, then tests 21 deliberate regressions in disposable copies; every probe must fail the same complete suite. It changes no worktree source or private data.

If Windows blocks the local script under its execution policy, use `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/ci.ps1` for that process only; do not change machine policy. D-6 failure probes on 2026-10-31 confirmed `CI FAIL` with nonzero exit for a deliberately wrong visual golden and for a blocked `pypdfium2` import; sources were restored after the probes. Visual and hidden-text fixtures and their `review.html` sheets belong in private storage outside Git. Owner per-pair review and the independently arranged code review remain distinct from automated CI.

Individual checks:

```powershell
powershell -NoProfile -File scripts/check-trace.ps1
```

The check passes only if:
- every plan document exists
- every acceptance criterion in `docs/02-mvp-spec.md` §7 is mapped in `docs/traceability.md` to a design section and an existing backlog task
- every acceptance criterion is covered by a step in `docs/03a-pipeline-logic.md`
- every architecture decision (AD-n) in `docs/03-technical-design.md` §9.6 has an ADR in `docs/adr/`

Save the output to `evidence/check-trace.txt` when it is used as evidence.

Cost-model benchmark. The defaults are the D-7 prices for Claude Sonnet 5.5 on AWS Bedrock (€1.97 / €9.85 per million input / output tokens). They are a conservative budgeting case, not the provider in use: D-17 led to IONOS (ADR-0021), whose recorded list prices are about a third of these, and the defaults stay so that every gate is tested with headroom (03 §8). The output is an estimate, not a measured cost. To try other prices, pass `-PIn` and `-POut`; if the defaults change, update 03 §8 in the same commit. `-TokenFactor` (default 1.3) sets the informational tokenizer sensitivity:

```powershell
powershell -NoProfile -File scripts/cost-model.ps1 [-PIn <EUR> -POut <EUR>]
```

It recomputes the 03 §8 scenarios and fails if a scenario uses more tokens than the reviewed baseline (stored as the 14748b6 token counts and priced at the same rates, so a price change alone never fails this part) or costs more than its gate (typical and first comparison €0.20, heavy €0.60, worst case €1.50, screenshot parse €0.13). It also prints the Gate 4 unit-economics sensitivity, which is informational. If the token estimates in 03 §8 change, update the scenario in the script in the same commit.

Mission completion check (fails until independent verification and review closure are recorded):

```powershell
powershell -NoProfile -File scripts/check-verification.ps1
```

It passes only if every AC has a row in `docs/verification.md` from a verifier who is not the author (the names `author`, `planner`, `claude-main` and `self` are rejected), with a result of `pass` or `accepted-gap` (a `fail` row fails the check) and evidence, and every finding in `docs/review-ledger.md` is `resolved` (with a reference) or `accepted` (with a reason). A pass means the plan covers every AC, not that the product does: see the Product evidence section of `docs/verification.md`. Ledger rows are recognised by an ID with an uppercase prefix, a hyphen and a number (`SEC-1`, `REV-20`, `SA-3`, `CR-13`); any new review may use a new prefix.

## 2. Change a requirement

1. Edit or add the criterion (AC-n) in `02-mvp-spec.md` §7.
2. Update or add its row in `traceability.md`, reference it from the backlog task that satisfies it (`05-backlog.md`), and tag the step that satisfies it in `03a-pipeline-logic.md`.
3. Run the check, then add a row to the change log in `06-decision-log.md` with the reason.
4. Commit. The commit is the record of when the change happened.

## 3. Make or change a decision

- **New decision:** add `docs/adr/NNNN-slug.md` (Status, Context, Decision, Consequences, Links) and list it in the index below. Architecture decisions also get an AD-n row in 03 §9.6.
- **Changed decision:** never edit an accepted ADR's decision in place. Write a new ADR, set the old one's status to "Superseded by ADR-NNNN", and update the index.
- **Owner decisions:** recorded as O-n in `06-decision-log.md` and, where they shape the architecture, as an ADR.

## 4. Frozen items

- **Gate 1 definitions and thresholds** (04 §6.1–6.3) are frozen. Any change before recruitment needs a decision-log entry with a reason. After recruitment starts, a change opens a new experiment, and its results are never pooled with the old one.
- **Gate 2 thresholds** are fixed before the held-out evaluation runs.

## 5. Reviews

After substantial changes, run independent read-only reviews against handoff §13 and for security. When a change alters the logic an AC row cites, that row must be re-verified by a non-author and its Method marked `re-verified <commit>`; `check-verification` cannot detect a stale row on its own. Record each finding in `docs/review-ledger.md` as resolved or explicitly accepted, and record per-AC verification in `docs/verification.md`.

## 6. Encoding

Files are UTF-8. Windows PowerShell 5.1 reads files as ANSI unless told otherwise, so scripts that rewrite docs must use `-Encoding utf8` on read and write.

## 7. Owner labelling rounds (option A)

Real labelling is postponed until the owner is ready after building the app. Follow the exact PowerShell commands in [GUIDE §7](../scripts/eval/GUIDE.md): create R1 pages, label all 25 real pairs (excluding P-015), `freeze`, `sample --seed 7`, wait at least 14 days from freeze, create and label blind R2 pages, `compare`, complete the resolution files, `build`, then `calibrate`. All commands take `--data` pointing outside Git. Freeze and sample refuse replacement; do not reroll the sample or edit frozen R1 exports. R1/R2 are rounds of one owner, not two labellers. Build retains `unsplit`, sets `labelled_by` to owner and records round provenance. Real metrics remain separate and non-gating; constructed model-evaluation results decide gates. No real documents or labels enter tests or Git.

## ADR index

| ADR | Title | Status |
|---|---|---|
| [0001](adr/0001-mobile-first-app.md) | iOS and Android app; no web front end | Accepted |
| [0002](adr/0002-flutter-client.md) | Flutter + Riverpod client | Accepted, conditional on D-15 |
| [0003](adr/0003-modular-monolith.md) | FastAPI modular monolith (AD-1) | Accepted |
| [0004](adr/0004-postgres-rls-queue.md) | PostgreSQL with RLS and a Postgres job queue | Accepted |
| [0005](adr/0005-managed-eu-idp.md) | Managed identity provider with EU residency | Superseded by 0020 |
| [0006](adr/0006-hosting-germany.md) | Host in Germany on IONOS | Accepted |
| [0007](adr/0007-pdfium-both-sides.md) | PDFium on the backend and the device | Accepted, verified by D-15 |
| [0008](adr/0008-no-device-content.md) | No document content on the device | Accepted |
| [0009](adr/0009-pure-pipeline-stages.md) | Pure pipeline stages (AD-2) | Accepted |
| [0010](adr/0010-uploads-through-api.md) | Uploads through the API (AD-3) | Accepted |
| [0011](adr/0011-parse-job-and-fact-cache.md) | Parse job and per-version fact cache (AD-4) | Accepted |
| [0012](adr/0012-rest-openapi.md) | REST + OpenAPI-generated client (AD-5) | Accepted |
| [0013](adr/0013-cross-tenant-not-found.md) | Cross-tenant access returns not_found (AD-6) | Accepted |
| [0014](adr/0014-deterministic-verification.md) | Deterministic evidence verification | Accepted |
| [0015](adr/0015-share-snapshots.md) | Share snapshots and web share page (AD-7) | Accepted |
| [0016](adr/0016-push-plus-polling.md) | Push plus polling (AD-8) | Superseded by 0022 |
| [0017](adr/0017-llm-port.md) | Model provider behind an injected port (AD-9) | Accepted |
| [0018](adr/0018-pilot-billing-distribution.md) | Pilot billing and distribution | Accepted |
| [0019](adr/0019-model-provider.md) | Model provider selection | Superseded by 0021 |
| [0020](adr/0020-self-hosted-logto.md) | Self-hosted Logto on IONOS for sign-in | Accepted |
| [0021](adr/0021-ionos-only-comparison-model.md) | IONOS Qwen as the only v1 comparison model | Accepted |
| [0022](adr/0022-polling-push-deferred.md) | Polling in v1, push deferred (AD-8) | Accepted |
