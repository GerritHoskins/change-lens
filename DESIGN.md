# ChangeLens — Calm Bold

Implemented Flutter design, 7 November 2026. The owner selected Calm Bold, requested
the typeset/animate/delight refinements, then Roboto, and subsequently authorized
app implementation. Product behavior remains owned by PRODUCT.md and the current
API contracts. The earlier HTML concepts are design references, not API authority.

## Direction and scope

Calm Bold makes source comparison the main task: explicit source order, restrained
topic color, readable quotations and a stable review action. It retains the warm
neutral surfaces, dark primary action and lime personal-review accent from A+B.
Roboto replaces the prototype font pairing. Proof's editorial presentation and
Signal's denser navigation were not selected; the implemented layout favors quick
source inspection over novelty or a dashboard of inferred values.

The implementation covers the existing projects, project, comparison setup,
processing status, report, all differences, finding, evidence and developer-settings
screens. Existing domain logic and concurrent backend work were preserved.

The prototype's resume hero and extracted value headlines require data not present
in current project/finding DTOs. They were not fabricated. Reports show the exact
provided quotations and explanations. Synthetic Cedar content lives only in tests
and the isolated preview entry point, never in lib/main.dart.

## Typography

Roboto is bundled for offline use in app/assets/fonts. No font network request is
made by the app. The fonts are static normal-width instances of the official
[Google Fonts Roboto variable source](https://github.com/google/fonts/tree/main/ofl/roboto),
with actual 400, 600 and 700 weights. The SIL OFL is bundled and registered with
Flutter's license registry. No package dependency was added.

Sizes and line heights follow the Calm Bold design-system tokens (artifact
V9325dymoruEtTngXEULo5, aligned 10 November 2026). Roboto ships only 400/600/700,
so the tokens' 800 weight renders as 700 and 500 as 400.

| Token role | Flutter role | Size / line height / weight | Tracking |
| --- | --- | --- | --- |
| display | displayLarge | 54 / 54 / 700 | -2 |
| figure | displayMedium | 64 / 56 / 700 | -2 |
| headline (screen title) | headlineLarge | 38 / 40 / 700 | -1.4 |
| value | headlineMedium | 28 / 32 / 700 | -0.8 |
| title | titleMedium | 17 / 22 / 600 | |
| body (quotes) | bodyLarge | 16 / 23 / 400 | |
| running text | bodyMedium | Android 16, iOS 17 / 1.45 / 400 | |
| meta | bodySmall | 14 / 20 / 400, muted | |
| button label | labelLarge | 17 / 22 / 600 | |
| label (chips, text buttons) | labelMedium | 14 / 20 / 600 | |
| eyebrow | labelSmall | 13 / 16 / 600 | 0.4 |

Sizes are logical pixels and respect system text scaling. Full evidence wraps;
list previews may truncate and open the complete finding. Quotes are not rewritten
or struck through. Source side, label, page and actual evidence mode are shown
separately from the explanation.

## Semantic color tokens

Source: app/lib/design/calm_theme.dart. ThemeMode.system follows the device theme.

| Token | Light | Dark |
| --- | --- | --- |
| ground (canvas) | #F5F5F2 | #121214 |
| surface / quote | #FFFFFF | #1E1E22 |
| line | #DCDCD6 | #34343A |
| control-border (text field outline) | #86868E | #76767E |
| ink | #111114 | #F3F3EF |
| muted | #5E5E66 | #A6A6AE |
| action / on-action | #111114 / #FFFFFF | #F3F3EF / #111114 |
| link (also focus ring) | #4B3BFF | #A99FFF |
| disabled / disabled-text | #E4E4DE / #8A8A92 | #2A2A2F / #6E6E76 |
| marker / on-marker | #DFFF4F / #111114 | same |
| marker-fill (PDF highlight) | #DFFF4F at 55% | same |
| review (dashed border, ? disc) | #F05A1E | same |
| error | #C4320A | #FF8A65 |
| topic deadlines / deliverables / responsibilities | #CDBEFF / #A8F0C6 / #A9DCFF | same |
| topic approval wording / budget / other | #FFB3D1 / #FFE45C / #E4E4DE | same |
| on-topic | #111114 | same |

The text fallback banner is surface with a 2px solid ink border. Needs-review
findings use a 2px dashed review border and the ? disc; failed and rejected
states use error text.

Measured text pairs, including the topic foregrounds, have contrast from 5.67:1
upward. Separator colors are decorative and are not used as text. Uncertainty,
partial processing, personal review and client approval always have explicit text.

## Components and state map

- **Projects:** prominent Compare action; simple project rows with actual server
  comparison counts. Empty state, creation, refresh and connection recovery remain.
- **Project:** comparison entry points and immutable versions; deletion remains a
  distinct destructive confirmation using the existing server behavior.
- **Compare:** one form for project, ordered inputs and newer scope. Nothing is
  preselected. Swap resets scope because it now describes a different source.
  Pending ambiguous submissions retain their body and idempotency key.
- **Status:** actual reading/queued/running/terminal status; no invented progress
  percentage. The user can return to the project while processing continues.
- **Report:** source pair/scope, personal-review count, all-differences access,
  processing warnings and horizontal topic filters. Needs-review findings remain
  visible across topic selection on the main report. All differences retains its
  own explicit filtering and the separate unexplained/presentation-only sections.
- **Finding:** explanation, exact evidence cards, personal review/history, and a
  separate client-approval record. The footer places the fallback warning before
  Confirm in visual and semantic order. It can scroll at large text sizes.
  Confirm and next labels actual progression; uncertain findings stay open.
- **Recovery:** failed source checks block review. Failed reload after a successful
  save retains visible evidence but disables mutations until Retry succeeds.
  Superseded revisions reload without silently resubmitting the rejected action.
- **Evidence:** exact located PDF highlights or readable text. When available,
  original bytes can be viewed without a highlight; readable text remains an
  explicit alternative. These bytes and text stay in memory. Opening parsed text
  does not claim that a physical PDF page was viewed.
- **Forms:** new project, version import, correction, note and approval are Calm
  sheets (title, content, one main pill, Cancel under it) that scroll with the
  keyboard and large text. Choices open a sheet of radio rows instead of a
  dropdown; only the destructive delete confirmation stays an adaptive dialog. Saving feedback is localized and announced. Client approval remains
  a separate, unverified record; confirming a finding never records approval.

Shared components live in app/lib/design/calm_widgets.dart and calm_controls.dart
(`CalmSheet`, `CalmRadioRow`, `CalmSelectField`, `CalmSurfaceScope`). Text fields use
`CalmFieldBorder`: label inside the block, 1px `control-border`, 2px `link` on focus;
on a surface block (sheet, compare slot) fields and radio rows flip to `ground`.
Secondary actions are ink text buttons; menus are shadowless surfaces. Icons are
Lucide at weight 500 (2.5px stroke) through app/lib/design/calm_icons.dart. Normal content uses
20-pixel horizontal padding and 18-pixel card padding; review cards, banners and
quotes use the 16-pixel `space-inset`. Radii follow the tokens:
18 for rows, fields and menus, 24 for cards, 28 for dialogs, 36 for sheet tops,
and pills for buttons and chips. Text/icon buttons have a 48-pixel minimum target;
the main action is a 60-pixel pill.

## Motion and platform behavior

Evidence enters over 180 ms with a small horizontal translation. A successful
personal review that stays on screen can receive a 220 ms lime marker. Neither
motion asserts certainty or client approval. Warnings and Confirm do not move.
Custom motion is immediate when reduced-motion or accessible-navigation settings
request it. There are no looping decorative animations or artificial delays.

Flutter platform navigation, Back behavior, selection and input controls are
retained. iOS uses the larger body role and platform route defaults; Android uses
the 16-pixel body role. Safe-area padding protects fixed review actions. Device
gesture and assistive-technology behavior still require the native checks below.
The privacy cover also excludes covered document semantics while inactive.

## Integration boundaries

Report.scope reads the existing response field; the comparison's known scope is
also passed as a fallback. No backend contract was changed. Existing evidence-mode
and page-opened telemetry, opened-event retention behavior, corrections, picker
cleanup and project-deletion logic remain separate from visual styling.

Account/sign-in, image/camera/share import, billing/restore and other gated v1
surfaces remain designs from the handoff. No corresponding production feature,
price, entitlement, automatic monitoring or new backend dependency was introduced.
Developer connection settings remain a development surface; this work does not
establish production authentication or waive release gates.

## Verification and remaining acceptance

Evidence is in the local task artifact directory:
`C:/Users/Gerrit/.codex/visualizations/2026/11/07/01a1b6b3-17f9-7c02-b86e-b794c71fd40b`.

- Flutter analysis passed with no issues.
- The 86-test full suite passed. The subsequent 12-test app suite adds the swap
  regression (87 distinct tests in the resulting suite).
- The layout matrix exercises 320×568 and 390×844, EN/DE, light/dark and 1×/2×
  text, scrolling beyond the first viewport. Focused checks cover keyboard dialogs,
  reduced motion, privacy semantics, bundled font weights and stale-save recovery.
- Android debug compilation passed. Native screenshots show real Flutter rendering
  on the isolated Android 16/API 36 emulator, using synthetic services. The captures
  include projects, setup, report, finding, dark mode and German at 2× text.
- An independent agent reviewed correctness and wrote the failed-reload regression.
  Its stale-state, scope-fallback and saving-feedback findings were addressed.

Widget renders are not native evidence. Emulator screenshots do not prove physical
device behavior, TalkBack completion, performance, real PDF pan/zoom/jump behavior,
picker lifecycle cleanup or app-switcher privacy. Native iOS compilation/device,
VoiceOver, edge-swipe and real Dynamic Type acceptance were not performed here.
The iOS-themed keyboard test is a Flutter widget test, not an iPhone test.
These remain acceptance gaps under UX-6; owner acceptance is separate.

No commit, push, publication, deployment or dependency/lockfile update was made.
Other agents' existing app/backend changes remain in the working tree.
