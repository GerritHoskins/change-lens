# 03 — Technical Design

Plan section: §13.3. Tags: [E] established, [A] assumption, [U] unverified, [O] owner decision. This is a planning design, not an approved specification (handoff §1).

## 1. Architecture alternatives

| Option | Summary | For | Against |
|---|---|---|---|
| A. Notebook or script prototype | Local scripts run the pipeline over the evaluation set; no UI | Fastest way to measure comparison quality; no hosting or privacy surface | Cannot test the workflow, history or sharing with users |
| **B. Single web app + Postgres + background worker** | One deployable app (UI + API), Postgres for records and the job queue, object storage for originals, one worker process for pipeline jobs | Simplest design that supports private uploads, background processing, history and sharing; one database to secure and back up | Needs auth, hosting and a security pass before real client data |
| C. Serverless functions + managed queue + document DB | Pipeline steps as functions | Scales to zero | More moving parts, harder to keep provenance and transactions together; not needed at pilot scale |
| D. No-code builder + LLM plugin | Bubble or Retool style tool | Quick demo | Weak control over evidence fidelity, tenancy and data sent to providers |

**Recommendation:**
- Use **A** for the comparison prototype stage (handoff §12, stage 2).
- Then build **B** for the thin product slice and pilot, reusing the same pipeline module.
- The language and framework are an owner decision [O]. Default proposal: TypeScript or Python. PDF text extraction with page and character offsets should be strong in the chosen ecosystem (`pdfplumber` / `pdf.js`) [A].
- Do not add queues, agents, vector stores or OCR services beyond B unless measurements require them (handoff §8).

## 2. Pipeline

`Import → Parse with provenance → Extract facts → Align → Compare → Verify evidence → Generate report → Human review`

| Stage | Deterministic or AI | Output | Failure handling |
|---|---|---|---|
| Import | Deterministic | Validated source version: original bytes stored immutably, plus hash | Reject over-limit or unsupported input with a named reason (AC-20) |
| Parse | Deterministic | Text blocks with locators (`page`, `char_start`, `char_end`; image region later) | Pages with no text layer → partial warning (AC-11) |
| Extract | AI (structured output, schema-validated) | Extracted facts: type, raw span, normalised value, locator, confidence | Retry once on schema failure. If it fails again, the block is marked *unextracted* and the comparison becomes partial |
| Align | Deterministic keys first, AI for remaining candidates | Fact pairs: matched / unmatched-earlier / unmatched-newer / ambiguous | Ambiguous pairs are never forced (AC-7) |
| Compare | Deterministic for numbers, dates and quantities; AI for meaning, with guards (§4) | Draft findings | Guard violations downgrade the finding to *needs review* |
| Verify | Deterministic | Each evidence quote is an exact substring at its locator | Unverifiable finding → withheld with a count (AC-9, AC-10) |
| Report | AI for explanation wording only; structure is deterministic | Findings with explanations | If wording generation fails, fall back to a template |
| Review | Human | Review records | — |

Facts are extracted **once per source version** and cached. A new revision compared with the previous one only needs extraction for the new version. This matters for cost (§8).

## 3. Evidence representation

- **Locator:** `{source_version_id, kind: text|pdf|image, page?, char_start, char_end, bbox?}`. Character offsets refer to the stored parsed text of that version. That parsed text is immutable, so locators never drift.
- **Evidence item:** `{locator, quote}`, where `quote` must equal `parsed_text[char_start:char_end]`. The verifier enforces this (AC-9).
- **Omissions:** the evidence is the *earlier* passage plus the comparison scope. There is never a newer-side quote.
- **Confidence:** stored as internal metadata. It decides routing to *needs review* but is never displayed as evidence (AC-10).

## 4. Comparison and omission logic

### 4.1 Matched pairs

1. If the normalised values differ (number, date, quantity, named owner), the finding is **changed**, whatever the AI says about meaning.
2. If either side has a negation or modality difference (`not`, `no longer`, `must`/`should`/`may`, `only`, `at least`/`up to`), the finding is **changed** or **needs review**, never equivalent (AC-8).
3. Otherwise the AI classifies the pair as **equivalent** or **meaning changed**, with a short rationale. An equivalent pair keeps its raw text diff (AC-5).
4. If dates are ambiguous (for example `03/04`), the entity is ambiguous or alignment confidence is low, the finding is **ambiguous → needs review** (AC-7).

### 4.2 Unmatched facts — decision table

| Earlier fact unmatched? | Newer fact unmatched? | Newer scope | Result |
|---|---|---|---|
| yes | — | complete | **absent from replacement** (never "cancelled") (AC-2) |
| yes | — | partial | **not addressed by this update** (AC-3) |
| yes | — | unknown | **uncertain — needs review**, no removal claim (AC-4) |
| — | yes | any | **added** |
| yes, but a candidate match was rejected as ambiguous | yes | any | **ambiguous pair → needs review** (AC-7) |

### 4.3 Reorder robustness

Alignment uses content keys (fact type + normalised subject), not position. Section order is recorded only as a presentation-only difference (AC-6).

## 5. Data model

The six logical records from handoff §8, plus two supporting records. Every row has `tenant_id`, and every query is scoped by it (AC-19).

| Record | Key fields | Mutability |
|---|---|---|
| Project | id, tenant_id, name, client_label, created_at, deleted_at | Mutable metadata |
| SourceVersion | id, project_id, label, kind, original_object_key, sha256, parsed_text, parse_warnings, user_order_index, scope (complete / partial / unknown), confirmed_at | Immutable after confirm (AC-15) |
| ExtractedFact | id, source_version_id, type, raw_text, normalised_value, locator, status (ok / ambiguous / unextracted), confidence, model_config_id | Immutable |
| Comparison | id, project_id, earlier_id, later_id, scope_snapshot, pipeline_version, model_config_id, status (queued / running / complete / partial / failed), cost_estimate, cost_actual, warnings | Status only |
| Finding | id, comparison_id, category, change_type, before, after, evidence[], explanation, uncertainty, priority, revision, supersedes_id | New revision on correction |
| ReviewEvent | id, finding_id, actor_id, action (confirmed / corrected / dismissed / note), at | Append-only |
| ClientApprovalRecord | id, finding_id, evidence_text_or_object, stated_by, stated_at, recorded_by | Append-only, separate from review (AC-12) |
| SharedReport | id, comparison_id, token_hash, snapshot_json, included_finding_ids, expires_at, revoked_at, view_log | Snapshot immutable; revocation state mutable |

Share tokens are stored only as hashes. The share route loads `snapshot_json` alone and has no joins to project data (AC-16).

## 6. Privacy and security boundaries

| Concern | Design | AC |
|---|---|---|
| Prompt injection | Document text is placed in delimited data fields, and the system prompt states that it is untrusted. The model has **no tools** and no network access, and structured output is validated against a schema. Explanations are rendered as escaped text. | AC-18 |
| Link fetching or actions | The pipeline never dereferences URLs found in documents. The worker has no outbound network except the model API and storage. | AC-18 |
| Tenant isolation | `tenant_id` on every row, a scoped data-access layer, row-level security in Postgres as a second layer, and object keys prefixed by tenant. Authorisation tests cover every route. | AC-19 |
| Share links | Hashed random token, snapshot-only route, expiry and revocation checked on every request, no caching headers. `noindex` is set. | AC-16, AC-17 |
| Model provider | Choose a provider and plan that contractually excludes training on inputs and offers zero or short retention, with processing in the EU or UK. Verify this before any real client document [U][O]. Send only the parsed text blocks needed, never original files or account data. | — |
| Storage | Encryption at rest (provider default), originals in a private bucket, signed short-lived URLs for owner download. | — |
| Retention and deletion | Default: keep until the user deletes [A][O]. Deletion removes primary rows and objects immediately, and backups expire within 30 days. Pilot terms state this. | AC-22 |
| Upload validation | Check MIME type and magic bytes, enforce size and page caps, parse PDFs in a sandboxed worker with timeouts. | AC-20 |
| Claims | No compliance claims (GDPR certification, SOC 2) are made until they are verified. The pilot uses only synthetic data or data with consent. | — |

## 7. Failure handling

- Comparison states are `complete`, `partial` or `failed`. A partial result always lists what was skipped (AC-11).
- Each stage retries once for schema or transient errors. After that the comparison is marked failed with a user-facing reason, and no misleading partial report is shown.
- Jobs are idempotent and keyed by `(earlier_id, later_id, pipeline_version, model_config_id)`. A retry never duplicates findings.
- If model output fails verification, that finding is withheld. The comparison still completes and shows the withheld count.

## 8. Cost model [A][U]

Model prices are **placeholders** until a provider is chosen (D-7). `p_in` and `p_out` are € per million input and output tokens. Illustrative values: `p_in = 3`, `p_out = 15`. These are not a quote.

Assume a typical brief of about 3,000 words ≈ 4,000 tokens per version.

| Step | Input tokens | Output tokens |
|---|---|---|
| Extract newer version (earlier version cached) | 5,000 | 1,500 |
| Align and compare (AI part) | 8,000 | 2,000 |
| Report wording | 4,000 | 1,000 |
| **Per comparison (typical)** | **17,000** | **4,500** |

`cost = (in × p_in + out × p_out) / 1e6 × (1 + retry_rate)`

| Scenario | Tokens in / out | Retry rate | Model cost | Notes |
|---|---|---|---|---|
| Typical (3k words, earlier cached) | 17k / 4.5k | 10% | **≈ €0.13** | |
| First comparison (both extracted) | 22k / 6k | 10% | ≈ €0.17 | |
| Heavy (20 pages ≈ 15k words) | 70k / 15k | 20% | ≈ €0.52 | At the input cap |
| Worst case (heavy, both extracted, 2 retries) | 100k / 22k | 100% | ≈ €1.26 | The hard ceiling (AC-21) should stop beyond ≈ €1.50 |

**Monthly cost per account (sensitivity):**

| Usage | Comparisons per month | Mix | Model cost per month | vs €12 individual / €49 team |
|---|---|---|---|---|
| Light freelancer | 10 | typical | ≈ €1.3 | 11% of €12 |
| Heavy freelancer | 40 | 75% typical / 25% heavy | ≈ €9.1 | 76% of €12 — needs an allowance |
| Small team | 120 | 75 / 25 | ≈ €27 | 55% of €49 |

These figures exclude hosting (≈ €20–60 per month flat at pilot scale [A]), payment fees (≈ 1.5–3% + fixed fee [U]), support time and acquisition.

**Implications:**
- Each plan needs a comparison allowance, for example 25 per month for individuals and 100 per month for teams [O].
- Heavy documents should count as more than one comparison.
- The pilot must measure real token usage per comparison (I-14) and replace these placeholders.
