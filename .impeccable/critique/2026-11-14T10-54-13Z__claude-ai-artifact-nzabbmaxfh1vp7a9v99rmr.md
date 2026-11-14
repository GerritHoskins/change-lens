---
target: "ChangeLens first-launch canvas https://claude.ai/artifact/NZAbbmaXfh1Vp7A9V99rMr"
total_score: 26
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 4
target_identity: "url:https://claude.ai/artifact/NZAbbmaXfh1Vp7A9V99rMr"
timestamp: 2026-11-14T10-54-13Z
slug: claude-ai-artifact-nzabbmaxfh1vp7a9v99rmr
---
Method: design review only (detector not applicable, native platform). Canvas artboards (HTML mock-ups of the Flutter app) rendered locally at 390x844 in EN, DE and dark; overflow measured in the browser.

## Design Health Score

| # | Heuristic | Score | Key Issue |
|---|-----------|-------|-----------|
| 1 | Visibility of System Status | 3 | Step counter, "Signing in…", resend countdown; no resume state for interrupted onboarding |
| 2 | Match System / Real World | 3 | Plain, product-true copy; dev annotation "link_required.methods = [email_code]…" in screen body (untranslated in DE) |
| 3 | User Control and Freedom | 2 | Skip/Back/replay exist; MFA has no backup-code route; consent promises a Settings screen that doesn't exist |
| 4 | Consistency and Standards | 2 | Calm Bold applied faithfully, but step 3 shows a value headline the real finding screen doesn't have; sheets mix Close/Cancel |
| 5 | Error Prevention | 3 | Disabled Confirm until code complete, cooldown; no invalid-email state |
| 6 | Recognition Rather Than Recall | 3 | Definition sheets and "How ChangeLens works" replay |
| 7 | Flexibility and Efficiency | 3 | Skip on every step, replay; no paste/autofill affordance on the code field |
| 8 | Aesthetic and Minimalist Design | 2 | Steps 2 and 3 each carry two ideas and overflow the screen |
| 9 | Error Recovery | 2 | Good wrong-code message; one generic sign-in error for all failures; MFA dead end |
| 10 | Help and Documentation | 3 | Four in-context definition sheets plus replay |
| **Total** | | **26/40** | **Acceptable** |

## Design Specificity Verdict

Onboarding row is authored for ChangeLens: real topic colours, the earlier/newer slot pattern with the lime newer marker, the ? disc, the verbatim client-approval label; definition sheets reuse in-app strings. Sign-in row is category-generic, which matters because O-22 makes it the first screen.

Deterministic scan: not applicable (native platform).

## Overall Impression

Faithful Calm Bold execution of a truthful script; every claim traces to the feature brief, nothing from the do-not-promise list appears, German is complete. Pacing is the problem: a sign-in wall with no promise, two of five steps that don't fit a phone screen, and an ending on limitations plus a permission ask. Biggest opportunity: let sign-in carry the promise, give each step one idea.

## What's Working

- Truthful copy that reuses product vocabulary.
- Definition sheets pair each in-app label with its consequence.
- Expired session is a sheet over the current screen, matching O-22, with Sign out as the exit.

## Priority Issues

- [P1] Steps 2 and 3 overflow at 390x844: step 3 870px content in 636px (DE 916), step 2 732px (DE 755). The uncertainty example and "? / Needs your review" rule sit below the fold in a nested scroll above a pinned Next. Fix: split step 3 into source and uncertainty; static three-line scope list on step 2; no scroll at 390x844 EN/DE 1x. Commands: /impeccable distill, /impeccable layout.
- [P1] Step 3 example teaches a UI that doesn't exist: "20 Nov → 27 Nov" value headline; real finding shows passages only (app/lib/screens/report_widgets.dart:173; DESIGN.md "extracted value headlines" not built). Fix: draw the real finding anatomy. Command: /impeccable clarify.
- [P1] Sign-in is the first screen but makes no promise ("Sign in to start comparing briefs." over an empty top half). Fix: question, one line, static topic chips above the providers. Command: /impeccable onboard.
- [P1] Dead ends: MFA has no backup-code / try-another-method path (D-8 C1 confirmed backup codes); consent says "change this later in Settings" but no Settings exists and account deletion (I-18, App Store 5.1.1(v)) has no entry. Fix: backup-code link; Settings with usage-events toggle, delete account, sign out. Command: /impeccable harden.
- [P2] Sequence ends on limitations then a consent ask then empty Projects. Fix: compress limits, repeat them in the import sheet; step 5 drives to the first comparison; consent as a sheet on first Projects arrival. Command: /impeccable onboard.

## Persona Red Flags

- Jordan: sign-in wall with no explanation; inert radio rows on step 2; uncertainty rule hidden in step 3's scroll.
- Casey: code field without paste/autofill; nested scroll vs pinned Next on step 3; no resume state.
- Sam: illustrative radios and review rows would be announced as live controls; step counter not progress semantics.
- Mara (freelance designer, revised brief just arrived): sign-in + 5 steps + consent before first comparison; learns scanned-PDF limit only at step 5.

## Minor Observations

- Dev annotation in LinkRequired body, untranslated in DE.
- Canvas note claims three equal sign-in buttons; Apple is filled black, others outlined.
- Wrong-code copy sends typo-makers to request a new code.
- Single generic sign-in error.
- Email entry lacks "we'll email you a 6-digit code" and an invalid-address state.
- Expired-session sheet: no emphasis on last-used method; decorative lime block in background mock.
- Step 5 first run shows both Skip and Continue.
- Selected-summary sheet uses Cancel, others Close.
- Canvas decides consent placement, replay and example content, which handoff §5 reserves for the owner.

## Questions to Consider

- What if the sign-in screen were step 1, with promise and account ask on one screen?
- Would four steps that each fit teach more than five that scroll?
- Should onboarding end inside "Compare two briefs" rather than on a list?
