# ADR 0019: Model provider selection

**Status:** Proposed: the D-17 spike decides between IONOS AI Model Hub and Bedrock (2026-10-30)

## Context

Retention, training use, EU processing, DPA and price are all unverified.

## Decision

At the owner's request IONOS AI Model Hub is evaluated first: Qwen3.5-397B-A17B becomes primary if it passes the D-17 spike thresholds, and Claude Sonnet 5.5 on AWS Bedrock (EU geo profile `eu.anthropic.claude-sonnet-5-5` from eu-central-1, zero data retention) stays the configured fallback behind the `llm` port. If IONOS fails the spike, Bedrock is primary. Further fallback: Mistral Large 4 on La Plateforme, only after Mistral approves zero data retention and the training opt-out is confirmed. Ruled out: Anthropic's first-party API (no EU residency), Azure OpenAI (abuse data kept for human review by default), Claude on Vertex (abuse retention unverified). Full comparison and sources: 06, D-7 comparison.

## Consequences

Unblocks I-2 and the pilot data terms (D-4) once confirmed. Processing is EU-wide, not Germany-only, and AWS is a US company, so D-4 discloses this and includes a transfer impact assessment. Real prices replace the placeholders in 03 §8 and `scripts/cost-model.ps1`.

## Links

05 D-7; O-5; 03 §6. Process for changing this record: `docs/SOP.md`.
