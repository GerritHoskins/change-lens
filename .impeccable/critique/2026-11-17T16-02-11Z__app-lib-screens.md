---
target: Whole app, screen by screen
total_score: 28
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 2
target_identity: "file:C:\\Users\\Gerrit\\job-search\\POCs\\change-lens\\app\\lib\\screens"
timestamp: 2026-11-17T16-02-11Z
slug: app-lib-screens
---
Method: design review only (detector not applicable, native platform)

Target: all app screens after WP-A to WP-F (commit e9e1716). Evidence: real-font widget renders of projects, project, compare, status, report, finding, review summary, onboarding, sign-in, settings and consent at 390 EN light (some dark) and 320 DE 2× (Cedar fixture data; not device).

| # | Heuristic | Score | Key Issue |
|---|---|---|---|
| 1 | Visibility of System Status | 3 | Honest status headlines and review counts |
| 2 | Match System / Real World | 3 | "Selected summary", "Text fallback", project row "(1)" |
| 3 | User Control and Freedom | 3 | Back everywhere, Cancel in sheets, gated destructive actions |
| 4 | Consistency and Standards | 3 | Calm components now used throughout; "Partial" means two things |
| 5 | Error Prevention | 3 | Disabled Start with reason, delete confirmations |
| 6 | Recognition Rather Than Recall | 3 | Timeline presets Earlier; topic chips |
| 7 | Flexibility and Efficiency | 2 | Few accelerators; needs-review count not a shortcut |
| 8 | Aesthetic and Minimalist Design | 3 | Zero-count chips; finding header says the topic twice |
| 9 | Error Recovery | 2 | Raw exception text in 8 places across 5 screens |
| 10 | Help and Documentation | 3 | Info buttons, onboarding, explicit approval copy |
| Total | | 28/40 | Good |

Priority issues
1. [P1] German at 2× text breaks headings mid-word: "Was sich geä/ndert hat" (report H1), "Kundenfreigab/e" (finding section), "Ausgewählte Zusa/mmenfassung", "Darstellung/sänderungen". Fix: shrink headline styles to fit the longest word at large scale (measure, scale down to a floor), shared in CalmPageHeader and section headings. /impeccable adapt
2. [P1] Raw exception text reaches users: error = '$e' in projects_screen.dart:73/97, project_screen.dart:71/158, report_screen.dart:56, finding_screen.dart:94/114/135; ApiException prints "code (detail)", transport errors print SocketException text. Fix: one mapper from exception to localized message (connection, sign-in expired, not found, server) with Retry. /impeccable harden
3. [P2] "Partial" means two things side by side: scope "Partial update" vs status "Partial: some content could not be processed" (project card, status headline, report). Fix: status copy "Some content couldn't be read" without the "Partial:" prefix. /impeccable clarify
4. [P2] The finding that most needs attention comes last: report lists certain changes first; the uncertain one sits below them, and "Needs your review · 1" near the top is not a link. Fix: make the count jump to the section, or place Needs your review first. /impeccable layout
5. [P2] Noise in the report header: zero-count chips ("Deliverables (0)") offer empty filters; "Selected summary — 1 other difference, including presentation-only edits" is jargon in bold. Fix: hide or disable zero chips; reword to "Also 1 smaller difference (layout or wording)" with All differences link. /impeccable distill

Personas
- Mara (freelancer): sees "Partial update" and "Partial: …" together and can't tell whether the brief or the processing was partial.
- Sam (screen reader, large text): German headings read fine but look broken at 2×; error snackbars read raw codes.
- Casey (one-handed): main Compare action sits at the top on Projects and Project; Finding and Summary pin theirs at the bottom.

Minor
- Finding: H1 "Budget" then "Changed · Budget" repeats the topic; "Your review" status line indented 24 px vs 20.
- Projects row "(1)" after the status has no label.
- Settings Privacy switch shows disabled with no reason while consent is gated.
- Apple button label and debug banner in captures are test artifacts.

Questions
- Should the report open on what needs your review, then everything else?
