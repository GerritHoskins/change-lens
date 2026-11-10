# Prior design references — reviewed 2026-11-07

The owner supplied these three private Claude artifacts during the handoff interview.
The web reader could not access them. After the owner signed into the in-app browser,
all three were inspected read-only. No artifact text, sharing, comments or design
content was changed. Future readers may need the owner's authenticated access.
Do not store authentication cookies or temporary frame URLs in the repository.

## Source map

| Reference | Observed title and contents | Authority |
| --- | --- | --- |
| [A: v1 screens](https://claude.ai/artifact/2oxDXfdjVheCfHT7NbrPGW?org=9fa5e83c-15b7-4533-adf4-75445b144fdb) | **ChangeLens v1 screens**, 78 artboards: incumbent screens, M1b P0–P7, accounts/import/billing states, EN/DE, dark, three visual variants and an A+B iteration | Historical design evidence; compare against current product decisions |
| [B: Calm Bold](https://claude.ai/artifact/V9325dymoruEtTngXEULo5) | **ChangeLens Calm Bold**, proposed tokens/components/voice; 25 files listed | Candidate replacement system, explicitly labelled a proposal |
| [C: original system](https://claude.ai/artifact/Dhhsup9qRnHA7uyn8cvoYm) | **ChangeLens**, indigo Material 3 roles, component guidance and D-15 POC provenance; 19 files listed | Historical POC/system documentation, not proof of current app completeness |

The first artifact resolves the missing canvas reference. P5 is **Dismiss with a
reason**; P7 is **Review done ≠ client approval**, with a later Calm Bold **all checked**
version. Do not confuse these screen IDs with pipeline step IDs.

## What was actually inspected

- Canvas inventory and foundations; documented P0–P7 labels and loaded state text.
- Full-window visual previews of A/Calm Bold Home, B/Sticker Pop Home and C/Night
  Shift Home.
- A+B Compare two briefs, What moved/report, and finding text-fallback previews.
- Calm Bold P5 dismissal, P7 completion and P3 dark-report previews.
- Both design-system overview/readme texts and covers; the original system's visible
  light/dark/accessible color-role tables.

This was a representative review, not exhaustive testing of all 78 artboards or
every prototype link. These are browser-rendered design prototypes, not native
Flutter implementations. Some artboards show horizontal/vertical scrollbars at
Fit preview size. Do not treat that as a measured Flutter overflow; use native tests.
The private artifacts remain the full source; no complete export was produced.

## Recovered screen/state map

| Historical screen | Role and details recovered |
| --- | --- |
| P0 | Vocabulary separating detection, personal review, approval, types and topics; some approval granularity text conflicts with current API (below) |
| P1 | Projects/home and Compare two briefs entry; reading status and comparisons to review |
| P2 | Earlier/newer input slots, project, explicit scope; empty and ready-with-newer-reading variants |
| P3 | Topic-filtered report, counts, separate needs-review, selected-summary access; EN/DE/dark variants |
| P4 | Finding evidence, checking-page disabled Confirm state, pinned text-fallback warning, needs-review confirmed-but-stays state; EN/DE/dark variants |
| P5 | Dismissal reasons: reworded, wrong passage, irrelevant to work, other; optional note; dismiss-and-next; currently a design proposal |
| P6 | Version timeline and explicit comparison shortcuts |
| P7 | Reviewed-count summary, confirmed/corrected/dismissed breakdown, explicit non-approval statement, return to project and separate approval record entry |

Additional artboards cover sign-in/email code/linking, account deletion, share-to-
project picker, launch versus post-D-19 import/paywall, feedback, reading/queued/
processing/complete/failed comparisons, unknown/partial omission findings and privacy.
Their presence does not mean those features are implemented.

## Visual comparison and recommendation to the receiving agent

| Candidate | Observed character | Useful elements | Rework for this brief |
| --- | --- | --- | --- |
| Original Material/POC | Indigo roles, platform fonts, conventional Material components | Semantic roles, evidence discipline, native familiarity | POC locator/debug metrics are not consumer UI; no need to preserve indigo or its old screen composition |
| A / Calm Bold home | Quiet light ground, heavy value-focused headings, vivid purple summary, black bottom compare action, simpler project rows | Primary task is obvious; result-focused hierarchy | Large hero can overtake frequent-use lists; choose semantic color consistently with later token proposal |
| B / Sticker Pop home | Lilac ground, yellow/mint blocks, black outlines/offset shadows, sticker-like branding and bento tiles | Strong recognition and clear action | Decorative treatment competes with evidence/status; short prototype labels do not prove long DE/large-type fit |
| C / Night Shift home | Dark surfaces, luminous green accents, compact project cards, bottom Projects/Compare control | Compact status scanning, dark-mode exploration | Do not make darkness mandatory; an action should not masquerade as a navigation destination; avoid implying autonomous overnight monitoring |
| Later A+B / Calm Bold system | Neutral ground, heavy sans, pastel topic blocks, bright marker, black action pill, orange dashed needs-review with question icon | Best existing candidate for value-first reports, two-slot setup and pinned fallback explanation | Tighten native controls, compact/large-text layouts, copy accuracy and color-role consistency before committing |

**Reviewer recommendation, not owner approval:** use the later Calm Bold/A+B work
as the strongest starting candidate, because it addresses the owner's priority of
clear comparison/evidence review. Preserve its useful information hierarchy and
state distinctions; let the receiving agent decide whether to evolve it or replace
it after comparing actual task performance. The owner explicitly delegated this
comparison rather than pinning a winner.

The proposed system names Inter Tight, custom stroke icons, large radii, topic
pastels, a bright marker and a bottom action. None is automatically approved as a
new dependency or non-native control. Fonts need licensed assets/explicit scope;
platform text scaling and control expectations win. The prototype's 44px icon
discs do not establish Android's required 48dp interactive target.

## Conflicts that must not migrate silently

1. **Hidden text:** the canvas foundations say hidden text was compared and marked.
   Current app wording says it was left out, and the pipeline's warning behavior
   must own the truth. Reconcile against parser/report semantics; never copy the
   prototype claim as a fact.
2. **Approval granularity:** historical P0 says approval is per version, never per
   finding; P7 invites recording approval of v2. Current API stores it under
   `/findings/{id}/client-approvals`, with `finding_id`. Keep the current contract
   or explicitly plan a product/data-model change; do not imply version-wide approval.
3. **Approval attachments:** P7 mentions an attached email/document. Current dialog
   accepts pasted evidence text, stated-by and date. Do not promise attachment UI
   without an implemented storage/privacy contract.
4. **Dismissal:** P5 preselects the first reason and says the finding leaves the
   report. Current code stores dismissal as a review and dims the finding in place.
   Reason taxonomy, default selection, next behavior and report filtering need an
   explicit interaction/data contract. Do not relabel a finding as equivalent merely
   because a person dismisses it, and do not invent an unchosen reason.
5. **Withheld findings:** foundations say count-only, while some controls/summary
   wording suggest showing the hidden findings. Preserve counts/explanations and
   permitted differences; do not reveal unverified findings as normal results.
6. **Token consistency:** the Calm Bold overview reserves topic colors for topics,
   but its completion preview uses the bright marker for confirmed count; other
   variants use colored project badges. Reconcile roles in one final system rather
   than importing incompatible variants component-by-component.
7. **Placeholder claims:** example dates, project names, prices, allowances/reset
   dates, progress counts and overnight wording are prototype data. Bind real server/
   store state; do not copy them as product claims.
8. **Dark/accessibility claims:** reference C documents dark and contrast values,
   but says dark is not wired in the app. Reference B specifies pastel behavior in
   dark. Neither proves current Flutter contrast, font scaling or screen-reader behavior.

## Required comparison output from the receiving agent

Produce a short retain/replace/defer table for navigation, compare setup, report
hierarchy, finding/evidence, P5/P7, typography/color, and native adaptation. Name
which artifact/artboard informed each choice. Resolve contract conflicts before
implementing affected controls. Continue using the current owner decisions as
product authority, and record new choices in the agreed design brief.
