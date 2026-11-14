# Onboarding 24 px margin: implementation handoff

Prepared 2026-11-14 for the implementing agent. Repository:
`C:\Users\Gerrit\job-search\POCs\change-lens`, branch `m1-iphone`. Baseline: the commit that adds this
file, on top of `fc7bf38`. Check `git status` and HEAD first.

The untracked tool folders (`.claude-flow/`, `app/.claude-flow/`, `.playwright-mcp/`, `.claude/`) and
the older critique snapshot aren't yours: leave them alone.

> **Line endings.** The repo stores LF. A Windows checkout has CRLF. A git without `core.autocrlf` (for
> example a Linux shell over the Windows folder) lists about 400 "modified" files that have no content
> change (`git diff --ignore-cr-at-eol` is empty). Never stage those. Add only the paths named below.

## 1. Goal

After round 4 (`c33bee7`) no onboarding step scrolls. But the tightest spare room at 390×844 and text
scale 1.0 is **13 px**, against the design's 24 px margin:
- step 3 on iOS, in EN and DE;
- step 5 on iOS, in DE.

Design round 5 shortened three strings by one line each at the iOS 17 px body. Apply them, and make
the margin a test assertion so it can't erode again.

## 2. Changes to apply

The source of truth is `docs/onboarding/onboarding_en.arb` and `onboarding_de.arb`. Old and new text,
and the line measurements, are in `docs/onboarding/direction.md` §11.

| Key | Locale | Change |
|---|---|---|
| `onbEvidenceBody` | EN | 5 → 4 lines (step 3) |
| `onbEvidenceBody` | DE | 5 → 4 lines (step 3) |
| `onbReviewApproval` | DE | 3 → 2 lines (step 5) |

1. **Strings.** Copy those three values into `app/lib/l10n/app_en.arb` and `app_de.arb`. Don't change any
   other key, and keep the `@` metadata. Run `flutter gen-l10n`.
2. **Test.** Turn the margin into an assertion in `app/test/onboarding_test.dart`, `tearDownAll`. Today it
   only fails when a step scrolls. Keep that check, and add one that every key in `spare` (390×844, 1.0,
   EN and DE, iOS and Android, first run and replay) is **at least 24 px**, with the key and the value in
   the failure reason. Name the constant `minSpare = 24.0`, with a comment pointing to design handoff
   §11.2 and `direction.md` §11.
3. **Nothing else.** Same type, line heights, spacing, layout, widgets and step count. Don't shrink
   anything to make it fit.

## 3. If a step still has less than 24 px

Don't edit copy yourself. Copy is a design decision. Report it as a blocker instead: each failing step,
locale, platform and spare value, plus the test's printed "least spare room" list.

One pre-measured option is already recorded in `direction.md` §10 for step 2: the new key `onbContextBody`,
which replaces `confirmIntro` on step 2 only. It's an owner trade-off, so mention it only if step 2 is the
one failing.

## 4. Gates

- `flutter gen-l10n` produces no untranslated keys.
- `flutter analyze` reports no issues.
- The full `flutter test` suite passes. Report the counts before and after.
- The printed line from `onboarding_test.dart` shows no overflow, and the least spare room is 24 px or more.
- `git status --short` (Windows git, or `git diff --ignore-cr-at-eol --stat`) lists only:
  `app/lib/l10n/app_en.arb`, `app_de.arb`, the three generated `app_localizations*.dart` files, and
  `app/test/onboarding_test.dart`.
- No dependency, pubspec, backend or docs changes. Commit only if the owner asks in your session. Never push.

## 5. What to return

- The diff stat.
- The test's printed no-scroll line (overflow and the four tightest spare values).
- The analyze summary and the test counts.
- Any blocker from §3, with exact values.

## 6. Receiving-agent prompt

> Work in the ChangeLens checkout on `m1-iphone`. Verify `git status` and HEAD, and ignore line-ending-only
> changes. Read `docs/onboarding-margin-handoff.md` and `docs/onboarding/direction.md` §11. Copy the three
> changed onboarding strings from `docs/onboarding/*.arb` into `app/lib/l10n/`, run `flutter gen-l10n`, and add
> a 24 px minimum-spare assertion to `app/test/onboarding_test.dart`. Change nothing else, and never edit copy
> yourself: report any step under 24 px as a blocker. Run `flutter analyze` and `flutter test`. Return the diff
> stat, the printed no-scroll line, the gate results, and any blocker. Commit only if the owner asks. Never push.
