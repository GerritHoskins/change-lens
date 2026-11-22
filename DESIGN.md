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
| compact headline (onboarding steps 2 to 6) | displaySmall | 32 / 35 / 700 | -1.4 |
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
| error / error-surface | #C81E1E / #FDECEC | #FF8A8A / #3A1D1D |
| warning / warning-surface | #8A5300 / #FFF3D6 | #FFC857 / #33290F |
| info-surface (accent is link) | #ECEBFF | #25234A |
| topic deadlines / deliverables / responsibilities | #CDBEFF / #A8F0C6 / #A9DCFF | same |
| topic approval wording / budget / other | #FFB3D1 / #FFE45C / #E4E4DE | same |
| on-topic | #111114 | same |

**Messages (changed 2026-11-21, owner: messages must be more noticeable).** A message
banner (`CalmWarning`) has one of three kinds, each with its own colour and its own icon, so
the kind never rests on colour alone: **error** (red `error`, circled "!") for a failed load,
save or sign-in; **warning** (amber `warning`, triangle) for the text fallback banner, the
report's processing warnings and a choice that can't proceed; **info** (blue `link`, circled
"i") for a notice such as "You signed out" (a session that ended or a failed account link is a
warning: the user has to act). Each banner is its kind's tinted surface with a
2px solid border and a 20px icon in the kind's colour; the text stays ink (12:1 or more on
every tint). Snackbars (`calmSnack`) fill with the error or warning colour and carry the same
icon; an info snackbar keeps the ink fill. `error` moved from orange-red (#C4320A) to a true
red, so it can't be read as `review`; amber is never dashed. Needs-review findings keep the
2px dashed review border and the ? disc; failed and rejected states use error text.

Measured text pairs, including the topic foregrounds, have contrast from 5.25:1
upward (error on ground). Separator colors are decorative and are not used as text. Uncertainty,
partial processing, personal review and client approval always have explicit text.

## Components and state map

- **Projects (home artboard, built 2026-11-21):** Compare is the main action, pinned at the bottom like every
  other screen's. The headline leads with the result ("2 briefs changed.", then a `muted` line); with nothing
  to check it says so. A bento follows, `space-3` apart, built only from the list response's
  `latest_comparison` (server counts, never derived): one `marker` hero (radius 28) for the changed project
  compared most recently, with name, "v1 → v2", the count in `figure`, two topic counts as white pills plus
  "+N", the review pill ("2 need your review": white, 2px dashed `review` border, the "?" disc) and an ink arrow disc; it opens the report. Then a
  pair of `surface` tiles (radius 24, min 148) for the next projects to check or being read, never a lone
  tile and none at large text; then `surface` rows (radius 18, min 56) with the status in words ("All
  checked", "3 to check", a failure in `error`). "Changed" means the latest comparison has findings without
  a review. Each block is one button whose label says all of it. Empty state, creation, refresh and
  connection recovery remain.
- **Project:** Compare pinned at the bottom as the main action, and immutable versions; deletion remains a
  distinct destructive confirmation using the existing server behavior.
- **History (P6, WP-D, 2026-11-16; owner-approved drafts on the WP-D/E canvas):** one list
  replaces Versions and Comparisons. Versions are placed only by the comparisons the user ran,
  newest first: each comparison is a card between its versions ("earlier → newer", scope, the
  server's status), joined by a 2px `line` rail. Upload time, list order and labels never place a
  version. Versions compared with the same earlier one but not with each other form a fork: one
  indented block, in label order, opened by a note that neither is newer, with the main rail running
  past it to the version they share. Comparisons in both directions keep both cards; a note above the
  rail says the order is open. Versions in no comparison sit under "Not compared yet". Each version
  row says "Compare from here" under its details and opens Compare with it preset as Earlier; a
  rejected version shows its reason instead and offers no comparison. A card opens the comparison; a
  failed card gives the cause from the comparison's warnings, or the generic next step, and when
  both versions can be read offers "Compare again" (the generic advice then shortens to "couldn't be completed" so it doesn't repeat the button) (the same pair preset, scope still unset). A
  comparison that finishes while the project is open is announced once. "Compare from here" is
  muted body text so it never outweighs the version names, and the rail carries no arrows. The arrow
  in "earlier → newer" is a Lucide icon (the bundled Roboto has no U+2192). Only Failed and Partial
  statuses are emphasised. At about 1.3× text and up the card drops its chevron and the rail gaps
  narrow, so German status words never break mid-word (tested with the real font at 320 px, 2×).
  No dates, page counts or finding progress: the list responses don't carry them.
- **Compare:** one form for project, ordered inputs and newer scope. Nothing is
  preselected. Swap resets scope because it now describes a different source.
  Pending ambiguous submissions retain their body and idempotency key. The earlier slot is a
  `surface` card; the newer slot is filled with `marker` and keeps ink text and a white field in
  both themes, as on the onboarding slots (2026-11-21; it was a 2-pixel marker outline). Start is
  pinned at the bottom, and an error or the "Choose two different versions" warning sits directly
  above it, inside the pinned bar. While Start is disabled the line under it names what is missing,
  first thing first (project, earlier version, newer version, scope); once it can start, the line says
  what Start does. The pinned bars of
  Projects, Project and Compare (`CalmPinnedBar`) carry a `line` hairline, so a list scrolling
  under them is not cut mid-word.
- **Status:** actual reading/queued/running/terminal status; no invented progress
  percentage. The user can return to the project while processing continues.
- **Report:** source pair/scope, personal-review count, all-differences access,
  processing warnings and horizontal topic filters (a topic with no findings has no chip unless
  it is the selected one). "Needs your review · n" comes first, then the changes; needs-review
  findings remain visible across topic selection on the main report. The summary line reads
  "n more differences, including moved or reformatted text" and opens All differences, which
  lists needs-review first too. All differences retains its
  own explicit filtering and the separate unexplained/presentation-only sections.
- **Finding:** explanation, exact evidence cards, personal review/history, and a
  separate client-approval record. The footer places the fallback warning before
  Confirm in visual and semantic order. It can scroll at large text sizes.
  Confirm and next labels actual progression; uncertain findings stay open.
  The topic is the title; the change label adds the category only when it differs from the topic.
  The screen opens with a full-width block in the topic's colour (`FindingHeader`, bottom corners
  `radius-sheet`) holding the position, the topic, the change label, the explanation and, for an
  uncertain finding, the "?" line; the app bar takes the same colour and all text on both is ink in
  both themes. The old and new values of the design system's block are still not drawn (no data).
  The footer is the shared `CalmPinnedBar`: 20-pixel gutter and a hairline.
- **Recovery:** failed source checks block review. Failed reload after a successful
  save retains visible evidence but disables mutations until Retry succeeds.
  Superseded revisions reload without silently resubmitting the rejected action.
- **Evidence:** exact located PDF highlights or readable text. When available,
  original bytes can be viewed without a highlight; readable text remains an
  explicit alternative. These bytes and text stay in memory. Opening parsed text
  does not claim that a physical PDF page was viewed.
- **Forms:** new project, version import, correction, note and approval are Calm
  sheets (title, content, one main pill, Cancel under it) that scroll with the
  keyboard and large text. The keyboard in a sheet closes on a tap on the sheet outside a field,
  on dragging its content, on Cancel, and whenever the sheet closes (the platform is told to hide
  it, 2026-11-21); Done on New project's last field creates the project. Choices open a sheet of radio rows instead of a
  dropdown; only the destructive delete confirmation stays an adaptive dialog. Saving feedback is localized and announced. Client approval remains
  a separate, unverified record; confirming a finding never records approval.
- **Sign-in (WP-A, 2026-11-16):** Logo D lockup, the promise heading and body, the six
  topic blocks, then the methods (iOS: Apple, Google, email; Android: Google, email, since
  native Apple is iOS-only). An error replaces the topic blocks so the buttons stay put;
  a cancelled sign-in is announced, never shown as a banner. Email, its code and MFA run on
  Logto's hosted page (docs/logto-branding-plan.md). `link_required` lists only the
  account's methods; a completed link is announced (`linkDone`).
- **Expired session:** a non-dismissible sheet over the current screen, never a route
  reset, so an in-memory compare draft survives. The last-used method comes first, the
  others behind "Other ways to sign in"; Sign out is the secondary action. No handle (it can't be
  dragged): 28 pixels above the title, the last-used method as a `title` line, and the two text
  buttons centred under the pill. If a different
  account signs in, the old one is treated as signed out and every screen above Projects closes.
- **Settings (WP-B):** opened from the Projects menu. One `surface` card per section under a muted
  `eyebrow` label, as on the artboard: Account (identity with the signed-in method and the Keychain
  line, then the rows Sign out and Delete account in `error`, each with its icon; the deletion note
  sits under the card; adaptive destructive dialog, error and retry), then Privacy with the
  usage-events switch. A switch that is on is `action`, never the platform's green. Privacy and the consent screen read and write the account's
  answer (`/me/consent`, D-18 Task 2) but appear only in builds with `CHANGELENS_CONSENT=true`, off
  until the I-20 legal review. Legal links are not built (I-20).
- **Dismissal (P5, WP-C):** a sheet with four reason rows (reworded, wrong passage, not
  relevant to the work, another reason), none preselected, and an optional note. Its
  action is disabled until a reason is chosen and reads "Dismiss and next" when another
  open finding follows. The finding stays in the report, dimmed, and keeps its change type.
- **Review summary (P7, WP-C):** after the last open finding, the server's counts of
  confirmed, corrected and dismissed findings in ink (no marker, no topic colour), a line
  saying this is not client approval, and "Back to the project". The counts come from
  reloading the report; if that fails, the finding screen simply stays.

Shared components live in app/lib/design/calm_widgets.dart and calm_controls.dart
(`CalmSheet`, `CalmRadioRow`, `CalmSelectField`, `CalmSurfaceScope`, `calmAnnounce`),
calm_brand.dart (`CalmLogoMark`, `CalmLogoLockup`: Logo D drawn from the docs/brand
geometry; the wordmark ignores text scale and the lockup scales down to fit) and
calm_actions.dart (`CalmProviderButton`, `CalmEqualPillPair`, `CalmCountSummary`,
`calmOutlinedPill`). Text fields use
`CalmFieldBorder`: label inside the block, 1px `control-border`, 2px `link` on focus;
on a surface block (sheet, compare slot) fields and radio rows flip to `ground`.
Secondary actions are ink text buttons; menus are shadowless surfaces. Icons are
Lucide at weight 500 (2.5px stroke) through app/lib/design/calm_icons.dart. Normal content uses
20-pixel horizontal padding and 18-pixel card padding; review cards, banners and
quotes use the 16-pixel `space-inset`. Radii follow the tokens:
18 for rows, fields and menus, 24 for cards, 28 for dialogs, 36 for sheet tops,
and pills for buttons and chips. Text/icon buttons have a 48-pixel minimum target;
the main action is a 60-pixel pill.

**Recorded exceptions to one main action (designed 2026-11-14, built 2026-11-16).** Two
first-launch screens have no black main pill. (1) Sign-in shows its methods as buttons of the
same 60-pixel height, because App Review 4.8 requires an *equivalent* option. All three are
the same pill with the `title` label (`CalmProviderButton`, `calmProviderPill`), in the two
styles Apple allows for its button: white with a 2-pixel ink outline on the light theme,
plain white on the dark theme, ink content on both. This pill does not flip with the theme.
Apple adds Apple's logo in the label's colour before the label (changed 2026-11-20: the
package's black `SignInWithAppleButton` drew a 26-pixel label on a black pill and read as the
main action on the iPhone). Google has no "G" until Google's official asset is bundled (not in
the repository). (2) The usage-events consent screen (D-18 tier B) shows Allow
and Don't allow as two identical outlined ink pills (`CalmEqualPillPair`), nothing preselected,
no Back, because refusing must be as easy as accepting. With `CHANGELENS_CONSENT=true` it follows
onboarding until the account has answered for the current policy version; without the flag no route
reaches it. See `docs/onboarding/direction.md`.

**Headings and errors (2026-11-17).** Page headers and section headings use `CalmFitText`: at
large text, when the longest word is wider than the line, the text scale shrinks just enough for
it to fit, never below 1×, so German headings never break inside a word. Errors reach users
through `userErrorMessage` (sign-in ended, not found, not accepted, server problem, no
connection), never the exception's text; an upload over a server limit names the limit. The
partial status reads "Some content couldn't be read", so it no longer collides with the
"Partial update" scope, and project rows say "1 comparison: <status>".

**Audit fixes (2026-11-21).** History rows and comparison cards replace their text with one spoken
label, so the tap is passed to that node and "Compare again" is a custom screen-reader action. Project
rows, finding tiles and quotes that open a source carry the button role; loading spinners are
labelled. Topic filter chips show their topic colour with ink text until pressed, with the count
after the name ("Budget 1"); the report shows the review bar (`action` on `disabled`) under the
"Your review" line. On iOS: alert actions are Cupertino actions, pull-to-refresh is the adaptive
indicator, the approval date uses the date wheels, and a swipe from the left edge steps back in
onboarding (where `canPop` is off). The two most recently used original PDFs stay in memory for the
Api's lifetime, so stepping through findings fetches each once. A poll that changed nothing rebuilds
nothing. Dark-theme text selection is `link` at 40%, because selected text stays light there.
Disabled labels keep the `disabled-text` token and the 38% dim of the design system: disabled
controls are exempt from contrast minimums and always come with a `muted` line saying what is missing. A step
change in onboarding and "Confirm and next" on a finding are announced with the new position. The
sheet scrim is ink at 40% on light and black at 60% on dark (`bottomSheetTheme`). On a screen wider
than 600 pixels (a large Android screen that ignores the portrait lock) the phone layout is centred
at 600 on `ground`. Example finding tiles in onboarding are not announced as buttons. The marked
quote in readable text uses `marker-fill` on light, so a selection shows through it.

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
also passed as a fallback. WP-C added one backend contract: `dismissal_reason` on
`POST /findings/{id}/reviews` (required with `dismissed`, refused otherwise, no default;
revision `0007_dismissal_reason`). Existing evidence-mode
and page-opened telemetry, opened-event retention behavior, corrections, picker
cleanup and project-deletion logic remain separate from visual styling.

Sign-in and account deletion are built (I-18, WP-A/B). Image/camera/share import,
the version timeline, the fair-use allowance, feedback, billing/restore and other gated v1
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

**WP-A to WP-C (2026-11-16, on `14d2360`).** `flutter analyze --no-pub`: no issues.
`flutter test`: 246 passed (215 before the new tests). The new layout matrix
(`new_screens_layout_test.dart`) covers sign-in, the expired-session sheet, Settings, consent,
P5 and P7 at 320×568 and 390×844, EN/DE, light/dark, 1× and 2× text: no overflow, pinned
actions reachable without scrolling. It found one real defect, the lockup overflowing at 320
pixels with 2× text, now fixed. Backend: the full suite (1014 tests) passes with the new revision. Not done: device or emulator renders, TalkBack/VoiceOver walkthroughs,
edge-swipe, real Dynamic Type, iOS compilation, a fresh `.impeccable` critique and contrast
measurement of the new screens.

**WP-F state check (2026-11-16, code only).** Each import and status state in the handoff has
a handler: picker cancel returns silently and purges (`compare_screen.dart`); unsupported type,
oversize, no text layer and the other parse rejections map to `rejectionReasonLabel`
(`comparison_screen.dart`); upload progress is the busy main action; a 4xx rejection frees
the inputs for editing, while a transport or server failure keeps the in-memory submission and its
idempotency key for a retry (`pendingComparison`, `compareRetrySame`); partial parse is the
partial scope and `warningPartial`; status covers reading, queued, running, partial and failed;
offline shows the connection message with Retry. Not done: the visual comparison against the v1
canvas (needs canvas access) and feedback (needs the D-18 content-free endpoint).

**WP-D (2026-11-16).** Built from the approved drafts on the existing comparisons list (no new
API). `project_timeline_test.dart` covers ordering, forks, both directions, unplaced and
unattached comparisons, and the widget; the layout matrix includes P6; Compare's Earlier preset
has its own test. The v1 canvas's Calm Bold P6 matches in structure; its dates, page counts and
progress bars were left out (no data). A follow-up `/impeccable critique` (27/40) found two P1s and
three P2s; all five were fixed the same day (the History bullet above describes the result) and
`flutter test` passed 262.

**Audit fixes (2026-11-22, from the screenshot audit against the first-launch canvas and the design
system).** Sign-in: the methods sit at the bottom of the screen, the promise is the compact headline
with a `muted` body, and the email pill carries a mail icon. Consent: "Don't allow" comes first and the
second paragraph is `muted`. Projects with no project: the empty note is a `surface` card and "New
project" is the pinned main pill. The uncertain group has one name, "Needs your review", on home too.
The text-fallback banner uses the design system's sentence ("The passage couldn't be placed on the
page. These quotes come from the parsed text."; the evidence screen says "This quote comes"). A
disabled main button always has its reason under it (Compare, the dismissal sheet). German "wird
gelesen …" keeps its ellipsis on the line. `flutter analyze`: no issues; `flutter test`: all passed;
the screenshots in `app/build/screenshots` were regenerated. Kept as decided earlier: the failure
code under a sign-in error (L35) and the "Continue with" labels.

**Not started.** WP-E (allowance) has owner-reviewable drafts but needs the I-14 allowance
contract. WP-G waits for D-19 and needs a region-evidence design and the share and image packages.
