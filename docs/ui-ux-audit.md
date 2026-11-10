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
`C:\Users\Gerrit\.codex\visualizations\2026\11\07\01a1b698-3344-78f2-9b9c-2e9ce25c0885\baseline-ui`.
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
