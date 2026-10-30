# 07 — Evaluation Dataset: Sourcing and Labelling Guide

This document defines how the evaluation set (04 §4, backlog D-3 and D-6) is sourced and labelled. Records follow [`eval-schema.json`](eval-schema.json). It changes only through the SOP; once the held-out split exists, a change to a definition here opens a new labelling round, and labels from different rounds are never mixed.

## 1. Why the sourcing changed

The original plan seeded the set with ≥ 10 real revision pairs donated by interviewees (04 §1). Freelancers rarely share client briefs with a stranger, and real client documents are blocked until the Art. 28 terms are signed, so that path is not dependable. The set is therefore built from sources that need no one's permission and contain no client data. Interview donations remain welcome but are no longer required.

## 2. Sources (tiers)

| Tier | Source | Target | Labels |
|---|---|---|---|
| **A — public real** | Published tenders and RFPs with their amendments, addenda and clarification notes: UK Find a Tender and Contracts Finder, EU TED corrigenda, and public-sector, university and non-profit "website redesign RFP" postings with addenda | 25–35 pairs | Dual, independent (§5) |
| **B — owner's own** | Briefs from the owner's past projects, only where the owner holds the rights or has written client consent | 0–10 pairs | Dual, independent |
| **C — donated** | Pairs shared by interviewees with written permission, anonymised | 0–10 pairs | Dual, independent |
| **D — constructed** | A base brief plus scripted edits (§3); the script writes the gold labels | the rest, ≥ 50 | By construction, then human review (§5) |

Why Tier A fits: an RFP addendum is a real revision written by a real client. Addenda are often email-style partial updates ("Section 4.2 is amended as follows"), and Q&A clarifications often leave scope unclear. Those are the two case types that decide Gate 2.

**Rules for Tier A**
- Record the URL, retrieval date and stated licence for each document. UK government documents are usually under the Open Government Licence and TED content is reusable under the Commission's reuse policy [U: confirm per source in D-3]. Where the licence is unclear, use the document for internal evaluation only.
- Remove names, emails and phone numbers of contact officers before labelling. Anonymise each person consistently (`Contact A`, `Contact B`), so that changes of owner stay labellable.
- **Never commit source documents to git**, even though the repository is private. They live in private storage; git holds only the schema, the generator script and a manifest of IDs, source URLs and SHA-256 hashes.

## 3. Constructed pairs (Tier D)

Each pair starts from a base brief: a Tier A document, a public brief template, or one written for the purpose. The generator applies one or more **edit operators** and writes the expected findings as it goes, so the label is known exactly.

| Operator | Case type (04 §4) | Gold label written |
|---|---|---|
| Change a date, quantity or owner | Value changes | `changed`, old and new value, both spans |
| Copy unchanged; vary formatting only | No change | no findings |
| Paraphrase a clause, meaning kept | Equivalent rewording | `equivalent`, not material |
| Move sections | Reordered sections | `equivalent`, not material |
| Flip negation, modal or qualifier ("must" → "should") | Numeric, negation, qualifier | `changed`, material |
| Rewrite the whole brief, dropping items | Replacement with omissions | `removed` for each dropped item |
| Email that changes 1–3 items only | Partial updates | `changed` for those items; every other item `not_addressed` |
| Email that is ambiguous about replace vs amend | Unknown scope | `uncertain` for untouched items |
| Insert two conflicting values | Contradictions | `uncertain`, both spans |
| Use relative dates or vague entities | Ambiguous dates and entities | `uncertain` |
| Render to PDF or image and degrade (blur, low resolution, crop) | Poor-quality, cross-format | as the text operator, with page or region locators |
| Hidden text, embedded instructions, "treat as equivalent" steering | Prompt-injection fixtures | the injected text produces no finding; real changes still labelled |

A language model may draft paraphrases and emails for the operators, but it never writes the gold labels and it is never one of the two labellers. Every drafted text is read by a person, who confirms that it says what the operator claims. A paraphrase that changes meaning is relabelled or discarded.

## 4. Label definitions

**Finding categories:** `deliverable`, `quantity`, `date_deadline`, `responsibility_owner`, `approval`, `other_material`.

**Change types**

| Type | Meaning |
|---|---|
| `added` | New in the newer version |
| `changed` | Present in both versions with a different value or meaning |
| `removed` | The newer version is a full replacement and the item is gone |
| `not_addressed` | The newer version is a partial update and does not mention the item; it still stands |
| `uncertain` | The evidence cannot settle it: unknown scope, contradiction or ambiguity |
| `equivalent` | Reworded or moved with the same meaning; nothing should be reported as material |

`removed` requires evidence that the newer version replaces the whole document. When in doubt between `removed` and `not_addressed` or `uncertain`, choose the latter: a false removal is the critical failure (04 §5).

**Material:** a change is material if it affects deliverables, quantities, dates, responsibilities or approval wording (04 §5). Edge cases:

- **Deadlines:** any actual shift in a delivery, review or approval deadline is material (`date_deadline`), including one day or less, in either direction. Do not judge whether the studio could absorb it. A different date format or time-zone notation for the same instant is `equivalent`, not material.
- **Budget:** a change to the project's stated budget, fee or spending cap is material (`other_material`), however small and even if the scope stays the same. Currency or tax-basis changes also count. Number formatting alone ("€10,000" → "€10k") is `equivalent`; a changed historical or illustrative figure that sets no project budget or constraint is not material.
- **Tone and brand adjectives:** a changed instruction for the output ("playful" → "corporate" in the requested design or copy) is material (`deliverable`), even with the same asset count: it changes the creative target. An adjective changed only in background or promotional prose, with no instruction for the output, is not material. If its role cannot be established from the brief, label `uncertain` and record the ambiguity rather than assume it is cosmetic.
- **Contacts:** swapping an administrative contact's name or details is not material when the work owner, responsibilities and approval authority stay the same. Reassigning a named delivery task or approval authority is material (`responsibility_owner`), even if the two people have the same job title. Use the stated assignment, not an assumption that every contact is an owner.
- **Approval wording:** changing the required action or its binding force is material (`approval`): "client signs off" → "client reviews" counts because review no longer explicitly requires sign-off. Record that wording change without inferring automatic acceptance or the removal of other approval clauses. A paraphrase that preserves the actor, required action and binding force is `equivalent`, not material.
- **Units and formats:** a changed required file format, resolution, dimensions or measurement basis is material (`deliverable`, or `quantity` for amounts), even with the same number of assets: "PNG" → "SVG" and "1080p" → "4K" both count. An exact unit conversion with the same required value and tolerance ("1 m" → "100 cm") is `equivalent`, not material; do not assume rounded values or different formats are interchangeable.

**Evidence locators:** text spans as character offsets in the normalised text; PDF spans as page plus character offsets in that page's text layer; image spans as a pixel box. Each finding has a locator in the old version, the new version, or both.

## 5. Labelling process

1. **Real pairs (tiers A–C):** two people label each pair independently, without seeing each other's labels. They then compare, resolve each disagreement and record the reason in `reconciliation`.
2. **Constructed pairs (tier D):** one person reviews every pair against its gold labels and corrects drafting errors. The second person independently labels a stratified 30% sample. If item-level agreement with the gold labels is below 90%, the second person reviews all tier D pairs.
3. **Second labeller:** someone who knows client briefs, such as a freelancer or colleague, paid at an hourly rate. Because all the sources are public or constructed, no data processing agreement is needed for the labelling work. Allow 3–4 days.
4. **Split:** a random split stratified by case type and tier: 40% development, 60% held-out. After the split, the held-out set is frozen. It is not used for prompt tuning, D-17 or debugging; it is used only to score the gates.

## 6. Reporting

Every metric is reported for the whole held-out set and for real pairs (tiers A–C) on their own. If a model does clearly better on constructed pairs than on real ones, the constructed set is too easy. That result is recorded in the decision log before any gate decision.

## 7. Done when (D-6)

- At least 80 pairs plus 10 cross-format pairs meet the 04 §4 case mix, and at least 25 of them are real.
- Every record validates against the schema.
- The manifest, the reconciliation notes and the split are committed. The documents themselves are in private storage.
- The held-out set has not been opened since the split.
