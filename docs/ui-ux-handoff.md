# ChangeLens UI/UX overhaul handoff

Prepared 2026-11-07. Repository: `C:\Users\Gerrit\job-search\POCs\change-lens`.
Assessed HEAD: `0031578787fcb24556c5d8292d2aaea5ec6e42ec`.
Purpose: give the receiving UI/UX agent the product truth, design brief, current
implementation map, migration dependencies, and acceptance gates for a complete
overhaul. This task produced context/review artifacts, not the redesign itself.

## 1. Start here

Read, in order:

1. [PRODUCT.md](../PRODUCT.md): confirmed audience, purpose, platform and invariants.
2. This handoff: owner decisions, target journeys, scope and migration gates.
3. [Design critique](../.impeccable/critique/2026-11-07T15-30-15Z__app-lib-main-dart.md)
   and [native technical audit](ui-ux-audit.md).
4. [Decision log](06-decision-log.md): O-14–O-18 and dated owner rows, especially
   2026-10-31 build-first/defaults and 2026-11-01 redesign decisions.
5. [MVP specification](02-mvp-spec.md), [backlog](05-backlog.md) M1b–M5,
   [SOP](SOP.md), [app README](../app/README.md), and relevant ADRs.
6. Production widgets and existing tests, then source references from section 4.

Preflight the current checkout/HEAD, applicable AGENTS.md and any repository-local
skill routing, Git status, and current APIs. A handoff is a baseline, not proof that
the checkout has not changed. No root/repository AGENTS.md or `.agents` routing
directory was found during this assessment; the session supplied repository rules.

**Concurrent work:** the initial tracked tree was clean, with unrelated untracked
`.claude-flow/` and `app/.claude-flow/`. During review, uncommitted backend cost-accounting
work appeared in domain/models, LLM, metering, pipeline, worker and tests, including
`domain/budget.py`. It was inspected only for migration overlap, not validated.
Preserve it and coordinate before touching shared backend files. That cost work
addresses per-comparison reservations, not monthly allowances, billing or topics.

Further concurrent edits later appeared in comparison API/queue helpers, Android
build/manifest files, Codemagic and release-gate scripts/tests. The comparison work
now partially implements I-24 (slots, idempotency, waiting state); integration was
still incomplete at inspection. It is neither absent nor verified complete.
These changes are outside this task and were not covered by its checks. A subsequent
status check also showed active edits to `app/lib/api.dart`. Revalidate final
contracts before integration or a native build. Widget evidence and analyzer/test
results describe the earlier tested baseline, not acceptance of the changing tree.

## 2. Owner interview and design authority

Confirmed on 2026-11-07:

| Decision | Direction |
| --- | --- |
| Audience/job | Keep web/design freelancers and small studios; understand revised briefs through checkable evidence |
| Platform | Adapt navigation and controls appropriately to both iOS and Android |
| Scope | Overhaul current screens and design the planned v1 flows |
| First priority | Faster, clearer comparison and evidence review |
| Visual authority | Propose a fresh visual language; retain ChangeLens's name and product safeguards |
| Older design | Receiving agent decides after comparing old and new designs; old visual blueprint was not automatically discarded |
| Workflow default | Leave future landing/showcase build preference unset; app screens are code-first |

This is an **Operate** interface. Precision, scanability, recovery and native
expectations are the design ambition. Freshness should come from a coherent task
structure, typography, semantic color, spacing and evidence presentation, not
decorative complexity or marketing layouts inside the app.

No new palette/typeface/logo is pinned. Existing indigo Material styling is the
incumbent to assess, not a preservation constraint. The next agent should choose,
record and justify the replacement direction within the owner's delegation before
implementing it. Ask only for new material decisions outside that delegation. Use Impeccable
`shape`/new-work for direction, then its craft floor immediately before UI editing.
Do not write DESIGN.md as if an unbuilt proposal were an established design system;
record it from the implemented, reviewed result. Keep internal direction notes out
of product copy and runtime payloads.

### Prior Claude designs supplied by the owner

- [Claude design A](https://claude.ai/artifact/2oxDXfdjVheCfHT7NbrPGW?org=9fa5e83c-15b7-4533-adf4-75445b144fdb)
- [Claude design B](https://claude.ai/artifact/V9325dymoruEtTngXEULo5)
- [Claude design C](https://claude.ai/artifact/Dhhsup9qRnHA7uyn8cvoYm)

All three were inspected after owner sign-in. [Design reference review](ui-ux-references.md)
maps the 78-artboard canvas, the proposed Calm Bold system, the older Material/POC
system, and specific contract conflicts. Their UI text is not authority to override
current product decisions. The receiving agent retains the final choice of what
to carry forward; this review recommends Calm Bold/A+B as a starting candidate.

## 3. Product truth and release boundaries

The app compares **exactly two user-selected versions**, not a merged current spec.
Both order and the newer input's scope are explicit. Full replacement, partial
update and unknown scope yield different omission semantics. "Not mentioned" is
neither cancellation nor reconfirmation. Correct the current partial-update hint,
"everything else still stands" (`app_en.arb:68`).

Detection, the user's review, and externally stated client approval are three
independent states. Keep the qualifier "not verified by ChangeLens" on the last.
Sources and original findings are immutable; corrections create revisions.
Quotes/locators must match; omissions never acquire fabricated absence quotes.
Partial reports, withheld findings and unexplained/presentation-only differences
remain visible/reachable. A selected summary is not a completeness guarantee.

No document content persists locally or enters logs/analytics. Retain memory-only
document handling, picker purge on every outcome/startup, privacy cover, secure
token storage and backup restrictions. Memory-only draft recovery is compatible;
offline document caching is not. See ADR-0008 and AC-23/25.

Current public-v1 direction supersedes old pilot plans: EU, EN/DE, single-account
freemium; App Store/Google Play subscriptions via RevenueCat; backend entitlements;
free three text/PDF comparisons per month; paid history and gated screenshots,
configurable fair use. No current public prices are established by this handoff.
Documents/comparisons are planned for deletion 30 days after last use, plus in-app
account deletion. Release copy must match implemented retention and store data.

**In scope to design, still feature-gated:** sign-in/linking/account deletion,
screenshots/camera/photo library/share-sheet import, German, limits/subscription/
restore, privacy/terms/imprint links. Screenshot import/promotion waits for D-19's
measured ≥95% passage placement. Do not sell it early or fake success states.

**Deferred/excluded:** report share links, push, teams, offline mode, inbox/calendar/
website integrations, legal interpretation, autonomous client communication,
multi-document reconciliation and general project management. OS share-sheet
*import* is not report sharing. Portrait phones remain v1 scope; tablet/foldable
expansion needs a deliberate scope decision.

## 4. Current implementation and file map

| Surface | Current owning source | Actual behavior |
| --- | --- | --- |
| App/theme/privacy | `app/lib/main.dart` | MaterialApp, indigo Material 3, portrait lock, lifecycle cover |
| Projects and developer setup | `screens/projects_screen.dart` | Projects list/create dialog, pull refresh, connection setup; save crash reproduced |
| Project detail/import | `screens/project_screen.dart` | Versions/comparisons, label/paste dialog and PDF picker; waits for two parsed versions |
| Confirmation | `screens/confirm_screen.dart` | Existing only start path: two dropdowns, explicit scope; replace after new route works |
| Status | `screens/comparison_screen.dart` | Two-second polling; terminal Open report; poor failure recovery |
| Report/all differences | `screens/report_screen.dart` | Warnings, selected-summary link, prioritised/needs-review groups, all/unexplained/presentation views |
| Finding/review dialogs | `screens/finding_screen.dart` | Quotes, review/correction/note/history, separate approval; no pre-confirm placement/next flow |
| Evidence | `screens/evidence_screen.dart` | In-memory PDF, exact substring check, glyph highlights, parsed-text fallback |
| Shared report widgets | `screens/report_widgets.dart` | Type/category/review labels, quotes, finding cards, section headers |
| State/import seams | `app/lib/services.dart` | ChangeNotifier + InheritedNotifier, injected API/store/picker; no Riverpod installed |
| DTOs/API | `app/lib/api.dart` | Handwritten client/models; do not assume planned generated client exists |
| Copy | `app/lib/l10n/app_en.arb`, `app/l10n.yaml` | English source; generated Dart localization files; German not implemented |

`screens/...` paths in this table are under `app/lib/`.
No dependency upgrade, state-library migration, lockfile change or generated-file
rewrite is implicit. For implementation, obtain explicit scope for necessary
localization generation and other generated outputs; edit ARB as source of truth.

Current route chain:
`Projects → Project → Confirm → Comparison status → Report → Finding → Evidence`.
Report also opens All differences; correction follows its new revision ID. Each
route currently carries versions/report context directly; preserve source IDs and
refresh-on-return behavior when changing navigation.

## 5. Target journeys and required states

The following is a migration specification derived from owner decisions and review;
composition/components are design work for the next agent, not approved mockups.

| Journey/surface | Required outcome and states |
| --- | --- |
| First use/auth | Explain value through the comparison task; product sign-in, not exposed dev-token setup. Design signed-out/loading/cancel/error/expired-session and link_required states against I-18; keep dev settings development-only when auth ships |
| Projects | One obvious Compare two briefs entry; create/open project; empty/loading/error/refresh; reading/processing comparisons recoverable from list |
| Compare | Two explicit earlier/newer slots, each existing version or new import; project plus complete/partial/unknown scope; no default scope/chronology; duplicate prevention; explicit swap must preserve deliberate user choice |
| Import | Label/paste/PDF now; gated image/camera/share-sheet later. Cancel, unsupported type, oversize/no text, upload progress, rejection, partial parse, retry with in-memory draft, interrupted handoff |
| Status | Reading source(s), queued, running, complete, partial, failed; truthful status, not invented percentages; leave and return; offline/backoff; rejected input reason with no allowance charge |
| Report | Source pair/scope context; topic counts/filtering; uncertainty independent of topic; prominent material changes; consolidated but explicit limitations; zero findings/partial-only/withheld-only/stale/error states |
| Finding | Clear before/after with source links; pre-confirm per-side evidence placement; fallback warning above Confirm; saving/error feedback; confirm-and-next only for certain items; needs-review stays; correction/dismiss/note/history separate from approval |
| Evidence | PDF highlight and context; readable-text alternative; fallback cause; exact version/page/quote; loading/error/retry, zoom/pan, long passages and missing locators; source-only omission without invented newer quote |
| Timeline/history | User-confirmed comparison relationships and revisions; explicit Compare v2 → v3 shortcut; never derive truth from upload chronology or filename; long/empty/multiple-branch history |
| All differences | Preserve every other finding, unexplained block and moved/reformatted span; clear route back and retained selection/filter/scroll |
| Account/privacy | Current identity/session, linking via existing method, account/project deletion consequences and errors, retention explanation, public legal links; no team/member screens |
| Allowances/purchase | Loading/available/exhausted/pending/declined/cancelled/restore/expired states; store-localized prices, server entitlements, no unsupported screenshot benefit; no fabricated purchase success |

Historical IDs: screen P0 vocabulary; P1 projects; P2 compare; P3 report; P4 finding;
P6 timeline are documented in I-25. The recovered canvas identifies P5 as dismissal
with a reason and P7 as review completion distinct from client approval. Their
behavior/approval granularity still needs reconciliation with the API as detailed
in the reference review. These IDs are unrelated to pipeline steps P0–P8.

## 6. Contracts that block honest implementation

| Dependency | Current reality | Required contract/acceptance |
| --- | --- | --- |
| I-23 topics | No topic/count DTO; MATERIAL excludes other_material | Six topics derived from category; budget separate/material; approval_wording migration; topic counts from API; needs_review unchanged; corrections affect new revision only; development-split evaluation |
| I-24 compare | Assessed HEAD: parsed IDs only, non-idempotent create, String(10). Concurrent partial work now adds slot requests, required Idempotency-Key/fingerprint, wider status and waiting queue; full integration not verified | Agree final API with its active owner; integrate client only after routing/worker/schema are ready; no duplicates; rejected input fails truthfully; monthly allowance charge at queued→running |
| I-26 review | Review requests/events lack evidence_mode and page_opened | Client determines each side's placement; store pdf_highlight/text_fallback/text_only and page_opened content-free; no approval inference or user badge |
| I-8/I-18 auth | Dev bearer-token connection | Production Logto/JWT/tenant boundary, supported sign-in methods, verified linking, account deletion; never deploy dev auth |
| I-1b/I-16/D-19 images | Text/PDF implemented | Image region locators + native import + placement gate; permission refusal and handoff cancellation; content cleanup |
| I-13/I-14/I-19 | Retention/monthly allowances/entitlements not delivered | Server policy, deletion inventory, metering, store receipts/webhooks, restore; configure prices/limits rather than embedding stale pilot values |

Exact backend review points: `backend/changelens/api/routes.py:147–162`,
`domain/models.py:73`, `api/reviews.py:37,76,140,176`, and
`pipeline/report.py:23`. Line locations describe the assessment baseline.
The concurrent work does not demonstrate I-23 topics or I-26 review metadata. New
I-24 helpers existed, but old routes remained active and no worker-resume integration
or app-side protocol handling was observed at the point-in-time inspection. Do not
copy the old DTO assumptions over the active implementation; inspect it again.

Do not rename the current `removed` wire enum merely because UI says "Not in the
replacement". Coordinate schema, validators, fixtures and clients. Preserve
`finding_superseded` (409) recovery: reload the new revision before retrying a review.
No API shape in a mock is proof the backend supports it.

## 7. Work packages and integration order

The requested scope is the overhaul of current screens plus **design** of planned
v1 flows. Backend changes and planned-feature integration below are dependencies
for separately scoped implementation work, not extra implementation authorized by
this handoff. The table is an integration roadmap, not a mandate to build every row.

| Package | Deliverable | Gate/dependency |
| --- | --- | --- |
| UX-1 Direction | Compare prior designs; choose replacement direction, native adaptation policy, annotated task flows and state map; retain/replace/defer rationale | Product interview above; references accessible or explicitly deferred |
| UX-2 Foundations | Semantic light/dark tokens, native typography/controls, spacing, status/evidence/review vocabulary, accessibility rules; representative screens | Chosen direction/rationale recorded; no unsolicited dependencies |
| Contract dependencies | Separately scoped I-23, I-24, I-26 with matching DTOs/fixtures | Backend ownership coordination; preserve concurrent changes; independent tests/review |
| UX-3 Compare | Projects, imports, new Compare, status/resume and timeline entry | I-24; all AC-14 assertions; no release path depending on fake waiting behavior |
| UX-4 Review | Topic report, all differences, finding/next, evidence and fallback | I-23/I-26; exact evidence and review/approval invariants |
| UX-5 Planned v1 | Auth/account/privacy, image imports, German, billing/restore designs; document integration contracts | Actual planned-feature integration separately scoped; APIs/gates above; unavailable features stay gated |
| UX-6 Acceptance | Native/device matrix, behavioral tests, critique/audit, documented design system, migration notes | No hidden gaps, independent review, owner acceptance |

M1b is scheduled after M1 and before M2. Current app M1 iPhone acceptance remains
open; existing Android/POC evidence cannot close it. Local design work can proceed,
but do not claim the milestone or release gate complete. I-7b must pass before
external testers; the historical I-7 deviation is not waived by a visual overhaul.

Keep changes bounded by package and ownership. Preserve the old behavior until the
replacement passes its contracts, then remove the legacy Confirm route so P2 is
the sole start path. Do not maintain two active release start flows. Preserve
stored IDs/revisions and historical comparisons across upgrades. Record schema
migration/backfill requirements before backend changes; never reset real data to
make a redesign work. No automatic rollback of other people's edits.

## 8. Acceptance checklist

### Product behavior

- [ ] Both slots, distinct versions, project and explicit scope required; only
  user-selected entry context prefills. No upload-time/filename inference.
- [ ] Rejected/read-pending inputs, retries and interrupted imports behave truthfully;
  no duplicate records/charges; no loss of in-memory draft on recoverable failure.
- [ ] Six topic counts/filter results match API; review uncertainty remains separate.
- [ ] Partial/unknown/omission/equivalence copy never overclaims. All differences
  and withheld/partial warnings remain reachable and understandable.
- [ ] Evidence mode resolved before Confirm; fallback announced before action;
  needs-review does not auto-advance; stored review metadata contains no content.
- [ ] Review/correction/dismissal never records client approval; revision history
  and superseded-finding recovery remain correct.
- [ ] Developer settings defect reproduced then fixed if that surface remains;
  known errors have localized retry/recovery, visible/announced saving state.
- [ ] No device persistence, logs/analytics content leakage, or privacy-cover regressions.

### Visual/native behavior

- [ ] Real Android and iOS app reviewed at compact portrait phone sizes; proposed
  coverage includes 320x568 and approximately 390x844 logical sizes where supported.
- [ ] Light/dark, long EN/DE labels, large system text (including 2x equivalent),
  keyboard open, safe-area/cutout/bottom insets, long quotes and dense histories.
- [ ] Standard touch targets (iOS 44 pt, Android 48 dp), measured text contrast,
  non-color status cues, semantic headings, meaningful progress announcements.
- [ ] TalkBack/VoiceOver complete compare→review→evidence without visual-only clues;
  fallback warning precedes Confirm; focus is retained sensibly after corrections.
- [ ] System Back/iOS edge-swipe, reduced-motion setting, PDF jump/zoom/pan,
  app interruption/resume, picker cancellation and app-switcher privacy verified.
- [ ] First report viewport communicates pair/scope and review priorities; large-text
  content may scroll without hiding essential actions or truncating full evidence.
- [ ] Prototype data, internal labels and implementation notes never ship as claims.

### Verification and deliverables

- [ ] Existing domain tests retained with meaningful new tests for changed behavior.
- [ ] Analyzer/tests pass; backend contract checks run only for changed contracts.
- [ ] Render/device evidence names scenario, build/commit, OS/device, size, theme,
  locale, text scale and observed limitations. No browser screenshot claims native parity.
- [ ] Direction/state map, component/token documentation, DESIGN.md from implemented
  result, reference comparison, acceptance results and remaining gaps are handed back.
- [ ] Independent review covers current diff, semantics and evidence; owner acceptance
  remains distinct from automated checks and from publishing authorization.

## 9. Runbook and evidence

With existing installed dependencies, from `app/`:

```powershell
flutter analyze --no-pub
flutter test --no-pub --reporter expanded test/app_test.dart test/report_test.dart
```

2026-11-07 baseline: analyzer exit 0, no issues; **12 original tests passed**.
Eight offscreen widget captures rendered without initial-viewport exceptions.
A targeted settings-save probe reproduced a LateInitializationError and collected
it intentionally; its exit 0 is not a passing settings test.

Evidence directory:
`C:\Users\Gerrit\.codex\visualizations\2026\11\07\01a1b698-3344-78f2-9b9c-2e9ce25c0885\baseline-ui`.
Read its `README.md`, images, exact harness and `*-output.txt`. It records the direct
installed-SDK workaround for the sandbox launcher/cache-lock limitation.
The renders use real widgets + synthetic mocks, Android fonts, no OS insets, screens
mounted as home. Missing back arrows/debug ribbon/fixture explanations are harness
artifacts. They do not establish actual device behavior. No server was started.

Native build/run: follow `app/README.md` and `backend/README.md`; approve exact
device/live/service commands and synthetic data where the repository workflow
requires it. No customer documents or paid model calls for visual iteration.
Use test doubles first. macOS/Xcode/signing is required for real iOS acceptance.
The real app's Codemagic workflows are `app-android-check` and
`app-ios-compile-check`; similarly named POC workflows are a different app.

Do not run `scripts/ci.ps1` as an offline shortcut: it force-reinstalls locked Python
dependencies and checks tracked files only. Do not stage unrelated work to satisfy
it. For these new documents, validate UTF-8, links, line limits and whitespace
directly, since they are not staged. Device/live/provider/production checks and
downloads are separate from safe local fixture checks.

Critique: **20/40**, first run for `app-lib-main-dart`, no prior trend.
Native audit: **10/20**, provisional. See the reports for severity and evidence.
Full native accessibility, performance, dark mode, PDF and iPhone validation did
not run in this task. Paseo progress dashboard was unavailable; no dashboard state
was updated. This task made no commit, push, PR, board update, publication or deployment.

## 10. Receiving-agent prompt

> Work in the current ChangeLens checkout. Read PRODUCT.md and
> docs/ui-ux-handoff.md, then verify current Git state and referenced contracts.
> Overhaul the UX and visual design for faster, clearer comparison and evidence
> review for web/design freelancers and small studios. Adapt appropriately to iOS
> and Android. Cover current screens and design planned v1 flows, respecting their
> implementation gates. Compare the three owner-supplied Claude designs before
> deciding what to retain or replace; report any access limitation honestly.
> Use Impeccable, preserve all correctness/privacy/review invariants, and record the
> chosen direction and rationale before implementing within the follow-on task's
> authorized scope. Ask only for decisions outside the owner's delegation. Follow
> the migration packages and acceptance
> checklist, coordinate backend ownership, and do not rewrite unrelated work.
> This handoff is not permission to commit, publish, deploy, alter dependencies,
> run paid/live checks, or treat prototypes as implemented capabilities. The owner
> starts the follow-on design/implementation task explicitly. Return the implemented
> result and verified evidence, or a precise dependency/access blocker.
