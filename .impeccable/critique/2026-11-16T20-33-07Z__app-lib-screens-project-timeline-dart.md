---
target: History timeline (WP-D)
total_score: 27
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 2
target_identity: "file:C:\\Users\\Gerrit\\job-search\\POCs\\change-lens\\app\\lib\\screens\\project_timeline.dart"
target_fingerprint: "sha256:fdb3f27ee2bbcde658f9118ccb67cc93da06cf44b2dfd870afd04c1b7668425f"
target_path: "C:\\Users\\Gerrit\\job-search\\POCs\\change-lens\\app\\lib\\screens\\project_timeline.dart"
timestamp: 2026-11-16T20-33-07Z
slug: app-lib-screens-project-timeline-dart
---
Method: design review only (detector not applicable, native platform)

Target: History timeline (P6, WP-D) — app/lib/screens/project_timeline.dart inside project_screen.dart.
Evidence: widget renders with bundled Roboto + Lucide at 390 EN light/dark and 320 DE 2× text (synthetic data, not device).

| # | Heuristic | Score | Key Issue |
|---|---|---|---|
| 1 | Visibility of System Status | 3 | Per-card server status; polling refresh is silent |
| 2 | Match System / Real World | 3 | "PDF · Rejected:" with no reason; fork note is long |
| 3 | User Control and Freedom | 3 | Back, pull-to-refresh; nothing destructive here |
| 4 | Consistency and Standards | 3 | Link cards have a chevron, tappable version rows have none |
| 5 | Error Prevention | 3 | Version tap only presets Earlier; nothing irreversible |
| 6 | Recognition Rather Than Recall | 2 | "Tap a version to compare from it" is invisible |
| 7 | Flexibility and Efficiency | 2 | Preset shortcut exists but hidden; no other accelerators |
| 8 | Aesthetic and Minimalist Design | 3 | Clean rail; fork note breaks the rail |
| 9 | Error Recovery | 2 | Failed card / rejected row give no reason or next step |
| 10 | Help and Documentation | 3 | Lead line, empty state and fork note explain the rules |
| Total | | 27/40 | Acceptable |

Priority issues
1. [P1] German at 2× text on 320 px breaks words mid-syllable in link cards ("Vollständige/r", "Fehlgeschla/gen", "Abgeschlosse/n"); rail 20 + gap 12 + fork indent 16 + card padding 30 + chevron 36 leave ~150 px. Fix: at large text scale drop the fork indent and chevron, shrink the rail gutter, or let the card span under the rail. /impeccable adapt
2. [P1] Version rows open Compare with that version as Earlier, but nothing signals it (no chevron, no label, no a11y hint). Fix: visible trailing "Compare from here" affordance or icon + semantics hint. /impeccable clarify
3. [P2] Fork is visually detached from its common parent: the note row (track -1) cuts the rail, so Brief v3 client/agency do not connect down to Brief v2. Fix: place the note above the fork members or continue the rail through it and join both tracks to the parent dot. /impeccable layout
4. [P2] Failure states without reasons: "PDF · Rejected:" renders a dangling colon when rejectReason is null; a Failed card says only "Failed". Fix: a no-reason variant of statusRejected; show the reason label on the card when known. /impeccable harden
5. [P2] "→" (U+2192) is not in the bundled Roboto files; on device it falls back to a system font, in captures it renders as tofu. Fix: draw the arrow as a Lucide icon in a WidgetSpan, or add the glyph to the bundled subset. /impeccable typeset

Personas
- Jordan (first-timer): sees versions as static rows; never discovers compare-from-here. Fork note reads as a warning.
- Sam (screen reader): good per-tile labels; version tile lacks a hint that activation opens Compare; rail and arrows correctly excluded.
- Mara (freelancer checking a client brief, project-specific): "Failed" with no reason forces opening the card to learn whether the client file is unusable.

Minor
- Project title in CalmPageHeader also breaks mid-word in DE 2× ("Northwi/nd") — outside the target.
- "Not compared yet" rows use dividers, placed rows do not; acceptable but slightly inconsistent.
- Status line in bold ink ("Processing", "Complete") competes with the pair label; only Failed/Partial need emphasis.

Questions
- Should a version row say what tapping it does, or should tapping a version do nothing at all?
- Does the fork need a note, or would a joined rail make the note redundant?
