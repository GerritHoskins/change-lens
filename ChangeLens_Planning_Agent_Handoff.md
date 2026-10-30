# ChangeLens — Planning-Agent Handoff

## 1. Assignment and decision status

Act as the product and technical planning agent for **ChangeLens**, an AI-assisted app that answers: **“What changed since the last version, and which changes matter?”**

Produce an actionable validation and implementation plan, not implementation code. Preserve the low–medium implementation-complexity constraint. Prefer a narrow, testable product over a general-purpose document platform.

**Initial complexity estimate:** Low–medium for bounded, manually supplied input pairs using existing models. Reliable support for arbitrary documents, formats, and multi-source reconciliation could exceed that estimate; validate the difficult parts before committing to them.

This is an idea-stage project. There is no validated customer demand, confirmed willingness to pay, selected technology stack, or established competitive advantage. The professional positioning and prices below are proposals from the discussion, not commitments or findings from customer research.

The original consumer concept and subsequent professional positioning are both retained here. **Recommended planning direction: changing client briefs for freelancers and small agencies.** Treat that as the first hypothesis to test, not a reason to build both products.

Technical safeguards and implementation suggestions in this handoff are planning recommendations, not previously approved specifications. State additional assumptions explicitly. Resolve noncritical gaps with conservative defaults; identify decisions that materially affect scope, privacy, cost, or correctness.

## 2. Original concept

### Problem

A person receives an updated timetable, booking confirmation, instruction sheet, or event announcement. The new version may use different wording, formatting, or a different medium. They must manually compare it with the previous version to discover what actually changed.

### Proposed experience

The user imports a new version and compares it with a saved earlier version. ChangeLens returns a short, evidence-backed report, with each finding linked to its original wording or image region.

Illustrative output:

> **Your evening class changed**
>
> Start time: 18:00 → 18:30  
> Location: unchanged  
> New requirement: bring indoor shoes  
> Select any finding to inspect the source evidence.

“Unchanged” is appropriate only when the available evidence supports it; omission from a partial update is not confirmation.

### Intended innovation

Match corresponding information across wording and layout changes, separate meaningful changes from cosmetic edits, and handle manually supplied information that originally arrived through different channels. One example is a screenshot of an update replacing or supplementing an earlier document.

The concept is not claimed to be unprecedented. Its potential originality lies in the workflow and usefulness of the result, not simply adding AI to a diff tool.

## 3. Proposed commercial focus

**Initial customer hypothesis:** Freelancers and small agencies managing repeated changes to client briefs or project requirements.

**Value proposition:** “Catch changed requirements before you deliver the wrong thing.”

**Job to be done:** “When a client sends a revised brief, show me what changed in deliverables, deadlines, responsibilities, and approval-related wording, with evidence I can check and share.”

Illustrative output:

> The revised brief adds two deliverables, changes the deadline, and removes the sentence describing the approval step.

That describes the supplied text. It must not silently conclude that the approval requirement is legally cancelled or that the client has accepted a new agreement.

The proposed paid differentiation is **project-specific change history**: track changes to scope, dates, ownership, and stated approval requirements over successive revisions. Reports should remain attached to their exact source versions and review status.

The consumer version is still a valid possible later direction, but occasional personal comparisons are a weaker subscription hypothesis. Do not combine consumer and agency feature sets in the initial MVP.

Previous assessment: ChangeLens was recommended for its balance of potential revenue and manageable implementation scope. Two documents can demonstrate the core value, and users can inspect the evidence. This is a product assessment, not market validation.

## 4. Core user journey

1. Create or open a project and import the earlier brief.
2. Import a revised brief or a partial update, such as pasted text or a screenshot.
3. Confirm the comparison pair, which input is newer, and whether the newer input is a complete replacement, a partial update, or of unknown scope.
4. Generate a concise report of meaningful differences, uncertainties, and supporting evidence.
5. Review or correct findings, then save the comparison in project history and optionally share a deliberately approved report.

Use explicit version selection in the MVP. Do not infer chronology solely from upload time, filenames, or ambiguous dates. Do not automatically merge every project document into a supposedly authoritative current specification.

## 5. MVP scope

| Capability | Required outcome |
|---|---|
| Manual import | Accept text and the selected document/image formats without connecting external accounts. |
| Saved projects and versions | Preserve original inputs, version labels, user-confirmed ordering, and comparison history. |
| Structured extraction | Identify relevant deliverables, quantities, dates, responsibilities, and approval-related statements while retaining source references. |
| Semantic comparison | Match equivalent information across wording or layout changes and distinguish meaningful changes from presentation-only edits. |
| Evidence-backed report | Show before/after values, a brief explanation, and inspectable supporting passages or image regions. |
| Review and sharing | Let the user inspect findings and uncertainties, record review status, and share a selected report with explicit access controls. |

**Input-format planning:** The original MVP included image/text import and highlighted evidence. A reasonable staged approach is pasted text and text-based PDFs first, followed by bounded screenshot support once evidence alignment is demonstrated. Evaluate these options rather than silently assuming arbitrary file compatibility. A text-only prototype is a validation slice, not the complete cross-format proposition.

Choose and document file-size, page-count, image-quality, and supported-language limits. Unsupported or partially processed content must produce an explicit warning, not an apparently complete result.

**Out of scope initially:** Inbox access, email ingestion integrations, website crawling, scheduled website monitoring, calendar integration, native mobile share extensions, autonomous client communication, contract interpretation, complex approval workflows, and comprehensive project management.

Do not build all of these formats, integrations, or workflows “for completeness.” The goal is a small paid pilot and one reliable comparison workflow.

## 6. AI responsibilities and limits

Use existing models; custom model training is not a prerequisite.

AI should help extract structured statements, match corresponding facts, distinguish equivalent wording from changed meaning, classify relevant changes, and generate concise explanations. It should not decide what a client legally agreed to or invent missing context.

Suggested bounded pipeline:

**Import → parse with provenance → extract structured facts → align facts → compare → verify evidence → generate report → human review.**

Use deterministic handling where possible for exact values, source lookup, simple text changes, and schema validation. Preserve raw wording alongside any normalised values. Do not let semantic similarity hide changes to numbers, negation, deadlines, or qualifiers.

Every substantive finding should identify its source version and location. A numeric confidence score alone is not evidence. Low-confidence matches should be marked for review or withheld rather than presented as certain.

Document contents are untrusted inputs, not instructions to the model. The comparison pipeline should not execute document instructions, retrieve arbitrary external links, or trigger external actions.

## 7. Critical correctness rules

**The central challenge is distinguishing “removed” from “not mentioned in this update.”**

| Situation | Expected behavior |
|---|---|
| Both inputs explicitly state different values | Report a changed value with evidence from both. |
| An explicitly complete replacement omits an earlier statement | Report that it is absent from the replacement document; do not automatically interpret that as cancellation of an obligation. |
| A partial update omits an earlier statement | Mark it as not addressed by this update, not removed or reconfirmed. |
| The scope or completeness of the update is unknown | Flag the uncertainty and avoid definitive removal claims. |
| The wording changes but the supported meaning does not | Classify it as equivalent or presentation-only, while retaining access to the underlying text difference. |
| Dates, entities, extraction, or matching are ambiguous | Preserve the ambiguity and request review; do not silently guess. |

For omissions, show the earlier passage and explain the newer document's comparison scope. There is no newer “absence quote” to fabricate.

Treat the following as separate states: **AI-detected finding**, **user-reviewed finding**, and **externally stated client approval**. A user reviewing a report is not evidence that a client approved a scope change.

Do not hide all non-prioritised differences. Retain a way to inspect them or clearly state that the report is a selected summary rather than an exhaustive diff.

## 8. Suggested architecture and data responsibilities

Prefer the simplest architecture that supports private uploads, reliable background processing where necessary, structured AI output, evidence inspection, and persistent history. A responsive web app is a reasonable default to evaluate, not an approved platform decision.

Suggested logical records:

| Record | Responsibility |
|---|---|
| Project | Customer context and its document/comparison history. |
| Source version | Original input, label, provenance, user-confirmed ordering, and full/partial/unknown scope. |
| Extracted fact | Raw and normalised values, source location, extraction status, and uncertainty. |
| Comparison | The exact two inputs, processing configuration, and completion or failure status. |
| Finding | Category, before/after values, evidence references, explanation, uncertainty, and review state. |
| Shared report | An approved snapshot, included content, access policy, and revocation state. |

Preserve original source records; record corrections and new comparisons without silently rewriting historical evidence. Do not allow report links to expose unrelated project files.

Plan for upload validation, tenant isolation, controlled deletion and retention, sensitive-data handling, and processing-cost limits. Determine what an external model provider receives and retains before handling real client documents. Do not make privacy or compliance claims before verifying them.

Do not add agents, a vector database, custom OCR infrastructure, or multi-document reconciliation unless the evaluated MVP actually requires them. Source-location fidelity is more important than an elaborate architecture.

## 9. Competitive context

### Diffchecker — direct comparison reference

The official pricing page lists **Pro + Desktop at US$15 per user/month**, AI summaries, multiple document formats, saved comparisons, and link sharing. Its homepage also describes saved/shareable comparison workflows. These capabilities mean that “upload two files and get an AI summary,” saving comparisons, and sharing results are not established differentiators. [S1, S2]

### Visualping — adjacent monitoring reference

Visualping describes scheduled website monitoring with visual, text, and code change detection, highlighted comparisons, and AI summaries. ChangeLens's proposed starting point is different: user-supplied personal or project materials rather than websites checked automatically. [S3]

### Hypothesis to validate

A domain-specific workflow for changing client briefs—structured changes to scope, deadlines, responsibilities, approval wording, and carefully handled partial updates—may be more useful than a generic comparison tool for a particular buyer.

This is not proof of a market gap. Validate competitors' workflows and compare against both existing comparison products and the user's current manual or general-purpose AI process. Two reference products are not an exhaustive market survey.

Source checks for this handoff: 30 October 2026. Recheck competitor capabilities, billing conditions, and prices when executing the plan. Competitor prices do not establish willingness to pay for ChangeLens.

## 10. Monetization hypotheses

| Offer | Price to test | Proposed customer |
|---|---|---|
| Individual subscription | **€9–15/month** | A freelancer with recurring brief revisions. |
| Small-team subscription | **€39–59/month** | A small agency sharing project-change reports. |

These are exploratory prices, not validated pricing or a final packaging decision. Included seats, comparison allowances, page limits, retention, and tax presentation remain undecided. Do not default to unlimited AI processing.

**Recommended initial offer:** One professional niche, manual uploads, saved projects, evidence-backed comparison reports, and controlled sharing. Sell a small paid pilot of this exact workflow before building the full product.

Illustrative revenue arithmetic, not a forecast: **62 teams × €49/month = €3,038/month** in subscription revenue, assuming €49 is the price before VAT. That is not profit. Acquisition, support, model processing, document extraction, hosting, storage, payment fees, refunds, and churn still matter.

The plan should model cost per comparison, heavier documents, failed/retried processing, and plausible customer usage. Show assumptions and sensitivities instead of inventing margins or adoption numbers.

## 11. Validation and evaluation

### Commercial validation

Choose one customer niche and obtain permissioned, anonymised, or synthetic examples of actual revision workflows. Determine how often revisions occur, how users currently compare them, what missed changes cost in time or rework, and who would pay.

Demonstrate the workflow with representative document pairs, then offer a small paid pilot. Test whether customers repeatedly use the project history and evidence-backed reports—not merely whether they find a single demo impressive.

Evaluate directly against a generic diff, a general-purpose AI comparison, and the current manual workflow. Enthusiastic feedback and competitor pricing alone are insufficient evidence of demand.

### Technical evaluation

Build a labelled dataset that includes straightforward changes, no changes, equivalent rewording, reordered sections, numeric changes, negation, complete replacements, partial updates, contradictory statements, ambiguous dates, and poor-quality inputs. Add cross-format examples before claiming cross-format reliability.

Measure factual precision/recall by change type, missed material changes, false removals, unsupported findings, evidence-location accuracy, correction effort, processing failures, latency, and cost. Distinguish complete comparisons from partial or failed processing.

Set acceptance thresholds before evaluating the pilot. Do not describe the product as reliable solely because its generated summaries read well.

### Minimum acceptance examples

A changed deadline must show both dates and their source locations. A reordered but otherwise identical brief must not produce fabricated scope changes. A partial email-style update that does not mention deliverables must not cancel them. A screenshot with unreadable text must surface its limitation. A review action must not become client approval. A revoked share link must stop exposing its report.

## 12. Delivery sequence and decision gates

| Stage | Deliverable | Gate before expansion |
|---|---|---|
| Problem validation | Target niche, representative examples, baseline workflow, and a paid-pilot offer. | Evidence of recurring need and a concrete buying decision. |
| Comparison prototype | Two manually selected inputs, structured findings, source evidence, and uncertainty handling. | Measured advantage on the chosen workflow, including partial-update cases. |
| Thin product slice | Saved projects/versions, reviewable reports, authentication, and controlled sharing. | Users can complete the workflow without operator intervention or accidental disclosure. |
| Paid pilot | Basic usage limits, metering, support process, and cost measurement. | Actual payment, repeat usage, acceptable correction burden, and viable unit economics. |
| Focused expansion | The next format or workflow improvement justified by pilot evidence. | Demonstrated need; no speculative integration platform. |

If the workflow offers no meaningful advantage over available tools, recommend narrowing, repositioning, or stopping rather than adding features to conceal weak demand.

## 13. Required planning-agent output

Deliver one coherent plan containing:

1. **Product decision:** Recommended initial customer, precise job to be done, value proposition, differentiator hypothesis, and explicit non-goals.
2. **MVP specification:** User flow, input limits, full-versus-partial semantics, review behavior, sharing behavior, and testable acceptance criteria.
3. **Technical design:** Architecture alternatives and recommendation, AI/extraction pipeline, evidence representation, data model, privacy boundaries, failure handling, and cost model.
4. **Validation plan:** Customer research, paid-pilot proposal, competitive baseline, evaluation dataset, metrics, and go/no-go thresholds.
5. **Execution backlog:** Dependency-ordered milestones and tasks with acceptance criteria, risks, effort ranges, and assumptions. Separate discovery tasks from implementation tasks.
6. **Decision log:** What is established by this handoff, what is assumed, what remains unverified, and which decisions require owner input before implementation.

Do not reframe this as a general document assistant or begin implementation. Produce the smallest credible plan for determining whether **client-brief change tracking is useful enough to pay for**.

## 14. Open decisions

The exact customer niche, validated revision frequency, willingness to pay, launch languages/market, first production input formats, stack, model provider, processing location, storage/retention policy, sharing mechanism, team-seat allowance, usage limits, quality thresholds, and acquisition channel remain open.

Do not assume enterprise compliance, a native mobile requirement, unlimited documents, or a settled deployment region. Propose reasoned defaults and identify where evidence or explicit approval is required.

## Sources

These references support competitor facts only. Product recommendations, examples, proposed prices, and validation methods are hypotheses or design proposals.

- **[S1] Diffchecker pricing**, checked 30 October 2026: `https://www.diffchecker.com/pricing/`
- **[S2] Diffchecker product overview**, checked 30 October 2026: `https://www.diffchecker.com/`
- **[S3] Visualping: “What is Visualping?”**, checked 30 October 2026: `https://help.visualping.io/en/articles/4438913`
