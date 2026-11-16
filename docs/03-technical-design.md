# 03 — Technical Design

Plan section: §13.3. Tags: [E] established, [A] assumption, [U] unverified, [O] owner decision. This is a planning design, not an approved specification (handoff §1).

## 1. Architecture alternatives

| Option | Summary | For | Against |
|---|---|---|---|
| A. Notebook or script prototype | Local scripts run the pipeline over the evaluation set; no UI | Fastest way to measure comparison quality; no hosting or privacy surface | Cannot test the workflow, history or sharing with users |
| **B. Mobile app (iOS + Android) + API + Postgres + background worker** | Flutter client; FastAPI service; Postgres for records and the job queue; S3-compatible storage for originals; one Python worker for pipeline jobs; one server-rendered read-only page for shared snapshots | Owner requires a mobile app [O, decided 2026-10-30]. Keeps document intelligence in Python, separate from the UI. One database to secure and back up | Two codebases (Dart + Python); store review on every release; needs auth, hosting and a security pass before real client data |
| C. Serverless functions + managed queue + document DB | Pipeline steps as functions | Scales to zero | More moving parts, harder to keep provenance and transactions together; not needed at pilot scale |
| D. No-code builder + LLM plugin | Bubble or Retool style tool | Quick demo | Weak control over evidence fidelity, tenancy and data sent to providers |

**Recommendation:**
- Use **A** for the comparison prototype stage (handoff §12, stage 2).
- Then build **B** for the thin product slice and pilot, reusing the same pipeline module.
- The stack below follows the owner's direction. Flutter becomes final only after the mobile proof of concept (D-15) passes. If it fails, React Native + Expo is evaluated against the same tests.
- Do not add queues, agents, vector stores or OCR services beyond B unless measurements require them (handoff §8).

### 1.1 Stack (owner direction, 2026-10-30)

| Layer | Choice | Notes |
|---|---|---|
| Mobile | Flutter + Dart; Riverpod; go_router; Dio; Freezed + json_serializable | Shared UI for iOS and Android |
| Device storage | `flutter_secure_storage` for tokens only. **No offline cache of document content in the MVP** | A device cache would put client briefs outside deletion (AC-22) and the data inventory (AC-23). Drift/SQLite only if pilot evidence needs offline use |
| Import | `file_picker` (PDF); paste; camera / photo library (screenshots); OS share sheet: an iOS Share Extension (a native Swift target) and an Android `ACTION_SEND` intent filter | The share sheet and screenshots are owner overrides of handoff §5 (see 06) |
| PDF evidence view | `pdfrx` (PDFium-based) with per-page highlight overlays, subject to D-15 | Fallback: highlighted spans in the parsed text, which always works because locators are character offsets |
| Backend API | FastAPI + Pydantic; SQLAlchemy + Alembic | Pydantic models double as the schema check on model structured output |
| PDF parsing | **`pypdfium2` (PDFium)** for text, character boxes and page geometry | The same engine as `pdfrx` on the device, so backend locators and on-device text coordinates come from one implementation. This is the main lever for the alignment risk D-15 tests |
| Database / queue | PostgreSQL with row-level security; Postgres-backed job queue (for example `procrastinate`) | RLS is set per request and per job with `SET LOCAL app.tenant_id` |
| Object storage | S3-compatible, Germany, same provider as hosting | Private bucket; short-lived signed URLs |
| Auth | **Logto, self-hosted on IONOS in Germany** [O, decided 2026-10-30; ADR-0020, superseding the managed-provider choice of ADR-0005]. Sign-in by email one-time code, Google and Sign in with Apple (Apple requires the last whenever Google is offered); Apple uses the native flow, with the backend storing the Apple refresh token encrypted so deletion can revoke it. Logto handles MFA, refresh-token rotation and session revocation; FastAPI verifies Logto JWTs (access tokens ≤ 15 min). Data stays under the IONOS DPA; the owner operates and patches it. Shortlist and reasons in 06 (D-8 comparison) | Linking accounts across the three sign-in methods by verified email must not merge tenants by accident; Logto later than 1.37.1 (CVE-2026-15611) |
| Hosting | **Germany** [O, decided 2026-10-30]; Hetzner excluded by the owner. **IONOS** (Germany), chosen and provisioned by the owner on 2026-10-30; D-8 checks it against the minimum spec below, PITR retention and the IONOS DPA | See 1.2 |
| Mobile CI | GitHub Actions macOS runners or Codemagic for iOS builds | Not on the application server; may add CI cost |

### 1.2 Minimum hosting spec (pilot: 5–10 accounts, ≤ ~1,000 comparisons per month, 2–3 concurrent)

| Component | Minimum | Rationale |
|---|---|---|
| Application VPS (API + worker + share page) | 2 vCPU, 4 GB RAM, 40 GB SSD, public IPv4, Ubuntu 24.04 LTS, x86_64 or ARM64 | 2 concurrent jobs × 512 MB parse cap, plus API, OS and headroom for 40 MP image decoding. No documents on local disk; temporary parse files in `tmpfs` |
| Managed PostgreSQL | 1–2 vCPU, 2 GB RAM, 10–20 GB storage, automated backups with point-in-time recovery, private network only | Avoids self-managed backups and patching for confidential data |
| Object storage | S3-compatible, < 10 GB during the pilot | Originals and screenshots |
| Must-haves | German region, private networking, firewall, snapshots, DPA | Data residency (03 §6) |
| Not recommended | Postgres on the same VPS (would need 4 vCPU / 8 GB / 80 GB plus self-run backups and restore drills) | Ops and security burden |
| Push notifications | Deferred until after v1 (O-18, ADR-0022; I-27). When built: FCM (Android) + APNs (iOS), sending only "comparison ready" with an ID, never content | Comparisons are asynchronous; v1 refreshes status in the app |
| Share page | One server-rendered HTML page from FastAPI, showing the snapshot only | A recipient (the client) may not have the app. This is the only web surface, not a web front end |
| AI | Hosted LLM with structured output; IONOS AI Model Hub, chosen by the owner after D-17 (ADR-0021) | — |
| Testing / CI | Flutter unit, widget and integration tests; pytest; GitHub Actions | — |
| Distribution (pilot) | TestFlight + Google Play closed testing; pilot invoiced directly, no in-app purchase | In-app purchase rules and fees (15–30%) must be checked before a public listing [U] |

## 2. Pipeline

`Import → Parse with provenance → Extract facts → Align → Compare → Verify evidence → Generate report → Human review`

| Stage | Deterministic or AI | Output | Failure handling |
|---|---|---|---|
| Import | Deterministic | Validated source version: original bytes stored immutably, plus hash | Reject over-limit or unsupported input with a named reason (AC-20) |
| Parse | Deterministic | Text blocks with locators (`page`, `char_start`, `char_end`; image region `bbox` for screenshots), each flagged if a reader can't see it or (screenshots) if the two vision passes disagree | Pages with no text layer → partial warning (AC-11). Invisible, tiny, off-page or image-covered text → hidden-text warning (SA-9), and that text is excluded from findings unless the user includes it (AC-18) |
| Extract | AI (structured output, schema-validated) | Extracted facts: type, raw span, normalised value, locator, confidence | Retry once on schema failure. If it fails again, the block is marked *unextracted* and the comparison becomes partial |
| Align | Deterministic keys first, AI for remaining candidates | Fact pairs: matched / unmatched-earlier / unmatched-newer / ambiguous | Ambiguous pairs are never forced (AC-7) |
| Compare | Deterministic for numbers, dates and quantities; AI for meaning, with guards (§4) | Draft findings | Guard violations downgrade the finding to *needs review* |
| Verify | Deterministic | Each evidence quote is an exact substring at its locator. A deterministic block-level diff is cross-checked against the findings; model "equivalent" verdicts do not count as explanations | Unverifiable finding → withheld with a count (AC-9, AC-10). A changed block that no finding covers is listed as an "unexplained difference", so injected text can't silently suppress a change (AC-18) |
| Report | AI for explanation wording only; structure is deterministic | Findings with explanations | If wording generation fails, fall back to a template |
| Review | Human | Review records | — |

Facts are extracted **once per source version** and cached. A new revision compared with the previous one only needs extraction for the new version. This matters for cost (§8).

## 3. Evidence representation

The schemas in §3 and §5 are illustrative, at design level. They are not final definitions.

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

The six logical records from handoff §8, plus supporting records for review, sharing and accounts. **Every table has a `tenant_id` column**, omitted from the field lists below for brevity, and every query is scoped by it (AC-19). The one exception is `User`: a user exists before any tenant and is found by subject on every request, so it is pre-tenant and read only through the narrow identity lookups (§6 Tenant isolation; I-8 S1):
- Postgres row-level security applies to the API *and* the worker. The worker runs under a tenant-scoped role per job, not a role that bypasses RLS.
- As built (I-8 S3): two roles. `changelens_owner` owns the tables and functions, bypasses RLS and is used only by migrations and the dev seed. `changelens_app` is what `api`, `worker` and `retention` connect as: `SELECT`/`INSERT`/`UPDATE`/`DELETE` on the tenant tables, `EXECUTE` on the functions in §6, no rights on `users`, no `BYPASSRLS`; the processes refuse to start as a role that bypasses RLS. Every table with `tenant_id` (14 today) has `ENABLE` and `FORCE ROW LEVEL SECURITY` and one policy for all commands, `tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid` in `USING` and `WITH CHECK`, so with no tenant set nothing matches. Exceptions, checked by a test that lists every table: `users`, `rate_limit_counters` (S6), `apple_token_parks` and `pending_links` (S4), each with RLS on, no policy and no app-role rights, and Alembic's version table.
- Job idempotency keys and fact caches include `tenant_id`.
- Content-hash (`sha256`) deduplication across tenants is forbidden.

| Record | Key fields | Mutability |
|---|---|---|
| Project | id, tenant_id, name, client_label, created_at, deleted_at | Mutable metadata |
| SourceVersion | id, project_id, label, kind, original_object_key, sha256, parsed_text, parse_warnings, user_order_index, scope (complete / partial / unknown), confirmed_at | Immutable after confirm (AC-15) |
| ExtractedFact | id, source_version_id, type, raw_text, normalised_value, locator, status (ok / ambiguous / unextracted), confidence, model_config_id | Immutable |
| Comparison | id, project_id, earlier_id, later_id, scope_snapshot, pipeline_version, model_config_id, status (waiting_for_versions / queued / running / complete / partial / failed), idempotency_key, cost_estimate, cost_actual, warnings | Status only |
| Finding | id, comparison_id, category, topic (derived from category, O-14), change_type, before, after, evidence[], explanation, uncertainty, priority, revision, supersedes_id | New revision on correction |
| ReviewEvent | id, finding_id, actor_id, action (confirmed / corrected / dismissed / note), evidence_mode_before and evidence_mode_after (pdf_highlight / text_fallback / text_only), page_opened, at | Append-only |
| ClientApprovalRecord | id, finding_id, evidence_text_or_object, stated_by, stated_at, recorded_by | Append-only, separate from review (AC-12) |
| SharedReport | id, comparison_id, token_hash, snapshot_json, included_finding_ids, expires_at, revoked_at, view_log | Snapshot never edited; set to null on revocation or expiry (03a P7); revocation state mutable |
| User | id, idp_subject (one Logto subject: a linked Google identity signs in as the same Logto user, D-8 C4), created_at, deleted_at; no `tenant_id` (pre-tenant, see above); no email (S4: `link_required` asks Logto's Management API instead, overview decision 5); apple_refresh_token_enc (I-8 S4: AES-GCM, bound to the user ID, keyring from a secret file; only for Apple sign-in; null on a tombstone) | Deleted users become a tombstone ID, so `actor_id` and `recorded_by` in append-only records stay valid without personal data (03a P8). As built (I-8 S5): the tombstone keeps `id`, `created_at` and `deleted_at`; `idp_subject` is null, allowed only on a deleted user |
| Membership | user_id, tenant_id, role (owner / member), status (active / inactive), created_at | Status and role only; GUARD requires `active` (03a P0). At most one active membership per user (v1 has one tenant per account; partial unique index) |
| AccountOnboarding | account_id, onboarding_step, onboarding_completed_at, updated_at | Step mutable; completion set once. Belongs to `User`: `account_id` is a foreign key to `users.id` (I-8 S1, O-23) |
| AppleTokenPark (I-8 S4) | id, logto_subject (null while a pending link holds it), token_enc (bound to the park ID), created_at, expires_at, next_attempt_at, attempts | No `tenant_id` (pre-tenant). An Apple refresh token from a sign-in with no user row yet (AR-5): attached to the user by the next `POST /session` with a bearer; otherwise after 1 h maintenance revokes it with Apple and deletes it, keeping it until Apple confirms (AR-6) |
| PendingLink (I-8 S4) | id (the `link_id`), provider, provider_subject, target_subject (the Logto user with the same verified email), park_id, created_at, expires_at | No `tenant_id`, no email. `link_required` state for 1 h, used once: deleted on any completion attempt and by maintenance after expiry (03a P1, O-19) |
| AccountDeletion (I-8 S5) | user_id, status (pending / complete), requested_at, next_attempt_at, attempts, idp_deleted_at, completed_at | The account-deletion receipt: IDs, status and timestamps only. Written when the account is frozen; maintenance retries it until complete |
| Invite | id, tenant_id, email, expires_at, consumed_at | Consumed once |
| Device (with I-27, after v1) | id, user_id, push_token, platform | Deleted on logout, removal and account deletion |

Share tokens are stored only as hashes. The share route loads `snapshot_json` alone and has no joins to project data (AC-16).

## 6. Privacy and security boundaries

| Concern | Design | AC |
|---|---|---|
| Prompt injection | Document text is placed in delimited data fields, and the system prompt states that it is untrusted. The model has **no tools** and no network access, and structured output is validated against a schema. The likeliest attacker is the author of the newer version, so the design does not rely on the model alone. Changed numbers, dates and negation are caught by deterministic guards (§4.1). Changed blocks no finding explains are listed (§2, Verify). Hidden text is flagged (§2, Parse). | AC-18 |
| Rendering | All document and model text is rendered as plain escaped text, never as HTML or Markdown, and never auto-linked. A strict CSP is set (no inline scripts, `self` only). Client-approval attachments get the same upload validation and are served only as `Content-Disposition: attachment` from a separate download origin. | AC-18 |
| Logs and telemetry | No parsed text, prompts or model responses go into logs, error-tracking breadcrumbs, metrics or queue payloads. Jobs carry IDs only, and the error tracker scrubs request bodies. A **data inventory** lists every store that holds content: database, object storage, backups, provider. Deletion and retention cover every store on it. | AC-22, AC-23 |
| Link fetching or actions | The pipeline never dereferences URLs found in documents. The worker has no outbound network except the model API and storage. | AC-18 |
| Tenant isolation | `tenant_id` on every row, a scoped data-access layer, row-level security in Postgres as a second layer, and object keys prefixed by tenant. Authorisation tests cover every route. The app role does not own the tables and RLS is `FORCE`d. Pre-tenant lookups (user by subject or email, invites, share token, queue dequeue) go through narrow `SECURITY DEFINER` functions, never the migration role. As built (I-8 S3): `session_lookup`, `session_bootstrap`, `queue_claim`, `queue_reclaim_expired`, `pending_object_writes` and `maintenance_candidates` (later slices add the account-deletion, rate-limit and, in S4, the `apple_park_*`, `pending_link*` and `account_apple_token*` functions), owned by `changelens_owner`, `search_path` pinned, arguments validated, `EXECUTE` for the app role only, returning IDs and scalar fields; queue complete and retry run under the job's tenant (§5 roles). The tenant comes from an active membership, and removed members are rejected on every request (03a P0, P1). Operator access for the pilot is an audited admin path that manages accounts and cannot read document content. | AC-19, AC-26 |
| Share links | Hashed random token, snapshot-only route, expiry and revocation checked on every request. Share pages send these headers: `Cache-Control: no-store`, `Referrer-Policy: no-referrer`, `X-Robots-Tag: noindex`. No third-party scripts, fonts or analytics. The share route is rate-limited per IP. Shares are revoked automatically when the owning account or member is removed. Share creation, revocation and views are audit-logged. | AC-16, AC-17 |
| Model provider | IONOS AI Model Hub, Qwen/Qwen3.5-397B-A17B, is the primary and only comparison model for v1 [O, decided 2026-10-31; ADR-0021]. Per the vendor documentation checked on 2026-10-30 (06), processing stays in Germany, prompts and outputs are never logged or stored, and there are no sub-processors; abuse monitoring is not mentioned [U]. There is no fallback model: if the model is unavailable, the job retries briefly and the comparison then fails, for the user to start again; it is never answered by a weaker model. Send only the parsed text blocks needed, never original files or account data. The AI processor is disclosed to users in the privacy policy (I-20). | — |
| Mobile client | Tokens only in Keychain / Keystore (`flutter_secure_storage`). No document content cached on the device; opened PDFs stream from signed URLs into memory. Screenshots taken in-app are not saved to the photo library. The share extension hands the file to the app through the app-group container; the app uploads it and deletes the container copy, picker cache and camera temp files after upload and on start (03a P10). Certificate pinning is optional [A]. App Store privacy labels and the Play data-safety form must match the data inventory | AC-22, AC-23 |
| Real client data gate | Synthetic or consented data only, until all of these are in place: signed pilot terms that include an **Art. 28 GDPR processor agreement** with each agency (including deletion or return at contract end); the freelancer's obligations to *their* client (confidentiality, disclosure of the AI processor); a published sub-processor list generated from the data inventory (hosting, IdP, model provider, error tracker, email sender, CI, and FCM/APNs with I-27); transfer assessments for any non-EU processor; and D-7 complete. The D-9 runbook notifies the affected agency without undue delay through a named contact, so the agency can meet its 72-hour Art. 33 deadline. | AC-22, AC-23 |
| Secrets and supply chain | The LLM key, database and S3 credentials, APNs/FCM keys (with I-27, after v1), signing keys, the Apple client-secret key (.p8), the encryption key for stored Apple refresh tokens, and the Logto Management API credential (which can link identities and delete users, so it is held only by the `api` and `retention` modules) live in a managed secret store or CI environment secrets (as built, I-8 S4: the Google client secret, the `.p8` key and the Apple-token keyring are files named by `CHANGELENS_GOOGLE_CLIENT_SECRET_FILE`, `CHANGELENS_APPLE_PRIVATE_KEY_FILE` and `CHANGELENS_APPLE_TOKEN_KEYS_FILE`; key rotation adds a key and keeps old ones for decryption), each with least privilege and scoped per environment, and never in the repository or the app bundle. GitHub Actions are pinned by commit SHA; lockfiles are committed and dependency-scanned in CI. PDFium (`pypdfium2` on the server, `pdfrx` on the device) and the image decoders parse attacker-authored files, so their security updates ship within 7 days on both server and app. The self-hosted Logto instance is internet-facing and gets the same 7-day rule, plus daily database backups and a restore test before the pilot (ADR-0020). | AC-18, AC-20 |
| Abuse and cost exhaustion | The per-tenant monthly spend cap (counting failed runs and screenshot parses) and the global monthly spend cap that acts as the kill switch (§8, SA-4), the per-comparison cost ceiling, per-account and per-IP rate limits, and a cap on signups per IP are built into the app skeleton (I-8), before any external user. As built (I-8 S6), all config values: EUR 5 per tenant and EUR 50 overall per UTC month, counting actual costs and open reservations of comparisons and of deleted comparisons' cost tombstones; 60 requests per minute per account, 20 per minute per IP for failed authentication and `POST /session`, 5 new accounts per IP per UTC day. Counters live in Postgres, keyed by an HMAC of the account or IP (never a raw address), and `X-Forwarded-For` is believed only from a configured trusted proxy. MFA is offered, sessions expire, and an incident-response runbook is ready before the pilot. | AC-21 |
| Storage | Encryption at rest (assumed provider default [A]; verify in D-8), originals in a private bucket, signed short-lived URLs for owner download. | — |
| Retention and deletion | Documents and comparisons expire 30 days after their last use [O, 2026-10-31]. Opening a report/source or an explicit import, comparison or review counts as use; background polling does not [O, 2026-11-07]. Opening/reviewing a comparison extends both input sources; opening one source extends only that source. A source needed by a retained comparison is kept. Empty project metadata is retained until explicit project deletion. Deletion purges primary rows and every object version; a pending cleanup must not be reported as complete. The backup/PITR target is at most 30 days, subject to deployment verification. See [data inventory](data-inventory.md) for coverage and unresolved stores. | AC-22 |
| Upload validation | Check MIME type and magic bytes. Enforce size limits, and check page count from metadata *before* full parsing. Parse in a sandboxed process with no network and caps of 60 s CPU, 512 MB memory and 5 MB extracted text [A]. Never execute PDF JavaScript or extract embedded files. For images, cap decompression and pixel count (≤ 40 MP). | AC-20 |
| Claims | No compliance claims (GDPR certification, SOC 2) are made until they are verified. The pilot uses only synthetic data or data with consent. | — |

## 7. Failure handling

- Comparison states are `complete`, `partial` or `failed`. A partial result always lists what was skipped (AC-11).
- Each stage retries once for schema or transient errors. After that the comparison is marked failed with a user-facing reason, and no misleading partial report is shown.
- Jobs are idempotent and keyed by `(earlier_id, later_id, pipeline_version, model_config_id)`. A retry never duplicates findings.
- If model output fails verification, that finding is withheld. The comparison still completes and shows the withheld count.

## 8. Cost model [A]

Prices from D-7 (2026-10-30): Claude Sonnet 5.5 on AWS Bedrock, EU geo profile from eu-central-1, USD 2.20 / 11.00 per million input / output tokens, so `p_in = €1.97`, `p_out = €9.85` at the ECB rate of EUR 1 = USD 1.1172 (06, D-7 comparison). The earlier placeholders were €3 / €15. Token counts are still estimates [A], not measured with Claude's tokenizer, which can count up to ~30% more tokens; the script prints that case too.

**What these figures are.** They are a conservative budgeting case, not a forecast and not the provider in use. D-17 led to IONOS (ADR-0021), and Bedrock is not implemented. The Bedrock prices stay as the defaults because they are about 3× the IONOS list prices recorded on 2026-10-30 (€0.60 / €3.60), so every gate is tested with headroom. At those IONOS prices the same token estimates give ≈ €0.026 typical and ≈ €0.096 heavy before retries (06), which is also an estimate. The 14748b6 baseline in `scripts/cost-model.ps1` stores token counts: it catches a design that uses more tokens and is not a record of spend.

**Measured IONOS cost.** The second I-7 held-out look (`scripts/eval/i7_receipt.json`, 46 pairs × 2 runs, each from an empty fact cache) gives p50 €0.0051 and p90 €0.0061 per comparison. Its constructed briefs are about 100 words (06), a few percent of the typical brief below, so this does not measure the 3,000-word case. No heavy document or screenshot has been measured. Real usage comes from I-14.

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
| Typical (3k words, earlier cached) | 17k / 4.5k | 10% | **≈ €0.086** (≈ €0.11 at +30% tokens) | |
| First comparison (both extracted) | 22k / 6k | 10% | ≈ €0.11 (≈ €0.15) | |
| Heavy (20 pages ≈ 15k words) | 70k / 15k | 20% | ≈ €0.34 (≈ €0.45) | At the input cap |
| Worst case (heavy, both extracted, every stage retried once) | 100k / 22k | 100% | ≈ €0.83 (≈ €1.08) | The hard ceiling (AC-21) should stop beyond ≈ €1.50 |
| Screenshot vision parse (per image, two independent passes, SA-9) | 3k / 1k | 10% | ≈ €0.017 | Charged as 1 allowance unit (03a P2) [U: image token counts vary by provider] |

**Monthly cost per account (sensitivity):**

| Usage | Comparisons per month | Mix | Model cost per month | vs €12 individual / €49 team |
|---|---|---|---|---|
| Light freelancer | 10 | typical | ≈ €0.9 | 7% of €12 |
| Heavy freelancer | 40 | 75% typical / 25% heavy | ≈ €6.0 | 50% of €12 — needs an allowance |
| Small team | 120 | 75 / 25 | ≈ €18 | 37% of €49 — needs an allowance |

These figures exclude hosting (≈ €20–60 per month flat at pilot scale [A]), storage (originals plus parsed text ≈ 1–5 MB per version, so under €0.10 per account per month at object-storage rates [A]), payment fees (≈ 1.5–3% + fixed fee [U]), support time and acquisition.

**Implications:**
- Each plan needs a comparison allowance, for example 25 per month for individuals and 100 per month for teams [O].
- Heavy documents (over 5,000 words) count as **4** comparisons, which matches their roughly 4× cost.
- Failed comparisons do not count against the allowance. Partial ones do. Failed-run cost is tracked as overhead. To stop free failed runs from being abused (SA-4), every run's cost, failed or not, counts toward a per-tenant monthly spend cap (default 3× the plan's expected allowance cost), and a global monthly spend cap (EUR 50, 06 2026-11-13) acts as the kill switch and pauses new comparisons and screenshot parses when reached; a screenshot's reserved unit is consumed even if its parse fails.
- **At D-7 prices the pilot's discounted prices (€9 / €39) cover full-allowance usage within 30%:** 25 typical comparisons cost about €2.15, 24% of €9 (about 31% at +30% tokens, so borderline). The unit-economics gate (04 §6, Gate 4) is still judged against **target** prices.
- The pilot must measure real token usage per comparison (I-14) and replace these token estimates.
- `scripts/cost-model.ps1` recomputes this table and fails if a scenario is worse than the reviewed baseline (14748b6) or breaks a cost gate. At D-7 prices, a full allowance costs about 18% of target price for follow-up revisions and about 23% if every comparison is a new project (REV-19, REV-20 resolved).

## 9. Modules, interfaces and data flow

These are design-level contracts. Names are illustrative; the shapes and boundaries are what the decisions in §9.6 fix.

### 9.1 Backend modules (one Python package, two process types: `api` and `worker`)

| Module | Responsibility | Depends on | Must not |
|---|---|---|---|
| `api` | FastAPI routers, JWT verification against the identity provider, `POST /session` bootstrap, membership and tenant resolution (GUARD), team routes (invite, remove, transfer ownership), request validation, problem+json errors | `domain`, `storage`, `metering`, `jobs` | Call the model provider or parse documents in-request |
| `share_page` | Server-rendered read-only page for `/s/{token}` | `domain` (SharedReport only) | Join to any table other than SharedReport (AC-16) |
| `domain` | SQLAlchemy models (03 §5), tenant-scoped session (`SET LOCAL app.tenant_id`), repositories | Postgres | Expose a session without a tenant |
| `storage` | Object-store adapter: put original, short-lived signed URL, delete by tenant/project prefix | S3-compatible store | Write document content to local disk |
| `jobs` | Enqueue and consume Postgres-queue jobs with ID-only payloads; idempotency key `(tenant_id, kind, ids, pipeline_version, model_config_id)` | Postgres | Carry document content in payloads (AC-23) |
| `worker` | Runs `parse` and `compare` jobs: loads records, calls `pipeline`, persists results, records cost; triggers `notify` after v1 (I-27) | `domain`, `storage`, `pipeline`, `metering`, and `notify` after v1 | Run a stage outside the cost ceiling (AC-21) |
| `pipeline` | Pure stage functions (§9.3). No database, storage or network access except through the `llm` port passed in | `llm` port | Hold state; read ambient config |
| `llm` | Provider adapter: one structured-output call with a schema, a system prompt and delimited data blocks; no tools; per-call token accounting | Provider SDK | Fetch URLs; enable tool use; log prompts or responses (AC-18, AC-23) |
| `metering` | Allowance check before enqueue, heavy-document weighting, per-comparison ceiling during a run, per-tenant monthly spend cap and global kill switch (incl. screenshot parses) | `domain` | — |
| `notify` | After v1 (I-27): content-free push via FCM / APNs (comparison ID plus generic text) | Device registry | Include document text (AC-25) |
| `retention` | Project, account and tenant deletion cascades (incl. IdP user deletion and Apple token revocation), version-aware object purge, share revocation and snapshot purge, data inventory checks | `domain`, `storage` | — |

Reuse: `llm`, the `verify` stage and log scrubbing follow the patterns in `mobile-engineering-intelligence` (06, "Prior art and reuse").

### 9.2 Mobile modules (Flutter, feature-first)

| Module | Responsibility |
|---|---|
| `core/api` | Dio client generated from the backend OpenAPI schema; attaches the access token; maps problem+json errors to typed failures |
| `core/auth` | Identity-provider SDK (email code, Google, Apple), token refresh, `flutter_secure_storage` |
| `features/projects` | Project list, create, delete |
| `features/import` | Paste, PDF picker, camera / photo library; receives share-intent hand-offs; uploads; keeps no local copies (AC-25) |
| `features/compare` | Pick the earlier and newer version, confirm scope (AC-14), start the comparison, show status (polling in v1; push after v1, ADR-0022) |
| `features/report` | Prioritised findings, needs-review group, withheld count, unexplained differences, full-difference view (AC-10, AC-13, AC-18) |
| `features/evidence` | `pdfrx` page view with highlight overlays from locators; parsed-text fallback; image region view for screenshots |
| `features/review` | Confirm / correct / dismiss, notes, separate client-approval record (AC-12) |
| `features/share` | Select findings, create link (shown once), list and revoke shares |
| iOS `ShareExtension` (Swift) / Android `ACTION_SEND` | Receive a file or text from another app, hand it to `features/import` through an app-group container or intent, then delete it (AC-24, AC-25) |

### 9.3 Pipeline stage interfaces

Each stage is a pure function, and the worker persists every output. The same functions therefore run in the script prototype (option A) and in the product (option B).

| Stage | Input | Output | Kind |
|---|---|---|---|
| `parse` | original bytes, kind (text / pdf / image), limits | `ParsedDocument`: parsed text, blocks with locators and a visibility flag, warnings | Deterministic (`pypdfium2`); vision-model call for images through the `llm` port |
| `extract` | `ParsedDocument`, `llm` port | list of `ExtractedFact` (type, raw span, normalised value, locator, status, confidence) | AI, schema-validated |
| `align` | earlier facts, newer facts, `llm` port | list of `FactPair` (matched / unmatched-earlier / unmatched-newer / ambiguous) | Deterministic keys, then AI candidates |
| `compare` | pairs, newer-version scope, `llm` port | list of `DraftFinding` | Deterministic guards (§4.1), omission table (§4.2), AI for meaning only |
| `verify` | drafts, both `ParsedDocument`s, block-level diff | verified findings, withheld count, unexplained differences | Deterministic |
| `report` | verified findings, `llm` port | findings with explanations and priority | AI wording, template fallback |

### 9.4 API surface (REST + JSON, OpenAPI)

Every route except `/s/{token}` needs a bearer JWT. The tenant comes from the user's active membership (03a P0), never from the request body; `POST /session` is the only authenticated route outside GUARD.

| Method and path | Purpose | Notes |
|---|---|---|
| `POST /projects`, `GET /projects`, `GET /projects/{id}` | Create, list, read projects | — |
| `DELETE /projects/{id}` | Delete project | Triggers `retention` (AC-22) |
| `POST /projects/{id}/versions` | Upload a version (multipart file or text, plus label) | Limits and magic bytes checked before storing (AC-20); enqueues `parse` |
| `GET /versions/{id}` | Version metadata, parse status and warnings | — |
| `GET /versions/{id}/original` | Short-lived signed URL for the original | Streamed into memory by the app (AC-25) |
| `GET /versions/{id}/text` | Parsed text with block locators | Evidence fallback |
| `POST /projects/{id}/comparisons` | Body: `earlier` and `later` (each an existing version ID or a new upload or paste with a label) and `scope`, plus an `Idempotency-Key` header. One request creates any new versions and the comparison (O-15) | This call *is* the user's order and scope confirmation (AC-14). A retry with the same key returns the same comparison and creates nothing. An early allowance check rejects with `allowance_exhausted`, but nothing is charged until processing starts (AC-21). Returns 202 with an ID |
| `GET /comparisons/{id}` | Status (waiting_for_versions / queued / running / complete / partial / failed), warnings; a failed comparison names the rejected version and its reason | Polling (the only status path in v1) |
| `GET /comparisons/{id}/findings` | Prioritised, needs-review, all differences, withheld count, unexplained differences, each finding's topic and the per-topic counts (O-14) | — |
| `POST /findings/{id}/reviews` | Confirm / correct / dismiss / note, with `evidence_mode` per side and `page_opened` (O-17); a dismissal carries `dismissal_reason` (`reworded`, `wrong_passage`, `irrelevant`, `other`; required with `dismissed`, refused with any other action, no default; WP-C, owner 2026-11-16) | A correction creates a new finding revision (AC-15). A dismissal never changes the finding or its change type; the finding stays in the report |
| `POST /findings/{id}/client-approvals` | Record external approval evidence | Separate record; never set by a review (AC-12) |
| `POST /comparisons/{id}/shares` | Create a snapshot from selected finding IDs, with expiry | Token returned once; only its hash is stored |
| `GET /comparisons/{id}/shares`, `DELETE /shares/{id}` | List and revoke | AC-17 |
| `GET /s/{token}` | Read-only share page (HTML) | Headers per §6; rate-limited |
| `POST /devices`, `DELETE /devices/{id}` | Register or remove a push token (after v1, I-27) | — |
| `POST /session` | Bootstrap after IdP sign-in: runs 03a P1. **With a bearer** (the Logto access token): no body, `{}` or `{"link_id"}` (anything else is `invalid_request`). Built for email one-time code (I-8 S2) and the second half of Google and Apple (S4). **Without a bearer** (S4): native Google or Apple sign-in, `{"provider": "google" \| "apple", "code", "nonce"?}`, the provider's authorization code from the native SDK and, for Apple, the raw nonce whose SHA-256 the app gave Apple. Invites are not built in v1 | The only route outside GUARD. With a bearer: the first call for a subject creates the user, a new tenant and an owner membership; later calls return the same account; a parked Apple token is attached to the user. With `link_id`, the pending link's identity is linked to this user through the Logto Management API first, only if this user is its target, before expiry and once; anything else is `unauthenticated` and the link is deleted. `200 {"status": "active", "onboarding": {"completed", "step"}}`, the onboarding object read in the same transaction (O-23); no IDs, subject, email or tenant. A deleted user or a user without an active membership is `unauthenticated`. Without a bearer: the backend exchanges the code once and verifies the ID token (signature, issuer, audience, expiry, nonce; email only when verified). `200 {"status": "sign_in", "one_time_token", "login_hint", "expires_in": 120}` when the identity is on a Logto user, or a new Logto user was just created with it (sign-up cap first): the app redeems the single-use token in Logto's sign-in with `one_time_token` and `login_hint` (the account's own email), where MFA applies, then calls `POST /session` with the bearer. `200 {"status": "link_required", "methods": ["email", ...], "link_id"}` when the identity is new and a Logto user has the same verified email: nothing is signed in or created; the user signs in with a listed method and sends `link_id`. A bad, reused or unverifiable code is `unauthenticated`; a provider or Logto failure is `503 provider_unavailable` with `Retry-After`. Step-0 finding: 06, 2026-11-16 |
| `DELETE /me`, `DELETE /team` | Delete own account; delete the whole team (owner) | In-app account deletion (Apple 5.1.1(v)); cascades through 03a P8 incl. the IdP user. As built (I-8 S5): `DELETE /me` under GUARD, no body; `204` when every step finished, `202` while one is pending (maintenance finishes it); the app treats both as signed out, and the same token is `unauthenticated` from the next request. `DELETE /team` is not built: v1 has no teams |
| `POST /team/invites`, `DELETE /team/members/{id}`, `POST /team/owner` | Invite a member; remove a member; transfer ownership | Owner (or operator for the owner) only; removal deactivates the membership, revokes IdP sessions, device tokens and the member's shares (03a P1) |
| `GET /me/usage` | Allowance used and remaining | — |
| `GET /me/onboarding`, `PUT /me/onboarding` | Read or write the account's onboarding state (O-23): `{"completed": bool, "step": int or null}`. `PUT` takes exactly one of `{"step": n}` (1–32) or `{"completed": true}` and returns the same object | No row reads as not started. Completion is set once and wins over any step write; later writes return the completed state. Other bodies get `invalid_request`. The Projects-menu replay never calls these |

Errors use problem+json with stable codes: `limit_exceeded`, `unsupported_type`, `allowance_exhausted`, `spend_cap_reached`, `scope_not_confirmed`, `not_found`, `unauthenticated`, `unsupported_method`, `link_required`, `rate_limited`, `provider_unavailable` (`503`, I-8 S4; `link_required` is a `POST /session` status, not an error). `spend_cap_reached` and `rate_limited` are `429`; `rate_limited` carries `Retry-After` (I-8 S6). Resources in another tenant return `not_found`, never `forbidden`, so their existence isn't revealed (AC-19).

### 9.5 End-to-end data flow

1. **Import.** The app calls `POST /projects/{id}/versions` (from paste, picker, camera or the share extension). The API checks limits and type, stores the original under a tenant-prefixed key, writes `SourceVersion(status=uploaded)` and enqueues `parse(version_id)`.
2. **Parse.** The worker runs the sandboxed parse, producing parsed text, blocks, locators and warnings. Status becomes `parsed`, or `rejected` with a reason.
3. **Compare screen.** The user fills both slots (existing versions or new imports), the scope and the project, then presses Start. The app sends one `POST /comparisons` with an idempotency key. New versions are stored and their `parse` jobs enqueued as in step 1. If either version isn't `parsed` yet, the comparison is written as `waiting_for_versions`; otherwise it is written as `queued` and `compare(comparison_id)` is enqueued. When the last parse finishes, the worker moves a waiting comparison to `queued` and enqueues `compare`, or to `failed` with the rejected version's reason. `metering` charges the allowance when the compare job starts (queued → running), so waiting and early failures are free (O-15).
4. **Compare.** The worker uses cached facts or runs `extract`, then `align`, `compare`, `verify` and `report`, all under the cost ceiling. It persists findings, cost and the final status. In v1 the app picks this up by polling; after v1, `notify` also sends a content-free push (I-27).
5. **Inspect.** The app fetches the findings, the original's signed URL and the locators. `pdfrx` highlights the passages, with the parsed text as fallback; the app records which mode each side was shown in (O-17).
6. **Review.** Review events are appended, corrections create new revisions, and client approval is recorded separately.
7. **Share.** The API builds an immutable snapshot of the selected findings and their excerpts and returns the token once. The recipient opens `GET /s/{token}`.
8. **Delete.** `DELETE /projects/{id}` cascades, purges the object prefix and revokes shares; backups expire within 30 days.

### 9.6 Architecture decisions

Each AD-n has an ADR in `docs/adr/` (index and change process in `docs/SOP.md`). `scripts/check-trace.ps1` fails if one is missing.

| ID | Decision | Alternatives rejected | Why |
|---|---|---|---|
| AD-1 | Modular monolith: one Python package, two process types (`api`, `worker`) | Microservices; serverless functions | Pilot scale; one deployment and one database to secure (§1) |
| AD-2 | Pipeline stages are pure functions; the worker owns persistence | Stages reading and writing the database directly | The same code runs on the evaluation set (Gate 2) and in production; stages can be tested in isolation |
| AD-3 | Uploads go through the API, not presigned straight to storage | Presigned S3 uploads | Limits, magic bytes and type are checked before anything is stored (AC-20); volumes are small |
| AD-4 | Parse is a separate job from compare, and facts are cached per version | Parsing inside each comparison | Lowers cost per revision (§8); parse warnings reach the user before the comparison |
| AD-5 | REST + JSON with an OpenAPI-generated Dart client | GraphQL; gRPC | Simple to test and document; a typed client with no extra infrastructure |
| AD-6 | Cross-tenant access returns `not_found` | Returning `forbidden` | Doesn't reveal that a resource exists (AC-19) |
| AD-7 | Share tokens shown once and stored only as hashes; the share page reads snapshots only | Reusable stored tokens; a live project view | A database leak doesn't expose links; snapshot isolation (AC-16, AC-17) |
| AD-8 | Polling for comparison status in v1; content-free push deferred until after v1 (ADR-0022) | WebSockets; push in v1 | Polling already works with notifications disabled and needs no device registry; push returns as I-27 |
| AD-9 | `llm` port injected into stages; provider adapter swappable | Calling a provider SDK directly inside stages | The provider is decided (ADR-0021) and the port keeps it replaceable; fixtures can stub it for deterministic tests |
