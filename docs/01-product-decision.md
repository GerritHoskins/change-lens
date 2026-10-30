# 01 — Product Decision

Plan section: §13.1. Source: `ChangeLens_Planning_Agent_Handoff.md` (commit `a8280b9`).
Status tags used throughout the plan: **[E]** established by the handoff, **[A]** assumption made by this plan, **[U]** unverified — needs evidence, **[O]** needs owner decision. See `06-decision-log.md`.

## Recommendation

Test one question before building a product: **is client-brief change tracking useful enough to pay for?** Pursue the agency/freelancer direction only. The consumer concept stays parked (handoff §3) and is not combined with it.

## Initial customer

| Item | Decision | Tag |
|---|---|---|
| Segment | Freelancers and agencies of 1–10 people delivering client work against written briefs | [E] direction, [A] size band |
| First niche to recruit from | Web/digital and design freelancers and small studios: revisions to scope, deliverable lists and deadlines are frequent, and briefs mostly arrive as text, PDF or email | [A], [O] confirm |
| Fallback niches | Copywriting/content agencies; event-production freelancers | [A] |
| Launch language and market | English-language briefs; EU/UK buyers; prices in EUR excluding VAT | [A], [O] |
| Buyer | The freelancer themself; at an agency, the owner or account/project lead | [A], [U] |

Under handoff v2, the niche is **fixed before recruitment** (D-2 in `05-backlog.md`), and only that niche's 10-organisation cohort counts toward Gate 1. Fallback-niche interviews are exploratory, recorded separately and never pooled. If Gate 1 points to a different niche, that niche is tested as a new hypothesis with a new cohort.

## Job to be done

> "When a client sends a revised brief, or a partial update by email or message, show me what changed in **deliverables, quantities, deadlines, responsibilities and approval-related wording**, with evidence I can check and share. Tell me plainly what the update did not address."

## Value proposition

**"Catch changed requirements before you deliver the wrong thing."** [E]

## Differentiator hypothesis [U]

Diffchecker already offers AI summaries, multiple formats, saved comparisons and link sharing (S1, S2), so those are not differentiators. Visualping's model, scheduled monitoring of websites (S3), is a different job. The hypothesis to test is that a **brief-specific workflow** beats both generic diffs and a general-purpose AI chat on these points:

1. **Typed findings.** Changes are reported as deliverables, quantities, dates, owners and approval wording, not as changed lines.
2. **Scope-aware omission handling.** Every report distinguishes *changed*, *absent from a complete replacement*, *not addressed by a partial update* and *unknown*. The hypothesis is that general AI chats blur these [U]; D-5 tests this against the baseline.
3. **Verifiable evidence.** Every finding points to an exact passage in each source version.
4. **Project change history** across successive revisions. Each report stays tied to its exact inputs and review state. This is the proposed paid feature.

The plan treats this as unproven. The validation plan (`04-validation-plan.md`) tests it head-to-head against a generic diff, a general-purpose AI comparison and the user's current manual process.

## Explicit non-goals (initial MVP)

- Consumer use cases: timetables, bookings, event notices.
- A general document assistant or a general diff tool.
- Inbox or email ingestion, website crawling or monitoring, calendar integration, mobile share extensions.
- Contract or legal interpretation, and any statement about what a client agreed to.
- Autonomous client communication.
- Complex approval workflows and project management features.
- Multi-document reconciliation into an "authoritative current spec".
- Agents, a vector database, custom OCR, or custom model training.
- Unlimited processing, enterprise compliance claims, native mobile apps.

## Stop and pivot conditions

If problem validation or the prototype gate fails (thresholds in `04-validation-plan.md` §6), the plan calls for narrowing the niche, repositioning, or stopping. It does not call for adding formats or integrations to hide weak demand (handoff §12).
