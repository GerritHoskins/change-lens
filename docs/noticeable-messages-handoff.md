# ChangeLens · Implementation handoff: noticeable messages (error, warning, info)

Nov 21, 2026 · @Gerrit

## Summary

The code for noticeable messages is written but has never been compiled or run. Your job is to verify it, fix what the first run finds, check it on a device, and bring the remaining surfaces in line.

- **Decision (owner, 2026-11-21):** user-facing error, warning and info messages must be more noticeable, with red for errors.
- **Design:** three message kinds, each with its own colour and its own icon. Error is red with a circled "!", warning is amber with a triangle, info is the existing link blue with a circled "i".
- **State:** the change sits uncommitted in the working tree on `m1-iphone`, on top of `5cd6afe`. The Calm Bold design system page and `DESIGN.md` already describe it.
- **Not done:** `flutter analyze`, `flutter test`, any render, any device check, the Logto error colour, the canvas artboards.

## Before you start

Repository `C:\Users\Gerrit\job-search\POCs\change-lens`, branch `m1-iphone`, HEAD `5cd6afe` when this was written. Check `git status` and HEAD first; the branch moves.

- **Line endings.** In a Linux shell over the Windows checkout, many files show as modified with no content change. Compare with `git -c core.autocrlf=true diff --stat` and stage with the same flag. Never stage a line-ending-only change.
- **Three modified files are not part of this work:** `deploy/ionos/README.md`, `deploy/ionos/logto/custom.css` and `docs/logto-branding-plan.md` carry the owner's own uncommitted edits. Don't revert, restage or reformat them.
- **Untracked `.claude/`** is a tool folder. Leave it.
- **No commit or push unless the owner says so.** Make surgical edits; change only what a step names.
- **Read first:** `DESIGN.md`, section "Semantic color tokens", paragraph "Messages (changed 2026-11-21)". It is the rule this work implements. The same rule is on the [Calm Bold design system page](https://claude.ai/artifact/V9325dymoruEtTngXEULo5) (README, Colour; FallbackBanner card).
- **Copy rules still hold:** no exclamation marks, no emoji, sentence case, never claim approval. This work changes how messages look, not what they say.

## The design

Every message has one of three kinds. A kind is always shown by colour and icon together, never by colour alone.

| Kind | Accent, light / dark | Surface, light / dark | Icon | Used for |
| --- | --- | --- | --- | --- |
| Error | `#C81E1E` / `#FF8A8A` | `#FDECEC` / `#3A1D1D` | circled "!" (`CalmIcons.error`) | A failed load, save, sign-in, consent or account deletion |
| Warning | `#8A5300` / `#FFC857` | `#FFF3D6` / `#33290F` | triangle (`CalmIcons.warning`) | The text-fallback banner, report processing warnings, a choice that can't proceed, the Partial status |
| Info | `#4B3BFF` / `#A99FFF` (the `link` token) | `#ECEBFF` / `#25234A` | circled "i" (`CalmIcons.info`) | A notice, such as "You're signed out." |

- **Banner (`CalmWarning`):** the kind's surface, a 2 px solid border and a 20 px icon in the accent, text in ink. Ink reads at 12.9:1 or more on every surface. Always solid; dashed stays reserved for "needs a second look".
- **Snackbar (`calmSnack`):** error and warning fill with the accent and carry the icon; the label is white on light and ink on dark (5.7:1 or more). Info keeps the ink snackbar and gains the icon.
- **Inline status text:** "Failed" uses the error colour, "Partial" uses the warning colour, both with their words.
- **Full-screen load error (`CalmLoadError`):** a 28 px error icon above the centred text and Retry.
- **The `error` token changed app-wide** from orange-red `#C4320A` / `#FF8A65` to a true red, so it can't be read as `review` orange (`#F05A1E`). Lowest text contrast is now error on ground, 5.25:1.
- **Amber is new.** It must never be dashed, never fill a topic block, and its surface is paler than the Budget topic yellow (`#FFE45C`).

## What is already in the working tree

Thirteen app and doc files are changed and one test file is new. None of it has been compiled.

| File | Change |
| --- | --- |
| `app/lib/design/calm_theme.dart` | `CalmColors` gains `errorLight`, `errorDark` and the getters `error`, `errorSurface`, `caution`, `cautionSurface`, `infoSurface`. The colour scheme's `error` now reads `colors.error`. The old `warning` and `warningSurface` fields (ink and surface) are untouched |
| `app/lib/design/calm_icons.dart` | New `CalmIcons.error` (`LucideIcons500.circleAlert`) and `CalmIcons.warning` (`LucideIcons500.triangleAlert`) |
| `app/lib/design/calm_widgets.dart` | New `CalmMessageKind` enum and `calmMessageLook()`. `CalmWarning` takes `kind` (default `error`) and draws surface, border, icon and ink text. New `calmSnack()`. `CalmLoadError` shows the error icon |
| `app/lib/screens/compare_screen.dart` | "Same version" banner is `warning` |
| `app/lib/screens/evidence_screen.dart` | Both fallback banners are `warning`; the load-failure snackbar uses `calmSnack` with `error` |
| `app/lib/screens/finding_screen.dart` | Review-fallback banner is `warning`; "finding changed" snackbar is `warning`; "save failed" snackbar is `error` |
| `app/lib/screens/report_screen.dart` | Processing-warnings banner is `warning` |
| `app/lib/screens/projects_screen.dart` | "Project deleted" snackbar uses `calmSnack` (info) |
| `app/lib/screens/sign_in_screen.dart` | The sign-out notice is a `CalmWarning` of kind `info` (was a soft `CalmCard`); key `sign-in-notice` kept |
| `app/lib/screens/definition_sheets.dart` | The text-fallback sample uses the amber surface and border |
| `app/lib/screens/project_timeline.dart` | Partial status text uses `colors.caution` |
| `app/test/projects_home_test.dart` | The hard-coded old error colour is replaced with `CalmColors.errorLight` |
| `app/test/calm_message_test.dart` (new) | Each kind's surface, border, icon and ink text in both themes; an error snackbar's fill and icon |
| `DESIGN.md` | Token table rows for error, warning and info surfaces; the "Messages" paragraph; the contrast floor |

Outside the repository, the [Calm Bold design system](https://claude.ai/artifact/V9325dymoruEtTngXEULo5) already has the tokens `error-surface`, `warning`, `warning-surface` and `info-surface`, the new `error` values, the rule in its README, and the three banner kinds on the FallbackBanner card.

## Work to do, in order

1. **Compile.** Run `flutter analyze --no-pub` in `app/`. Known risks:
   - `LucideIcons500.circleAlert` and `LucideIcons500.triangleAlert` were not checked against the pinned `lucide_icons_flutter` version. If either name is missing, pick that version's equivalent (older releases call them `alertCircle` and `alertTriangle`) and keep the `CalmIcons` names.
   - `colors` and `text` locals in `sign_in_screen.dart` may now be partly unused after the notice changed widget.
   - `calm_message_test.dart` destructures records in a `for` over `MapEntry`; simplify it if the analyzer objects.
2. **Test.** Run `flutter test` in `app/`. Expect failures only where a test asserts the old look: a banner's border or text colour, a snackbar found by type, or the sign-in notice as a `CalmCard`. Update the assertion to the new rule; don't change the widget to satisfy an old test.
3. **Layout matrix.** The banner now has an icon column (20 px + 12 px gap), so its text wraps 32 px earlier. Run the existing layout tests at 320 px width, German, and the largest text size. The pinned fallback banner above Confirm on the Finding screen is the tightest case.
4. **Review the classification** against the table in the next section. Anything not marked there is drawn as an error by default.
5. **Snackbars in dark mode.** Check that an error and a warning snackbar are readable on the dark theme (ink label on a light accent) and that the info snackbar's icon is visible on the ink fill.
6. **Logto hosted pages.** `deploy/ionos/logto/custom.css` still sets `--color-danger-default` to the old `#C4320A` (light) and `#FF8A65` (dark). Change them to `#C81E1E` and `#FF8A8A`. The file has the owner's uncommitted edits: ask before touching it, then change only those two values.
7. **Design system note.** In the Calm Bold design system, the `error` token's usage note may still quote the old contrast figure. Correct it to 5.7:1 on surface and 5.25:1 on ground (light), 7.3:1 on surface (dark).
8. **Canvases.** The artboards still draw the old ink-bordered banner. Update the fallback banner on "Calm Bold · Screen P4" (v1 screens) and the error and notice states on the sign-in artboard (first-launch canvas) to the new kinds, and refresh that canvas's copy of the design-system tokens. Do this after the device check, so the canvases record what shipped.
9. **Device check.** On the iPhone and the Fairphone, light and dark, trigger one of each: an error banner (sign-in with the network off), a warning banner (a finding with text fallback), the info notice (sign out), an error snackbar (save a review action offline). Screenshot each.

## Classification to review

Every message surface and the kind it now has. Line numbers are as of `5cd6afe` plus the working tree. A wrong kind is a one-word change at the call site.

| Where | Message | Kind |
| --- | --- | --- |
| `compare_screen.dart:191`, `:297` | Starting or loading a comparison failed | Error (default) |
| `compare_screen.dart:230` | The same version is chosen on both sides | Warning |
| `comparison_screen.dart:135` | Why a comparison failed (`comparisonFailureMessages`) | Error (default) |
| `comparison_screen.dart:137` | Status could not be loaded | Error (default) |
| `consent_screen.dart:62` | Consent could not be saved | Error (default) |
| `evidence_screen.dart:142` | Text fallback while reviewing | Warning |
| `evidence_screen.dart:176` | Highlight fallback note on the parsed text | Warning |
| `evidence_screen.dart` snackbar | Version text could not be loaded | Error |
| `finding_screen.dart:255` | Finding content could not be loaded | Error (default) |
| `finding_screen.dart:266` | Review fallback, pinned above Confirm | Warning |
| `finding_screen.dart` snackbars | "Finding changed" after a superseded revision | Warning |
| `finding_screen.dart` snackbars | Saving a review action failed | Error |
| `projects_screen.dart:186` | Projects could not be loaded, with Retry | Error (default) |
| `projects_screen.dart` snackbar | Project deleted, or deletion pending | Info |
| `project_screen.dart:149`, `:237` | A comparison failure; the project could not be loaded | Error (default) |
| `report_screen.dart:108` | Report content could not be loaded | Error (default) |
| `report_screen.dart:144` | Partial result, hidden text, cost ceiling, withheld findings | Warning |
| `settings_screen.dart:119`, `:135` | Account deletion failed; usage-events setting not saved | Error (default) |
| `sign_in_screen.dart:80` | Sign-in failed, with the event code under it | Error (default) |
| `sign_in_screen.dart:161` | Signed out, account deleted, deletion pending | Info |
| `sign_in_screen.dart:161` | Session expired, link failed (owner, 2026-11-21) | Warning |
| `project_timeline.dart` status text | Failed / Partial | Error text / warning text |
| `projects_home.dart` status text | A failed latest comparison | Error text (unchanged) |

Three calls to question:

- **`comparison_screen.dart:135`.** Answered by the owner, 2026-11-21: stays an error; a rejected input and the cost limit both stop the comparison.
- **`sign_in_screen.dart:158`.** Answered by the owner, 2026-11-21: "session expired" and "link failed" are warnings; the other notices stay info.
- **`finding_screen.dart` "finding changed".** Answered by the owner, 2026-11-21: stays a warning, because the user's action was not applied.

## Definition of done

- [ ] `flutter analyze --no-pub` reports no issues
- [ ] `flutter test` passes, including `calm_message_test.dart`
- [ ] The layout matrix passes at 320 px, German and the largest text size, with no overflow in a banner
- [ ] Every row of the classification table is confirmed or changed, and the three questioned calls are answered by the owner
- [ ] Error, warning and info are each seen on a device in light and dark, with screenshots
- [ ] The Logto error colour matches the app, or the owner has said to leave it
- [ ] `DESIGN.md`, the design system page and the canvases agree with what shipped
- [ ] Nothing is committed or pushed without the owner's word

Report back with: the diff stat, the analyzer and test output, the list of tests you changed and why, the screenshots, and any kind you reclassified.

## Receiving-agent prompt

> Work in the ChangeLens checkout on `m1-iphone`. Check `git status` and HEAD, and ignore line-ending-only changes (`git -c core.autocrlf=true diff --stat` shows the real ones). The working tree already holds an uncommitted, never-compiled change that gives error, warning and info messages their own colour and icon: read `DESIGN.md`, "Messages (changed 2026-11-21)", then this handoff. Do not touch `deploy/ionos/README.md`, `deploy/ionos/logto/custom.css` or `docs/logto-branding-plan.md` without asking: they carry the owner's edits.
>
> In `app/`, run `flutter analyze --no-pub` and `flutter test`, and fix what they find. The Lucide icon names `circleAlert` and `triangleAlert` are unverified. Where a test asserts the old look, update the test, not the widget. Run the layout matrix at 320 px, German and the largest text size. Then walk the classification table and report any message whose kind looks wrong.
>
> Don't commit, push, deploy or edit the canvases until the owner has seen the device screenshots. Return the diff stat, the analyzer and test output, the tests you changed and why, and the open questions.
