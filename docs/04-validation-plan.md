# 04 — Validation Plan

Plan section: §13.4. Tags: [E] established, [A] assumption, [U] unverified, [O] owner decision.

## 1. Customer research (problem validation)

- **Who.** 12–15 interviews from the first niche (`01-product-decision.md`), plus 5 from a fallback niche for contrast. Recruit through the owner's network, freelancer communities and agency directories [O].
- **What to learn (per interviewee):**
  - revisions per active project per month
  - the channels revisions arrive through (document, email, chat, screenshot)
  - how they compare versions today, and how long it takes
  - the last time a missed change caused rework, and roughly what it cost in hours or money
  - who would pay, and from which budget
- **Artefacts.** Collect at least 10 real revision pairs, with permission and anonymised, or reconstructed synthetic pairs. These feed the evaluation set (§4).
- **Method.** Ask about past behaviour, not hypothetical interest. Don't pitch before the problem questions are done.

## 2. Paid-pilot proposal

| Item | Proposal |
|---|---|
| Offer | 8-week pilot of the exact workflow: projects, comparisons, evidence reports, review, sharing |
| Price | €9 per month individual / €39 per month team for the pilot (low end of the §10 ranges), paid up front for 2 months [A][O] |
| Size | 5–10 accounts |
| Allowance | 25 comparisons per month individual, 100 per month team; heavy documents count as 2 |
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

At least 60 labelled pairs before the prototype gate, and at least 120 before the pilot gate [A]. Each change is labelled by type, with the expected finding and evidence location.

| Case type | Min pairs | Linked AC |
|---|---|---|
| Straightforward value changes (dates, quantities, owners) | 8 | AC-1 |
| No change | 4 | AC-6 |
| Equivalent rewording | 6 | AC-5 |
| Reordered sections | 4 | AC-6 |
| Numeric, negation and qualifier changes | 8 | AC-8 |
| Complete replacement with omissions | 6 | AC-2 |
| Partial updates (email or message style) | 8 | AC-3 |
| Unknown scope | 4 | AC-4 |
| Contradictory statements within one version | 3 | AC-7 |
| Ambiguous dates and entities | 4 | AC-7 |
| Poor-quality or partly unreadable inputs | 3 | AC-11 |
| Prompt-injection fixtures (instructions and links embedded in briefs) | 2 | AC-18 |
| Cross-format (screenshot vs text) — stage 2 only | 10 | AC-11 |

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

### Gate 1 — Problem validation

<!-- TODO(human): confirm or replace the proposed commercial thresholds below. -->

| Signal | Go if | Tag |
|---|---|---|
| Recurring need | ≥ 60% of interviewees in the niche get ≥ 2 brief revisions per active project per month | [A][O] |
| Cost of misses | ≥ 50% describe a missed-change incident in the last 6 months that cost ≥ 2 hours | [A][O] |
| Buying decision | ≥ 3 of ≥ 10 qualified prospects commit to paying for the pilot | [A][O] |

### Gate 2 — Comparison prototype (held-out set)

| Metric | Go if |
|---|---|
| False removals on partial or unknown-scope cases | **0** |
| Recall of material changes | ≥ 95% |
| Precision of reported findings | ≥ 90% |
| Evidence-location accuracy | ≥ 98% |
| Unsupported findings | ≤ 2% |
| Fabricated scope changes on reordered or no-change pairs | 0 |
| Measured advantage over the general-purpose AI baseline | Fewer false removals and missed material changes, with a 95% CI not overlapping on at least one of the two |
| Cost per comparison, p90 | ≤ €0.50 |

### Gate 3 — Thin slice

- 5 test users complete the import → report → review → share workflow without operator help.
- Zero cross-tenant or revoked-link exposures in authorisation tests and the security review.

### Gate 4 — Paid pilot (week 8)

| Signal | Go if |
|---|---|
| Payment | ≥ 5 accounts paid |
| Repeat use | ≥ 60% of paying accounts ran comparisons in ≥ 4 of 8 weeks, on ≥ 2 projects each |
| Correction burden | Median review time ≤ 3 minutes per report; ≤ 15% of findings corrected |
| Unit economics | Measured model + hosting cost ≤ 30% of pilot revenue per account |
| Retention intent | ≥ 50% would continue at the target price (€12 / €49) |

**No-go response.** Narrow the niche, reposition, or stop. Do not add formats or integrations (handoff §12).
