# Onboarding implementation handoff

Prepared 2026-11-14 for the implementing agent. Repository:
this repository, branch `m1-iphone`, baseline commit `c0b0a02`
(pushed; the onboarding docs, the O-23 and O-24 decisions and the DESIGN.md exceptions are all
committed). The only untracked paths are tool folders (`.claude-flow/`, `app/.claude-flow/`,
`.playwright-mcp/`) and one older critique snapshot: leave them alone. HEAD may be one commit
ahead of `c0b0a02`: the commit that updated this handoff. This is a baseline, not proof
that the checkout hasn't changed since: check `git status` and HEAD first.

> **Owner authorisation: APPROVED.** A + B, Gerrit Hoskins, 14.11.2026. Recorded as O-24 in
> the decision log (`06-decision-log.md`, private).
> Design status: final after design round 3 (canvas version `1794661231-a0f9`; critique 35/40 before the round 3
> polish, not re-scored since). Build from that version. If the canvas has changed since, the code-wins rule in §2 still applies.

## 1. Goal

Build the parts of the first-launch design that need no backend change:

- **Phase A, definition sheets.** Four info sheets that explain the scope options, change types,
  evidence modes and "Selected summary", opened in context from the existing screens.
- **Phase B, onboarding screens.** The six onboarding steps and the import sheet, reachable now
  as a replay ("How ChangeLens works") from the Projects screen.

First-launch gating, consent, Settings and sign-in are **out of scope** (§7). They wait for I-8
and I-18.

## 2. Sources, in order of authority

1. **Code wins.** `app/lib/screens/*`, `app/lib/design/*`. Where the canvas differs from what the app
   renders (for example a finding card), match the app.
2. [Design direction](onboarding/direction.md): the flow, owner decisions, Round 2 changes and measurements.
3. Canvas: the private Claude first-launch canvas. The artboards for these phases are
   `Onb1Promise`, `Onb2Context`, `Onb3Evidence`, `Onb3Uncertain`, `Onb4Review`, `Onb5Start` (steps 1–6),
   `ImportSheet`, `ProjectsReplay`, `DefScope`, `DefChangeTypes`, `DefEvidence` and `DefSummary`. Each one has
   locale, dark and state tweaks. The artboards are HTML mock-ups, not specs for pixel values: take
   values from DESIGN.md tokens and existing widgets.
4. Copy: [onboarding_en.arb](onboarding/onboarding_en.arb) and [onboarding_de.arb](onboarding/onboarding_de.arb)
   (114 keys each, final wording after design round 3).
5. [DESIGN.md](../DESIGN.md) (Calm Bold), `PRODUCT.md` (meaning rules; private),
   [onboarding feature brief](onboarding-feature-brief.md) §1–§7.

## 3. Phase A: definition sheets

### A1. Strings

Copy only the keys these phases use from the two fragments into `app/lib/l10n/app_en.arb` and
`app_de.arb`, with their `@` metadata: `def*`, `close`. Generate with the existing `l10n.yaml`.
Labels inside the sheets reuse existing keys (`scope*`, `type*`, `evidenceMode*`, `selectedSummary`,
`showAllDifferences`). Don't duplicate them.

### A2. Info button

Add one shared widget to `app/lib/design/calm_widgets.dart` (for example `CalmInfoButton`):

- A Lucide `info` icon through `calm_icons.dart` (add a `CalmIcons.info` entry), with a 48 px target.
- Tooltip and semantics label `defInfo(term)`.
- `onPressed` opens the sheet with the existing `showCalmSheet` / `CalmSheet`.

### A3. Sheets and where they open

| Sheet | Trigger placed next to | Content |
|---|---|---|
| Scope | `compare_screen.dart:197` (the `scopeQuestion` header) | 3 rows: the scope label, its existing hint, then `defScopeComplete` / `Partial` / `Unknown` |
| Change types | `finding_screen.dart:233` (the "type · category" line) | 6 rows: the `type*` label, then the `def*` text. Two names differ: `typeRemoved` pairs with `defRemoved` ("Not in the replacement") and `typeEquivalent` with `defReworded` ("Reworded"). Only *Uncertain* gets `CalmReviewDisc`. **No other icons** (decided: the app names types in words) |
| How a passage was found | The evidence label in `report_widgets.dart:114` | 3 rows, each with an icon and a preview: `CalmIcons.document`, `CalmIcons.text`, `CalmIcons.paste` |
| Selected summary | `report_screen.dart:115` (the `selectedSummary` line) | `defSummaryBody`. The main pill "Show all differences" goes to the same destination as the existing link |

How each sheet behaves:

- **Buttons.** Every sheet's secondary action is **Close** (`close`). The only main pill is the one on
  the summary sheet. The others have no main action.
- **Evidence-mode previews.** These are decorative, so wrap them in `ExcludeSemantics`.
  - PDF: a mini page with grey lines and the quote under `CalmColors.markerFill`. The page is **white
    in both themes**, because it stands for a PDF page.
  - Fallback: the quote inside a 2 px solid ink border, the same as `CalmWarning`.
  - Text-only: a plain quote surface.
- **Quote text.** Use a short, neutral sample sentence, marked `lang: en`.

## 4. Phase B: onboarding screens

### B1. Strings

Copy the `onb*` and `importSheetTitle` keys, plus `close` if A didn't. Skip `signIn*`, `email*`,
`code*`, `mfa*`, `link*`, `session*`, `consent*`, `settings*`, `deleteAccount*`, `legal*` and `signOut`:
they belong to the gated screens.

### B2. Screen

Create `app/lib/screens/onboarding_screen.dart`: `OnboardingScreen({required OnboardingMode mode})`,
where the mode is `firstRun` or `replay`. Keep the step index in a `StatefulWidget`. Don't add a state
package or `PageView` paging gestures: the steps must not be swipeable, because horizontal swipe
belongs to iOS back.

**Layout per step.** The top bar is fixed, the body scrolls and the footer is pinned inside `SafeArea`.

| Area | Content |
|---|---|
| Top bar | Back on steps 2–6. Then `onbStep(n, 6)` as text. Then Skip (`firstRun`, steps 1–5 only) or Close (`replay`, every step) |
| Body | Title (`CalmPageHeader` or the headline role), then the step content. Only this area scrolls |
| Footer | One main pill: `onbNext` on steps 1–5. On step 6, `onbStart` (`firstRun`) or `onbDone` (`replay`) |

**Step content.** The canvas artboards are the reference for each step:

| Step | Content |
|---|---|
| 1 | `onbIntroTitle`, `onbIntroBody`, an illustration (Earlier and Newer tiles → "What changed"), `onbIntroGoal` |
| 2 | `onbContextTitle`, `confirmIntro` (existing), an illustration of the slots (newer slot with the lime marker), `onbContextScope`, the static three-line list `onbScopeLine*`, `onbContextNote` |
| 3 | `onbEvidenceTitle`, `onbEvidenceBody`, an **Example** section holding one finding card |
| 4 | `onbUncertainTitle`, `onbUncertainBody`, an **Example** section with the *Needs your review* group header and one uncertain card, then `onbUncertainSummary` |
| 5 | `onbReviewTitle`, `onbReviewBody`, an **Example** section holding an illustration (`onbReviewAlt`) of the finding screen's own "Your review" section with `CalmReviewMark` (`reviewConfirmed`, active), a divider, then "Client approval" with `approvalNone`. After it come `onbReviewApproval` and `onbReviewApprovalLabel(approvalRecorded)` (muted). No review buttons |
| 6 | First run: `onbStartTitle`, then `onbStartNext` (bold), `onbStartLine`, `onbStartLanguage` (muted), and an underlined text link `onbImportLink` that opens the import sheet. Replay: `onbStartTitleReplay` and no `onbStartNext` |

**Example cards.** Render the **real** `FindingTile` from `report_widgets.dart` with a synthetic
finding, inside `IgnorePointer`. Don't redraw it. Keep the content verbatim from
`test/fixtures/calm_scenario.dart`: the deadline finding on step 3, the hosting finding on step 4.

- The owner approved labelled example content in onboarding (direction.md §1, decision 2). DESIGN.md
  otherwise keeps Cedar data out of `lib/`, so put it in its own file,
  `app/lib/screens/onboarding_examples.dart`, with a header comment naming that decision.
- Wrap each example in `Semantics(label: onbExample, container: true)`.
- Quotes stay English in both locales: they're document content.

**Illustrations** (steps 1, 2 and 5). Use `Semantics(label: <onb*Alt>, image: true, child:
ExcludeSemantics(...))`. Nothing inside may be focusable or announced as a button or radio button.

**Import sheet.** A `CalmSheet` with four icon rows (`onbStartInputs`, `onbStartLimits`,
`onbStartOnline`, `onbStartLanguage`) and Close. `onbStartLimits` needs `words`, `pages` and
`megabytes`. No endpoint exposes the parse limits yet, so add one `ParseLimits` constant mirroring
`backend/changelens/config.py:18-20` (15,000 words, 20 pages, 10 MB). Give it a comment naming that file. Serving
the values from the API is a follow-up: name it in your §9 report, and don't edit the backlog yourself. Format `words` with the locale's thousands
separator (`15,000` / `15.000`).

### B3. Navigation and system back

- **Skip** (`firstRun`) and **Close** (`replay`) pop the screen.
- **Main button on step 6.** `onbStart` (`firstRun`) and `onbDone` (`replay`) both pop for now.
  First-run consent and gating come later.
- **Android back** (`PopScope`). On steps 2–6 it goes to the previous step. On step 1 it behaves like
  Skip or Close. Use `canPop: step == 0` and handle steps 2–6 in `onPopInvokedWithResult`.
- **iOS edge swipe.** A route with `canPop: false` has its back swipe switched off
  (`ModalRoute.popGestureEnabled` in Flutter's `widgets/routes.dart`), so the swipe can't step back
  on one route. Accept that: on step 1 the swipe pops the screen, and on steps 2–6 the on-screen Back
  is the way back. Don't build a nested navigator or a custom gesture for it. Report this in §9 as a
  known platform deviation.
- **Motion.** No custom step transition: swap the content without animation. DESIGN.md defines no
  transition timing, and this avoids a reduced-motion branch. Move focus to the new step's title after
  each change.

### B4. Entry point

In `projects_screen.dart:103`, replace the single dev-settings `IconButton` with a menu:
`CalmIcons.more` on Android, `CalmIcons.moreIOS` on iOS, as a shadowless surface menu per DESIGN.md.

- **"How ChangeLens works"** (`onbReplayEntry`) opens `OnboardingScreen(mode: replay)`.
- **"Developer settings"** (the existing `devSettings` string) opens `DevSettingsScreen` as it does today.
  Keep it reachable with `Key('settings')`, which `test/app_test.dart:316` taps, or update that test in the
  same change.
- `firstRun` mode is built and tested but **not wired** to app start (§7).

## 5. Constraints that can't be broken

- **Copy.** Use the ARB wording as given. No new claims, nothing from brief §7, never "approved" or
  "agreed". Don't change existing strings.
- **Calm Bold.**
  - Pastel only as topic colour (it appears here only inside the real `FindingTile`).
  - Orange `?` only for uncertainty. Lime only as the newer slot, a marker or a PDF highlight.
  - One main pill per screen, and secondary actions as ink text buttons with targets of at least 48 px.
  - Reuse `CalmSheet`, `CalmPageHeader`, `CalmWarning`, `CalmReviewDisc` and `FindingTile`.
- **Privacy.** No document content on the device or in logs or analytics (AC-23, AC-25). Onboarding
  stores nothing: no flags, no `shared_preferences`, no secure-storage keys.
- **No dependency, pubspec or backend changes. No commit, push or publish.**

## 6. Tests and gates

Write widget tests in `app/test/onboarding_test.dart` and `app/test/definition_sheets_test.dart`.

1. **Layout matrix.** Each step and sheet at 320×568 and 390×844, EN/DE, light/dark, text scale 1.0 and
   2.0, for both `TargetPlatform.android` and `TargetPlatform.iOS` (iOS body text is 17 px). There must
   be no overflow exceptions, and the main pill must stay visible and hit-testable.
2. **No-scroll criterion.** At 390×844 and 1.0, in EN and DE, the onboarding body's
   `maxScrollExtent == 0` on both platforms. This is the design's done criterion. If iOS's 17 px body
   breaks it, report the step and how many pixels it overflows by. Don't shrink type to compensate.
3. **Controls.** Skip appears on steps 1–5 in `firstRun` and not on step 6. Close appears on every step in
   `replay`. Back and system back follow B3, and step 1 back pops.
4. **Semantics.**
   - Reading order per step: back, step label, title, body, then the main button.
   - Each illustration is one image node with its alt text, and no button or radio flags beneath it.
   - The example section is announced as "Example".
5. **Sheets.** Each info button opens its sheet, and every label equals the existing ARB string. Close
   dismisses. The summary sheet's main action reaches *All differences*. Change types shows a disc only
   on *Uncertain*.
6. **Entry point.** The menu opens the replay and still reaches Developer settings.
7. **Gates.**
   - `flutter gen-l10n` produces no untranslated keys.
   - `flutter analyze` reports no issues, and the full `flutter test` suite passes (existing tests included).
   - `git status` shows only the intended files.

Widget tests are not device evidence. Still report VoiceOver and TalkBack, real Dynamic Type,
and edge-swipe on hardware as not done unless you ran them.

## 7. Out of scope, and why

| Item | Blocked by |
|---|---|
| Showing onboarding once on first launch, and resuming at the same step | Account fields for "onboarding seen" and the saved step (owner decision: server-side; AC-25 forbids a local flag), and sign-in (I-8) |
| Analytics consent screen, Settings switch | Server-side consent storage, the D-18 tier B event pipeline, legal review (I-20) |
| Settings: Delete account | The account-deletion backend (I-18, 03a P8) |
| Sign-in, email code, MFA, `link_required`, expired session | I-8 and I-18. The MFA prompt being native or Logto-hosted is undecided, and Sign in with Apple on Android needs a web flow. Provider buttons, for later: Apple via `sign_in_with_apple`'s `SignInWithAppleButton` (it draws Apple's logo, so there's no asset to bundle). Google needs the official "G" from Google's sign-in branding zip, which isn't in the repo yet. The owner skipped it for now, so the canvas keeps dashed logo slots. *Since resolved:* MFA is Logto-hosted and Apple on Android is a backend code exchange (`logto-branding-plan.md` §1a); the three methods are one white pill, Apple's logo drawn with `AppleLogoPainter`, not `SignInWithAppleButton` (DESIGN.md, 2026-11-20). The Google "G" is still missing |
| App icon / Logo A | No logo chosen yet (the canvas has drafts). *Since resolved:* Logo D (Aperture), O-29, 2026-11-16; assets in `docs/brand/` |

## 8. Acceptance checklist

- [ ] Only the authorised phases were built. Nothing from §7 is reachable in a release build.
- [ ] All four sheets open from their screens. Labels match existing strings word for word.
- [ ] The six steps match the canvas content. Examples use the real `FindingTile` with Cedar content
      from `onboarding_examples.dart`.
- [ ] Skip, Close, Back and system back behave as in B3. No step persists state.
- [ ] The §6 test matrix passes. The no-scroll criterion holds, or each failure is reported with its overflow in pixels.
- [ ] `flutter analyze` and `flutter test` are green. No dependency or pubspec changes, no commit.

## 9. What to return

- The changed and added files, and their diff stat.
- Gate output: the analyze summary and the test counts (before → after).
- The layout matrix result per step and platform, including any no-scroll failures with their overflow in pixels.
- Deviations from the canvas, with reasons (code wins).
- Anything that needs the owner, as a precise blocker.

## 10. Receiving-agent prompt

> Work in the current ChangeLens checkout on `m1-iphone`. Verify `git status` and HEAD against
> `c0b0a02` (HEAD may be its direct child that updates this handoff; the tool folders are untracked). Read
> `docs/onboarding-implementation-handoff.md`, then `docs/onboarding/direction.md`, DESIGN.md, the
> O-23 and O-24 rows in `docs/06-decision-log.md`, and the canvas artboards the handoff names. Build
> only the phases O-24 authorises (A: definition sheets; B: onboarding screens with the
> Projects-menu replay). On iOS, steps 2–6 go back with the on-screen Back only (§B3). Reuse the existing Calm
> widgets and the real `FindingTile`. Take copy only from `docs/onboarding/*.arb`. Don't wire first
> launch, consent, Settings or sign-in. Don't add dependencies, store anything on the device, commit
> or push. Write the §6 widget tests, run `flutter analyze` and `flutter test`, and return the §9
> evidence or a precise blocker.
