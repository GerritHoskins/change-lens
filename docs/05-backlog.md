# 05 — Execution Backlog

Plan section: §13.5. Effort is in person-days for one experienced developer [A]. At the owner's 10–20 hours a week, one person-day is about 2–4 calendar days. **D-** tasks produce evidence or decisions. **I-** tasks are implementation.

**Approach: build first, then learn (owner decision 2026-10-31, 06).** ChangeLens is built as a hobby app that can grow into a paid product, not as a gated validation programme. Discovery gates no longer block building. Milestones M1–M5 replace the earlier Gates 1–4; where a gate's quality thresholds still apply, the milestone's exit criteria say so. v1 is:
- a Flutter app for iOS and Android, in English and German, for the EU market, with launch copy aimed at freelancers and small studios;
- comparing PDFs and pasted text, imported by paste or the PDF picker;
- free at launch, with a fair-use allowance as cost protection and no in-app purchase (O-20, 2026-11-13);
- running on IONOS: FastAPI, Postgres, a worker, self-hosted Logto, and IONOS AI Model Hub.

**Launch scope (O-20).** The first public release is free: M3 (screenshots and the share sheet) and the billing part of M4 (I-19) move to after launch. D-18 collects content-free usage data and pricing signals, and a later owner decision sets the subscription and billing strategy from them. Share links and teams are not in v1. There is no fixed launch date. Task IDs from the earlier plan are kept, so the AC links in `traceability.md` stay valid.

## M1 — Compare works end to end on a device (PDF and pasted text)

| ID | Task | Depends on | Acceptance | Effort | Risks / assumptions |
|---|---|---|---|---|---|
| D-15 | Flutter proof of concept on both platforms: import a PDF with the document picker; receive a passage and locator from a mock API (produced by `pypdfium2`); open the right page and highlight the passage with `pdfrx`; zoom, scroll and switch versions | — | All four pass on a physical iOS device and an Android device, with highlight boxes matching the backend locators on ≥ 95% of 20 test passages. **Passed 2026-10-31 on Android (Fairphone 5) and iOS (iPhone via TestFlight, 23/23 passages matched); see 06** | 3–5 | Coordinate mismatch between engines |
| I-22 | Dev comparison API: FastAPI `api` and `worker` processes, a Postgres job queue whose payloads carry IDs only, object storage, log scrubbing and the per-comparison cost ceiling. Authentication is a single dev token; this is never deployed publicly | — | A comparison submitted by the API runs in the worker and returns a report. No document content in logs or payloads (AC-23). The ceiling aborts runs cleanly (AC-21) | 2–3 | Superseded by I-8 in M2 |
| I-1 | Parser with provenance for text and text-based PDFs, plus input-limit checks and sandbox resource caps | — | Locators round-trip exactly on the constructed dataset; over-limit inputs rejected with a reason (AC-20); pages with no text warned (AC-11); hostile-file fixtures (oversized, malformed, JavaScript, embedded files) handled safely | 3–5 | PDF layout quirks (columns, tables) |
| I-1c | Rotated and cropped PDF pages: map PDFium character boxes through each page's /Rotate and CropBox (and a MediaBox off the origin) for both the visibility check and the locators, so those pages are parsed and checked instead of failing closed as hidden. Pages that still cannot be mapped keep failing closed | I-1 | Constructed fixtures with /Rotate 90/180/270, a CropBox and an offset MediaBox: visible text stays visible and evidence round-trips; text cropped away or hidden on those pages is still flagged; the eval round trip stays exact | 1–2 | Owner decision 2026-10-31: before testers, not blocking D-17 |
| D-17 | Model quality check on IONOS AI Model Hub (Qwen3.5-397B-A17B; Qwen3.8-27B as the cheaper variant). First split the constructed pairs into development and held-out sets by the 07 §5.4 group rule. Run on the **development split** only, behind the `llm` port, with `json_schema` strict. Measure schema adherence, numeric/date fidelity, change-detection F1, p95 latency and error rate | I-1 | ≥ 99% schema-valid at the first try and 100% after one retry; zero invented numbers or dates; change F1 ≥ 0.90 on the dev split. If IONOS misses these, record the result and run the same check on Bedrock Claude Sonnet 5.5 before choosing. Result in the decision log | 1–2 | No published SLA; short retirement notice; quantised builds |
| I-2 | Fact extraction with schema validation and per-version caching | I-1, D-17 | Schema-valid output on ≥ 98% of development pairs; failures marked unextracted | 3–5 | Extraction misses implicit deliverables |
| I-3 | Alignment (deterministic keys plus AI candidates) and comparison guards | I-2 | Reordered pairs yield no scope findings (AC-6); numeric, negation and modality guard tests pass (AC-8); ambiguity preserved (AC-7) | 4–7 | Over-matching hides changes |
| I-4 | Omission decision table by scope | I-3 | Partial or unknown cases yield zero removal claims (AC-2, AC-3, AC-4) | 1–2 | — |
| I-5 | Evidence verifier and report generation | I-3 | Every quote matches its locator exactly (AC-9); unverifiable findings withheld (AC-10); summary labelled selective (AC-13); equivalent pairs keep their diff (AC-5); changed values cite both sides (AC-1) | 2–4 | — |
| I-6 | Prompt-injection hardening: no tools, delimited data, schema output, hidden-text flagging (including text covered by images or shapes), and a list of unexplained differences | I-2, I-5 | Injection, suppression and hidden-text fixtures (P-613..P-616) produce no instruction following, no link fetches and no unlisted changed blocks; covered text is flagged (AC-18) | 2–3 | New injection styles |
| I-7 | Evaluation harness: run the pipeline on the constructed held-out split and compute the 04 §5 metrics and cost. Runs in CI as a regression check whenever prompts or models change | D-17, I-5 | Metric report with CIs and cost per comparison. M1 exit: zero false removals on partial or unknown-scope pairs, recall ≥ 90%, precision ≥ 90%, evidence location ≥ 98%, p90 cost ≤ €0.20 for typical documents | 2–3 | Constructed pairs are easier than real ones; real-pair metrics come later (07 §6) |
| I-9 | Flutter app shell and the projects and versions screens, portrait only on phones in v1 (owner decision 2026-10-31), with the permanent app identifier `dev.changelens.app` (06). Import by paste and the PDF picker (camera and photo library come in M3), with explicit order and scope confirmation; originals immutable; UI strings localised from the start (English first) | I-22, I-1 | Processing blocked until confirmation (AC-14); originals immutable (AC-15); paste and picker imports work on both platforms (AC-24); no document content stored on the device, and the app sandbox holds no document files after import (AC-25) | 4–6 | — |
| I-10 | Report screens: PDF evidence highlighting (`pdfrx`) with a parsed-text fallback, a needs-review group, a full-difference view and review actions, plus a separate client-approval record | I-9, I-5 | Review never sets approval (AC-12); corrections create revisions (AC-15) | 4–6 | Highlight alignment on small screens |

**M1 exit:** on both test phones, you paste or pick two versions and get a report whose evidence highlights land on the right passage, and the I-7 thresholds hold.

## M1b — Freelancer-first redesign (screens P0–P7)

From the redesign handoff of 2026-11-01. The owner decided O-14 to O-17 on 2026-11-01 (06), all as recommended, and scheduled this work after M1 and before M2, so the account screens are built in the new style and testers see it. Screen IDs P0–P7 are the v1 screens canvas IDs, not the 03a pipeline steps P0–P8; write "screen P3" to keep them apart. Effort is [A].

| ID | Task | Depends on | Acceptance | Effort | Risks / assumptions |
|---|---|---|---|---|---|
| I-23 | Finding topics (O-14): `topic` derived from `category` by a fixed mapping (02 §4), required and never null (`other` is the fallback); `budget` split out of other_material in extraction (extract-v7) and counted as material; `approval` renamed `approval_wording`; a sentence touching two topics yields two findings; per-topic counts in the findings response; a correction can change the topic in the new revision only (AC-15); EN/DE labels on the client, keyed by the enum | I-7 | I-7 gates hold on the development split after extract-v7; per-topic precision reported on ≥ 30 labelled findings across the six topics (most mapped from existing `category` labels, budget vs other labelled new); share of findings in `other` reported (above about 20% means the topic list needs revising); topic never changes `needs_review` | 2–4 | Budget vs other is the only new label |
| I-24 | One-screen compare backend (O-15): one create request for new versions plus the comparison, with an idempotency key; comparison state `waiting_for_versions` (migration: the status column is 10 characters) → `queued` when both versions are parsed, → `failed` with the version's reject reason; allowance charged on queued → running; version and comparison status refresh in the app without a manual pull (M1 Android finding 2) | I-22, I-9 | A retried create makes no duplicate versions or comparisons; a rejected version fails the comparison without spending allowance (AC-21); order is the user's, never upload time (AC-14); jobs still carry IDs only (AC-23) | 2–3 | Interaction with I-14 metering, which isn't built yet |
| I-25 | App screens P0–P7 from the v1 screens canvas: topic vocabulary (P0), projects list entry point "Compare two briefs" (P1), one-screen compare (P2), report grouped and filtered by topic (P3), finding detail with Confirm and go to next and the text-fallback guardrail (P4), timeline in the user's order with "Compare v2 → v3" (P6). Confirm screen 4 (`confirm_screen.dart`) is removed; P2 is the only start path. The user may leave P2 while versions are read; the projects list shows the comparison as reading | I-23, I-24, I-26, I-10 | Nothing preselected beyond the entry point's slots; Start enabled only with both slots, a scope and a project (AC-14); on screen P4 the fallback banner is pinned above Confirm and read before it by screen readers; needs-review findings do not auto-advance; review never sets approval (AC-12) | 6–10 | P4 must try passage placement before Confirm without opening the page view |
| I-26 | Review evidence telemetry (O-17): the app derives `evidence_mode` per side (`pdf_highlight`, `text_fallback`, `text_only`); the review request and `review_events` store it with `page_opened` | I-10 | Stored on every review; content-free (AC-23); not shown as a badge and never read as approval (AC-12); the post-launch share of `text_fallback` confirmations with `page_opened = false` can be queried | 0.5–1 | — |

**M1b exit:** on both test phones, a comparison started from screen P2 while a version is still being read completes; the report is grouped by topic with counts from the API; confirming a text-fallback finding shows the banner above the button; screen 4 is gone.

## M2 — Accounts, storage and privacy

| ID | Task | Depends on | Acceptance | Effort | Risks / assumptions |
|---|---|---|---|---|---|
| D-8 | Logto check (ADR-0020), self-hosted on IONOS. On a test instance, verify: MFA is in the open-source edition; automatic linking is off and the link prompt forces sign-in with the existing method; whether link_required leaves an orphan Logto user (AR-4); and whether a link made by Logto's own prompt is visible to the backend (AR-7). Pin a version later than 1.37.1. Confirm the retention defaults | D-15 | Results recorded in the decision log | 0.5–1 | Blocks I-8 |
| I-8 | Backend for public sign-up, replacing I-22's dev token. Self-hosted Logto on IONOS: deploy, Postgres, daily backups with a restore test, and transactional email. JWT verification for email one-time codes, Google, and native Sign in with Apple (backend code exchange, encrypted Apple refresh token). One tenant per account. Postgres RLS for the API and the worker, rate limits, the per-account spend cap and a global kill switch. `POST /session` returns the account's onboarding state (`completed`, `step`; O-23). No teams in v1 | D-8, I-22 | Cross-tenant tests on every route and job are denied (AC-19). No document content in logs, payloads, metric labels or trace spans; OpenTelemetry body and DB-parameter capture off (AC-23). Sign-in, MFA and session revocation behave as in AC-26 (for a single user); only `POST /session` bypasses GUARD. The spend cap and kill switch stop new work (AC-21) | 6–10 | Operating your own login system |
| I-18 | Account screens: sign-in, the `link_required` prompt, and account deletion in the app. The app gates first launch on the account's onboarding state and saves the step with `PUT /me/onboarding` (O-23) | I-8, I-9 | Account deletion works in the app on both platforms (Apple 5.1.1(v)); linking needs the existing method (AC-22, AC-26) | 1–2 | Store review of the deletion flow |
| I-13 | Data inventory (including object versions, PITR, VPS snapshots, the IdP, crash reports and analytics, and push with I-27), plus project and account deletion and retention jobs covering every store on it. Default retention: comparisons and documents are deleted 30 days after the last use [O] | I-8 | Project deletion purges primary storage at once and backups within the window (AC-22); account deletion removes the IdP user and revokes the Apple token; no object versions survive (AC-22); the inventory covers every store that holds content (AC-23) | 2–3 | Backup tooling; IdP deletion API |
| I-20 | Privacy policy and terms of use in English and German for a public consumer and small-business app. Name IONOS as processor (existing IONOS DPA, which covers Model Hub), list sub-processors from the data inventory, set out retention and deletion, and explain that users upload their own documents. Add an imprint (Impressum) | I-13 | Texts published on a web page and linked in the app and store listings; they match the data inventory | 1–2 | Legal review is advisable before charging money [U] |

**M2 exit:** a new user can sign up, compare, and delete their account on both platforms. Cross-tenant tests are green.

## M3 — Screenshots and share-sheet import (after launch, O-20)

Not part of the free launch. Screenshots were planned as the paid feature (O-16), so M3 is rescheduled together with the billing decision that D-18 informs.

| ID | Task | Depends on | Acceptance | Effort | Risks / assumptions |
|---|---|---|---|---|---|
| I-1b | Screenshot input in the pipeline: text extraction by a vision model (LightOnOCR-2 or Qwen on IONOS) with region locators; unreadable regions reported; a second independent pass, with blocks that differ routed to needs-review | I-1, D-17 | Cross-format constructed pairs (P-600..P-612) meet the I-7 thresholds; unreadable regions warned (AC-11); misleading-screenshot fixtures flagged or sent to needs-review (AC-18) | 4–8 | Vision-model location accuracy [U] |
| I-16 | Share-sheet import: an iOS Share Extension (Swift) and the Android `ACTION_SEND` intent, both handing off to the project picker. Adds camera and photo-library import to I-9, behind a flag until D-19 passes (O-16) | I-9 | Sharing a PDF, an image or text from Mail and Files lands in the chosen project on both platforms; the app-group container and app sandbox hold no document files after import (AC-24, AC-25) | 3–5 | iOS extension memory limits |
| D-19 | Screenshot placement gate (O-16, option 1): a photo eval set (screenshots of development-split briefs, never held-out) and a region-placement metric reported like D-15: the share of passages whose highlighted region on the image covers the quoted text | I-1b | ≥ 95% placement, recorded in 06. Until it passes, screenshot import stays behind a flag, and the paywall (screen 16) and the import sheet's Pro badges leave screenshots out | 1–2 | Vision-model location accuracy [U] |

## M4 — Fair-use allowance (billing after launch, O-20)

| ID | Task | Depends on | Acceptance | Effort | Risks / assumptions |
|---|---|---|---|---|---|
| I-14 | Metering as cost protection for the free launch (O-20): one fair-use comparison allowance per account per month, weighting for heavy documents, token and cost logging. No tiers and no paywall. The app says plainly when the allowance is used up and when it resets. Starting values (owner, 2026-11-13): 20 comparisons per account per month, a heavy document counts as 4 (O-8), and a global monthly model-spend cap of EUR 50 that trips the kill switch; all limits are config values. Tiers return with the billing decision | I-8 | No unmetered path (AC-21); limits change without a release; how often accounts reach the limit is counted for D-18 | 2–3 | Allowance too low hides demand; too high raises model cost |

I-19 (subscriptions) is deferred until after launch; see the table of superseded or deferred tasks.

## M5 — Launch and learning

There is no external tester phase (O-21): no TestFlight or Play testing track is opened to outside users. Builds before launch go to the owner's own devices only.

| ID | Task | Depends on | Acceptance | Effort | Risks / assumptions |
|---|---|---|---|---|---|
| I-21 | German translation of the app and both store listings (DE/EN), with screenshots aimed at freelancers and studios | I-10, I-18 | Every UI string is translated; the listings are reviewed | 2–3 | — |
| I-7b | Fabricated scope changes (I-7 deviation, owner Q4 = A, 2026-11-01): reproduce and fix on the development split the cause of the 2 reportable findings on reordered or unchanged held-out pairs in the second I-7 look; first suspect the align contradiction rule sending a sentence read twice to the model aligner. Then construct fresh held-out pairs (new bases, never tuned on) and run the I-7 gates on them | I-7 | Zero fabricated scope changes on the development split over 2 runs; all I-7 gates pass on the fresh held-out pairs, recorded with a receipt and a decision-log row | 1–2 | Run-to-run variation at temperature 0 (34/46 identical) |
| I-17 | Distribution: TestFlight and Play internal testing for the owner's devices only (O-21), store submission, App Store privacy labels and the Play data-safety form matching the data inventory, a release pipeline in GitHub Actions, and an inspection of a release build on each platform (O-18) | I-9, I-13 | The owner installs a release build on both platforms; store declarations checked against 03 §6; a release build on each platform is inspected and meets 03a P10 DEVICE_STORAGE (AC-25) and CLIENT_TELEMETRY (AC-23) | 1–2 | Review delays. The owner's old Play developer account was closed for inactivity (2024-06-29), so Android needs a new account (O-21). A new personal account must run a closed test with at least 12 testers opted in for 14 continuous days and then apply for production access; friends and family are not an option. An organisation account (D-U-N-S number, up to 30 days) is exempt |
| D-9 | Security review: tenancy, injection, logging, provider data flow, mobile client and share extension. Write the incident-response runbook, including the 72-hour Art. 33 notification to the supervisory authority. Repeat for every new input path | I-13, I-16, I-19 | No open high-severity finding; runbook exists | 2–3 | — |
| D-10 | Usability test with 5 users from the target audience (friends and contacts are fine), in person on the owner's phones, not through a tester build (O-21) | I-10, I-17 | 5 users complete import → report → review without help; the main issues are fixed or logged | 1–2 | — |
| D-18 | Learning loop and pricing evidence (O-20): in-app feedback, and content-free product analytics: activation (first comparison completed), comparisons per active account per week, retention at 4 weeks, how often and how soon accounts reach the fair-use allowance (I-14), and use of report features and evidence modes (I-26). A short in-app question after a few comparisons asks what the app is worth to the user; no fake paywall or offer that cannot be bought. Declared in the privacy policy and store forms, with consent where device access needs it (§ 25 TDDDG): server-side counts always, app-side events opt-in only, design in `docs/legal/README.md` | I-17, I-14 | Metrics visible from the first public user; no document content in any event (AC-23); a monthly readout in the decision log, and after about 3 months of public use a readout that feeds the owner's billing decision (O-20) | 2–3 | Small numbers early on; stated willingness to pay overstates real payment |

**Public launch** follows M5 when D-9 has no open high-severity finding, the D-10 users can complete the flow, and I-7b passes (the release gate blocks a failing I-7 receipt). It is free (O-20). There is no date.

## Superseded or deferred

The earlier validation plan (04 §1–§3, Gates 1 and 4) is superseded by the build-first decision. These tasks are kept for traceability and are not scheduled.

| ID | Task | Status |
|---|---|---|
| D-1 | Customer interviews (cohort of 10) | Superseded 2026-10-31; D-18 learns from real users instead |
| D-2 | Freeze the Gate 1 experiment | Done 2026-10-30, superseded 2026-10-31 |
| D-3 | Collect ≥ 25 real revision pairs | Done (25 pairs after P-015 was dropped) |
| D-4 | Pilot offer and per-pilot Art. 28 terms | Superseded by I-20 (public privacy policy and terms) |
| D-5 | Competitor recheck and baselines | Deferred; optional before launch |
| D-6 | Labelled evaluation set (07) | Constructed pairs done (text, visual, hidden text). Real-pair labelling (option A: R1 by the owner, blind R2 on a third) paused 2026-10-31 |
| D-7 | Model provider shortlist | Decided 2026-10-31: IONOS AI Model Hub, checked by D-17 |
| D-11 | Onboard pilot accounts | Superseded by M5 and D-18 |
| D-12 | Pilot readout | Superseded by the D-18 monthly readout |
| D-13 | Operator-assisted usefulness test | Superseded 2026-10-31 |
| D-14 | Bounded Gate 1 retest | Superseded 2026-10-31 |
| D-16 | Operator-assisted paid pilot | Superseded 2026-10-31 |
| I-12 | Share snapshots: token hashing, expiry, revocation, view log, read-only share page (AC-16, AC-17) | Deferred until after v1 |
| I-27 | Content-free push notification when a comparison is ready: FCM and APNs, device registry, `POST /devices` and `DELETE /devices/{id}` (AC-25) | Deferred until after v1 (O-18, ADR-0022); v1 refreshes status in the app (I-24) |
| I-15 | Pilot billing by invoice | Superseded by I-19 (in-app subscriptions) |
| I-19 | Subscriptions through App Store and Google Play in-app purchase, using RevenueCat; the backend reads entitlements from verified webhooks and receipts; restore purchases; prices in EUR | Deferred until after launch (O-20, 2026-11-13). The launch is free; the billing strategy is decided again from the D-18 readout, and this task is rescoped then |

## Totals (rough)

| Milestone | Effort |
|---|---|
| M1 Compare end to end | 31–51 d |
| M1b Freelancer-first redesign | 10.5–18 d |
| M2 Accounts and privacy | 10.5–18 d |
| M3 Screenshots and share sheet (after launch, O-20) | 8–15 d |
| M4 Fair-use allowance (I-14; I-19 billing after launch) | 2–3 d now, 3–5 d later |
| M5 Launch and learning | 7–12 d |
| **Total** | **about 72–122 person-days**: roughly 7–15 months at 10–20 hours a week |
| **Free launch scope (O-20)** | about 62–103 person-days in all: M1, M1b, M2, I-14 and M5, with D-18 one day larger; M3 and I-19 come after launch |

Main risk: the evidence-highlight fidelity of PDFs and screenshots on a small screen. D-15 tests it first. Main assumption: IONOS AI Model Hub gives schema-valid extraction within the cost gates in `03-technical-design.md` §8. D-17 and I-7 measured this on short constructed briefs only.
