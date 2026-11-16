# ChangeLens labelling guide

You compare two versions of a public tender document (an original and a later revision: an addendum, erratum, Q&A or full re-issue) and record every change that matters to someone delivering the work. Each page shows one pair. The owner works alone in two rounds, R1 and a blind R2 sample; do not use AI assistants, translation or comparison tools on the texts. The page shows the documents and nothing else, on purpose.

Rules come from the project's labelling definitions (docs/07 §4). Where this guide and those definitions differ, the definitions win; tell the owner.

## 1. Using the page

1. Open `P-NNN.html` from the current round folder (`R1` or `R2`) in Chrome, Edge or Firefox. It works offline and saves your work in the browser as you go, but **export** is the only copy that counts.
2. Read both texts in full. Use *Go* (line number) and *Find next* to move around long documents.
3. For each finding, select the text in the old and/or new pane, check the characters shown under *Current selection* (quotes and `\n` line breaks are shown exactly), and press *Use as old/new evidence*. You cannot type values; they always come from your selection.
4. Choose category, change type and material, add a note if useful, and *Save finding*.
5. Choose the primary **Pair case type** (the owner assigns it during R1; choose it afresh, blind, in R2). Tick *I have read both documents in full…* and press *Export labels*. Save `labels-P-NNN-R1.json` or `labels-P-NNN-R2.json` in `labelling/returned/`. The required case type is the R1 sampling stratum and becomes the record’s `case_types` entry. A pair with no change is exported with no findings and the box ticked.

**Selecting evidence.** For a changed value, select the smallest span that shows the value: `14 March 2027`, not the whole sentence. For an item that is not addressed, removed or uncertain in scope, select the whole item line in the old text, from the clause number to the final full stop, without the line break. The texts were extracted from PDFs, so tables may be split across columns; if a value is broken up, select the part that holds it and say so in the note.

## 2. Categories

| Category | Use for |
|---|---|
| `deliverable` | What is produced: features, pages, formats, resolution, creative direction |
| `quantity` | Numbers of things: pages, users, hours, copies |
| `date_deadline` | Delivery, review, approval and submission dates |
| `responsibility_owner` | Who does a named task or holds approval authority |
| `approval` | The required approval action and its binding force |
| `other_material` | Budget, fee, spending cap, currency or tax basis; other material terms |
| `structure` | Sections moved without change of meaning (never material) |

## 3. Change types

| Type | Use when |
|---|---|
| `added` | New in the revision. Needs new-side evidence. |
| `changed` | In both versions, with a different value or meaning. |
| `removed` | The revision explicitly deletes the item, or **replaces the whole document** and the item is gone. Needs old-side evidence. |
| `not_addressed` | The revision is a partial update and does not mention the item; it still stands. Needs old-side evidence. |
| `uncertain` | The documents cannot settle it: unknown scope, a contradiction, or ambiguity. Say why in the note. |
| `equivalent` | Reworded or moved, same meaning. Never material. |

A false `removed` is the worst error. When torn between `removed` and `not_addressed` or `uncertain`, choose the latter.

## 4. Material or not

A change is material if it affects deliverables, quantities, dates, responsibilities or approval wording.

- **Deadlines:** any real shift is material, even one day, in either direction. The same instant written differently is `equivalent`.
- **Budget:** any change to the stated budget, fee or cap is material, however small, as are currency or tax-basis changes. `€10,000` → `€10k` is `equivalent`.
- **Tone words:** a changed instruction for the output ("playful" → "corporate") is material (`deliverable`). The same word changed only in background prose is not. If you cannot tell, use `uncertain` and say why.
- **Contacts:** a new administrative contact is not material. Reassigning a delivery task or approval authority is (`responsibility_owner`).
- **Approval:** "signs off" → "reviews" is material (`approval`). A paraphrase that keeps the actor, action and binding force is `equivalent`.
- **Units and formats:** PNG → SVG or 1080p → 4K is material. An exact conversion ("1 m" → "100 cm") is `equivalent`.

## 5. Worked examples (invented texts)

### Example 1: a value change in an addendum

> **Old:** `2.1 Tenders must be received by 12:00 noon on 3 June 2027.`
> **New (Addendum 2):** `Clause 2.1 is amended: tenders must be received by 12:00 noon on 10 June 2027. All other terms of the invitation remain unchanged.`

One finding: `date_deadline`, `changed`, material yes. Old evidence `3 June 2027`, new evidence `10 June 2027`. The submission deadline counts as a date even though it is not a delivery date.

### Example 2: `removed` versus `not_addressed`

> **Old (RFP):** `4.1 Build a member portal.` / `4.2 Migrate 300 news articles.` / `4.3 Provide 12 months of hosting.`

**(a) Addendum:** `Addendum 1. Clause 4.2 is amended: migrate 450 news articles.`
The addendum amends the RFP; it does not replace it. Record 4.2 as `quantity`, `changed`, material (`300` → `450`). Record 4.1 and 4.3 as `not_addressed`, not material, with the whole old line as evidence (`deliverable` for 4.1, `deliverable` for 4.3). They still stand.

**(b) Full re-issue:** `Revised RFP (this document supersedes the RFP of 1 May in its entirety). 4.1 Build a member portal. 4.2 Migrate 300 news articles.`
The revision says it replaces the whole document, and hosting is gone. Record 4.3 as `deliverable`, `removed`, material, with old evidence only. An explicit deletion also justifies `removed`; silence in an addendum never does.

**(c) Explicit deletion inside an addendum** (`Clause 4.3 is deleted.`): record `deliverable`, `removed`, material, with the whole old clause as evidence and the deletion sentence as new evidence. It is explicitly removed even though the addendum is only a partial update.

### Example 3: unknown scope

> **Old (brief):** `Deliver 8 illustrations by 30 April. Final files as layered PSD.`
> **New (email):** `Hi both, updated brief below. Illustrations: 10, due 30 April.`

The email changes the quantity (`8` → `10`: `quantity`, `changed`, material). It does not say whether the "updated brief" replaces the old brief or amends it, so the PSD requirement may or may not still stand. Label the PSD line `deliverable`, `uncertain`, material yes, with the note "email does not say whether it amends or replaces the brief". Do not guess `removed`.

### Example 4: when a Q&A answer is a material change

> **Old (RFP):** `3.2 The client signs off each design stage.` / `5.1 Five design templates are required.`
> **New (Clarifications, which "form part of the tender documents"):**
> `Q3. Will the client sign off designs? A3. Designs are reviewed by the client; sign-off is not required.`
> `Q4. Are five templates still required? A4. Yes, as stated in 5.1.`
> `Q5. Can we submit in Word format? A5. PDF only.`

- A3 changes the approval action and its binding force: `approval`, `changed`, material, old `signs off`, new `reviewed by the client; sign-off is not required` (or the shortest span that carries the change).
- A4 repeats the requirement: no changed finding. It is expressly addressed, so do not call it `not_addressed`; unchanged clauses follow §6.
- A5 is about the bid, not the work: not material. Record it only if it changes a stated requirement of the original.

A Q&A answer that changes a requirement counts as an amendment to the RFP, including when it is silent about whether it amends. Apply the same materiality rules and add a finding note such as "Q&A answer amends the RFP requirement". If it also explicitly says it does not amend, record that contradiction as `uncertain` and explain both statements in the note.

### Example 5: a pair with no real change

> **Old:** `Section 6 – Fees. The fee is capped at £20,000 (excl. VAT).`
> **New (re-issued with a new cover page):** `SECTION 6: FEES` / `The fee is capped at £20,000 excluding VAT.`

Only layout, capitals and an abbreviation changed. Record nothing: no `equivalent` finding is needed for a pure formatting change. Tick the review box and export with zero findings. An empty export with the box ticked is a real answer, "no change"; an export without the tick is a draft.

### Example 6: a moved section

> Old has `7. Accessibility` after `6. Hosting`; new has it before, word for word.

One finding: `structure`, `equivalent`, material no, with both headings (or both first lines) as evidence. Moves are never material.

## 6. Unchanged clauses and inclusion scope

For partial or unknown-scope revisions, label untouched clauses only in the **scope, deliverables, timeline, budget/fees, roles and approval sections**. Do not enumerate unchanged general terms and conditions or evaluation criteria. In those listed sections, use `not_addressed` when a partial update leaves the clause standing, or `uncertain` when replace-versus-amend scope cannot be established. An expressly repeated unchanged clause is addressed and needs no finding; a substantive rewording or move uses `equivalent`. Pure formatting changes need no finding. This bounds the unchanged-clause inventory, not the search for actual changes.

P-015 is dropped in its entirety, leaving 25 real pairs (P-001..P-026 excluding P-015). Pair discovery, explicit kit selection, the freeze manifest, sample and builds skip it. The private collection manifest may retain the historical collection entry; it is filtered out by the tooling.

## 7. Option A workflow (postponed; tooling only)

Real-pair labelling is postponed while the owner builds the app. These are instructions for a future run, not a record that a run took place. No second human labeller is required. R1 versus R2 measures **intra-owner consistency**, not inter-annotator agreement. Do not open R1 exports, R1 pages, previous browser drafts, answer keys or reconciliation files during blind R2. The R2 kit includes no R1 findings or selected case type, uses separate storage, and rejects cross-round imports.

Run from the `change-lens-label` worktree in PowerShell, using the project environment:

```powershell
$data = '..\change-lens-data'  # your private data folder, outside Git
$python = '.\.venv\Scripts\python.exe'
$pairs = (Get-Content -Raw -Encoding UTF8 "$data/manifest-draft.json" | ConvertFrom-Json).pairs |
    Where-Object { $_.id -ne 'P-015' } | ForEach-Object { $_.id }
# R1: label every included pair once; export each file to labelling/returned/.
& $python scripts/eval/label_kit.py --data $data --round R1 --pairs $pairs
# Only after all R1 exports are complete:
& $python scripts/eval/reconcile.py freeze --data $data --pairs $pairs
& $python scripts/eval/reconcile.py sample --data $data --seed 7
# Wait at least 14 full days after the R1 freeze, then label the sample blind:
& $python scripts/eval/label_kit.py --data $data --round R2
# Save each R2 export to labelling/returned/ before comparing:
& $python scripts/eval/reconcile.py compare --data $data
# Complete every decision and reason in labelling/reconcile/<pair>-resolution.json.
& $python scripts/eval/reconcile.py build --data $data
& $python scripts/eval/reconcile.py calibrate --data $data
```

Freeze writes `labelling/r1-freeze.json`, recording each R1 file's SHA-256, UTC freeze time, case type, tier and source metadata. It refuses to overwrite an existing manifest. Later operations verify the R1 hashes: edits after freezing are rejected. This is a tooling lock, not an operating-system access-control change. Keep the files and manifest unchanged.

Sample writes `labelling/r2-sample.json` exactly once. It selects ceiling(N/3) pairs (9 of 25), stratified jointly by owner-assigned R1 case type and manifest tier. It includes at least one per stratum when the quota permits, then allocates the remaining places towards proportional coverage. If there are more strata than places, the seed chooses which strata fit. The same cohort and seed reproduce the same sample; deleting the sample to reroll is not part of this protocol. Calibration exercises must use a separate synthetic data root, not the real cohort.

Compare uses only sampled pairs and refuses an R2 export earlier than its pair's freeze plus 14 days, malformed or future-dated exports, changed R1 files, incomplete review, and invalid evidence. Export dates include timezone and time, not just calendar dates. Findings match on category plus overlapping evidence. Item agreement counts identical change type and material across matched items, with unmatched items in the denominator; Cohen's kappa uses matched items only. Undefined values remain undefined.

In each resolution item, choose `R1`, `R2`, `drop`, or `edit` (supply the complete finding for `edit`) and give a reason. Keep the R1 case type: the sampling stratum cannot change in hindsight. Compare refuses to overwrite existing decisions unless explicitly rerun with `--force`. Build uses R1 for every frozen pair, including those without R2. If a resolution exists, it must resolve every difference against the current valid exports; incomplete or stale resolutions fail. A valid resolution takes precedence over R1. An R2 export without a resolution does not change the R1 record. Built records have `labelled_by: ["owner"]`, round/hash provenance, and `split: "unsplit"`; the full output is validated before replacement.

The accepted source fields are preserved: tier from the collection manifest; for the public RFP revisions, `source.kind: "rfp_addendum"`, the newer document's URL and retrieval date, manifest licence, and `anonymised: true`. The freeze retains both versions' collection metadata; the output schema keeps the existing source shape. No source URL, licence, hint, R1 label or manifest note is shown on the labelling page.

Calibrate prints per-category agreement and kappa for 07 §6, with real and constructed pairs in separate tables. Real-pair metrics are descriptive and **never gate anything**. Model-evaluation gates are judged on constructed pairs. All source documents, returned labels, freeze/sample manifests, reconciliation files and built real records stay in private storage outside Git. Tests use invented texts only.
