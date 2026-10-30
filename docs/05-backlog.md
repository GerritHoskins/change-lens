# 05 — Execution Backlog

Plan section: §13.5. Effort is in person-days for one experienced developer or researcher [A]. **D-** tasks are discovery: they produce evidence or decisions, not product code. **I-** tasks are implementation. Milestone 1 has discovery tasks only. No task in milestone *N* starts until the gate closing milestone *N − 1* (`04-validation-plan.md` §6) has passed.

## Milestone 1 — Problem validation (discovery only)

| ID | Task | Depends on | Acceptance | Effort | Risks / assumptions |
|---|---|---|---|---|---|
| D-2 | Freeze the experiment: niche (O-1), eligibility, revision-event definition and lookback, materiality, useful-outcome test method, commitment definition, decision deadline (04 §6.1) | — | Definitions committed to git before the first recruitment message. **Frozen by the owner on 2026-10-30** (04 §6.1) | 0.5–1 | Pressure to loosen definitions later → changes logged with reason |
| D-1 | Write the interview guide and a 3-question screener (team size, country, briefs per month); build a list of about 150–250 studios of 1–10 people from directories; send about 40 personal research-only invites a week (email to UK companies, LinkedIn for sole traders and Germany), plus community posts; interview 10 eligible organisations in the frozen niche (04 §1); exploratory interviews logged separately | D-2 | Per-organisation event counts and examples, current method, cost of the last miss, buyer, channel and prior relationship; signal A scored with its denominator; actual reply and booking rates recorded in week 1 and volume adjusted | 6–10 | Booking rate unverified (assumed 5–12% with no incentive); if fewer than 7 are booked by week 3, fill at most 3 places through Malt, reported separately |
| D-3 | Collect ≥ 10 permissioned, anonymised or synthetic revision pairs | D-1 | Pairs stored with consent records; no client PII | 2–4 | Clients unwilling to share → synthesise from patterns |
| D-4 | Draft the pilot offer and data terms (an Art. 28 GDPR processor agreement with deletion at contract end, the freelancer's obligations to their client, disclosure of the AI processor, and the sub-processor list from the data inventory); present the documented offer to all 10 cohort organisations, ideally the budget holder | D-1, D-7 | Signal C scored: offer exposure, price, scope, decision-maker, accepted / rejected / pending / no response by deadline; no real client documents until terms are signed | 2–3 | Terms depend on provider retention (D-7) |
| D-5 | Recheck competitors (S1–S3) and test the generic-diff and AI-chat baselines on 5 pairs | D-3 | Dated notes; baseline outputs saved | 1–2 | Competitor features change |
| D-7 | Shortlist 2 model providers; verify retention (including abuse-monitoring retention), training use, region, DPA, sub-processors and pricing | — | Written comparison in the decision log; placeholder cost inputs replaced | 1–2 | Terms may not support EU processing |
| D-13 | Operator-assisted usefulness test (signal B): with 5 pre-selected cohort organisations, run one permissioned, redacted real pair each. The participant uses their normal process. The operator produces a report in the 02 §4 format using a fixed general-purpose-model prompt plus manual evidence checking. The model runs on IONOS AI Model Hub (Qwen3.5-397B-A17B, Germany only, prompts never logged; owner decision 2026-10-30), under the existing IONOS contract and DPA, with the model ID and `reasoning_effort` recorded with the prompt. Both are compared against frozen material-change labels | D-2, D-3, D-7 | Signal B scored with its denominator; refusals, unusable inputs and failures reported; method and prompt fixed before the first session | 3–5 | Tests the report *format and workflow*, not the eventual pipeline's accuracy; that is Gate 2's job [A] |
| D-14 | Bounded retest (only on a 2-of-3 verdict): one predeclared experiment that changes one hypothesis | Gate 1 verdict | Fixed end date, success condition and budget (04 §6.3) recorded before start; results reported separately | ≤ 8 (not in totals) | Temptation to pool samples |

**Gate 1** (three-signal rubric, `04-validation-plan.md` §6). Only a 3-of-3 verdict opens Milestone 2.

## Milestone 2 — Comparison prototype (architecture option A)

| ID | Task | Depends on | Acceptance | Effort | Risks / assumptions |
|---|---|---|---|---|---|
| D-16 | Operator-assisted paid pilot (O-12): on a 3-of-3 Gate 1 verdict, start the committed organisations on the agreed dates with no app. They send brief pairs by email or a shared folder; the operator runs the D-13 setup (fixed prompt, manual evidence check) and returns a report in the 02 §4 format. Invoiced at the O-11 price. Runs in parallel with the rest of Milestone 2 | Gate 1 (3 of 3), D-4, D-7 | Every commitment's start window honoured; payments collected; per-pair turnaround, reports delivered and issues logged; data terms signed before the first real pair (03 §6) | 3–5 d, plus about 2 h per org per week for 6–8 weeks | Operator time does not scale; it is a learning instrument, not the product |
| D-6 | Build the labelled evaluation set (≥ 80 pairs plus 10 cross-format, case mix from 04 §4, dual labelling) | D-3 | Dataset with labels, inter-annotator notes and a held-out split | 6–9 | Labelling disagreement on "material" |
| D-17 | Provider spike (O-5): run IONOS AI Model Hub (Qwen3.5-397B-A17B; Qwen3.8-27B as a cheaper variant; LightOnOCR-2 for dense screenshots) and Bedrock Claude Sonnet 5.5 on the same **development split** of D-6 (never the held-out split), behind the `llm` port. Measure schema adherence with `json_schema` strict, numeric/date fidelity, fact recall and precision, 70k-token recall, change-detection F1, screenshot character error rate, reasoning on vs off, p95 latency, error rate and determinism. Ask IONOS in writing for its SLA, minimum retirement notice and confirmation that no abuse-monitoring retention exists | D-6, D-7 | IONOS becomes primary only if it meets all of: ≥ 99% schema-valid first try and 100% after one retry; ≥ 98% exact numbers and dates with zero invented values; fact recall ≥ 95% and precision ≥ 97%, each ≤ 2 points below Sonnet; ≥ 95% long-context recall; change F1 ≥ 0.95; screenshot CER ≤ 2% with 100% on numbers and dates; p95 heavy call ≤ 90 s; < 1% errors over ≥ 200 calls; written IONOS answers received. Otherwise Bedrock is primary. Result and decision recorded in the decision log | 3–5 | No published SLA; one-week retirement notice seen in 2025; no version pinning; quantised builds may score below model cards |
| D-15 | Mobile proof of concept (Flutter), on both platforms: import a PDF through the document picker; receive a passage and locator from a mock API (produced by `pypdfium2`); open the right page and highlight the passage with `pdfrx`; zoom, scroll and switch versions; share a PDF into the app from Mail or Files | — | All five pass on a physical iOS device and an Android device, with highlight boxes matching the backend locators on ≥ 95% of 20 test passages. If not, run the same tests on React Native + Expo before D-8 | 3–5 | Coordinate mismatch between engines; iOS share-extension memory limits |
| I-1 | Parser with provenance for text and text-based PDFs, plus input-limit checks and sandbox resource caps | D-6 | Locators round-trip exactly on the dataset; over-limit inputs rejected with a reason (AC-20); no-text pages warned (AC-11); hostile-file fixtures (oversized, malformed, JavaScript, embedded files) handled safely | 3–5 | PDF layout quirks (columns, tables) |
| I-1b | Screenshot input in the pipeline: vision-model text extraction with region locators; unreadable regions reported | I-1, D-7 | Cross-format set passes the Gate 2 thresholds; unreadable regions warned (AC-11) | 4–8 | Vision-model location accuracy [U] |
| I-2 | Fact extraction with schema validation and per-version caching | I-1, D-17 | Schema-valid output on ≥ 98% of dev pairs; failures marked unextracted | 3–5 | Extraction misses implicit deliverables |
| I-3 | Alignment (deterministic keys + AI candidates) and comparison guards | I-2 | Reorder pairs yield no scope findings (AC-6); numeric, negation and modality guard tests pass (AC-8); ambiguity preserved (AC-7) | 4–7 | Over-matching hides changes |
| I-4 | Omission decision table by scope | I-3 | Partial or unknown cases yield zero removal claims (AC-2, AC-3, AC-4) | 1–2 | — |
| I-5 | Evidence verifier and report generation | I-3 | Every quote matches its locator exactly (AC-9); unverifiable findings withheld (AC-10); summary labelled selective (AC-13); equivalent pairs keep their diff (AC-5); changed values cite both sides (AC-1) | 2–4 | — |
| I-6 | Prompt-injection hardening: no tools, delimited data, schema output, hidden-text flagging (incl. text covered by images or shapes), AI-transcription labels and a second independent vision pass for screenshots (differing blocks routed to needs-review), list of unexplained differences | I-2, I-5 | Injection, suppression and hidden-text fixtures produce no instruction following, no link fetches and no unlisted changed blocks; covered-text and misleading-screenshot fixtures are flagged or routed to needs-review (AC-18) | 2–3 | New injection styles |
| I-7 | Evaluation harness: run the prototype and baselines; compute 04 §5 metrics and cost | D-6, I-5, D-5 | Metric report on the held-out set, with CIs and cost per comparison | 2–4 | Baselines hard to automate → run manually |

**Gate 2.** If it fails, iterate I-2 to I-5 at most twice, then narrow or stop.

## Milestone 3 — Thin product slice (architecture option B)

| ID | Task | Depends on | Acceptance | Effort | Risks / assumptions |
|---|---|---|---|---|---|
| D-8 | Confirm Flutter (from D-15); pick the IdP vendor (EU residency, DPA, sub-processors); **hosting decided by the owner on 2026-10-30: IONOS (Germany), already provisioned**; confirm retention and share expiry defaults | D-7, D-15, Gate 2 | Decisions recorded in the decision log | 0.5–1 | Blocks I-8 |
| I-8 | Backend skeleton (FastAPI): JWT verification against the managed IdP (email one-time code, Google, Sign in with Apple; MFA, rotation and revocation via the IdP), tenants, Postgres with RLS for API and worker, object storage, Postgres job queue with ID-only payloads, log scrubbing, per-comparison cost ceiling, rate limits, CSP on the share page | D-8 | Cross-tenant tests on every route and job are denied (AC-19). No document content in logs, payloads, metric labels or trace spans; OpenTelemetry body and DB-parameter capture off (AC-23). The ceiling aborts runs cleanly (AC-21). Sign-in, MFA, session revocation, operator-issued team invites (3 seats, O-13) and member removal behave as in AC-26; a removed member is denied on the next request and their shares are revoked; only `POST /session` bypasses GUARD. The per-tenant spend cap (incl. failed runs and screenshot parses) and the global kill switch stop new work (AC-21) | 6–10 | Auth provider choice |
| I-9 | Flutter app shell, plus projects and versions screens. Import by paste, PDF picker and camera / photo library, with explicit order and scope confirmation; immutable sources; content-free push notification when a comparison is ready | I-8, I-1 | Processing blocked until confirmation (AC-14); originals immutable (AC-15); paste, picker and camera imports work on both platforms (AC-24); no document content on the device or in push notifications, and the app sandbox holds no document files after import (AC-25); `DEVICE_STORAGE` and `CLIENT_TELEMETRY` rules from 03a P10 hold, checked by a release-build inspection (AC-23, AC-25) | 5–8 | — |
| I-18 | Account screens (Flutter), pilot scope (O-13): `link_required` prompt and in-app account deletion. Team seats are operator-managed (I-15); the invite choice, member list and ownership-transfer screens are deferred, and their backend routes stay operator-only | I-8, I-9 | Account deletion works in-app on both platforms (Apple 5.1.1(v)); linking needs the existing method (AC-22, AC-26) | 1–2 | Store review of the deletion flow |
| I-16 | Share-sheet import: iOS Share Extension (Swift) and Android `ACTION_SEND` intent, handing off to the project picker | I-9 | Sharing a PDF, an image or text from Mail and Files lands in a chosen project on both platforms; the app-group container and app sandbox hold no document files after import (AC-24, AC-25) | 2–4 | iOS extension memory limits |
| I-10 | Report screens: PDF evidence highlighting (`pdfrx`) with a parsed-text fallback, needs-review group, full-difference view, review actions, and a separate client-approval record | I-9, I-5 | Review never sets approval (AC-12); corrections create revisions (AC-15) | 5–8 | Highlight alignment on small screens |
| I-12 | Share snapshots: token hashing, expiry, revocation, view log, server-rendered read-only share page | I-10 | Snapshot contains only selected findings (AC-16); revoked or expired links return no content (AC-17) | 2–4 | — |
| I-17 | Pilot distribution: TestFlight and Play closed-testing tracks, App Store privacy labels and Play data-safety form matching the data inventory, release pipeline in GitHub Actions | I-9, I-13 | Pilot testers can install on both platforms; store declarations reviewed against 03 §6 | 1–2 | Review delays |
| I-13 | Data inventory (incl. object versions, PITR, VPS snapshots, IdP, push, mobile crash and analytics), plus project, account and tenant deletion and retention jobs covering every store on it | I-8 | Project deletion purges primary storage at once and backups within the window (AC-22); account deletion in the app removes the IdP user and revokes the Apple token; tenant deletion at contract end; no object versions survive (AC-22); inventory covers every content store (AC-23) | 2–4 | Backup tooling; IdP deletion API |
| D-9 | Security review: tenancy, share links, injection, logging, provider data flow, mobile client and share extension; write the incident-response runbook, including notifying the affected agency without undue delay so it can meet its 72-hour Art. 33 deadline. Repeat for every new input path and before the pilot (I-14) | I-12, I-13, I-16 | No open high-severity finding; runbook exists | 2–3 | — |
| D-10 | Usability test with 5 users | I-12 | Gate 3 met | 2–3 | — |

**Gate 3.**

## Milestone 4 — Paid pilot

| ID | Task | Depends on | Acceptance | Effort | Risks / assumptions |
|---|---|---|---|---|---|
| I-14 | Metering: comparison allowance, heavy-document weighting, one unit per screenshot parse, token and cost logging (the ceiling and rate limits already exist from I-8) | I-8 | No unmetered path (AC-21) | 2–3 | — |
| I-15 | Pilot billing by direct invoice or payment link, outside the app stores; accounts provisioned by the operator; no in-app purchase | D-4 | Pilot accounts can pay; VAT handling confirmed [U]; in-app purchase rules checked before any public listing [U] | 1–2 | Tax setup; store policy |
| D-11 | Onboard 5–10 pilot accounts; support process; weekly metric review | I-14, I-15, Gate 3 | Gate 4 metrics collected for 8 weeks | 8 weeks elapsed, 0.5 d/week | Low engagement |
| D-12 | Pilot readout and next-step decision | D-11 | Go / narrow / stop decision recorded | 1 | — |

**Gate 4.** Then focused expansion only (handoff §12, stage 5).

## Milestone 5 — Focused expansion

Only work justified by pilot evidence. Screenshot input, formerly I-11 here, moved into the MVP as I-1b and I-9 after the owner's mobile-first decision.

## Totals (rough, milestones 1–4)

| Milestone | Discovery | Implementation |
|---|---|---|
| 1 Problem validation | 15.5–27 d | — |
| 2 Prototype | 15–24 d (incl. D-16, D-17) | 21–38 d |
| 3 Thin slice | 4.5–7 d | 24–42 d |
| 4 Pilot | 1 d + 8 wk part-time | 3–5 d |
| **Total** | **36–59 d** | **48–85 d** — about 84–144 person-days plus the 8-week pilot (excluding D-14) |

Main risk: evidence-location fidelity for PDFs and screenshots on a small screen. D-15 tests it before the stack is locked, and Gate 2 measures it. Main assumption: an existing hosted model gives schema-valid extraction at the cost in `03-technical-design.md` §8.
