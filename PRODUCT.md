# ChangeLens product context

<!-- impeccable:product-schema 1 -->

Captured 2026-11-07 for the UI/UX migration handoff. Audience, platform approach,
and scope were confirmed by the owner in the interview on that date. Repository
facts below were checked against HEAD `0031578787fcb24556c5d8292d2aaea5ec6e42ec`.
This record distinguishes product commitments from implemented functionality.

## Platform

adaptive

Flutter for iOS and Android. The owner wants navigation and controls to adapt
appropriately to each OS. Existing implementation uses Material 3 throughout;
that is the baseline, not the approved destination. Current v1 documentation
specifies portrait phones. Tablet/foldable expansion is not confirmed.

## Users

Web/digital and design freelancers and small studios handling revisions to client
briefs. The primary job is to understand changed deliverables, quantities,
deadlines, responsibilities, budget, and approval-related wording, and check the
supporting source evidence. The core stays domain-neutral; launch communication
focuses on this audience. This is an owner-selected audience, not validated demand.

## Product Purpose

Answer: "What changed since the last version, and which changes matter?"
Help the user catch changed requirements before delivering the wrong thing.
Success means a comprehensible comparison of the exact inputs the user selected,
with uncertainty visible and evidence reachable before they review a finding.

## Positioning

The mechanism combines explicit version order, explicit scope of the newer input,
typed findings, checkable evidence, and project comparison history. Its usefulness
relative to generic diff tools or AI chat remains a hypothesis. Do not invent
customer proof, time savings, accuracy guarantees, or competitive superiority.

## Operating Context

- Users supply documents manually: currently pasted text or text-layer PDFs.
- They choose an earlier version, a newer version, and whether the newer one is a
  complete replacement, partial update, or unknown in scope.
- Comparisons and reviews belong to a project. Sources and original findings are
  immutable; corrections create revisions.
- Evidence is accessed online and held in memory. Offline document use is excluded.
- Launch planning covers English and German and the EU market. The current UI and
  evaluated text fixtures are English; German support is planned, not delivered.
- This is a hobby project intended to grow into a paid product. Current development
  functionality and planned public v1 must be labelled separately.

## Capabilities and Constraints

### Implemented baseline

`app/lib/` contains project creation/listing, project versions/comparisons, text/PDF
import, an explicit comparison confirmation screen, polled comparison status,
reports, all differences, finding review/correction/notes/history, a separate
client-approval record, and PDF evidence with parsed-text fallback. Connection
setup still uses developer settings. Flutter state currently uses StatefulWidget
and ServicesScope; planned architecture is not proof of an installed state library.

### Approved direction, still planned

The owner confirmed that the handoff covers both the current screens and planned
v1 flows. Existing decisions O-14 through O-18 remain the basis:

During handoff preparation, another session began uncommitted I-24 comparison
creation/queue work. It is not verified complete; recheck its current contracts.
The baseline UI and the planned UX below must not be confused with that active work.

- One comparison start screen with two input slots, project, and scope; entry-point
  selections are permitted, inferred chronology is not. Remove the separate
  confirmation route when the replacement is complete.
- Start may create a waiting comparison before versions finish reading. Processing
  and allowance charging must obey the backend state contract.
- Group/filter findings by six topics independently of change type and review need:
  deadlines, deliverables, responsibilities, approval wording, budget, and other.
- Before enabling Confirm, determine evidence placement per side. Show any PDF
  fallback warning above Confirm and before it in screen-reader order. Certain
  findings may advance; needs-review findings stay on screen.
- Store content-free evidence mode and whether the page was opened with each
  review. These are analysis fields, not confidence/approval badges.
- Public sign-in/account linking/deletion, screenshot and share-sheet import,
  German localization, allowances, subscriptions and restore purchases are planned.
- The 2026-10-31 owner decision supersedes older pilot terms: delete documents and
  comparisons 30 days after last use; provide in-app account deletion. Free tier:
  three text/PDF comparisons per month. Paid plans add history and gated screenshots,
  with server-configured allowances/fair use and store-supplied prices. These are
  planned policies, not claims that current retention or billing is implemented.
- Screenshot import is gated on measured passage placement of at least 95%; do
  not advertise it as available or paid value before the gate passes.
- v1 polls. Push, share links, and teams are deferred. Receiving through an OS
  share sheet is distinct from publishing a shareable report.

### Non-negotiable meaning and data rules

- A partial update not mentioning something does not remove or reconfirm it.
  Unknown scope preserves uncertainty. Absence from a complete replacement does
  not imply cancellation of an obligation.
- A reviewed finding is not client approval. The separate record must retain
  "Client approval recorded (not verified by ChangeLens)" or equally explicit meaning.
- Evidence quotes must match sources; never fabricate an absence quote. Keep
  withheld counts, partial-processing warnings, unexplained and presentation-only
  differences reachable. A selected summary is not an exhaustive assurance.
- No document content persists on devices or enters logs/analytics. Preserve picker
  cleanup, lifecycle privacy cover, secure token storage, and backup restrictions.
- Keep the established Flutter/FastAPI boundary and source/evidence identifiers.
  Any API/schema work required by the new UX is an explicit dependency, not a UI mock
  quietly shipped as working functionality.
- No inbox integration, crawling, legal interpretation, autonomous client messaging,
  authoritative merged specification, or general project-management expansion.

## Brand Commitments

The existing product name is ChangeLens. No binding palette, custom typeface, logo,
or visual reference was supplied during the product interview. Keep factual copy
truthful and calm; the design interview and handoff own the replacement direction.

## Evidence on Hand

- [Product decision](docs/01-product-decision.md), [MVP specification](docs/02-mvp-spec.md),
  [decision log](docs/06-decision-log.md), [backlog](docs/05-backlog.md), and
  [SOP](docs/SOP.md) describe decisions, implementation dependencies and gaps.
- [App README](app/README.md), `app/lib/`, and `app/test/` describe the real baseline.
  Existing widget tests protect several domain and privacy contracts; they do not
  establish device accessibility or a complete adaptive visual system.
- The owner supplied three Claude design references, inspected after sign-in:
  the 78-artboard v1 screens canvas, a proposed Calm Bold system, and the older
  Material/POC system. See [reference review](docs/ui-ux-references.md). These are
  design evidence, not implemented features or a newly approved visual direction.
- No customer research or validated commercial claims are supplied by this record.

## Product Principles

1. Let the user establish context before interpreting a change.
2. Make uncertainty and evidence as accessible as the headline finding.
3. Separate detection, personal review, and externally stated client approval.
4. Preserve original sources and explain corrections through history.
5. Reduce effort without hiding information required for an informed decision.

## Open Decisions

- Replacement visual direction, approved references, and any identity constraints
  beyond the existing name: design interview/handoff.
- Additional target device classes and product-specific accessibility needs beyond
  standard native expectations: not confirmed.
- Exact public prices, fair-use limits, and the operational meaning of "last use"
  must come from implemented policy/configuration before final production copy.
