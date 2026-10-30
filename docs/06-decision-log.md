# 06 — Decision Log

Plan section: §13.6. Every entry is tagged:
- **[E]** established by the handoff (commit `a8280b9`)
- **[A]** assumed by this plan as a conservative default
- **[U]** unverified, needs evidence
- **[O]** needs owner input before implementation

## Established by the handoff [E]

- Recommended direction: changing client briefs for freelancers and small agencies. The consumer concept is parked, and the two are not combined (§1, §3).
- Plan only, no implementation code. Low–medium complexity constraint (§1, §13).
- Out of scope: inbox or email integration, crawling and monitoring, calendar, mobile share extensions, autonomous client communication, contract interpretation, complex approvals, project management (§5).
- Use existing models; no custom training. Document content is untrusted input (§6).
- The correctness rules distinguish changed / absent / not addressed / unknown / equivalent / ambiguous. AI-detected, user-reviewed and client approval are separate states (§7).
- Explicit version ordering; no automatic merge into an authoritative spec (§4).
- Competitor facts as of 30 Oct 2026: Diffchecker Pro + Desktop costs US$15 per user per month and includes AI summaries, multiple formats, saved comparisons and sharing (S1, S2). Visualping offers scheduled website monitoring with AI summaries (S3).
- Prices to test: €9–15 per month individual, €39–59 per month team. These are hypotheses, not validated (§10).

### Added by handoff v2 (`ChangeLens_Planning_Agent_Handoff_v2.md`) [E]

- Gate 1 cohort: 10 independent organisations in one preselected niche. The denominator is that niche only; no pooling.
- Three-signal rubric: A ≥ 6/10 recurring need; B ≥ 3/5 observed usefulness; C ≥ 2/10 written buying commitments (3/10 is the strong target).
- Verdicts: 3/3 proceed to a limited pilot; 2/3 one bounded retest; 0–1/3 stop or reposition. Incomplete evidence is inconclusive.
- Non-compensable safeguards override commercial results.
- These thresholds are proposed experiment defaults, not validated market facts.

### Owner decisions after the handoff

- 2026-10-30: ChangeLens is an **iOS and Android app, not a web app**. This overrides handoff §14 ("do not assume a native mobile requirement") and §5 (native share extensions out of scope): share-sheet import and screenshot / camera input are in the MVP.
- 2026-10-30: Stack direction is Flutter + Riverpod, FastAPI + Pydantic + SQLAlchemy, PostgreSQL, a Python worker, S3-compatible storage and GitHub Actions. It is subject to the D-15 proof of concept, with React Native + Expo as the fallback.
- 2026-10-30: The pilot is billed by direct invoice and distributed through TestFlight and Play closed testing; no in-app purchase.

## Assumed by this plan [A]

| Decision | Default | Where |
|---|---|---|
| First niche | Web/digital and design freelancers and studios of 1–10 people | 01 |
| Language and market | English; EU/UK; EUR excluding VAT | 01 |
| MVP formats | Pasted text, text-layer PDF and PNG/JPEG screenshots, imported through paste, the PDF picker, camera / photo library or the OS share sheet; DOCX deferred | 02 §2 |
| Input limits | ≤ 15k words, ≤ 20 pages, ≤ 10 MB; images ≤ 5 MB | 02 §2 |
| Share expiry | 30 days by default, revocable — owner-confirmed 2026-10-30 | 02 §6 |
| Architecture | Script prototype (A), then Flutter mobile app + FastAPI + Postgres + Python worker + a read-only web share page (B) | 03 §1 |
| Retention | Until the user deletes; backups purged within 30 days — owner-confirmed 2026-10-30 | 03 §6 |
| Cost inputs | Placeholder `p_in = €3/M`, `p_out = €15/M`; brief ≈ 4k tokens | 03 §8 |
| Allowances | 25 comparisons per month individual / 100 per month team; heavy document = 4; failed runs not counted | 03 §8, 04 §2 |
| Team seats | 3 seats per team plan — owner-confirmed 2026-10-30 | 06 O-8 |
| Pilot price | €9 / €39 per month, 2 months prepaid, 5–10 accounts; unit economics judged at target €12 / €49 | 04 §2, §6 |
| Evaluation data | ≥ 10 real permissioned pairs; the rest of the ≥ 80 are synthetic | 04 §1, §4 |
| Gate 1 definitions | Event = written client change to deliverables, quantities, deadlines, owners or approval wording; ≥ 3 in 90 days with ≥ 2 concrete; useful = missed material change caught or ≥ 30% less effort; 14-day decision deadline — confirmed by the owner 2026-10-30 | 04 §6.1 |
| Signal B method | Operator-assisted test (D-13) before any prototype: fixed general-purpose-model prompt plus manual evidence checking, in the 02 §4 report format. It tests format and workflow value, not pipeline accuracy | 04 §6.2, 05 D-13 |
| Retest budget | ≤ 10 new organisations, ≤ 6 weeks, ≤ 8 person-days — confirmed by the owner 2026-10-30 | 04 §6.3 |
| Device data | No document content cached on the device in the MVP; tokens in Keychain / Keystore only | 03 §1.1, §6 |
| Technical thresholds | As proposed in 04 §6, Gates 2–4 | 04 §6 |
| Effort | Person-day ranges for one experienced developer | 05 |

## Unverified [U]

- Real revision frequency, cost of missed changes, and willingness to pay in any niche.
- Whether a general-purpose AI chat already solves the job well enough. This is the most likely threat to the differentiator.
- Model provider terms: training use, retention, EU processing, and actual prices.
- Token usage per comparison and extraction quality on real briefs.
- Location accuracy of vision models for screenshot evidence.
- Typical brief length (assumed 1–10 pages).
- Payment fees and VAT handling for the pilot.
- App Store and Google Play in-app purchase rules and fees (15–30%) for B2B subscriptions, and whether direct billing is allowed at public launch.
- Whether `pdfrx` (device) and `pypdfium2` (backend) produce matching text coordinates (tested in D-15).
- That Diffchecker's AI summary does not already handle partial-update semantics (to recheck in D-5).

## Requires owner input before implementation [O]

| # | Decision | Recommendation | Needed by |
|---|---|---|---|
| O-1 | Customer niche | **Decided 2026-10-30:** web/digital and design freelancers and studios of 1–10 people | — |
| O-2 | Launch language and market | **Decided 2026-10-30:** English; EU + UK | — |
| O-3 | First production input formats | **Decided 2026-10-30:** text, PDF and screenshots, via paste, picker, camera and share sheet | — |
| O-4 | Stack, auth and hosting | **Decided 2026-10-30:** Flutter + FastAPI stack (final after D-15); managed IdP with EU residency, using email one-time code + Google + Sign in with Apple; Germany region; Hetzner excluded; minimum spec in 03 §1.2. **Open:** IdP vendor and OVHcloud vs IONOS, both priced in D-8 | D-8 |
| O-5 | Model provider and processing location | Provider with a no-training, zero or short retention plan in the EU/UK; pick from the D-7 comparison | I-2 |
| O-6 | Storage and retention policy | **Decided 2026-10-30:** kept until the user deletes; immediate primary deletion; backups expire within 30 days | — |
| O-7 | Sharing mechanism and default expiry | **Decided 2026-10-30:** revocable snapshot link, 30-day default expiry | — |
| O-8 | Team seats and usage limits | **Decided 2026-10-30:** 3 seats per team plan; 25 comparisons per month individual, 100 per month team; heavy document = 4 | — |
| O-9 | Gate 1 definitions and technical thresholds | **Gate 1 decided 2026-10-30:** v2 thresholds; ≥ 3 qualifying events in 90 days with ≥ 2 concrete; useful = missed material change caught or ≥ 30% less effort; 14-day decision deadline; retest ≤ 10 organisations, 6 weeks, 8 person-days. **Gate 2 decided 2026-10-30** as proposed in 04 §6. **Open:** confirm Gate 3–4 before the pilot | Gate 3 |
| O-10 | Acquisition channel for the pilot | **Decided 2026-10-30:** the owner's own network. Mitigation: a screener blind to revision pain, every eligible respondent kept in the denominator, the relationship to the owner recorded per organisation. If the network can't supply 10 eligible organisations by the D-1 deadline, Gate 1 is *inconclusive*; widening the channel is a logged change | — |
| O-11 | Pilot pricing and data terms | **Decided 2026-10-30:** €9 / €39 per month, 2 months prepaid. Data terms are still drafted after D-7 | D-4 (terms) |

## Prior art and reuse (searched 2026-10-30)

**Searched:**
- ruflo memory (`memory_search_unified` over default, claude-memories, auto-memory, patterns, tasks, feedback)
- the Claude project memory directory
- every project in `C:\Users\Gerrit\job-search`: Flutter and Python manifests, ADR directories, and planning docs

| Source | What exists | Reuse for ChangeLens | Verdict |
|---|---|---|---|
| `mobile-engineering-intelligence/app/llm/citations.py` (HEAD `8531a17`) | Deterministic grounding check: every model sentence must cite a valid ID; failures are returned as `Rejected` and never kept silently; `NothingGrounded` when all fail | The same contract as the 03 §2 Verify stage (AC-9, AC-10). Port the pattern, swapping ID checks for exact-substring-at-locator checks | **Reuse (pattern)** |
| `mobile-engineering-intelligence/app/llm/` (`client.py`, `config.py`, `schemas.py`, `prompts.py`, `packet.py`) | Anthropic SDK client with Pydantic-validated structured output and a prompt-packet builder | Scaffold for I-2 extraction and the schema check (03 §1.1). Provider-neutral wrapping is still needed until D-7 decides | **Reuse (adapt)** |
| `mobile-engineering-intelligence/app/privacy.py` | Personal-data minimisation at ingest (for example stripping URL query strings) | Pattern for AC-23 log scrubbing and for limiting what reaches the model provider | **Reuse (pattern)** |
| `mobile-engineering-intelligence` `app/db.py`, `alembic/`, `compose.yaml` (postgres:16), `Dockerfile`, `app/observability.py` | FastAPI + SQLAlchemy 2 + Alembic + Postgres skeleton with OpenTelemetry | Starting point for I-8. **No** `tenant_id`, RLS or job queue, so those must be added (03 §5) | **Reuse (adapt)** |
| `mobile-engineering-intelligence/evals/` | Evaluation harness (`repro_narrative`) | Structural pattern for I-7 | Reference |
| `mobile-engineering-intelligence/infra/` | Terraform for AWS (ECS RunTask jobs) | Not applicable: hosting is OVHcloud or IONOS in Germany | Not reused |
| `POCs/01-leaklens-plan.md` (Rust) | OCR words with a char→box map; image decode limits; "scanned content is inert data"; coverage accounting | Design input for I-1b screenshot locators, AC-11 partial-coverage warnings and the AC-18 posture. Concepts only, different language | **Reuse (concepts)** |
| `charge-portal-nuxt/docs/adr/0001–0010` | ADRs in Status / Context / Decision format | Format template if decisions are split into ADRs; content (Nuxt, NestJS) unrelated | Reference |
| `screenshot-ai` (Electron/TypeScript) | Screenshot annotation desktop app | No overlap with a Flutter client or Python pipeline | Not reused |
| `POCs/cross-platform-translation-test-app-main` | Capacitor / Ionic app | Capacitor excluded by owner | Not reused |
| Flutter projects | None in the workspace | D-15 starts from scratch | — |
| ruflo memory and Claude memory | No entries for ChangeLens, document comparison or this stack | Nothing to reuse; plan outcomes should be stored after the mission | — |

## Change log

| Date | Change | Reason |
|---|---|---|
| 2026-10-30 | Initial plan | Handoff `a8280b9` |
| 2026-10-30 | Applied security review (2 high, 6 medium, 1 low) and plan review (1 high, 9 medium, rest low) findings; added AC-23; moved D-7 to M1 and I-11 to post-pilot; unit-economics gate judged at target prices | Reviewer findings |
| 2026-10-30 | Adopted handoff v2 Gate 1 rubric; added 04 §6.1 definitions, D-13 operator-assisted usefulness test and D-14 bounded retest; niche fixed before recruitment (D-2 now precedes D-1); owner kept the original Gate 1 values, now superseded by v2 | Handoff v2 |
| 2026-10-30 | Mobile-first owner decision: Flutter + FastAPI stack (03 §1.1); share sheet and screenshots moved into the MVP (I-1b, I-16); added D-15 mobile proof of concept and I-17 pilot distribution; same PDF engine (PDFium) on device and backend; no device content cache; read-only web share page kept for recipients | Owner direction |
| 2026-10-30 | O-4 interview: managed EU IdP; email one-time code + Google + Sign in with Apple; Germany; Hetzner excluded; OVHcloud vs IONOS shortlist; minimum hosting spec (03 §1.2) | Owner interview |
| 2026-10-30 | Interview round 2: O-1 web/design niche, O-2 English EU+UK, O-10 own network (with bias mitigation), O-11 €9 / €39 prepaid | Owner interview |
| 2026-10-30 | Interview round 3: Gate 1 definitions (04 §6.1) and retest budget confirmed and frozen | Owner interview |
| 2026-10-30 | Interview round 4: O-6 retention until deletion with 30-day backups; O-7 30-day revocable shares; O-8 3 seats; Gate 2 thresholds accepted | Owner interview |
| 2026-10-30 | Prior-art search (mission t1): reuse candidates recorded from mobile-engineering-intelligence and the LeakLens plan; ruflo and Claude memory empty | Mission t1 |
| 2026-10-30 | Spec gap check (mission t2): added AC-24 (mobile import paths), AC-25 (no document content on device or in push), AC-26 (auth behaviour); mapped in traceability.md | Mission t2 |
| 2026-10-30 | Architecture (mission t3): added 03 §9 modules, pipeline stage interfaces, API surface, end-to-end data flow and decisions AD-1 to AD-9 | Mission t3 |
| 2026-10-30 | ADRs and SOP (mission t4): 19 ADRs in docs/adr (AD-1 to AD-9 plus owner and security decisions; 0006 and 0019 Proposed); docs/SOP.md; check-trace.ps1 links the SOP and fails on any AD-n without an ADR | Mission t4 |
| 2026-10-30 | Pseudocode (mission t5): docs/03a-pipeline-logic.md with steps P0–P10 covering AC-1 to AC-26; check-trace.ps1 requires 03a and fails on any AC not covered there | Mission t5 |
| 2026-10-30 | Failing tests first (mission t6): scripts/check-verification.ps1 with empty docs/verification.md and docs/review-ledger.md; fails on 26 unverified ACs and an empty ledger. Product test code not written: handoff §13 forbids implementation without an owner decision | Mission t6 |
| 2026-10-30 | Implement until tests pass (mission t7): ledger of 46 findings (44 resolved, PLAN-3 and REV-17 accepted); ac-verifier found 12 failures, then a regression and a metrics gap; all fixed in 60f038b, 3a40a87, 2a253de; 26 of 26 ACs independently verified as pass | Mission t7 |
| 2026-10-30 | Benchmark (mission t8): scripts/cost-model.ps1 shows the current design no worse than baseline 14748b6 and within cost gates at placeholder prices; added screenshot parse to 03 §8; sensitivity findings REV-19, REV-20 accepted. Runtime benchmark against the §11 baselines stays with I-7 / Gate 2 (no implementation exists) | Mission t8 |
| 2026-10-30 | Security review (mission t9): independent audit since 14748b6 found 1 high (SA-1, no member removal) and 12 medium/low findings, plus 3 regressions on re-verification (SA-14..16). All resolved and re-verified with no open high finding. Screenshot parse is now two vision passes (≈ €0.026, still one unit); check-verification now checks every finding prefix | Mission t9 |
| 2026-10-30 | Change review (mission t10): independent review of 331687c..08c4e54 found 13 findings (CR-1..CR-13, none high), all resolved or accepted; 11 AC rows re-verified as pass. Backlog adds I-18 (account and team screens) and re-estimates I-8 and I-13; total now 78–133 person-days. cost-model.ps1 compares token use with the baseline, so price changes test only the gates | Mission t10 |
