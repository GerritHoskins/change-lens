# Review Ledger

Every review finding, with its status. Checked by `scripts/check-verification.ps1`.

- **IDs:** `SEC-n` (security review), `PLAN-n` (§13 plan review), `REV-n` (later reviews).
- **Status:** `resolved` (with a commit or section reference) or `accepted` (with a reason).

| ID | Source | Finding | Severity | Status | Resolution |
|---|---|---|---|---|---|
| SEC-1 | security-reviewer, 2026-10-30 | Injection could suppress findings or force false equivalence; hidden text not detected | high | resolved | 14748b6: AC-18 extended; 03 §2 hidden-text flag and unexplained-difference listing; I-6; 04 §4 fixtures; ADR-0014 |
| SEC-2 | security-reviewer | Document content could reach logs, telemetry and job payloads | high | resolved | 14748b6: AC-23; 03 §6 logs row; I-8, I-13 data inventory |
| SEC-3 | security-reviewer | tenant_id missing on records; worker may bypass RLS; cache keys without tenant | medium | resolved | 14748b6: 03 §5 tenant rules; ADR-0004 |
| SEC-4 | security-reviewer | Approval attachments unvalidated; no CSP; auto-linking risk | medium | resolved | 14748b6: 03 §6 Rendering row |
| SEC-5 | security-reviewer | Share-link hardening incomplete (cache, referrer, rate limit, audit) | medium | resolved | 14748b6: 03 §6 Share links row; ADR-0015 |
| SEC-6 | security-reviewer | Cost ceiling and rate limits arrive after external users | medium | resolved | 14748b6: moved into I-8; 03 §6 Abuse row |
| SEC-7 | security-reviewer | Upload sandbox lacks resource caps and hostile-file handling | medium | resolved | 14748b6: 03 §6 Upload validation; I-1 hostile fixtures |
| SEC-8 | security-reviewer | Provider data flow and end-client consent undefined | medium | resolved | 14748b6: D-7, D-4; 03 §6 Real client data gate |
| SEC-9 | security-reviewer | No incident runbook, MFA or session controls; D-9 coverage gaps | low | resolved | 14748b6: D-9 runbook and re-runs; MFA and sessions in I-8; later AC-26 (c2669a8) |
| PLAN-1 | plan-reviewer, 2026-10-30 (1.1) | Gate rule blocked every milestone from starting | medium | resolved | 14748b6: 05 header uses the previous milestone's gate |
| PLAN-2 | plan-reviewer (1.2) | D-4 in M1 depended on D-7 in M2 | medium | resolved | 14748b6: D-7 moved to M1 |
| PLAN-3 | plan-reviewer (1.3) | Discovery and implementation share tables; risks and assumptions share a column | low | accepted | D-/I- prefixes plus the M1 discovery-only rule keep them separate; splitting tables adds length without new information |
| PLAN-4 | plan-reviewer (1.4) | Cost model omitted storage and failed-run accounting | low | resolved | 14748b6: 03 §8 storage and failed-run rules |
| PLAN-5 | plan-reviewer (2.1) | AC-3 and AC-4 lacked earlier passage and scope explanation | medium | resolved | 14748b6: AC-3, AC-4 text |
| PLAN-6 | plan-reviewer (2.2) | Screenshot example untested if I-11 never built | medium | resolved | 14748b6 (rejection path), then e863ddb: screenshots in MVP (I-1b) |
| PLAN-7 | plan-reviewer (3.1) | Client-approval record and view log lean toward approval workflow | low | resolved | 14748b6: 02 §5 justification (handoff §7 requires a separate state); view log kept as security audit (SEC-5) |
| PLAN-8 | plan-reviewer (4.1) | Untagged claim that general AI chats blur omission states | medium | resolved | 14748b6: tagged [U], tested in D-5 |
| PLAN-9 | plan-reviewer (4.2) | Encryption at rest untagged | low | resolved | 14748b6: tagged [A], verify in D-8 |
| PLAN-10 | plan-reviewer (5.1) | Pilot fails its own unit-economics gate; heavy documents under-weighted | high | resolved | 14748b6: Gate 4 judged at target price; heavy = 4 |
| PLAN-11 | plan-reviewer (5.2) | Gate 2 cost limit below the plan's own heavy-document cost | medium | resolved | 14748b6: ≤ €0.20 typical, ≤ €0.60 heavy |
| PLAN-12 | plan-reviewer (5.3) | Screenshot timing inconsistent across 02, 05, 06 | medium | resolved | 14748b6, superseded by e863ddb (owner: screenshots in MVP everywhere) |
| PLAN-13 | plan-reviewer (5.4) | Worst case assumed two retries; design allows one | low | resolved | 14748b6: 03 §8 wording |
| PLAN-14 | plan-reviewer (5.5) | Evaluation set too small for zero-false-removal and CI claims | medium | resolved | 14748b6: ≥ 80 pairs, 20 partial + 10 unknown; rule-of-three limit stated; CIs directional |
| PLAN-15 | plan-reviewer (5.6) | Synthetic share of evaluation set not stated | low | resolved | 14748b6: 04 §1 |
| PLAN-16 | plan-reviewer (5.7) | Team seats assumption missing from the Assumed table | low | resolved | 14748b6: 06 Assumed table; later owner-confirmed (2e694a1) |
| PLAN-17 | plan-reviewer (5.8) | Open TODO(human) marker in 04 §6 | low | resolved | Owner removed it; superseded by the v2 rubric (0216e96) |
| PLAN-18 | plan-reviewer (5.9) | Conditional I-11 counted in totals; no grand total | low | resolved | 14748b6: grand total added; I-11 later folded into the MVP (e863ddb) |
| PLAN-19 | plan-reviewer (6.1) | Locator schema and field lists border on implementation detail | low | resolved | 14748b6: 03 §3 labels the schemas illustrative |
| REV-1 | ac-verifier, 2026-10-30 | AC-2/3/4: model explanations could describe omissions as removed or cancelled | high | resolved | 60f038b: P5.5 templates for omissions; contradiction check falls back to template; re-verified pass |
| REV-2 | ac-verifier | AC-5: equivalent findings had no evidence and were withheld; presentation-only step missing | medium | resolved | 60f038b: P5.3 evidence; P5.4 presentation_only; re-verified pass |
| REV-3 | ac-verifier | AC-7: needs-review drafts lacked evidence; ambiguity checked only on matched pairs; no within-version contradiction logic | medium | resolved | 60f038b: P5.2 step 0; P5.3 evidence and all-kinds check; re-verified pass |
| REV-4 | ac-verifier | AC-10: prioritised list included needs-review findings | medium | resolved | 60f038b: P5.5 excludes the needs-review group; re-verified pass |
| REV-5 | ac-verifier | AC-18: model "equivalent" verdicts counted as explanations, hiding forced false equivalence | high | resolved | 60f038b: P5.4 excludes equivalent from coverage; 03 §2 Verify row; re-verified pass |
| REV-6 | ac-verifier | AC-20: word cap checked only for pasted text | medium | resolved | 60f038b: P3 word count for all kinds; re-verified pass |
| REV-7 | ac-verifier | AC-21: screenshot vision parse unmetered | medium | resolved | 60f038b: P2 unit reservation, P3 CostMeter; I-14; re-verified pass |
| REV-8 | ac-verifier | AC-22: deletion only revoked share snapshots; approval attachments possibly outside the purged prefix | high | resolved | 60f038b: P8 deletes SharedReport rows; P6 stores approvals under the project prefix; re-verified pass |
| REV-9 | ac-verifier | AC-23: deny-list logging; exception messages unscrubbed; then metrics and traces unconstrained | high | resolved | 60f038b (allow-list, ON_EXCEPTION), 3a40a87 (METRIC, TRACING_CONFIG, I-8 acceptance) |
| REV-10 | ac-verifier | AC-25: hand-off and picker/camera temp files persisted on device | medium | resolved | 60f038b: P10 purge after upload and on start; I-9, I-16 acceptance; re-verified pass |
| REV-11 | ac-verifier (note) | Scanned PDFs: P3 warned per page; 02 §2 says reject | low | resolved | 60f038b: P3 rejects all-pages-without-text with no_text_layer |
| REV-12 | ac-verifier (note) | Share-extension upload path described differently in 03 §6 and §9.2 | low | resolved | 60f038b: 03 §6 aligned with §9.2 and P10 |
| REV-13 | ac-verifier (note) | block_diff ordering and moved blocks ambiguous | low | resolved | 60f038b: P5.4 separates moved_identical into presentation_only |
| REV-14 | ac-verifier (note) | No team-seat invite flow; every new user got a new tenant | medium | resolved | 3a40a87: P1 invite flow and INVITE_MEMBER; I-8 acceptance |
| REV-15 | ac-verifier (note) | OS app-switcher snapshot could capture document screens | low | resolved | 3a40a87: P10 ON_APP_BACKGROUNDING privacy cover |
| REV-16 | ac-verifier | AC-26 regression: the INVITE_MEMBER insertion moved the 15-minute and MFA lines out of ON_SIGN_IN | high | resolved | Lines restored under ON_SIGN_IN (commit after 3a40a87); re-verification requested |
| REV-17 | ac-verifier (note) | An existing user with their own tenant can never join a team | low | accepted | Pilot accounts are operator-provisioned before first sign-in (I-15), so invites precede tenant creation. Tenant migration is deferred until pilot evidence shows teams form after solo sign-up |
| REV-18 | ac-verifier (note) | INVITE_MEMBER comment allowed the operator; the body required the team owner | low | resolved | P1 body now permits the owner or the operator acting for that owner during the pilot |
| REV-19 | benchmark t8, 2026-10-30 | If every comparison is a new project (both versions extracted), full-allowance cost is ≈ 35% of target price, above the Gate 4 limit of 30% | medium | accepted | Gate 4 is judged on observed usage, and repeat revisions (the paid differentiator) cost ≈ 27%. I-14 measures the real new-project share; if it exceeds ≈ 50%, lower the allowance or weight first comparisons higher before launch pricing |
| REV-20 | benchmark t8 | At 1.5x the placeholder model prices, heavy documents exceed the €0.60 Gate 2 limit and the worst case exceeds the €1.50 ceiling | medium | accepted | Prices are placeholders until D-7. After D-7, rerun scripts/cost-model.ps1 with the real prices; if it fails, lower the input cap or re-derive the limits before Gate 2 |
