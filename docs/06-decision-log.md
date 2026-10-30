# 06 — Decision Log

Plan section: §13.6. Every entry is tagged:
- **[E]** established by the handoff (commit `a8280b9`)
- **[A]** assumed by this plan as a conservative default
- **[U]** unverified, needs evidence
- **[O]** needs owner input before implementation

## Established by the handoff [E]

- Recommended direction: changing client briefs for freelancers and small agencies. The consumer concept is parked, and the two are not combined (§1, §3).
- Plan only, no implementation code. Low–medium complexity constraint (§1, §13).
- Out of scope: inbox or email integration, crawling and monitoring, calendar, mobile share extensions, autonomous client communication, contract interpretation, complex approvals, project management (§5).
- Use existing models; no custom training. Document content is untrusted input (§6).
- The correctness rules distinguish changed / absent / not addressed / unknown / equivalent / ambiguous. AI-detected, user-reviewed and client approval are separate states (§7).
- Explicit version ordering; no automatic merge into an authoritative spec (§4).
- Competitor facts as of 30 Oct 2026: Diffchecker Pro + Desktop costs US$15 per user per month and includes AI summaries, multiple formats, saved comparisons and sharing (S1, S2). Visualping offers scheduled website monitoring with AI summaries (S3).
- Prices to test: €9–15 per month individual, €39–59 per month team. These are hypotheses, not validated (§10).

### Added by handoff v2 (`ChangeLens_Planning_Agent_Handoff_v2.md`) [E]

- Gate 1 cohort: 10 independent organisations in one preselected niche. The denominator is that niche only; no pooling.
- Three-signal rubric: A ≥ 6/10 recurring need; B ≥ 3/5 observed usefulness; C ≥ 2/10 written buying commitments (3/10 is the strong target).
- Verdicts: 3/3 proceed to a limited pilot; 2/3 one bounded retest; 0–1/3 stop or reposition. Incomplete evidence is inconclusive.
- Non-compensable safeguards override commercial results.
- These thresholds are proposed experiment defaults, not validated market facts.

### Owner decisions after the handoff

- 2026-10-30: ChangeLens is an **iOS and Android app, not a web app**. This overrides handoff §14 ("do not assume a native mobile requirement") and §5 (native share extensions out of scope): share-sheet import and screenshot / camera input are in the MVP.
- 2026-10-30: Stack direction is Flutter + Riverpod, FastAPI + Pydantic + SQLAlchemy, PostgreSQL, a Python worker, S3-compatible storage and GitHub Actions. It is subject to the D-15 proof of concept, with React Native + Expo as the fallback.
- 2026-10-30: The pilot is billed by direct invoice and distributed through TestFlight and Play closed testing; no in-app purchase.

## Assumed by this plan [A]

| Decision | Default | Where |
|---|---|---|
| First niche | Web/digital and design freelancers and studios of 1–10 people | 01 |
| Language and market | English; EU/UK; EUR excluding VAT | 01 |
| Evaluation data sourcing | Public tender and RFP amendments (≥ 25 real pairs) plus constructed pairs with labels by construction; interview donations optional, because freelancers are unlikely to share client briefs (owner, 2026-10-30) | 07, 04 §4 |
| MVP formats | Pasted text, text-layer PDF and PNG/JPEG screenshots, imported through paste, the PDF picker, camera / photo library or the OS share sheet; DOCX deferred | 02 §2 |
| Input limits | ≤ 15k words, ≤ 20 pages, ≤ 10 MB; images ≤ 5 MB | 02 §2 |
| Share expiry | 30 days by default, revocable — owner-confirmed 2026-10-30 | 02 §6 |
| Architecture | Script prototype (A), then Flutter mobile app + FastAPI + Postgres + Python worker + a read-only web share page (B) | 03 §1 |
| Retention | Until the user deletes; backups purged within 30 days — owner-confirmed 2026-10-30 | 03 §6 |
| Cost inputs | Placeholder `p_in = €3/M`, `p_out = €15/M`; brief ≈ 4k tokens | 03 §8 |
| Allowances | 25 comparisons per month individual / 100 per month team; heavy document = 4; failed runs not counted | 03 §8, 04 §2 |
| Team seats | 3 seats per team plan — owner-confirmed 2026-10-30 | 06 O-8 |
| Pilot price | €9 / €39 per month, 2 months prepaid, 5–10 accounts; unit economics judged at target €12 / €49 | 04 §2, §6 |
| Evaluation data | ≥ 10 real permissioned pairs; the rest of the ≥ 80 are synthetic | 04 §1, §4 |
| Gate 1 definitions | Event = written client change to deliverables, quantities, deadlines, owners or approval wording; ≥ 3 in 90 days with ≥ 2 concrete; useful = missed material change caught or ≥ 30% less effort; 14-day decision deadline — confirmed by the owner 2026-10-30 | 04 §6.1 |
| Signal B method | Operator-assisted test (D-13) before any prototype: fixed general-purpose-model prompt plus manual evidence checking, in the 02 §4 report format. It tests format and workflow value, not pipeline accuracy | 04 §6.2, 05 D-13 |
| Retest budget | ≤ 10 new organisations, ≤ 6 weeks, ≤ 8 person-days — confirmed by the owner 2026-10-30 | 04 §6.3 |
| Device data | No document content cached on the device in the MVP; tokens in Keychain / Keystore only | 03 §1.1, §6 |
| Technical thresholds | As proposed in 04 §6, Gates 2–4 | 04 §6 |
| Effort | Person-day ranges for one experienced developer | 05 |
| Small images in PDFs (AC-11 residual) | Image regions under 15% of a text page are listed in the full-difference view but do not mark the run partial, so a small text-bearing image (a timeline, a price table) can go unread while the run shows complete. This narrows AC-11's literal wording to keep the partial warning meaningful (CR-9, SA-15). Measured on the 10 cross-format pairs at Gate 2; if any missed change sits in a small image, lower the threshold or warn on every image | 03a P3; 04 §4 |

## Unverified [U]

- Real revision frequency, cost of missed changes, and willingness to pay in any niche.
- Whether a general-purpose AI chat already solves the job well enough. This is the most likely threat to the differentiator.
- Model provider terms: training use, retention, EU processing, and actual prices.
- Token usage per comparison and extraction quality on real briefs.
- Location accuracy of vision models for screenshot evidence.
- Typical brief length (assumed 1–10 pages).
- Payment fees and VAT handling for the pilot.
- App Store and Google Play in-app purchase rules and fees (15–30%) for B2B subscriptions, and whether direct billing is allowed at public launch.
- Whether `pdfrx` (device) and `pypdfium2` (backend) produce matching text coordinates (tested in D-15).
- That Diffchecker's AI summary does not already handle partial-update semantics (to recheck in D-5).

## Requires owner input before implementation [O]

| # | Decision | Recommendation | Needed by |
|---|---|---|---|
| O-1 | Customer niche | **Decided 2026-10-30:** web/digital and design freelancers and studios of 1–10 people | — |
| O-2 | Launch language and market | **Decided 2026-10-30:** English; EU + UK | — |
| O-3 | First production input formats | **Decided 2026-10-30:** text, PDF and screenshots, via paste, picker, camera and share sheet | — |
| O-4 | Stack, auth and hosting | **Decided 2026-10-30:** Flutter + FastAPI stack (final after D-15); managed IdP with EU residency, using email one-time code + Google + Sign in with Apple; Germany region; Hetzner excluded; minimum spec in 03 §1.2. **Decided 2026-10-30:** hosting on IONOS in Germany, already provisioned. **IdP decided 2026-10-30:** Logto, self-hosted on IONOS (ADR-0020, supersedes ADR-0005); see the D-8 comparison | D-8 |
| O-5 | Model provider and processing location | **Owner asked to evaluate IONOS first (2026-10-30).** Candidate primary: IONOS AI Model Hub, Qwen3.5-397B-A17B (Germany only, prompts never logged, no sub-processors, BSI C5 scope, ≈ 3× cheaper), **if it passes the D-17 spike**. Otherwise Bedrock Claude Sonnet 5.5 (EU geo, zero retention). Both sit behind the `llm` port (AD-9), so the other stays a configured fallback. See the D-7 comparison and IONOS follow-up below, and ADR-0019 | D-17 |
| O-6 | Storage and retention policy | **Decided 2026-10-30:** kept until the user deletes; immediate primary deletion; backups expire within 30 days | — |
| O-7 | Sharing mechanism and default expiry | **Decided 2026-10-30:** revocable snapshot link, 30-day default expiry | — |
| O-8 | Team seats and usage limits | **Decided 2026-10-30:** 3 seats per team plan; 25 comparisons per month individual, 100 per month team; heavy document = 4 | — |
| O-9 | Gate 1 definitions and technical thresholds | **Gate 1 decided 2026-10-30:** v2 thresholds; ≥ 3 qualifying events in 90 days with ≥ 2 concrete; useful = missed material change caught or ≥ 30% less effort; 14-day decision deadline; retest ≤ 10 organisations, 6 weeks, 8 person-days. **Gate 2 decided 2026-10-30** as proposed in 04 §6. **Open:** confirm Gate 3–4 before the pilot | Gate 3 |
| O-10 | Acquisition channel for the pilot | **Changed 2026-10-30 (owner):** the owner's network can't supply 10 organisations. Recruiting is now direct, research-only outreach run by the owner: directory-sourced personal invites plus LinkedIn and community posts, with **no interview incentive**. Research panels are excluded (their terms forbid selling to recruits). Marketplace hires may fill at most 3 places, reported separately. Details in 04 §1. Logged before the first recruitment message, so the Gate 1 freeze (D-2) holds | D-1 |
| O-11 | Pilot pricing and data terms | **Decided 2026-10-30:** €9 / €39 per month, 2 months prepaid. Data terms are still drafted after D-7 | D-4 (terms) |
| O-12 | What a Gate 1 pass authorises | **Decided 2026-10-30 (owner approved the recommendation):** a 3-of-3 verdict starts an operator-assisted paid pilot with no app (D-16) on the committed dates; Milestone 2 runs in parallel; the app pilot stays bounded by Gate 4. 04 §6.3 updated | — |
| O-13 | Thin-slice scope | **Decided 2026-10-30 (owner approved the recommendation):** pilot workspaces have one owner, and the operator manages extra seats (I-15). Self-service team screens (invite choice, member list, ownership transfer) are deferred; I-18 keeps only the `link_required` prompt and in-app account deletion. Removal, account deletion and the GUARD membership check stay, because they are security- or store-required. The backend team routes stay, operator-only | — |

## D-7 model provider comparison (2026-10-30)

Checked against provider documentation on 2026-10-30 by a read-only research agent; prices at the ECB rate EUR 1 = USD 1.1172. [U] marks what the sources did not confirm.

| Candidate | Training on inputs | Retention, incl. abuse monitoring | Region | DPA | Fit (schema JSON, vision, context) | Price per M tokens in / out |
|---|---|---|---|---|---|---|
| **Bedrock, Claude Sonnet 5.5** (EU geo from eu-central-1) | No; Anthropic has no access ([AWS data protection](https://docs.aws.amazon.com/bedrock/latest/userguide/data-protection.html)) | Not on AWS's abuse-retention list (only Fable 5 / 5.1); `data_retention_mode: none` at account level; CSAM-flagged images excepted ([abuse detection](https://docs.aws.amazon.com/bedrock/latest/userguide/abuse-detection.html), [retention](https://docs.aws.amazon.com/bedrock/latest/userguide/data-retention.html)). That `none` is allowed for this model [U] | EU-wide: Frankfurt, Stockholm, Milan, Spain, Ireland, Paris; not Germany-only | AWS GDPR DPA + SCCs + UK addendum, automatic ([DPA](https://d1.awsstatic.com/legal/aws-gdpr/AWS_GDPR_DPA.pdf), [sub-processors](https://aws.amazon.com/compliance/sub-processors/)) | Yes / yes / 1M; no batch tier | USD 2.20 / 11.00 = **€1.97 / €9.85** (AWS Price List, eu-central-1, 2026-10-12) |
| Vertex AI, Claude Sonnet 5.5 (EU multi-region) | No | 24 h implicit cache (can disable); partner-model abuse retention [U] | EU multi-region only | Google Cloud DPA [U] | Yes / yes / 1M | ≈ USD 2.20 / 11.00 [U] |
| Anthropic API (first-party) | No | ZDR needs sales approval; flagged content kept up to 2 years | **US or global only** ([data residency](https://platform.claude.com/docs/en/manage-claude/data-residency)) | Not checked | Yes | USD 2 / 10 |
| Mistral La Plateforme, Large 4 | Allowed unless opted out ([DPA](https://legal.mistral.ai/terms/data-processing-addendum)); API default [U] | Abuse monitoring unless ZDR; ZDR on request at Mistral's discretion ([ZDR](https://docs.mistral.ai/admin/monitor-comply/zero-data-retention)); 30-day default [U] | EU by default [U] | DPA with SCCs; self-serve coverage [U] | Yes / [U] / 1M | USD 0.70 / 2.10 = €0.63 / €1.88 |
| Azure OpenAI, GPT-5.4 (EU Data Zone) | No | Flagged content stored for human review; opt-out by Limited Access application | Any EU member state | Microsoft DPA | [U] | USD 2.75 / 16.50 |
| Vertex AI, Gemini (EU) | No | Abuse logging, period and opt-out [U] | EU regional | Google Cloud DPA | Not checked | Not checked |
| IONOS AI Model Hub, Qwen3.5-397B | No | Prompts and outputs never logged ([data handling](https://docs.ionos.com/cloud/ai/ai-model-hub/data-handling)) | Germany only | Accepted electronically; no sub-processors | Vision yes; schema JSON [U]; ≈262k [U] | €0.60 / €3.60 |

**IONOS AI Model Hub follow-up (owner request, 2026-10-30).** Candidates: Qwen3.5-397B-A17B (262k context, vision, €0.60 / €3.60, ≈ €0.026 typical and €0.096 heavy per comparison) and Qwen3.8-27B (262k, up to 4 images, €0.40 / €2.70); LightOnOCR-2 for dense screenshots ([models](https://docs.ionos.com/cloud/ai/ai-model-hub/models), [price list](https://docs.ionos.com/cloud/support/general-information/price-list/ionos-cloud-eur-en)). Data: prompts and outputs never logged or stored, no training, German data centres, EU-only operations staff, no sub-processors, DPA part of the contract, BSI C5 scope ([data handling](https://docs.ionos.com/cloud/ai/ai-model-hub/governance-and-compliance/data-handling)); abuse monitoring not mentioned [U]. Risks: `json_schema` is in the API, but which models enforce it strictly is model-specific and undocumented [U]; no published SLA, and the status page shows several 2026 degradations; one retirement had one week's notice (2025) and model IDs cannot be pinned; Qwen3.5 reasons by default, which adds billed output unless `reasoning_effort` is `none`; rate limit 5 req/s per model per contract. Quality evidence is vendor-reported only (strong on OCR and format following, slightly weaker on long-context reasoning than Claude Opus 4.5). Decision deferred to the D-17 spike.

**Shortlist (before the IONOS follow-up):** primary Bedrock Claude Sonnet 5.5, fallback Mistral Large 4 (only after ZDR approval and training opt-out), then IONOS AI Model Hub (after a structured-output and quality spike). Ruled out: Anthropic first-party (no EU residency), Azure (default human review of flagged content), Vertex Claude (abuse retention unverified). Placeholder prices in 03 §8 and `scripts/cost-model.ps1` replaced.

## D-8 identity provider comparison (2026-10-30)

Checked against vendor documentation on 2026-10-30 by a read-only research agent. [U] marks what the sources did not confirm. No IdP revokes Sign in with Apple tokens on user deletion, so the backend does it (03a P8) whichever is chosen. IONOS has no customer-identity product.

| Candidate | Residency | Email code / Google / Apple | Linking control | Flutter | Price at 100 / 5k users | Verdict |
|---|---|---|---|---|---|---|
| **Logto OSS, self-hosted on IONOS** | Germany, IONOS DPA, no new sub-processor | Yes / yes / browser flow, native via backend | Auto-linking off; whether the link prompt forces proof of the existing account [U] | Official SDK | Hosting only | **Chosen (owner)**; needs a version after 1.37.1 (CVE-2026-15611); MFA in OSS [U] |
| Ory Network EU (Production) | EU, country not stated; global session data replicated; US company, SCCs ([data location](https://www.ory.com/docs/security-compliance/personal-data-location)) | Yes / yes / native | Requires the existing credential by default ([linking](https://www.ory.com/docs/kratos/social-signin/link-multiple-provider-account)) | No SDK; API-based screens | ≈ $64 / ≈ $115–255 per month [U] | Recommended managed option; exit to self-hosted Kratos |
| Logto Cloud EU | EU (reportedly NL, Azure); US company, SCCs ([DPA](https://logto.io/terms/dpa)) | Yes / yes / browser flow | As self-hosted | Official SDK | ≈ $72/month with MFA ([pricing](https://logto.io/pricing)) | Managed exit for the chosen option |
| Zitadel (Cloud EU or self-hosted) | Frankfurt; Swiss company | Email code only as a second factor | Auto-linking can be disabled | Official example | Free ≤ 100 DAU, Pro $100/month ([pricing](https://zitadel.com/pricing)) | Ruled out: no email-code primary login |
| Keycloak, self-hosted | Germany | Email code and Apple need community extensions | Configurable | flutter_appauth | Hosting only | Ruled out: two extensions to maintain |
| AWS Cognito (eu-central-1) | Frankfurt; US company | Email code on Essentials; native Apple [U] | Admin-driven; our own code | Amplify | $0 / $0 (10k free) ([pricing](https://aws.amazon.com/cognito/pricing/)) | Cheapest; most own code |
| Auth0 (EU tenant) | Frankfurt + Dublin; US company | Yes / yes / native on iOS | No auto-linking; Management API | Official SDK | $35 / $350 per month ([pricing](https://auth0.com/pricing)) | Ruled out: cost and lock-in |
| Supabase Auth (Frankfurt) | Frankfurt; US company | Yes / yes / native | Links automatically by email, no off switch ([docs](https://supabase.com/docs/guides/auth/auth-identity-linking)) | Official SDK | $25 / $25 per month | Ruled out: violates the linking rule |
| Firebase Auth, Clerk, Stytch | US-only processing | — | — | — | — | Ruled out: residency |

## Prior art and reuse (searched 2026-10-30)

**Searched:**
- ruflo memory (`memory_search_unified` over default, claude-memories, auto-memory, patterns, tasks, feedback)
- the Claude project memory directory
- every project in `C:\Users\Gerrit\job-search`: Flutter and Python manifests, ADR directories, and planning docs

| Source | What exists | Reuse for ChangeLens | Verdict |
|---|---|---|---|
| `mobile-engineering-intelligence/app/llm/citations.py` (HEAD `8531a17`) | Deterministic grounding check: every model sentence must cite a valid ID; failures are returned as `Rejected` and never kept silently; `NothingGrounded` when all fail | The same contract as the 03 §2 Verify stage (AC-9, AC-10). Port the pattern, swapping ID checks for exact-substring-at-locator checks | **Reuse (pattern)** |
| `mobile-engineering-intelligence/app/llm/` (`client.py`, `config.py`, `schemas.py`, `prompts.py`, `packet.py`) | Anthropic SDK client with Pydantic-validated structured output and a prompt-packet builder | Scaffold for I-2 extraction and the schema check (03 §1.1). Provider-neutral wrapping is still needed until D-7 decides | **Reuse (adapt)** |
| `mobile-engineering-intelligence/app/privacy.py` | Personal-data minimisation at ingest (for example stripping URL query strings) | Pattern for AC-23 log scrubbing and for limiting what reaches the model provider | **Reuse (pattern)** |
| `mobile-engineering-intelligence` `app/db.py`, `alembic/`, `compose.yaml` (postgres:16), `Dockerfile`, `app/observability.py` | FastAPI + SQLAlchemy 2 + Alembic + Postgres skeleton with OpenTelemetry | Starting point for I-8. **No** `tenant_id`, RLS or job queue, so those must be added (03 §5) | **Reuse (adapt)** |
| `mobile-engineering-intelligence/evals/` | Evaluation harness (`repro_narrative`) | Structural pattern for I-7 | Reference |
| `mobile-engineering-intelligence/infra/` | Terraform for AWS (ECS RunTask jobs) | Not applicable: hosting is OVHcloud or IONOS in Germany | Not reused |
| `POCs/01-leaklens-plan.md` (Rust) | OCR words with a char→box map; image decode limits; "scanned content is inert data"; coverage accounting | Design input for I-1b screenshot locators, AC-11 partial-coverage warnings and the AC-18 posture. Concepts only, different language | **Reuse (concepts)** |
| `charge-portal-nuxt/docs/adr/0001–0010` | ADRs in Status / Context / Decision format | Format template if decisions are split into ADRs; content (Nuxt, NestJS) unrelated | Reference |
| `screenshot-ai` (Electron/TypeScript) | Screenshot annotation desktop app | No overlap with a Flutter client or Python pipeline | Not reused |
| `POCs/cross-platform-translation-test-app-main` | Capacitor / Ionic app | Capacitor excluded by owner | Not reused |
| Flutter projects | None in the workspace | D-15 starts from scratch | — |
| ruflo memory and Claude memory | No entries for ChangeLens, document comparison or this stack | Nothing to reuse; plan outcomes should be stored after the mission | — |

## Change log

| Date | Change | Reason |
|---|---|---|
| 2026-10-30 | Initial plan | Handoff `a8280b9` |
| 2026-10-30 | Applied security review (2 high, 6 medium, 1 low) and plan review (1 high, 9 medium, rest low) findings; added AC-23; moved D-7 to M1 and I-11 to post-pilot; unit-economics gate judged at target prices | Reviewer findings |
| 2026-10-30 | Adopted handoff v2 Gate 1 rubric; added 04 §6.1 definitions, D-13 operator-assisted usefulness test and D-14 bounded retest; niche fixed before recruitment (D-2 now precedes D-1); owner kept the original Gate 1 values, now superseded by v2 | Handoff v2 |
| 2026-10-30 | Mobile-first owner decision: Flutter + FastAPI stack (03 §1.1); share sheet and screenshots moved into the MVP (I-1b, I-16); added D-15 mobile proof of concept and I-17 pilot distribution; same PDF engine (PDFium) on device and backend; no device content cache; read-only web share page kept for recipients | Owner direction |
| 2026-10-30 | O-4 interview: managed EU IdP; email one-time code + Google + Sign in with Apple; Germany; Hetzner excluded; OVHcloud vs IONOS shortlist; minimum hosting spec (03 §1.2) | Owner interview |
| 2026-10-30 | Interview round 2: O-1 web/design niche, O-2 English EU+UK, O-10 own network (with bias mitigation), O-11 €9 / €39 prepaid | Owner interview |
| 2026-10-30 | Interview round 3: Gate 1 definitions (04 §6.1) and retest budget confirmed and frozen | Owner interview |
| 2026-10-30 | Interview round 4: O-6 retention until deletion with 30-day backups; O-7 30-day revocable shares; O-8 3 seats; Gate 2 thresholds accepted | Owner interview |
| 2026-10-30 | Prior-art search (mission t1): reuse candidates recorded from mobile-engineering-intelligence and the LeakLens plan; ruflo and Claude memory empty | Mission t1 |
| 2026-10-30 | Spec gap check (mission t2): added AC-24 (mobile import paths), AC-25 (no document content on device or in push), AC-26 (auth behaviour); mapped in traceability.md | Mission t2 |
| 2026-10-30 | Architecture (mission t3): added 03 §9 modules, pipeline stage interfaces, API surface, end-to-end data flow and decisions AD-1 to AD-9 | Mission t3 |
| 2026-10-30 | ADRs and SOP (mission t4): 19 ADRs in docs/adr (AD-1 to AD-9 plus owner and security decisions; 0006 and 0019 Proposed); docs/SOP.md; check-trace.ps1 links the SOP and fails on any AD-n without an ADR | Mission t4 |
| 2026-10-30 | Pseudocode (mission t5): docs/03a-pipeline-logic.md with steps P0–P10 covering AC-1 to AC-26; check-trace.ps1 requires 03a and fails on any AC not covered there | Mission t5 |
| 2026-10-30 | Failing tests first (mission t6): scripts/check-verification.ps1 with empty docs/verification.md and docs/review-ledger.md; fails on 26 unverified ACs and an empty ledger. Product test code not written: handoff §13 forbids implementation without an owner decision | Mission t6 |
| 2026-10-30 | Implement until tests pass (mission t7): ledger of 46 findings (44 resolved, PLAN-3 and REV-17 accepted); ac-verifier found 12 failures, then a regression and a metrics gap; all fixed in 60f038b, 3a40a87, 2a253de; 26 of 26 ACs independently verified as pass | Mission t7 |
| 2026-10-30 | Benchmark (mission t8): scripts/cost-model.ps1 shows the current design no worse than baseline 14748b6 and within cost gates at placeholder prices; added screenshot parse to 03 §8; sensitivity findings REV-19, REV-20 accepted. Runtime benchmark against the §11 baselines stays with I-7 / Gate 2 (no implementation exists) | Mission t8 |
| 2026-10-30 | Security review (mission t9): independent audit since 14748b6 found 1 high (SA-1, no member removal) and 12 medium/low findings, plus 3 regressions on re-verification (SA-14..16). All resolved and re-verified with no open high finding. Screenshot parse is now two vision passes (≈ €0.026, still one unit); check-verification now checks every finding prefix | Mission t9 |
| 2026-10-30 | Change review (mission t10): independent review of 331687c..08c4e54 found 13 findings (CR-1..CR-13, none high), all resolved or accepted; 11 AC rows re-verified as pass. Backlog adds I-18 (account and team screens) and re-estimates I-8 and I-13; total now 78–133 person-days. cost-model.ps1 compares token use with the baseline, so price changes test only the gates | Mission t10 |
| 2026-10-30 | Docs aligned with shipped behaviour (mission t13): SOP now states what cost-model.ps1 and check-verification.ps1 fail on (token baseline, gates, rejected verifier names, ledger ID rule, stale-row re-verification) and documents scripts/ci.ps1; check-trace header lists the 03a coverage check; 03a route path aligned with 03 §9.4. Every route and error code in 03a is in 03 §9.4 | Mission t13 |
| 2026-10-30 | Goal validation (mission t14): goal-validator found all six handoff §13 deliverables met and re-verified 18 stale AC rows at 16beb12 (all pass); all 26 ACs now have a current non-author check. Its goal-level gaps are logged as O-12 (what a Gate 1 pass authorises) and O-13 (thin-slice scope), plus the AC-11 small-image residual as an assumption; G3 (signal B close to the general-AI baseline) was already flagged [A] in D-13 | Mission t14 |
| 2026-10-30 | Owner decisions: O-12 and O-13 approved as recommended (new D-16 operator-assisted paid pilot; I-18 reduced to account screens); hosting is IONOS, already provisioned (ADR-0006 accepted); Gate 1 definitions (04 §6.1, D-2) frozen as of this commit. Totals now 80–137 person-days | Owner |
| 2026-10-30 | Recruitment channel changed (O-10): direct outreach by the owner, no incentive; research panels excluded; D-1 re-estimated at 6–10 d. Totals now about 81–139 person-days | Owner |
| 2026-10-30 | D-7 done: provider comparison recorded; Bedrock Claude Sonnet 5.5 recommended (O-5 awaiting owner confirmation); cost-model defaults set to €1.97 / €9.85 with a +30% tokenizer sensitivity; all gates pass, REV-19 and REV-20 resolved | Mission follow-up |
| 2026-10-30 | IONOS AI Model Hub evaluated first at the owner's request: candidate primary Qwen3.5-397B-A17B if it passes the new D-17 spike (thresholds in 05); Bedrock Sonnet 5.5 stays the fallback; cost-model defaults stay at Bedrock prices as the conservative case. Totals now about 84–144 person-days | Owner |
| 2026-10-30 | D-13 (Gate 1 operator-assisted test) uses IONOS AI Model Hub, Qwen3.5-397B-A17B, under the existing IONOS contract; model ID and settings fixed with the prompt before the first session. D-8 identity-provider shortlist research started | Owner |
| 2026-10-30 | D-8 identity provider: Logto, self-hosted on IONOS (ADR-0020 supersedes ADR-0005); native Apple sign-in with the backend storing the Apple refresh token encrypted, revoked at deletion; I-8 7–12 d; totals now about 85–146 person-days. Correction: 03 §1.1 had listed three earlier candidates (Auth0 EU, Cognito, Supabase), none chosen | Owner |
| 2026-10-30 | Logto re-verification: ac-reverifier passed AC-22 and AC-26 at d18f0cc and found 3 defects plus 1 note (AR-1..AR-4: Apple token revoke order, token stored before a user row existed, unnamed credentials, orphan Logto user); all resolved | Review |
| 2026-10-30 | Correction to the row above: AR-2 was only partly resolved at 99fc61b (pending-invite path and repeat Apple code exchange). Completed as AR-5, with parked tokens revoked at Apple on expiry | Review |
| 2026-10-30 | Evaluation data: freelancers are unlikely to donate client briefs, so D-3 now sources ≥ 25 real pairs from public tender and RFP amendments and no longer depends on D-1; D-6 adds constructed pairs with labels by construction (07, `eval-schema.json`). D-3 1–3 d, D-6 7–10 d; totals unchanged | Owner |
