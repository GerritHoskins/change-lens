# Fresh text/PDF evaluation cohort

This prepares the next I-7b review pack. It does **not** pass the quality gate,
authorize model calls, replace the historical split/receipt, or certify human
review. No network access, credentials or inference is used by these commands.

## Scope and construction

- 120 English constructed pairs, P-800–P-919, from ten new synthetic brief
  families. No existing evaluation document is reused.
- Each family has the eleven established edit operators plus a second distinct
  partial update. Labels and exact spans come from those operators, not from a
  model or its predictions. Contradictions use only mutually exclusive exact
  counts; maxima and separate prerequisites cannot establish a contradiction.
- Text/text, text/PDF, PDF/text and PDF/PDF cases exercise the currently supported
  formats. The existing pinned renderer and PDFium validate source bytes, page
  offsets, exact evidence slices and visible evidence.
- After owner review, a seeded split assigns **whole families**: 48 development
  and 72 held-out pairs. Every case profile is split 40/60, including 12 partial
  updates and 6 unknown-scope cases in held-out. There are 12 held-out no-change
  or reordered cases. The legacy splitter is not used or modified.
- These are short documents. Screenshots, degraded images, hidden-text techniques,
  German quality, real-client performance and long/heavy-document costs remain
  unmeasured. Eighteen scope cases share six base families; do not describe them
  as eighteen independent samples for a population confidence bound.

The ten-family/twelve-case design meets the non-image case minima in
`docs/04-validation-plan.md` §4. Owner review follows `docs/07-eval-dataset.md`
§3 and §5.4. Image acceptance is deferred under O-16. Existing numerical
quality thresholds are unchanged.

## Prepare and review, outside Git

Use the existing project `.venv` with `scripts/eval/requirements-render.txt`
already installed. No dependency changes are required. From the repository root:

```powershell
.venv/Scripts/python.exe scripts/eval/fresh_cohort.py prepare --out ../change-lens-data/constructed-fresh-20261107
.venv/Scripts/python.exe scripts/eval/fresh_cohort.py verify --cohort ../change-lens-data/constructed-fresh-20261107
```

Any new directory outside Git is supported, including an isolated artifact
directory. The directory name identifies the dataset set. Existing destinations
are refused, including Git paths reached through directory links.

Open that directory's `review.html`. The owner must read **both complete inputs
and every construction label for all 120 pairs**. Pair pages show full text/PDF
previews, original file links, highlighted gold evidence and label definitions.
Mark each pair Approved or Changes requested and record corrections in its note.
Do not rubber-stamp a label because a script produced it.

The page has no network access and does not persist data automatically. Use
**Save review progress** to export partial decisions, and import that JSON to
resume. **Export completed owner review** requires every pair to be approved,
the reviewer's identity and the explicit personal-review attestation. Store the
resulting `owner-review.json` outside Git. The generated template contains only
pending decisions; it is not an approval.

If a fixture needs correction, fix its construction before evaluating it, prepare
a new directory and review the new pack. Changed sources, labels, pair pages and
PDF previews change the cohort identity and invalidate earlier review. Never
select or edit fixtures based on the comparison model's answers.

## Freeze only after actual owner review

```powershell
.venv/Scripts/python.exe scripts/eval/fresh_cohort.py freeze --cohort ../change-lens-data/constructed-fresh-20261107 --owner-review ../change-lens-data/owner-review.json
.venv/Scripts/python.exe scripts/eval/fresh_cohort.py verify --cohort ../change-lens-data/constructed-fresh-20261107
```

Freeze checks the source/label/review hashes, every approved pair, the attestation
and review timestamp, then writes `frozen/split.json`, the copied review and
`frozen/freeze.json`. It refuses an existing freeze. Verification rejects missing
or altered freeze files, cross-family reassignment and stale reviews. These are
integrity checks, not proof that a person actually performed the review.

The freeze receipt records **zero model calls** and **paid evaluation not
authorized**. It is not an I-7 quality receipt. Preserve the frozen files; do not
reroll the seed or inspect held-out results for tuning. The old
`scripts/eval/split.json` and `i7_receipt.json` remain untouched.

## Before any paid evaluation

1. Finish owner review and freeze; run the verification command again.
2. Commit the actual pipeline candidate and its regression tests in a clean,
   isolated checkout, including all required runtime modules. Publishing only
   this preparation tooling does not commit the pipeline candidate.
3. Request explicit approval stating the model, exact frozen cohort digest,
   run count, ceiling and whether a baseline is included. Two passes over all
   72 held-out pairs mean **144 comparisons**. At a EUR 0.20 reservation ceiling
   per comparison, the planned reservation maximum is **EUR 28.80**. Provider
   actual billing may exceed estimates. This is a plan, not authorization or
   a measured price. A baseline adds paid comparisons and needs its own scope.
4. Use the current I-7 runner with `--data` pointing to the cohort's parent and
   `--split-file` pointing to its frozen split. Keep per-pair model outputs
   outside Git. This tooling can be published independently; the published
   branch alone is not the updated I-7 pipeline or a release candidate.
5. Report every required gate from the full frozen set. Undefined denominators,
   skipped formats, failed comparisons or a targeted development diagnostic
   cannot establish release quality. A failed result remains a failure.

Run the preparation regressions without inference:

```powershell
.venv/Scripts/python.exe -m unittest discover -s scripts/eval -p test_fresh_cohort.py
```

Only these preparation scripts, invented base templates, tests and instructions
belong in Git. Generated documents, labels, review exports, collection manifests
and per-pair evaluation results stay outside Git.
