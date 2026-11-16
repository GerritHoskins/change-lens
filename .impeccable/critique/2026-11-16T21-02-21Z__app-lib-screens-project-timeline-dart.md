---
target: History timeline (after fixes)
total_score: 29
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 0
target_identity: "file:C:\\Users\\Gerrit\\job-search\\POCs\\change-lens\\app\\lib\\screens\\project_timeline.dart"
target_fingerprint: "sha256:c81fc6fa112df4ac6bc7cda115c6082be762cb44a6c49589778bbc4eb0fd02af"
target_path: "C:\\Users\\Gerrit\\job-search\\POCs\\change-lens\\app\\lib\\screens\\project_timeline.dart"
timestamp: 2026-11-16T21-02-21Z
slug: app-lib-screens-project-timeline-dart
---
Method: design review only (detector not applicable, native platform)

Target: History timeline after the five fixes. Evidence: real-font widget renders at 390 EN light/dark and 320 DE 2× (synthetic data, not device).

| # | Heuristic | Score | Key Issue |
|---|---|---|---|
| 1 | Visibility of System Status | 3 | Card statuses refresh every 3 s but changes are not announced |
| 2 | Match System / Real World | 3 | Plain copy; fork note runs six lines in German at 2× |
| 3 | User Control and Freedom | 3 | Back, refresh; nothing destructive |
| 4 | Consistency and Standards | 3 | Rail arrow points up, pair arrow points right |
| 5 | Error Prevention | 3 | Rejected versions no longer offer a comparison |
| 6 | Recognition Rather Than Recall | 3 | "Compare from here" now visible |
| 7 | Flexibility and Efficiency | 2 | No path from a failed card to retrying |
| 8 | Aesthetic and Minimalist Design | 3 | Six identical bold "Compare from here" lines |
| 9 | Error Recovery | 3 | Reasons and next step shown; recovery still manual |
| 10 | Help and Documentation | 3 | Lead, notes and empty state explain the rules |
| Total | | 29/40 | Good |

Priority issues
1. [P2] "Compare from here" repeats on every row in bold ink and competes with the version names; on a 6-version project it is the loudest repeated element. Fix: render it in muted labelMedium (regular weight), keep the icon ink. /impeccable quieter
2. [P2] A failed card says "Start a new comparison to try again" but offers no way to do it; the user must go back up to Compare and re-pick both versions. Fix: on a failed card whose inputs are both readable, a "Compare again" text button opening Compare with the same pair preset (no scope preset). /impeccable clarify
3. [P2] Status changes from polling (Processing → Complete/Failed) are silent for screen readers. Fix: announce a card's status change once via calmAnnounce when it moves to a finished state. /impeccable harden
4. [P3] Two arrow directions: the rail's up arrow means "newer above", the pair's right arrow means "earlier → newer". Fix: drop the rail arrow; the card copy carries direction. /impeccable distill

Personas
- Sam (screen reader): hears nothing when a running comparison finishes while on the project.
- Mara (freelancer): sees why a comparison failed but has to rebuild it by hand.
- Jordan: the repeated bold action reads as a list of buttons rather than a history.

Minor
- Fork note is long in German at 2× (six lines).
- Page header title breaks mid-word in German at 2× (shared header, outside target).

Questions
- Does every version need a visible action, or only the newest of each branch?
