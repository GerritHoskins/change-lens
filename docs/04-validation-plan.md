# 04 — Validation Plan

Plan section: §13.4. Tags: [E] established, [A] assumption, [U] unverified, [O] owner decision.

## 1. Customer research (problem validation)

- **Cohort (handoff v2 §11) [E].** **10 independent customer organisations** within one niche chosen *before* recruitment (O-1).
  - A freelancer counts as one organisation.
  - Several people at one agency are one organisation: extra qualitative evidence, not extra votes.
  - Recruit through the owner's network, freelancer communities and agency directories [O].
- **Eligibility, frozen before recruitment [A][O]:**
  - Works as a freelancer or at an agency of ≤ 10 people in the chosen niche.
  - Personally responsible for delivering client work against a written brief.
  - Has had at least one active client project in the last 90 days.
  - Screening must not ask about revision pain, so the cohort isn't pre-selected for the problem.
  - Eligible respondents with few revisions or little pain stay in the denominator.
- **Exploratory interviews** in other niches, or extra people at the same agency, are recorded separately. They are never pooled into the gate.
- **What to learn (per organisation):**
  - qualifying revision events in the last 90 days (§6.1), with concrete examples where possible
  - the channels revisions arrive through (document, email, chat, screenshot)
  - how they compare versions today, and how long it takes
  - the last time a missed change caused rework, and roughly what it cost in hours or money
  - who would pay, and from which budget
- **Artefacts.** Collect at least 10 real revision pairs, with permission and anonymised. These feed the evaluation set (§4). The remaining ≥ 70 pairs there are synthetic, modelled on the real pairs and on interview patterns. Results are reported separately for real and synthetic pairs.
- **Method.** Ask about past behaviour, not hypothetical interest. Don't pitch before the problem questions are done.

## 2. Paid-pilot proposal

| Item | Proposal |
|---|---|
| Offer | 8-week pilot of the exact workflow: projects, comparisons, evidence reports, review, sharing |
| Price | €9 per month individual / €39 per month team for the pilot (low end of the §10 ranges), paid up front for 2 months [A][O] |
| Size | 5–10 accounts |
| Allowance | 25 comparisons per month individual, 100 per month team; heavy documents count as 4; failed runs are not counted |
| Support | Email support with a 1-business-day response; one onboarding call |
| Data terms | Written terms covering processing location, model provider retention, deletion and the no-training clause. These must be verified before onboarding (D-7) |
| What we measure | Payment, weekly active use, comparisons per project, share-link use, correction effort, churn intent at week 8 |

## 3. Competitive baseline

Each evaluation-set pair is run through all four methods. Prices and capabilities are rechecked at execution time (S1–S3, checked 30 Oct 2026).

| Baseline | How it is run | What it shows |
|---|---|---|
| Generic diff | Diffchecker text or PDF comparison, including its AI summary if available on the tested plan | Whether typed findings and omission handling add value over line diffs plus a summary |
| General-purpose AI | A frontier chat assistant with a fixed prompt: "Compare these two briefs and list what changed in deliverables, deadlines, responsibilities and approvals" | Whether a cheap, available alternative already does the job |
| Manual workflow | 3–5 interviewees compare 2 pairs the way they normally do, and are timed | Time cost and miss rate today |
| ChangeLens prototype | Pipeline from `03-technical-design.md` | The candidate |

## 4. Evaluation dataset

At least 80 labelled pairs before the prototype gate, and at least 120 before the pilot gate [A]. Partial and unknown-scope cases are deliberately over-weighted, because false removals are the critical failure. Each change is labelled by type, with the expected finding and evidence location.

| Case type | Min pairs | Linked AC |
|---|---|---|
| Straightforward value changes (dates, quantities, owners) | 8 | AC-1 |
| No change | 4 | AC-6 |
| Equivalent rewording | 6 | AC-5 |
| Reordered sections | 4 | AC-6 |
| Numeric, negation and qualifier changes | 8 | AC-8 |
| Complete replacement with omissions | 6 | AC-2 |
| Partial updates (email or message style) | 20 | AC-3 |
| Unknown scope | 10 | AC-4 |
| Contradictory statements within one version | 3 | AC-7 |
| Ambiguous dates and entities | 4 | AC-7 |
| Poor-quality or partly unreadable inputs | 3 | AC-11 |
| Prompt-injection fixtures: embedded instructions and links, "treat as equivalent" steering, attempts to suppress findings, hidden or white-on-white text | 6 | AC-18 |
| Cross-format (screenshot vs text or PDF), required for Gate 2 because screenshots are in the MVP | 10 | AC-11 |

Labels are produced by two people working independently, with disagreements resolved and recorded. The set is split into a dev set (40%) and a held-out set (60%). Thresholds are judged on the held-out set only.

## 5. Metrics

- **Factual precision and recall by change type.** A finding is correct when its category, change type and values match the label.
- **Missed material changes.** A change counts as material if it affects deliverables, quantities, dates, responsibilities or approval wording.
- **False removals.** Any *removed*, *absent* or *cancelled* claim where the label says *not addressed* or *uncertain*. This is the critical metric.
- **Unsupported findings.** Findings whose evidence does not support the claim.
- **Evidence-location accuracy.** The locator points at the labelled span.
- **Correction effort.** Median user time to review a report, and the share of findings corrected.
- **Processing outcomes.** Complete, partial and failed rates; p50 and p90 latency; cost per comparison.

## 6. Go/no-go thresholds (fixed before the evaluation runs)

These must be agreed and committed before the held-out evaluation and the pilot start. Changing them afterwards must be logged in `06-decision-log.md` with a reason.

### Gate 1 — Problem validation (three-signal rubric, handoff v2 §11)

The thresholds are the v2 proposed defaults [E]. They are experiment defaults, not market benchmarks. The definitions in §6.1 were proposed by this plan and **confirmed by the owner on 2026-10-30**. They are frozen; any change before recruitment must be logged in 06 with a reason.

#### 6.1 Frozen definitions (owner-confirmed 2026-10-30)

| Term | Definition |
|---|---|
| Qualifying revision event | A client-originated change, received in writing after work on the project started, to deliverables, quantities, deadlines, responsibilities or approval wording. It can be a revised brief or a written partial update (email, message, document). Internal edits, verbal-only changes and purely cosmetic edits don't count. |
| Revision-frequency criterion | **≥ 3 qualifying events in the last 90 days** across the organisation's client projects, with **≥ 2 described concretely** (approximate date, channel, what changed). Rationale: about one per month is the least use that makes a monthly subscription feel worth it. A lower rate belongs to a separately tested occasional-use hypothesis. |
| Material change (signal B) | A change to deliverables, quantities, deadlines, responsibilities or approval wording that would alter the work delivered or its acceptance. Two people label it before the test. |
| Useful outcome (signal B) | Either the ChangeLens report surfaces a material change the participant's normal process missed, or total review-and-correction time is ≥ 30% lower with no additional material errors. |
| Valid buying commitment (signal C) | Written acceptance of a specific pilot offer naming budget holder, price, scope and a start date or window, **plus** a concrete next step (permitted documents supplied, or onboarding booked). "Would probably pay", waitlist sign-ups, free-trial interest and conditional interest do not count. Payments, deposits and unpaid written commitments are reported separately. |
| Decision deadline | 14 days after the offer is presented. No response by then is recorded as *no commitment*. A response still pending inside its window is *pending* and is not counted as a pass. |

#### 6.2 Signals

| Signal | Pass if | Evidence |
|---|---|---|
| **A. Recurring need** | ≥ **6 of 10** cohort organisations meet the revision-frequency criterion | Interview event counts and examples (D-1) |
| **B. Observed usefulness** | ≥ **3 of 5** cohort organisations show a useful outcome against their normal process | Operator-assisted comparison test (D-13). The 5 participants are chosen before any outcome is seen. Refusals, unusable inputs and failures are reported |
| **C. Buying commitment** | ≥ **2 of 10** accept the pilot offer. **3 of 10** is the strong target | Documented offer made to all 10 (D-4), with exposure, price, scope, decision-maker role and outcome recorded |

Denominators are always reported. Missing evidence is never counted as a pass or dropped. The three signals can come from the same customers, so three passes are not three independent confirmations, and they are not proof of product–market fit.

#### 6.3 Verdict

A signal is **inconclusive** if its minimum evidence is incomplete: fewer than 10 organisations assessed for A or C, or fewer than 5 completed tests for B. The verdict is not issued while any signal is inconclusive.

| Result | Decision | Authorises |
|---|---|---|
| 3 of 3 pass | **Proceed to a limited paid pilot** | First an operator-assisted paid pilot with no app (D-16), starting on the committed dates; Milestone 2 runs in parallel, and the app pilot (Milestone 4) is bounded by Gate 4. Not a full platform build (O-12) |
| 2 of 3 pass | **Narrow and retest once** (D-14) | Change one explicit hypothesis tied to the failed signal (v2 §11 guidance) and run a single predeclared experiment |
| 0–1 of 3 pass | **Stop or reposition** this niche/offer hypothesis | Record what failed and what a different hypothesis would need to show |

**Retest budget (D-14):**
- One experiment, with its end date, success condition and budget set before it starts.
- Budget: ≤ 10 new independent organisations, ≤ 6 weeks and ≤ 8 person-days [A][O].
- Reused participants may join product retests but are not counted as new demand observations.
- Original and retest results are reported separately and never pooled.
- If the same signal fails again: stop or reposition.

**Non-compensable safeguards (all gates).** No commercial result overrides unresolved privacy exposure, fabricated source evidence or systematic material comparison errors. Any of these blocks use of live client material until corrected.

Two written commitments justify only a bounded, possibly operator-assisted pilot. Gate 4 still requires actual payment, repeat use, an acceptable correction burden and viable costs.

### Gate 2 — Comparison prototype (held-out set)

| Metric | Go if |
|---|---|
| False removals on partial or unknown-scope cases (about 18 held-out pairs; zero observed means a true rate of ≤ 17% at 95% confidence by the rule of three, so this is a floor, re-tested at 120 pairs) | **0** |
| Recall of material changes | ≥ 95% |
| Precision of reported findings | ≥ 90% |
| Evidence-location accuracy | ≥ 98% |
| Unsupported findings | ≤ 2% |
| Fabricated scope changes on reordered or no-change pairs | 0 |
| Measured advantage over the general-purpose AI baseline | Fewer false removals *and* fewer missed material changes on the held-out set. CIs are reported, but the sample is too small to require them to separate, so treat this as directional evidence |
| Cost per comparison, p90 | ≤ €0.20 for typical documents (≤ 5,000 words); ≤ €0.60 for heavy ones |

### Gate 3 — Thin slice

- 5 test users complete the import → report → review → share workflow without operator help.
- Zero cross-tenant or revoked-link exposures in authorisation tests and the security review.

### Gate 4 — Paid pilot (week 8)

| Signal | Go if |
|---|---|
| Payment | ≥ 5 accounts paid |
| Repeat use | ≥ 60% of paying accounts ran comparisons in ≥ 4 of 8 weeks, on ≥ 2 projects each |
| Correction burden | Median review time ≤ 3 minutes per report; ≤ 15% of findings corrected |
| Unit economics | Measured variable cost (model + storage) per account at observed usage ≤ 30% of the **target** price (€12 / €49). Hosting is tracked as a fixed cost, with a break-even account count reported. Pilot prices are discounted and not used for this gate (03 §8) |
| Retention intent | ≥ 50% would continue at the target price (€12 / €49) |

**No-go response.** Narrow the niche, reposition, or stop. Do not add formats or integrations (handoff §12).
