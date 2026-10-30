# SOP — Running and Changing the ChangeLens Plan

This repository is a plan, not an application. "Running" it means running its checks; "changing" it means editing the plan without losing traceability.

## 1. Run the checks

Everything at once (the same entry point `.github/workflows/plan-checks.yml` runs on push and pull request):

```powershell
powershell -NoProfile -File scripts/ci.ps1
```

It runs the build checks (tracked files under 500 lines, strict UTF-8 without mojibake, relative Markdown links resolve, no secrets or `.env` files), then the three checks below and the evaluation generator's unit tests (`python -m unittest discover -s scripts/eval`, see 07 §3), and exits 1 if anything fails. New files must be `git add`ed first, because it checks tracked files.

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

Cost-model benchmark. The defaults are the D-7 prices for Claude Sonnet 5.5 on AWS Bedrock (€1.97 / €9.85 per million input / output tokens); if the provider or prices change, pass `-PIn` and `-POut` and update the defaults in the same commit. `-TokenFactor` (default 1.3) sets the informational tokenizer sensitivity:

```powershell
powershell -NoProfile -File scripts/cost-model.ps1 [-PIn <EUR> -POut <EUR>]
```

It recomputes the 03 §8 scenarios and fails if a scenario uses more tokens than the reviewed baseline (stored as the 14748b6 token counts and priced at the same rates, so a price change alone never fails this part) or costs more than its gate (typical and first comparison €0.20, heavy €0.60, worst case €1.50, screenshot parse €0.13). It also prints the Gate 4 unit-economics sensitivity, which is informational. If the token estimates in 03 §8 change, update the scenario in the script in the same commit.

Mission completion check (fails until independent verification and review closure are recorded):

```powershell
powershell -NoProfile -File scripts/check-verification.ps1
```

It passes only if every AC has a row in `docs/verification.md` from a verifier who is not the author (the names `author`, `planner`, `claude-main` and `self` are rejected), with a result of `pass` or `accepted-gap` (a `fail` row fails the check) and evidence, and every finding in `docs/review-ledger.md` is `resolved` (with a reference) or `accepted` (with a reason). Ledger rows are recognised by an ID with an uppercase prefix, a hyphen and a number (`SEC-1`, `REV-20`, `SA-3`, `CR-13`); any new review may use a new prefix.

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
| [0016](adr/0016-push-plus-polling.md) | Push plus polling (AD-8) | Accepted |
| [0017](adr/0017-llm-port.md) | Model provider behind an injected port (AD-9) | Accepted |
| [0018](adr/0018-pilot-billing-distribution.md) | Pilot billing and distribution | Accepted |
| [0019](adr/0019-model-provider.md) | Model provider selection | Proposed |
| [0020](adr/0020-self-hosted-logto.md) | Self-hosted Logto on IONOS for sign-in | Accepted |
