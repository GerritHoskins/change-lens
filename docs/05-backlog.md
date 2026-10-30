# 05 — Execution Backlog

Plan section: §13.5. Effort is in person-days for one experienced developer or researcher [A]. **D-** tasks are discovery: they produce evidence or decisions, not product code. **I-** tasks are implementation. No I-task in a milestone starts before that milestone's gate in `04-validation-plan.md` §6 has passed.

## Milestone 1 — Problem validation (discovery only)

| ID | Task | Depends on | Acceptance | Effort | Risks / assumptions |
|---|---|---|---|---|---|
| D-1 | Write the interview guide; recruit and run 12–15 niche interviews plus 5 fallback interviews | — | Notes for each interview, with revision frequency, channels, current method, cost of the last miss, and the buyer | 6–10 | Recruiting is slow; assumes access to the owner's network |
| D-2 | Pick the niche by scoring interview evidence | D-1 | One niche selected, with evidence recorded in the decision log | 0.5–1 | Evidence may be split across niches → choose narrower |
| D-3 | Collect ≥ 10 permissioned, anonymised or synthetic revision pairs | D-1 | Pairs stored with consent records; no client PII | 2–4 | Clients unwilling to share → synthesise from patterns |
| D-4 | Pilot offer and data terms draft; sound out ≥ 10 prospects | D-1, D-7 | Commitment count recorded against Gate 1 | 2–3 | Terms depend on provider retention (D-7) |
| D-5 | Recheck competitors (S1–S3) and test the generic-diff and AI-chat baselines on 5 pairs | D-3 | Dated notes; baseline outputs saved | 1–2 | Competitor features change |

**Gate 1** (see `04-validation-plan.md` §6).

## Milestone 2 — Comparison prototype (architecture option A)

| ID | Task | Depends on | Acceptance | Effort | Risks / assumptions |
|---|---|---|---|---|---|
| D-6 | Build the labelled evaluation set (≥ 60 pairs, case mix from 04 §4, dual labelling) | D-3 | Dataset with labels, inter-annotator notes and a held-out split | 5–8 | Labelling disagreement on "material" |
| D-7 | Shortlist 2 model providers; verify retention, training-use, region and pricing terms | — | Written comparison in the decision log; placeholder cost inputs replaced | 1–2 | Terms may not support EU processing |
| I-1 | Parser with provenance for text and text-based PDFs, plus input-limit checks | D-6 | Locators round-trip exactly on the dataset; over-limit inputs rejected with a reason (AC-20); no-text pages warned (AC-11) | 3–5 | PDF layout quirks (columns, tables) |
| I-2 | Fact extraction with schema validation and per-version caching | I-1, D-7 | Schema-valid output on ≥ 98% of dev pairs; failures marked unextracted | 3–5 | Extraction misses implicit deliverables |
| I-3 | Alignment (deterministic keys + AI candidates) and comparison guards | I-2 | Reorder pairs yield no scope findings (AC-6); numeric, negation and modality guard tests pass (AC-8); ambiguity preserved (AC-7) | 4–7 | Over-matching hides changes |
| I-4 | Omission decision table by scope | I-3 | Partial or unknown cases yield zero removal claims (AC-2, AC-3, AC-4) | 1–2 | — |
| I-5 | Evidence verifier and report generation | I-3 | Every quote matches its locator exactly (AC-9); unverifiable findings withheld (AC-10); summary labelled selective (AC-13); equivalent pairs keep their diff (AC-5); changed values cite both sides (AC-1) | 2–4 | — |
| I-6 | Prompt-injection hardening (no tools, delimited data, schema output) | I-2 | Injection fixtures produce no instruction following or link fetches (AC-18) | 1–2 | New injection styles |
| I-7 | Evaluation harness: run the prototype and baselines; compute 04 §5 metrics and cost | D-6, I-5, D-5 | Metric report on the held-out set, with CIs and cost per comparison | 2–4 | Baselines hard to automate → run manually |

**Gate 2.** If it fails, iterate I-2 to I-5 at most twice, then narrow or stop.

## Milestone 3 — Thin product slice (architecture option B)

| ID | Task | Depends on | Acceptance | Effort | Risks / assumptions |
|---|---|---|---|---|---|
| D-8 | Owner decisions: stack, hosting region, retention and share expiry defaults | D-7, Gate 2 | Decisions recorded in the decision log | 0.5–1 | Blocks I-8 |
| I-8 | App skeleton: auth, tenants, Postgres with row-level security, object storage, worker queue | D-8 | Cross-tenant tests on every route are denied (AC-19) | 4–7 | Auth library choice |
| I-9 | Projects and versions UI; import with explicit order and scope confirmation; immutable sources | I-8, I-1 | Processing blocked until confirmation (AC-14); originals immutable (AC-15) | 3–5 | — |
| I-10 | Report UI with evidence highlighting, needs-review group, full-difference view, review actions and a separate client-approval record | I-9, I-5 | Review never sets approval (AC-12); corrections create revisions (AC-15) | 4–6 | Evidence highlighting in PDFs |
| I-11 | Screenshot input (stage 2), only if pilot interviews show need | Gate 2, D-1 evidence | Cross-format set passes Gate 2 thresholds; unreadable regions warned (AC-11) | 4–8 | Vision-model location accuracy [U] |
| I-12 | Share snapshots: token hashing, expiry, revocation, view log | I-10 | Snapshot contains only selected findings (AC-16); revoked or expired links return no content (AC-17) | 2–3 | — |
| I-13 | Deletion and retention jobs | I-8 | Project deletion purges primary storage at once and backups within the window (AC-22) | 1–2 | Backup tooling |
| D-9 | Security review: tenancy, share links, injection, provider data flow | I-12, I-13 | No open high-severity finding | 1–2 | — |
| D-10 | Usability test with 5 users | I-12 | Gate 3 met | 2–3 | — |

**Gate 3.**

## Milestone 4 — Paid pilot

| ID | Task | Depends on | Acceptance | Effort | Risks / assumptions |
|---|---|---|---|---|---|
| I-14 | Metering: comparison allowance, heavy-document weighting, per-comparison cost ceiling, token and cost logging | I-8 | No unmetered path; the ceiling aborts runs cleanly (AC-21) | 2–3 | — |
| I-15 | Billing for the pilot (payment links or a simple subscription), no custom billing system | D-4 | Pilot accounts can pay; VAT handling confirmed [U] | 1–2 | Tax setup |
| D-11 | Onboard 5–10 pilot accounts; support process; weekly metric review | I-14, I-15, Gate 3 | Gate 4 metrics collected for 8 weeks | 8 weeks elapsed, 0.5 d/week | Low engagement |
| D-12 | Pilot readout and next-step decision | D-11 | Go / narrow / stop decision recorded | 1 | — |

**Gate 4.** Then focused expansion only (handoff §12, stage 5).

## Totals (rough)

| Milestone | Discovery | Implementation |
|---|---|---|
| 1 Problem validation | 11.5–20 d | — |
| 2 Prototype | 6–10 d | 16–29 d |
| 3 Thin slice | 3.5–6 d | 18–31 d |
| 4 Pilot | 1 d + 8 wk part-time | 3–5 d |

Main risk: evidence-location fidelity for PDFs and screenshots, which is why screenshots are gated (I-11). Main assumption: an existing hosted model gives schema-valid extraction at the cost in `03-technical-design.md` §8.
