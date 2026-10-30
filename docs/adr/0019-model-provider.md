# ADR 0019: Model provider selection

**Status:** Proposed: D-7 recommendation recorded, awaiting owner confirmation (2026-10-30)

## Context

Retention, training use, EU processing, DPA and price are all unverified.

## Decision

Primary: Claude Sonnet 5.5 on AWS Bedrock, EU geo profile `eu.anthropic.claude-sonnet-5-5` from eu-central-1, with zero data retention enforced at account level. Fallback: Mistral Large 4 on La Plateforme, only after Mistral approves zero data retention and the training opt-out is confirmed; if it refuses, IONOS AI Model Hub after a structured-output spike. Ruled out: Anthropic's first-party API (no EU residency), Azure OpenAI (abuse data kept for human review by default), Claude on Vertex (abuse retention unverified). Full comparison and sources: 06, D-7 comparison.

## Consequences

Unblocks I-2 and the pilot data terms (D-4) once confirmed. Processing is EU-wide, not Germany-only, and AWS is a US company, so D-4 discloses this and includes a transfer impact assessment. Real prices replace the placeholders in 03 §8 and `scripts/cost-model.ps1`.

## Links

05 D-7; O-5; 03 §6. Process for changing this record: `docs/SOP.md`.
