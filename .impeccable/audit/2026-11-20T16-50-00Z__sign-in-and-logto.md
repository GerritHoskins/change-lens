---
target: Sign-in (native) and Logto hosted pages, after the iPhone session of 2026-11-20
total_score: 15
max_score: 20
target_identity: "file:C:\\Users\\Gerrit\\job-search\\POCs\\change-lens\\app\\lib\\design\\calm_actions.dart"
timestamp: 2026-11-20T16-50-00Z
slug: sign-in-and-logto
---
Method: code audit, same caveats as the critique of this timestamp: impeccable skill not installed, no Flutter
test run, Logto branding not applied to a server. Files: `app/lib/design/calm_actions.dart`, `calm_theme.dart`,
`app/lib/screens/sign_in_screen.dart`, `deploy/ionos/logto/*`, `deploy/ionos/Caddyfile`, `scripts/logto/apply-branding.py`.

| Dimension | Score | Finding |
|---|---|---|
| Accessibility | 3 | Apple is now a real `OutlinedButton` (was a hand-built `Semantics` + `IgnorePointer` + `Opacity` wrapper); logo scales with text size and is not announced. Logto: focus on code boxes 2 px ink (5.2:1 against the 1 px border). Open: disabled label 2.68:1 |
| Performance | 3 | Three Roboto WOFF2 files at about 70 KB each, unsubsetted (212 KB for a page that shows a few dozen glyphs); `font-display: swap`, cached one day. A Latin subset would be about a quarter |
| Responsive | 3 | Provider row is `Row(min) + Flexible`, wraps at large text like the progress row. Not run at 320 px or 200 % since the change |
| Theming | 3 | `custom.css` repeats 20 token hex values by hand; nothing checks them against `calm_theme.dart`. Dark `--color-static-white` override is needed by Logto's button and now paired with a light toast |
| Anti-patterns | 3 | Three FRAGILE CSS-module selectors (`_headline`, `_primary`/`_secondary`, `_passcode`) tied to Logto 1.45 class names; guarded only by a manual check in the runbook |
| Total | 15/20 | |

Findings by severity

- **High · Not verified by a run.** `flutter analyze` and `flutter test` were not run after: the `CalmProviderButton`
  rewrite, the new test in `session_settings_test.dart`, and `letterSpacing: tracking ?? 0` (app-wide; text gets
  narrower, so line breaks can move in the layout matrix).
- **High · Server state is hand-set.** The lime brand colour can only have come from the Console. Until
  `apply-branding.py --apply` has run and the README step is followed, the repository does not describe the server.
- **Resolved 2026-11-20 · Two copies of the Logto files.** `docs/logto-branding/` removed; `deploy/ionos/logto/`
  is the only copy.
- **Medium · No token check.** A test that reads `custom.css` and `calm_theme.dart` and compares the hex values
  would stop drift; `scripts/release/check_config.py` is the natural home.
- **Medium · `apply-branding.py` has no test.** `--check` covers the files; the HTTP path was never exercised,
  not even against `scripts/d8-logto`.
- **Low · Fonts unsubsetted**, see Performance.
- **Low · `handle_path` strips the prefix**, so `brand/` must stay flat under `/changelens-brand/`; a file named
  like a Logto route cannot collide, but the folder is world-readable: keep only public assets in it.
