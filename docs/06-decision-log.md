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

## Assumed by this plan [A]

| Decision | Default | Where |
|---|---|---|
| First niche | Web/digital and design freelancers and studios of 1–10 people | 01 |
| Language and market | English; EU/UK; EUR excluding VAT | 01 |
| Prototype formats | Pasted text + text-layer PDF; screenshots gated to stage 2; DOCX deferred | 02 §2 |
| Input limits | ≤ 15k words, ≤ 20 pages, ≤ 10 MB; images ≤ 5 MB | 02 §2 |
| Share expiry | 30 days by default, revocable | 02 §6 |
| Architecture | Script prototype (A), then single web app + Postgres + worker (B) | 03 §1 |
| Retention | Until the user deletes; backups purged within 30 days | 03 §6 |
| Cost inputs | Placeholder `p_in = €3/M`, `p_out = €15/M`; brief ≈ 4k tokens | 03 §8 |
| Allowances | 25 comparisons per month individual / 100 per month team; heavy document = 2 | 03 §8, 04 §2 |
| Pilot price | €9 / €39 per month, 2 months prepaid, 5–10 accounts | 04 §2 |
| Thresholds | As proposed in 04 §6 | 04 §6 |
| Effort | Person-day ranges for one experienced developer | 05 |

## Unverified [U]

- Real revision frequency, cost of missed changes, and willingness to pay in any niche.
- Whether a general-purpose AI chat already solves the job well enough. This is the most likely threat to the differentiator.
- Model provider terms: training use, retention, EU processing, and actual prices.
- Token usage per comparison and extraction quality on real briefs.
- Location accuracy of vision models for screenshot evidence.
- Typical brief length (assumed 1–10 pages).
- Payment fees and VAT handling for the pilot.
- That Diffchecker's AI summary does not already handle partial-update semantics (to recheck in D-5).

## Requires owner input before implementation [O]

| # | Decision | Recommendation | Needed by |
|---|---|---|---|
| O-1 | Customer niche | Choose from D-2 evidence; start recruiting from web/design | D-1 |
| O-2 | Launch language and market | English, EU/UK | D-1 |
| O-3 | First production input formats | Text + text-layer PDF; screenshots only after pilot evidence | I-1 |
| O-4 | Stack and hosting region | Single web app + Postgres in an EU region; language picked for PDF tooling | D-8 |
| O-5 | Model provider and processing location | Provider with a no-training, zero or short retention plan in the EU/UK; pick from the D-7 comparison | I-2 |
| O-6 | Storage and retention policy | Until deletion; 30-day backup purge | I-13 |
| O-7 | Sharing mechanism and default expiry | Revocable snapshot link, 30 days | I-12 |
| O-8 | Team seats and usage limits | 3 seats per team plan [A]; allowances as above | I-14 |
| O-9 | Quality and commercial thresholds | Confirm the 04 §6 proposals before the evaluation | Gate 1 / Gate 2 |
| O-10 | Acquisition channel for the pilot | Owner network + freelancer communities | D-4 |
| O-11 | Pilot pricing and data terms | €9 / €39 prepaid; terms after D-7 | D-4 |

## Change log

| Date | Change | Reason |
|---|---|---|
| 2026-10-30 | Initial plan | Handoff `a8280b9` |
