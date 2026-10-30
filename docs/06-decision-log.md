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
| Share expiry | 30 days by default, revocable | 02 §6 |
| Architecture | Script prototype (A), then Flutter mobile app + FastAPI + Postgres + Python worker + a read-only web share page (B) | 03 §1 |
| Retention | Until the user deletes; backups purged within 30 days | 03 §6 |
| Cost inputs | Placeholder `p_in = €3/M`, `p_out = €15/M`; brief ≈ 4k tokens | 03 §8 |
| Allowances | 25 comparisons per month individual / 100 per month team; heavy document = 4; failed runs not counted | 03 §8, 04 §2 |
| Team seats | 3 seats per team plan | 06 O-8 |
| Pilot price | €9 / €39 per month, 2 months prepaid, 5–10 accounts; unit economics judged at target €12 / €49 | 04 §2, §6 |
| Evaluation data | ≥ 10 real permissioned pairs; the rest of the ≥ 80 are synthetic | 04 §1, §4 |
| Gate 1 definitions | Event = written client change to deliverables, quantities, deadlines, owners or approval wording; ≥ 3 in 90 days with ≥ 2 concrete; useful = missed material change caught or ≥ 30% less effort; 14-day decision deadline | 04 §6.1 |
| Signal B method | Operator-assisted test (D-13) before any prototype: fixed general-purpose-model prompt plus manual evidence checking, in the 02 §4 report format. It tests format and workflow value, not pipeline accuracy | 04 §6.2, 05 D-13 |
| Retest budget | ≤ 10 new organisations, ≤ 6 weeks, ≤ 8 person-days | 04 §6.3 |
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
| O-1 | Customer niche | Fix before recruitment (D-2); proposed: web/digital and design freelancers and studios | D-2 |
| O-2 | Launch language and market | English, EU/UK | D-1 |
| O-3 | First production input formats | **Decided 2026-10-30:** text, PDF and screenshots, via paste, picker, camera and share sheet | — |
| O-4 | Stack and hosting region | **Directed 2026-10-30:** Flutter + Riverpod, FastAPI + PostgreSQL, Python worker; final after D-15. Still open: auth approach and hosting region (EU proposed) | D-8 |
| O-5 | Model provider and processing location | Provider with a no-training, zero or short retention plan in the EU/UK; pick from the D-7 comparison | I-2 |
| O-6 | Storage and retention policy | Until deletion; 30-day backup purge | I-13 |
| O-7 | Sharing mechanism and default expiry | Revocable snapshot link, 30 days | I-12 |
| O-8 | Team seats and usage limits | 3 seats per team plan [A]; allowances as above | I-14 |
| O-9 | Gate 1 definitions and technical thresholds | Gate 1 thresholds adopted from handoff v2; confirm the 04 §6.1 definitions (event, ≥ 3 in 90 days, materiality, 30% effort reduction, 14-day deadline), the retest budget and the Gate 2 technical thresholds | D-2 / Gate 2 |
| O-10 | Acquisition channel for the pilot | Owner network + freelancer communities | D-4 |
| O-11 | Pilot pricing and data terms | €9 / €39 prepaid; terms after D-7 | D-4 |

## Change log

| Date | Change | Reason |
|---|---|---|
| 2026-10-30 | Initial plan | Handoff `a8280b9` |
| 2026-10-30 | Applied security review (2 high, 6 medium, 1 low) and plan review (1 high, 9 medium, rest low) findings; added AC-23; moved D-7 to M1 and I-11 to post-pilot; unit-economics gate judged at target prices | Reviewer findings |
| 2026-10-30 | Adopted handoff v2 Gate 1 rubric; added 04 §6.1 definitions, D-13 operator-assisted usefulness test and D-14 bounded retest; niche fixed before recruitment (D-2 now precedes D-1); owner kept the original Gate 1 values, now superseded by v2 | Handoff v2 |
| 2026-10-30 | Mobile-first owner decision: Flutter + FastAPI stack (03 §1.1); share sheet and screenshots moved into the MVP (I-1b, I-16); added D-15 mobile proof of concept and I-17 pilot distribution; same PDF engine (PDFium) on device and backend; no device content cache; read-only web share page kept for recipients | Owner direction |
