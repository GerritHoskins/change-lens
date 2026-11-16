---
target: "ChangeLens first-launch canvas, round 2 (private Claude artifact)"
total_score: 35
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 0
target_identity: "artifact:first-launch-canvas"
timestamp: 2026-11-14T12-08-35Z
slug: first-launch-canvas
---
Method: design review only (detector not applicable, native platform). Round 2 re-score of the canvas after handoff §9 fixes. 20 artboards, 30 EN states, rendered locally at 390x844 in EN, DE and dark; overflow and target sizes measured in the browser. Previous run: 26/40 (2026-11-14T10-54-13Z).

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 4 | Step "of 6", loading, cooldown, cancelled line, resume state with role=status |
| 2 | Match System / Real World | 4 | Dev annotation gone; finding card matches report_widgets.dart; replay keeps the title "Before your first comparison" |
| 3 | User Control and Freedom | 4 | Backup code, Settings (switch, sign out, delete), Skip/Back, Close on replay |
| 4 | Consistency and Standards | 3 | Sheets all say Close; step 5's illustrative review rows still look like a tappable list |
| 5 | Error Prevention | 3 | Invalid-email state, delete confirmation; code fields don't specify one-time-code autofill or a numeric keyboard |
| 6 | Recognition Rather Than Recall | 3 | Definition sheets, last-used method; UI labels in body copy ("Show in document", "All differences") aren't marked as labels |
| 7 | Flexibility and Efficiency | 3 | Skip, paste hint; first run is now sign-in + 6 steps + consent before Projects |
| 8 | Aesthetic and Minimalist Design | 3 | One idea per step, no overflow; step 6 is sparse and still reads as a list of constraints |
| 9 | Error Recovery | 4 | Separate network/server errors, wrong vs expired code, quiet cancel, backup code |
| 10 | Help and Documentation | 4 | Four definition sheets plus the import sheet, replay from Projects |
| **Total** | | **35/40** | **Good** |

## Design Specificity Verdict

Both rows are now authored for ChangeLens. Sign-in carries the product question and the six topic chips, so the first screen explains the product. The onboarding example is the real finding card, not an invented headline.

Deterministic scan: not applicable (native platform).

## Overall Impression

All four P1s from round 1 are fixed and measured: 0 px overflow on every artboard and state in EN, DE and dark at 390x844. What's left is polish: one illustration that still looks interactive, a thin last step, and implementation notes for the code fields.

## What's Working

- Sign-in states keep the heading fixed; errors replace the chips instead of pushing buttons off screen.
- Steps 3 and 4 split source and uncertainty cleanly, and both examples use real app anatomy inside an "Example" frame.
- The Settings screen closes the loops from consent (switch) and account deletion (03a P8 wording, AC-22 30-day backups).

## Priority Issues

- [P2] Step 5 illustration still reads as controls. Confirm/Correct/Dismiss sit as icon rows in a white card, like a menu. Screen readers now skip it, but sighted users may tap. Fix: put it inside the same "Example" frame as steps 3 and 4, or render it as the real review bar, scaled. Command: /impeccable clarify.
- [P2] The sequence still ends on constraints. Step 6 shows input type, online-only and English-only, then consent. Fix: lead step 6 with what Start does next ("Next: create a project and compare two briefs"), keep one limits line plus the import link. Command: /impeccable onboard.
- [P3] Code fields (email code, MFA) don't specify one-time-code autofill or a numeric keyboard. Fix: a canvas note for implementation (AutofillHints.oneTimeCode, TextInputType.number). Command: /impeccable harden.

## Persona Red Flags

- Mara (freelance designer, revised brief just arrived): 8 screens before Projects on first run, one more than round 1. Skip on steps 1–5 softens this.
- Jordan: may tap the step 5 review rows.
- Casey: code field autofill depends on implementation; not shown in the design.

## Minor Observations

- Replay variant keeps the title "Before your first comparison".
- Settings: section header "Share usage events" repeats the row title.
- Import sheet icons render at about 12 px and sit above the text baseline.
- UI labels quoted in body copy are plain text; bold or quotes would help users find them later.
- Dark mode: the white Apple button reads as the main action (documented exception, Apple's rule).
- Category "Date or deadline" on the card vs topic chip "Deadlines" is correct (app strings catDate vs topicDeadlines), but the pair may look inconsistent to a first-timer.

## Questions to Consider

- Should step 6 point forward ("Next: your first project") instead of listing what's required?
- Would one "Example" frame style across steps 3–5 make the illustrations unmistakably non-interactive?
