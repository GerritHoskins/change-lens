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
