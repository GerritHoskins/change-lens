---
target: ChangeLens app UI/UX overhaul handoff
total_score: 20
max_score: 40
na_heuristics: ""
p0_count: 0
p1_count: 4
target_identity: "file:C:\\Users\\Gerrit\\job-search\\POCs\\change-lens\\app\\lib\\main.dart"
target_fingerprint: "sha256:1b0a1780a595a81acb2ebecb32e5f4cb511c999cdffe452270c70eb4b6f97408"
target_path: "C:\\Users\\Gerrit\\job-search\\POCs\\change-lens\\app\\lib\\main.dart"
timestamp: 2026-11-07T15-30-15Z
slug: app-lib-main-dart
---
Method: design review only (detector not applicable, native platform).

# ChangeLens design critique — 2026-11-07

Target: `app/lib/main.dart` and its app screens at
`0031578787fcb24556c5d8292d2aaea5ec6e42ec`. Mode: Operate.
Source review plus eight offline renders of production Flutter widgets with
synthetic fixtures. No native-device validation or actual screen-reader session.

## Design specificity verdict

The interface is a coherent Material development shell, but not yet authored around
the freelancer's comparison-and-review task. Stock indigo, repeated cards, generic
Report/Finding headings, and setup-oriented first run dominate. Product-specific
meaning exists in source/uncertainty/review rules; make those the interface's structure.
Automated web detector: not applicable (native platform). No browser overlay.

## Design health score

| Heuristic | Score / 4 | Key issue |
| --- | ---: | --- |
| Visibility of system status | 2 | Comparisons poll; imported versions need manual refresh |
| Match system and real world | 2 | Clear labels undermined by partial-update reconfirmation wording |
| User control and freedom | 2 | Cancel/back exist; failed imports lose entered drafts |
| Consistency and standards | 3 | Standard Material components provide a consistent baseline |
| Error prevention | 3 | Explicit scope/order and distinct versions are strong safeguards |
| Recognition rather than recall | 2 | Pair context and evidence navigation affordances are weak |
| Flexibility and efficiency | 1 | Import, waiting, setup, status, report and repeated review fragmented |
| Aesthetic and minimalist design | 2 | Warnings and summary link dominate partial-report first viewport |
| Error recovery | 1 | Raw codes, no local retry, settings-save failure |
| Help and documentation | 2 | Helpful scope hints; developer-oriented first run |
| **Total** | **20/40** | **Acceptable; significant work remains** |

Scores are reviewer judgments based on this baseline, not measured user-research
results. All ten heuristics apply.

## Overall impression

Make starting a comparison and reviewing its evidence one coherent task. Preserve
the safeguards while replacing the presentation and reducing navigation overhead.

## What works

- Explicit earlier/newer/scope choices prevent accidental comparisons (AC-14).
- Personal review and external client approval are separate, labelled states (AC-12).
- Withheld counts, uncertainties, unexplained and presentation-only differences
  remain reachable (AC-10/13/18).

## Priority issues

### C1 — P1: fragmented comparison setup

`project_screen.dart:132–163` requires two parsed versions before opening the
separate `confirm_screen.dart`. Users must import, wait/refresh, select the pair,
start, and open the report. Apply O-15/I-24/I-25: a two-slot compare screen with
inline import, explicit scope/project, automatic status and resumable waiting.
Backend waiting/idempotency/allowance contracts must exist; a visual spinner is
not an implementation. Suggested command: `shape`.

### C2 — P1: partial-update copy implies reconfirmation

`app/lib/l10n/app_en.arb:68`: "Changes some items; everything else still stands."
This contradicts AC-3's not-addressed meaning and can mislead a delivery decision.
Explain that unmentioned items are not addressed by this update; do not infer
continuing agreement. Suggested command: `clarify`.

### C3 — P1: evidence limitations arrive after the review decision

`finding_screen.dart:129–140` offers Confirm before trying PDF placement; fallback
appears only in `evidence_screen.dart`. Apply O-17: determine placement per side,
show and announce fallback above Confirm, record content-free evidence mode,
and keep needs-review items on screen after confirmation. Suggested commands:
`harden`, `adapt`.

### C4 — P1: failed actions are expensive to recover

`project_screen.dart:81–107` closes import before upload and loses the editable
draft on failure. Empty form submissions lack field feedback. Report/finding/
evidence failures lack Retry. Separately, saving Developer settings reproduces
a late-final-controller error (`projects_screen.dart:135`). Keep drafts in memory,
map errors to clear localized recovery, and repair settings lifecycle handling.
Suggested command: `harden`.

### C5 — P2: report hierarchy is driven by notices, not the task

`report_screen.dart:63–90`: in the 390x844 partial/hidden/withheld fixture, three
similar banners plus the summary card occupy over half the viewport. Findings
lack prominent source-pair context and the approved topic structure. Consolidate
limitations with severity/counts and disclosure, retain explicit partial status,
and introduce topics independently of uncertainty. Make evidence navigation
explicit (`QuoteCard`, `report_widgets.dart:39`). Suggested command: `layout`.

## Persona red flags

- First-time user: developer configuration replaces product onboarding; no immediate
  "compare two briefs" entry. Scope hints contain a misleading assurance.
- Busy freelancer: version readiness needs manual refresh; report/review navigation
  repeats and no next-finding behavior exists yet.
- Screen-reader user: meaningful status changes lack deliberate announcements;
  highlights lack explicit nonvisual location descriptions. Existing Flutter
  controls have semantics; the whole app is not being declared inaccessible.

## Minor observations

- Offscreen 320x568/2x-text confirmation and finding renders had no initial-viewport
  render exceptions, but content extends below the capture; whole-flow behavior
  remains untested and narrow dropdown labels become less informative.
- System typography and wrapped actions are useful foundations.
- Screens mounted as home omit back arrows; this is a harness artifact. The debug
  ribbon and synthetic fixture explanations are not product design defects.
- No dark theme is defined; current indigo is evidence, not a binding brand choice.

## Questions considered

1. Prioritize faster comparison/review, visual identity, or both equally?
2. Replace stock Material visual language or preserve it?
3. Does the older screen canvas remain binding?

Owner answers, 2026-11-07: prioritize faster, clearer comparison/evidence review;
allow a fresh visual language while retaining ChangeLens and safeguards; let the
receiving agent decide after comparing the older canvas and this brief. Future
landing/showcase workflow default remains unset; native app work is code-first.

No design implementation was authorized in this handoff task.
