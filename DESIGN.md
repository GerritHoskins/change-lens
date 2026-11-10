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

| Role | Size / weight | Line height |
| --- | --- | --- |
| Screen title | 30 / 700 | 1.16 |
| Prominent value | 28 / 700 | 1.2 |
| Feature heading | 24 / 700 | 1.2 |
| Section heading | 20 / 700 | 1.3 |
| Evidence | 17 / 400 | 1.58 light, 1.65 dark |
| Body | Android 16, iOS 17 / 400 | 1.5 |
| Source label | 17 / 600 | 1.4 |
| Actions | 16 / 600 | 1.4 |
| Metadata | 14 / 400 or 600 | 1.5 |

Sizes are logical pixels and respect system text scaling. Full evidence wraps;
list previews may truncate and open the complete finding. Quotes are not rewritten
or struck through. Source side, label, page and actual evidence mode are shown
separately from the explanation.

## Semantic color tokens

Source: app/lib/design/calm_theme.dart. ThemeMode.system follows the device theme.

| Token | Light | Dark |
| --- | --- | --- |
| Canvas | #F4F4EF | #171916 |
| Surface | #FFFFFF | #232621 |
| Quote | #FFFFFF | #242821 |
| Ink | #20211E | #F3F4EC |
| Secondary text | #60615B | #B8BDB2 |
| Separator | #D2D4CA | #4D5247 |
| Primary / text | #25261F / #FFFFFF | #E5F78E / #20251A |
| Personal review marker | #E4F78D | #4A5825 |
| Warning / text | #FFF1D9 / #794300 | #3F301B / #FFD49B |
| Budget surface | #F4EDB8 | #454024 |
| Deadline surface | #ECE4FB | #372C49 |
| Deliverable surface | #D9F2E4 | #26463A |

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
- **Forms:** correction, note and approval dialogs scroll with the keyboard and
  large text. Saving feedback is localized and announced. Client approval remains
  a separate, unverified record; confirming a finding never records approval.

Shared components live in app/lib/design/calm_widgets.dart. Normal content uses
20-pixel horizontal padding, 12–16-pixel card padding/radii, and larger spacing
between task sections. Text/icon buttons have a 48-pixel minimum target; primary
actions have a 52-pixel minimum height.

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
