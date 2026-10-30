# 02 — MVP Specification

Plan section: §13.2. Tags: [E] established, [A] assumption, [U] unverified, [O] owner decision.

## 1. User flow

1. **Project.** The user signs in to the iOS or Android app (email one-time code, Google, or Sign in with Apple), then creates a project for a client engagement or opens an existing one.
2. **Earlier version.** In the iOS or Android app, the user imports it by pasting text, picking a PDF, taking or choosing a screenshot, or sharing it into ChangeLens from another app. They give it a label (for example "Brief v1, 3 Oct").
3. **Newer input.** The user imports the revised brief or a partial update.
4. **Confirm the pair** (required, no defaults inferred):
   - which input is the earlier one and which is the newer one
   - the scope of the newer input: **complete replacement**, **partial update** or **unknown**
   - The app may *suggest* an order from dates found in the text. Upload time and filenames are never used. The user must confirm either way (AC-14).
5. **Process.** The app shows progress, and any partial-processing warnings before the report.
6. **Report.**
   - prioritised findings, uncertainties, and a link to all other differences
   - each finding shows before and after values plus evidence passages
7. **Review.** The user marks each finding *confirmed*, *corrected* or *dismissed*, and can add notes. Optionally they can record *client approval* by attaching external evidence (see §5).
8. **Save and share.** The comparison is saved in the project history. The user can create a share link to a snapshot they approved.

## 2. Input limits (proposed defaults) [A][O]

| Limit | Prototype | Thin slice | Rationale |
|---|---|---|---|
| Formats | Pasted text; PDF with an extractable text layer; PNG/JPEG screenshots | Same, entered through the PDF picker, paste, camera / photo library, or the OS share sheet | Mobile-first owner decision (2026-10-30) overrides handoff §5 staging; screenshots are evaluated in Gate 2 |
| Size per input | ≤ 15,000 words; PDF ≤ 20 pages and ≤ 10 MB; image ≤ 5 MB, short side ≥ 800 px, ≤ 40 MP | Same | Typical briefs are 1–10 pages [U]; caps cost per comparison |
| Language | English only | English; others evaluated after the pilot | Evaluation dataset is English |
| Scanned PDFs | Rejected, with the message "no text layer" | Allowed only through the screenshot path, with warnings | No custom OCR |
| DOCX | Not supported; users export to PDF | Decide from D-1 interview evidence | Avoids speculative format work |

When content is rejected or only partly processed, the user sees an explicit message naming the pages or regions that were skipped. The comparison is marked **partial**, never shown as complete (AC-11, AC-20).

## 3. Full vs partial semantics

Comparison scope is a property of the **newer input** that the user confirms. Behaviour for each earlier fact with no counterpart in the newer input:

| Newer-input scope | Earlier fact has no counterpart | Report wording |
|---|---|---|
| Complete replacement | Absent from the replacement | "Not present in *v2* (complete replacement). This report does not mean the obligation is cancelled." |
| Partial update | Not addressed | "Not addressed by this update." Not reported as removed or reconfirmed. |
| Unknown | Uncertain | "This update's scope is unknown, so it is unclear whether this still applies." Flagged for review. |

Facts that appear in both inputs follow the comparison rules in `03-technical-design.md` §4 (changed, equivalent, ambiguous). The report displays the earlier passage for every omission. It never fabricates a quote showing the absence (handoff §7).

## 4. Report behaviour

- **Finding categories:** deliverable, quantity, date or deadline, responsibility or owner, approval-related statement, other material.
- **Each finding shows:**
  - category and change type (added, changed, absent, not addressed, uncertain, equivalent)
  - before and after values, in raw wording plus the normalised value where relevant
  - one or two sentences of explanation
  - evidence links to source version and location (character range for text; page plus text span for PDF; region for images)
  - review state
- **Prioritised view** lists material changes first. A visible line states: "Selected summary — N other differences, including presentation-only edits" and links to the full list (AC-13).
- **Withheld findings.** Low-confidence or unverified findings never appear as certain. They show in an "Needs your review" group, or are withheld with a count (AC-10).

## 5. Review behaviour

There are three separate states, stored separately and never derived from each other (AC-12):

| State | Set by | Meaning |
|---|---|---|
| AI-detected | Pipeline | The system found this from the supplied text |
| User-reviewed | User action: confirmed, corrected or dismissed | The user checked the finding |
| Client approval recorded | User attaches external evidence, such as a pasted email excerpt or file, plus a date | Someone has stated that the client approved. ChangeLens does not verify it. This is a single record, not an approval workflow. It exists because handoff §7 requires this state to be kept separate |

- Corrections create a new finding revision. The original AI output is kept (AC-15).
- No UI wording may present a reviewed finding as "approved" or "agreed".

## 6. Sharing behaviour

- A share is an **immutable snapshot** of selected findings and their evidence excerpts. It never links to the live project.
- The owner chooses which findings to include. The snapshot holds only those findings and their quoted passages. It never includes other project files or versions (AC-16).
- The link is unguessable, with at least 128 bits of entropy. It has a default expiry of 30 days [A][O], and the owner can revoke it at any time.
- After revocation or expiry, the link returns a "no longer available" page and none of the report content (AC-17).
- Share views are read-only and need no account. Each view is logged with a timestamp, without IP retention beyond 30 days [A].

## 7. Acceptance criteria

Each criterion is testable and mapped in `traceability.md`. "Evaluation set" means the labelled dataset defined in `04-validation-plan.md` §4.

| ID | Criterion | Origin |
|---|---|---|
| AC-1 | When both inputs state different explicit values, a *changed* finding shows both values and both source locations. Example: a changed deadline shows both dates. | §7, §11 |
| AC-2 | When a complete replacement omits an earlier statement, it is reported as *absent from the replacement*, with the earlier passage, and never as cancelled. | §7 |
| AC-3 | When a partial update omits an earlier statement, it is reported as *not addressed*, showing the earlier passage and stating that the update is partial. Example: an email-style update that does not mention deliverables produces zero removed-deliverable findings. | §7, §11 |
| AC-4 | When scope is unknown, omissions are flagged as uncertain, showing the earlier passage and stating that the scope is unknown. There are zero definitive removal claims. | §7 |
| AC-5 | Reworded text with unchanged meaning is classed as equivalent or presentation-only, and the underlying text diff stays reachable. | §7 |
| AC-6 | A reordered but otherwise identical brief produces zero scope, date, quantity or responsibility findings. | §11 |
| AC-7 | Ambiguous dates, entities, extraction or matches are preserved as ambiguous and flagged for review. No silent guess is made. | §7 |
| AC-8 | Changes to numbers, negation, deadlines or qualifiers (for example "must" → "may") are never classed as equivalent. | §6 |
| AC-9 | Every substantive finding cites its source version and location, and every quoted evidence string matches the source exactly. There are no fabricated absence quotes. | §6, §7 |
| AC-10 | Low-confidence matches are shown as "needs review" or withheld with a count, and never presented as certain. A numeric score alone is never shown as evidence. | §6 |
| AC-11 | Unreadable, unsupported or partly processed content produces an explicit warning, and the comparison is marked partial. Example: a screenshot with unreadable text surfaces its limitation. Any input type outside §2 is rejected with an explicit "not supported" message rather than processed silently. | §5, §11 |
| AC-12 | AI-detected, user-reviewed and client-approval states are stored separately, and a review action never creates or implies client approval. | §7, §11 |
| AC-13 | Non-prioritised differences can be inspected, or the report states that it is a selected summary. | §7 |
| AC-14 | Processing cannot start until the user confirms the order and scope of the comparison. Order is never inferred from upload time or filename. | §4 |
| AC-15 | Original sources and AI outputs are immutable. Corrections and re-runs create new records. | §8 |
| AC-16 | A shared report contains only the selected findings and their excerpts, and no other project files or versions. | §8 |
| AC-17 | A revoked or expired share link returns no report content on the next request. | §11 |
| AC-18 | Instructions embedded in a document are not followed, links are not fetched, and no external action is triggered. Injected text cannot suppress a finding or force a false equivalence: every changed text block that no finding explains is listed as an unexplained difference. Text the parser extracts but a reader cannot see (invisible, tiny or off-page) raises a warning. This is verified with prompt-injection, suppression and hidden-text fixtures in the evaluation set. | §6 |
| AC-19 | A user cannot read, list or share another tenant's projects, sources or reports. This is verified by authorisation tests on every data route. | §8 |
| AC-20 | Inputs over the limits in §2 are rejected before processing, with a message that names the limit. | §5 |
| AC-21 | Each account has a metered comparison allowance and a hard per-comparison cost ceiling. No path allows unlimited processing. | §10 |
| AC-22 | Deleting a project removes its sources, derived records and active shares from primary storage immediately, and from backups within the stated retention window. | §8 |
| AC-23 | No document content (parsed text, prompts, model responses) is written to application logs, error-tracking breadcrumbs, metrics or job payloads. Jobs carry record IDs only, and every content store is listed in the data inventory that deletion covers. | §8 |
| AC-24 | On both iOS and Android, a brief can be imported by paste, PDF picker, camera / photo library, or OS share sheet from another app (Mail, Files). Every path lands in a user-chosen project and goes through the same order and scope confirmation (AC-14) and input limits (AC-20). | Owner, O-3 |
| AC-25 | No document content is persisted on the device: no offline cache, no copy saved to the photo library, nothing kept by the share extension after hand-off. Only auth tokens are stored, in Keychain / Keystore. Push notifications carry a comparison ID and a generic message, never document text. | Owner, O-4; §8 |
| AC-26 | Users sign in with email one-time code, Google or Sign in with Apple. MFA is available. Revoking a session at the identity provider ends API access on the next token refresh, within 15 minutes at most [A]. Linking sign-in methods by verified email never merges two tenants. | Owner, O-4; §8 |
