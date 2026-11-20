---
target: Sign-in (native) and Logto hosted pages, after the iPhone session of 2026-11-20
total_score: 28
max_score: 40
na_heuristics: 
p0_count: 1
p1_count: 1
target_identity: "file:C:\\Users\\Gerrit\\job-search\\POCs\\change-lens\\app\\lib\\screens\\sign_in_screen.dart"
timestamp: 2026-11-20T16-50-00Z
slug: sign-in-and-logto
---
Method: design review only (detector not applicable, native platform). The impeccable skill was not installed in
the session that wrote this; the format follows the earlier files in this folder.

Target: `sign_in_screen.dart` with the provider-button and tracking fixes of 2026-11-20, and Logto's hosted
code/MFA page with `deploy/ionos/logto/` as written. Evidence: two iPhone screenshots taken **before** the fixes
(sign-in 10:22, Logto 2-step verification 17:10), the Dart source, Logto 1.45.0 source (`packages/experience`).
**No render after the fixes: Flutter tests were not run (no SDK in the session), and the Logto branding is not
applied to any server.** Scores are for the code as written; re-score from a device.

| # | Heuristic | Score | Key Issue |
|---|---|---|---|
| 1 | Visibility of System Status | 3 | Signing in is announced and shown in the button; Logto submits the code on the sixth digit with no visible "checking" state of our own |
| 2 | Match System / Real World | 3 | Logto's default copy was on screen ("2-step verification", formal German); the overrides exist but were never applied |
| 3 | User Control and Freedom | 3 | Browser sheet close and Logto's back arrow both leave; cancel is announced, no banner |
| 4 | Consistency and Standards | 2 | Apple has its logo, Google has none; Logto code boxes keep 8 px corners beside 18 px fields; hosted page language can differ from the app's |
| 5 | Error Prevention | 3 | One method at a time; the others disable while one runs |
| 6 | Recognition Rather Than Recall | 3 | The expired-session sheet offers the last method first |
| 7 | Flexibility and Efficiency | 3 | Code auto-submits; one-time-code autofill is Logto's |
| 8 | Aesthetic and Minimalist Design | 3 | Six topic pills look tappable and aren't; Logto shows a Continue button that the auto-submit makes redundant |
| 9 | Error Recovery | 3 | Plain messages, error replaces the chips so buttons don't move |
| 10 | Help and Documentation | 2 | No path for a lost authenticator beyond "Try another method" |
| Total | | 28/40 | Good, with one open P0 on the server |

Priority issues

- **P0 · Live Logto pages use the marker lime as brand colour.** White label on `#DFFF4F` is 1.13:1, the lime link
  on white is 1.13:1, the focused code box is not visible. Nothing from the branding plan was applied: white
  background (not ground), 8 px button (not the pill), Logto's own copy and no logo. Fix is in the repository
  (`deploy/ionos/logto/sign-in-experience.json`: `primaryColor #111114`; `custom.css`; `scripts/logto/apply-branding.py`)
  and **open until `--apply` runs on the cube**.
- **Resolved 2026-11-20 (owner) · Apple button style.** All three methods use Apple's allowed styles: white with
  an ink outline on light, plain white on dark, ink content, Apple's logo on Apple. New P3: on the dark theme three
  white pills are the brightest things on the screen, where Calm Bold otherwise keeps one bright action.
- **P1 · Google button has no "G".** Google's sign-in branding asks for it; with Apple's logo now present the gap
  is visible. Bundle the official asset.
- **P2 · Topic pills read as filters.** Same shape and colour as the tappable topic chips elsewhere, here static.
  Either smaller, non-pill blocks or drop the pill radius on this screen.
- **P2 · `ui_locales` is not sent** (`auth/logto.dart`), so a German app on an English-language browser opens
  English Logto pages (plan §4.6).
- **P2 · Body and label tracking.** `role()` passed a null `letterSpacing`, so Material's per-role tracking
  (0.1 to 0.5 px) applied to body, labels and chips app-wide; visible in the 10:22 screenshot. Fixed to 0 on
  2026-11-20; unverified on the layout matrix.

P3 polish (not change requests)
- Logto's secondary titles (code, MFA) get the 32 px bold headline through the variable but not the -1 px tracking.
- Disabled main button label is 2.68:1 (`disabled-text` on `disabled`), light and dark alike. Exempt under WCAG,
  still hard to read next to the line that says what is missing.
- "Powered by Logto" stays (licence), in Logto's grey.
