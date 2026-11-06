# ADR 0021: IONOS Qwen as the only v1 comparison model

**Status:** Accepted (owner decision of 2026-10-31, recorded 2026-11-06). Supersedes ADR-0019.

## Context

ADR-0019 proposed evaluating IONOS AI Model Hub first, with Claude Sonnet 5.5 on AWS Bedrock as the configured fallback. Qwen3.5-397B-A17B then passed D-17 on the development split, and the owner chose accuracy over cost. This ADR records that outcome; it makes no new decision.

## Decision

Qwen/Qwen3.5-397B-A17B on IONOS AI Model Hub is the primary and only comparison model for v1. No fallback model or provider is configured. Qwen3.8-27B is not used as a cheaper fallback, because it missed the D-17 F1 threshold (0.857 vs 0.90). If the model is unavailable, the comparison fails and is retried later; it is never answered by a weaker model. As built, the job retries a few times with a short backoff, then the comparison fails and the user starts it again. The Bedrock and Mistral options of ADR-0019 are closed for v1.

## Consequences

An IONOS outage or model retirement stops comparisons: IONOS publishes no SLA, model IDs cannot be pinned, and one retirement came with a week's notice (06). The `llm` port (ADR-0017) keeps a provider change out of the stage code, but only the `fake` and `ionos` adapters exist, so a change needs a new adapter and a new ADR, and the I-7 fingerprint check forces a new held-out run. Bedrock's EU-wide processing and transfer assessment no longer apply; I-20 names IONOS as processor. 03 §8 keeps Bedrock prices only as the conservative cost case. This ADR covers comparison; I-1b chooses the screenshot vision model.

## Links

05 D-7, D-17, I-1b, I-20; O-5; 06 model choice of 2026-10-31; 03 §6, §8; ADR-0017; ADR-0019. Process for changing this record: `docs/SOP.md`.
