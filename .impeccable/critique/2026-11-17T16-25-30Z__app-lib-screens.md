---
target: Whole app, loop iteration 2
total_score: 31
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 0
target_identity: "file:C:\\Users\\Gerrit\\job-search\\POCs\\change-lens\\app\\lib\\screens"
timestamp: 2026-11-17T16-25-30Z
slug: app-lib-screens
---
Method: design review only (detector not applicable, native platform). Loop run (/loop): iteration 2, stop condition "no P0-P2 change requests".

Target: all app screens after 303616c plus the History timeline fixes (quiet "Compare from here", Compare again on failed cards, announcement when a comparison finishes, no rail arrows). Evidence: real-font renders, 390 EN light/dark and 320 DE 2x; 285 Flutter tests.

| # | Heuristic | Score | Key Issue |
|---|---|---|---|
| 1 | Visibility of System Status | 4 | Status headlines, review counts, finished comparisons announced |
| 2 | Match System / Real World | 3 | Failed card says "start a new comparison" beside a Compare again button |
| 3 | User Control and Freedom | 3 | Back, Cancel, confirmations |
| 4 | Consistency and Standards | 3 | Main action on top for Projects/Project, pinned elsewhere (documented choice) |
| 5 | Error Prevention | 3 | Rejected versions offer no comparison; scope never preset |
| 6 | Recognition Rather Than Recall | 3 | Presets from history and failed pairs |
| 7 | Flexibility and Efficiency | 3 | Compare from here, Compare again |
| 8 | Aesthetic and Minimalist Design | 3 | Finding title and change label both name the topic |
| 9 | Error Recovery | 3 | Plain messages with Retry; limits named |
| 10 | Help and Documentation | 3 | Info sheets, onboarding |
| Total | | 31/40 | Good |

Priority issues: none at P0-P2.

P3 polish (not change requests)
- Failed card: the generic "Start a new comparison to try again" sits next to Compare again.
- Finding: H1 topic ("Budget") and "Changed · Budget" repeat when category and topic share a name.
- Projects/Project keep Compare at the top while Finding/Summary pin theirs (DESIGN.md choice).
