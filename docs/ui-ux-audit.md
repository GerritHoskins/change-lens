# ChangeLens native UI audit — 2026-11-07

Baseline: `0031578787fcb24556c5d8292d2aaea5ec6e42ec`. Scope: `app/lib/`, current
tests and applicable iOS/Android guidance. No product fixes were made.

Method: independent native source audit, supplemented by offline production-widget
renders and a targeted settings probe. No web detector applies to Flutter native
source. These findings are not a native accessibility certification.

## Verdict and score

Pass as a native Flutter foundation; not yet a fully adaptive iOS/Android experience.
Standard Material controls and route stacks exist. The app has no explicit dark
scheme, deliberate iOS component policy, or width-dependent composition. Portrait
phones are the current product scope; the portrait restriction itself is not a defect.

| Dimension | Score | Key evidence |
| --- | ---: | --- |
| Accessibility | 2/4 | Standard controls, but no deliberate status announcements, semantic headings, or nonvisual highlight location |
| Performance | 2/4 | Async work, but polling has no in-flight/lifecycle guard; no measured profile |
| Appearance and theming | 2/4 | Material roles, but light-only theme and raw highlight colors |
| Platform conformance | 2/4 | Native Flutter foundation; Material throughout both OS targets |
| Adaptivity | 2/4 | Mostly scrollable lists/wrapped actions; fixed status composition and no size policy |
| **Total** | **10/20** | **Acceptable: significant work required; provisional, source-led** |

Source audit: **0 P0, 2 P1, 6 P2, 0 P3**. The subsequent reproduced settings defect
adds **one P1**, for **nine technical findings: 0 P0, 3 P1, 6 P2, 0 P3**. Design
critique findings overlap; do not add both reports' counts as unique defects.

## Status of every finding (checked 2026-11-18, task L24)

Checked against `main` at `4e3df10` by reading the current source and tests, not on a device. The
locations in the findings below are those of the 2026-11-07 baseline; the screens were rebuilt since.
Tasks L27 and L28 are in [`tasks/launch-todo.md`](../tasks/launch-todo.md).

| Finding | Status | Reference | What the code shows now |
| --- | --- | --- | --- |
| A1 (P1) | Fixed | `28c04ca` | The finding screen resolves every passage first; Confirm stays off until then, and the fallback warning sits directly above it and earlier in reading order (`finding_screen.dart`, test `review_evidence_test.dart`) |
| A2 (P1) | Partly open | `28c04ca`, task L27 | Fixed: a comparison that fails to send keeps its exact inputs for Retry. Open: an import from the project screen closes its sheet before the upload and loses the label and pasted text on failure; blank required fields refuse without a message (import, note, approval); an empty project name closes the sheet |
| A3 (P2) | Fixed | `28c04ca`, `d357054` | Status, saving, uploading and errors are live regions; page and section titles are semantic headings; finished work is announced once |
| A4 (P2) | Fixed | `28c04ca`, `9b715c1` | Light and dark themes with named roles for marker, warning and muted text; dismissed cards are no longer dimmed |
| A5 (P2) | Fixed, iOS build pending | `28c04ca`, task L28 | The status screen scrolls; layouts are tested at 320 wide with 2x text. iPad was removed as a target on 2026-11-18 (the owner's decision): the iOS project targets iPhone only and lists no iPad orientations. Not yet built on Codemagic. Android tablets get the portrait phone layout; that was not checked |
| A6 (P2) | Partly open | `28c04ca`, task L28 | Fixed: one request at a time, and polling stops when the comparison finishes. Open: the status and project screens keep polling while the app is in the background; requests have no time limit |
| A7 (P2) | Fixed | `28c04ca`, `b23e76f` | Load errors offer Retry on every screen; messages come from `userErrorMessage`, never the exception text; limits are named |
| A8 (P2) | Partly open | `28c04ca`, task L28 | Fixed: side, version and page are text on the quote card; a readable-text view exists beside the PDF page. Open: the marked passage has no spoken label, in the PDF (canvas paint) or in the text view (colour and weight only) |
| A9 (P1) | Fixed | `28c04ca` | The settings controllers are created once; saving is covered by `app_test.dart` |

Timeline critique of 2026-11-16 (`.impeccable/critique/2026-11-16T21-02-21Z__app-lib-screens-project-timeline-dart.md`):

| Finding | Status | Reference | What the code shows now |
| --- | --- | --- | --- |
| 1 (P2) loud "Compare from here" | Fixed | `e980a2b` | Muted small text |
| 2 (P2) no way to retry a failed card | Fixed | `e980a2b` | "Compare again" opens Compare with the same pair |
| 3 (P2) silent status changes | Fixed | `e980a2b` | A comparison that finishes is announced once |
| 4 (P3) two arrow directions | Fixed | `e980a2b` | The rail arrow is gone |

The whole-app critique of 2026-11-17 confirms the four timeline fixes and lists nothing at P0 to P2; its
P3 notes were handled in `bd8d6f7`.

## Findings

### A1 — P1: evidence fallback safeguard absent before Confirm

- Location: `app/lib/screens/finding_screen.dart:129`, `evidence_screen.dart:38`.
- Category: accessibility and trustworthy review.
- Evidence: placement is attempted only inside EvidenceScreen; the finding screen
  renders review controls without that result. The fallback note appears only in
  the evidence view.
- Impact: a reviewer can confirm without learning that the passage could not be
  located on the PDF page.
- Requirement: O-17, I-25/I-26, `02-mvp-spec.md` section 5. This is an approved
  unimplemented requirement, not a claim that the old I-10 already promised it.
- Fix direction: resolve each side's placement before enabling Confirm; pin the
  fallback warning immediately above it and earlier in semantic traversal. Keep
  review distinct from approval. Commands: `harden`, `adapt`.

### A2 — P1: failed imports discard drafts; form validation is silent

- Location: `app/lib/screens/project_screen.dart:81`, `:96`; `projects_screen.dart:68`;
  `finding_screen.dart:282`.
- Category: recovery and accessibility.
- Evidence: import dialog closes before upload; failure produces a snackbar and
  the original field state is not restored. Blank import/approval fields silently
  refuse submission; empty project creation dismisses the dialog.
- Impact: network failures require repasting/retyping; invalid inputs give no
  actionable explanation.
- Fix direction: keep drafts in memory through retry; clear on success or explicit
  discard. Add field errors and announced focus guidance. Do not add disk draft
  storage (AC-25). Commands: `harden`, `clarify`.

### A3 — P2: status and saving lack deliberate accessible feedback

- Location: `comparison_screen.dart:77`, `finding_screen.dart:54`, `:123`,
  `report_widgets.dart:125` under `app/lib/screens/`.
- Category: accessibility.
- Evidence: polled text changes without explicit live-region treatment; saving
  uses AbsorbPointer without visible busy feedback; headings are visual Text styles.
- Impact: completion/saving may be missed; long reports lack deliberate semantic
  section navigation. Standard Flutter control semantics still exist.
- Fix direction: announce meaningful transitions once, expose busy state, semantic
  headings and logical focus. Validate with VoiceOver/TalkBack. Command: `harden`.

### A4 — P2: no defined dark appearance or evidence color system

- Location: `app/lib/main.dart:31`, `screens/evidence_screen.dart:87`, `:127`,
  `screens/report_widgets.dart:84`.
- Category: appearance and accessibility.
- Evidence: only a light ThemeData; translucent amber highlights; whole dismissed
  cards dimmed to 55% opacity.
- Impact: OS dark preference lacks a designed result. Highlight/dismissed text
  contrast needs measurement; no numerical contrast failure was measured here.
- Fix direction: semantic light/dark roles for evidence sides, warnings, review
  state and highlights; readable dismissed text. Commands: `colorize`, `audit`.

### A5 — P2: adaptive/large-text behavior lacks a complete policy

- Location: `app/lib/screens/comparison_screen.dart:71`, `app/lib/main.dart:14`,
  `app/ios/Runner/Info.plist:60`.
- Category: adaptivity.
- Evidence: status uses a non-scrollable Column; lists use full width without
  deliberate size classes; iPad orientations are listed while the app locks portrait.
- Impact: long status/error content can exhaust compact height; expanded surfaces
  are unspecified. This source risk was not reproduced as a status overflow.
- Renders: confirmation/finding at 320x568 and 2x text had no initial-viewport render
  exceptions. They do not prove the status screen, keyboard, or entire flow.
- Fix direction: safe scrolling, long-content testing, reading-width constraints;
  preserve portrait-phone scope unless expanded explicitly. Command: `adapt`.

### A6 — P2: polling can overlap and is not lifecycle-aware

- Location: `app/lib/screens/comparison_screen.dart:29`, `app/lib/api.dart:69`.
- Category: performance and state integrity.
- Evidence: Timer.periodic every two seconds, no in-flight/sequence guard or
  background coordination; client has no explicit timeout policy.
- Impact: slow requests can overlap and late responses can replace newer state.
  Battery/jank costs were not measured.
- Fix direction: serialized lifecycle-aware polling, bounded retry/backoff,
  cancellation/sequence protection and resumable status. Commands: `optimize`, `harden`.

### A7 — P2: load errors lack contextual recovery

- Location: `app/lib/screens/report_screen.dart:58`, `finding_screen.dart:115`,
  `evidence_screen.dart:103`, `app/lib/api.dart:15`.
- Category: recovery and localization.
- Evidence: terminal error text lacks Retry; API code/detail strings reach UI;
  existing upload test explicitly expects `limit_exceeded`.
- Impact: users navigate away/back and interpret implementation codes themselves.
- Fix direction: localized offline/session/limit/rejection/processing messages,
  safe retry, and preserved context; never log document content. Commands: `clarify`, `harden`.

### A8 — P2: evidence location lacks explicit nonvisual representation

- Location: `app/lib/screens/evidence_screen.dart:85`, `:127`.
- Category: accessibility.
- Evidence: PDF rectangles are canvas paint; text spans use background and weight.
  App code supplies no semantic highlight boundaries/page-location description.
- Impact: the application's visual locator has no deliberate nonvisual equivalent.
  Underlying pdfrx semantics were not tested; its whole viewer is not declared inaccessible.
- Fix direction: source/version/page/quote/fallback context in text and semantics,
  plus an intentional readable-text alternative. Commands: `adapt`, `harden`.

### A9 — P1: saving developer settings crashes the widget tree

- Location: `app/lib/screens/projects_screen.dart:129`, `:135`.
- Category: runtime correctness and recovery.
- Reproduction: mount current ChangeLensApp with synthetic configured Services;
  open Developer settings; save. Services notifies dependencies; didChangeDependencies
  assigns a `late final` controller a second time.
- Observed: `LateInitializationError: Field 'base' has already been initialized`,
  followed by `buildScope missed some dirty elements`.
- Impact: the current developer connection path fails even though existing tests pass.
- Fix direction: initialize/dispose controllers once, update them deliberately, and
  test settings reload. Recheck project refresh: its comparison uses two references
  to the same mutable Services, a separate unconfirmed source risk. Command: `harden`.
- Diagnostic consumed exceptions to record them. Its exit 0 does not mean this
  behavior passes. No fix was attempted in this handoff task.

## Patterns and strengths

Recovery, state announcements, appearance, and native adaptation need shared
components/policies rather than per-screen patches. Lists construct child widget
collections eagerly, but ListView still lays out lazily: do not label all lists
unvirtualized or add pagination without profiling realistic datasets.

Preserve explicit order/scope, immutable revisions, review/approval separation,
withheld counts, selected-summary/all-differences access, standard control semantics,
theme typography, wrapped actions, scrollable dialogs, picker cleanup and privacy cover.

## Validation evidence and limits

Evidence directory on the current host:
a local visualization folder outside the repository (`baseline-ui`).
Its README records exact commands, harness, fonts, dimensions and outputs.

- Analyzer with existing dependencies, `analyze --no-pub`: exit 0, no issues.
- Original `app_test.dart` and `report_test.dart`: exit 0, **12 tests passed**.
- Eight offline current-widget captures: no initial-viewport render exceptions.
- Settings probe: defect reproduced, recorded, not fixed.
- Existing report tests render at 800x2400, DPR 1; they protect behavior, not phone UX.
- No physical/emulator checks, native PDF placement, gestures, safe areas, IME,
  screen reader, contrast measurement, performance profile or real model calls ran.
- Normal launcher stalled under sandbox; direct installed SDK invocation required
  automatic approval for its existing cache lock. No dependency/lockfile updates.

## Recommended sequence

`harden` evidence and recovery; `adapt` native behavior/accessibility; `clarify` copy;
`colorize` semantic appearances; `optimize` polling when integrating state contracts;
re-run `audit` and `critique`; finish with `polish`.

Commands can be run separately or in the agreed implementation sequence. They are
recommendations for the receiving agent, not authorization to implement in this task.
