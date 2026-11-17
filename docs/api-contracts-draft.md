# Draft API contracts: timeline, allowance, D-18 feedback

**Status: owner-approved policies; operational contract specified for review (2026-11-16).**
O-25–O-28 in 06 (the private decision log) record the approved policies. This revision specifies their
remaining details: heavy classification, history paging/cap recovery, queue/refund accounting and
survey eligibility/offer. These are concrete contract defaults, not additional owner approvals.
This task changes documentation only; runtime implementation and verification belong to a subsequent
task. At implementation, reconcile 03 §9.4/§5, 03a and the data inventory with this contract.
It covers WP-D (P6 timeline), WP-E (allowance), WP-F feedback and the gated consent screen.

Conventions are the same as the built API: bearer JWT under GUARD, tenant from the membership,
snake_case fields, ISO 8601 UTC timestamps, problem+json errors with stable codes, another
tenant's resource returns `not_found`, and error bodies never echo input. Every change below is
**additive**: no existing field changes type or goes away.

---

## A. Comparison relationships (P6 timeline)

### Decided (owner, 2026-11-16): A1, the order comes from comparisons only

Every comparison is already a user-confirmed edge `earlier_id → later_id`. Creating it *is* the
order confirmation (AC-14, O-15). The timeline is therefore **derived from comparisons only**.
Upload time, labels and filenames are never used (ui-ux-handoff, Timeline row).

There is one read endpoint and no new relationship table. A version that has never been compared
appears as "not placed yet". Ordering it means comparing it, which also gives the user a report and
costs allowance units (B). The owner accepted that ordering = comparing. An explicit `relationships`
resource (the former A2) is not built: it would be a second source of truth that can contradict the
comparisons.

### `GET /projects/{project_id}/timeline?limit=50&cursor=…`

```jsonc
200 {
  "project_id": "uuid",
  "revision": "opaque",
  "version_capacity": { "limit": 200, "retained": 2, "pending": 0, "remaining": 198 },
  "versions": [
    {
      "id": "uuid", "label": "Brief v2", "kind": "pdf", "status": "parsed",  // existing version fields
      "created_at": "…",
      "rank": 1,            // 0-based layer from confirmed edges (longest path from a root); null = see below
      "in_conflict": false  // true when the version sits on a cycle (A→B and B→A both confirmed)
    }
  ],
  "relationships": [
    {
      "comparison_id": "uuid",
      "earlier_id": "uuid", "later_id": "uuid",
      "status": "complete",          // comparison status, unchanged enum
      "scope": "complete",
      "created_at": "…",
      "is_latest_for_pair": true     // several comparisons of the same pair: only the newest is true
    }
  ],
  "pagination": { "limit": 50, "next_cursor": null }  // null = no more relationships
}
```

Rules:

- `versions` lists every version of the project, in created order. A version is **not placed** when
  it is in no relationship: `rank: null` and `in_conflict: false`. A version on a cycle has `rank: null`
  and `in_conflict: true`. There is no separate list of unplaced IDs.
- Rejected versions, comparisons that failed because a version was rejected, and **retracted
  comparisons** are left out. Other failed comparisons stay in, because the order was still confirmed.
  The app shows their status.
- `rank` only lays the graph out. It never claims a version is "newer" beyond the confirmed edges.
  Branches (v2 → v3a, v2 → v3b) share a rank. For a cycle the app asks the user which comparison is
  wrong and retracts it (below). The server never picks one.
- **Provisional launch cap: 200 retained versions per project (O-25).** Pending imports reserve slots;
  rejected versions release theirs. Existing versions reused in a comparison need no new slots.
  Count and reserve capacity atomically per project on **both** version-creating paths:
  `POST /projects/{id}/versions` and inline uploads in `POST /projects/{id}/comparisons`.
  If all new versions in a request would not fit, return `409 version_limit_reached` and write nothing.
  (Not `limit_exceeded`: that code is always `413` for the size of one input today.) Rejected uploads
  remain subject to storage cleanup and abuse controls; releasing a slot is not unlimited storage.
- `version_capacity.retained` counts parsed, non-rejected versions; `pending` counts reserved import
  slots, including uploads/parse jobs not settled yet, without double-counting their version rows.
  `remaining = max(0, limit − retained − pending)`. Include the same object in `version_limit_reached`.
- **Page relationships, not graph meaning.** `limit` is an integer from 1 to 100, default 50. Use
  keyset order `(created_at DESC, id DESC)`. A signed opaque cursor binds the tenant, project, limit,
  revision and last returned key. Bad/tampered/mismatched cursors return `422 invalid_cursor`;
  invalid limits return `422 invalid_request`. Resolve project access first (`not_found` across tenants).
- Each page contains the complete bounded `versions` list. Compute ranks/cycles from all applicable
  distinct directed edges, and latest-for-pair from all eligible comparisons, never just one page.
  A missing edge on this page does not mean a version is unplaced. P6 uses this paged route for its
  timeline/history; it must not also fetch the legacy unbounded comparisons list to fill the screen.
- Store a monotonically increasing `projects.timeline_revision`; increment it transactionally for
  version/comparison creation, capacity reservations, relevant status changes, retraction and
  retention/deletion affecting this response. Read a page and its graph metadata from one database snapshot. If a cursor's revision
  has changed, return `409 timeline_changed`; the client discards accumulated pages and starts again.
  No silent page truncation or omission of older relationships; `next_cursor: null` ends the list.
- **At the cap:** keep reading and comparing existing versions available. Show "Create another
  project to add more versions", using existing `POST /projects`, then the existing upload/compare
  routes. The user explicitly names the new project and imports their chosen baseline and new input
  again; no automatic choice of the newest version, cross-project comparison, move or deletion.
  Explain that the new project has its own timeline, and the old one remains under normal retention
  (30 days after last use); this is not indefinite archiving. Rejected imports do not silently create
  a second project. Revisit the 200 limit using observed project sizes and performance.
- The **"Compare v2 → v3" shortcut stays client-only**: it pre-fills P2 with two version IDs the
  user tapped, then the existing `POST /projects/{id}/comparisons` runs. No new write endpoint.
- Errors: `not_found` (unknown or other tenant's project), `unauthenticated`.

### `POST /comparisons/{comparison_id}/retraction` → `204`

Takes a comparison off the timeline. It is how the user resolves a cycle, and how they undo an order
they confirmed by mistake.

- No body. Repeating it returns `204` again and changes nothing.
- The comparison and its report stay readable through the existing routes. `GET /comparisons/{id}`
  gains `"retracted_at": "…" | null`.
- Retraction itself never refunds allowance. A server-failure refund under B remains valid even if
  that comparison is subsequently retracted.
- Once one edge of a cycle is retracted, the versions on it get a `rank` again and `in_conflict: false`.
- There is no "un-retract". Comparing the pair again creates a new edge.
- Errors: `not_found` (unknown or other tenant's comparison), `unauthenticated`.
- Storage: one nullable `retracted_at` column on `comparisons` (a migration, no new table).

---

## B. I-14 fair-use allowance

The allowance belongs to the **tenant**, like the spend cap. In v1 one account is exactly one tenant,
so `/me/usage` reads the caller's tenant. If shared tenants arrive later, this section must say whether
teammates share it.

### Heavy classification

A comparison is heavy when **either parsed version has more than 5,000 words**, adopting 03a P5
(line 194) and 03 §8. Use the existing `ParsedDocument.word_count()` definition: sum `len(page.split())`
over the canonical parsed pages, with Python's Unicode-whitespace splitting, before model extraction.
Exactly 5,000 words is standard; 5,001 is heavy. Two 3,000-word versions are standard; two heavy
versions still cost 4 units, not 8. Page count/bytes remain input limits, not alternative heavy tests.
Classify once after parsing and store the class and charged weight; cache hits/retries do not reprice it.

### `GET /me/usage` (already named in 03 §9.4, shape is new)

```jsonc
200 {
  "period": { "start": "2026-11-01T00:00:00Z", "resets_at": "2026-12-01T00:00:00Z" },  // UTC calendar month
  "allowance": {
    "limit": 20, "replacement_units": 0, "used": 7,
    "reserved": 2, "remaining": 13, "available": 11
  },  // all values are units; remaining/available never below 0
  "weights": { "standard": 1, "heavy": 4 },                   // from config, so the app never hard-codes them
  "heavy_threshold_words": 5000,                             // strictly greater than this value
  "state": "available"   // "available" | "exhausted" | "paused"
}
```

- `paused` means the tenant spend cap or the global kill switch is reached. The app says comparisons are
  paused and shows no amount and no reason beyond that. No euro value is exposed here.
- Period settings (`limit`, weights and threshold) are snapshotted from config on first use of that
  tenant/UTC month. Config changes apply to new periods without repricing existing charges/reservations.
- `used = charged − refunded` in this period; `replacement_units` is compensation for late refunds
  from earlier periods (below), not ordinary rollover. `remaining = max(0, limit + replacement_units
  − used)`; `reserved` is the sum of outstanding minimum reservations; `available = max(0, remaining
  − reserved)`. Show replacement units separately with their expiry at this period's `resets_at`.
  `state` is `paused` when a spend cap applies, otherwise `available` if `available ≥ standard`, else
  `exhausted`. Reserving the last unit can therefore make the state exhausted before it is charged.
- **Which month a charge counts in:** the month of the comparison's **creation time**, the same rule as
  the spend cap (`domain/spend.py`). A comparison created on 30 Nov and charged on 1 Dec counts in
  November. Both allowance checks and ledger entries use that stored period, including late workers.
  For a closed period, subtract `transferred_refunds` (refunds paired with a replacement credit in a
  later period) when computing its spendable remaining units: `max(0, limit + replacement_units
  − used − transferred_refunds)`. Otherwise both an old queued job and a new-month job could spend
  the same returned units. The current-period `/me/usage` formula above has no outgoing transfers.
  Financial spend remains governed by the existing spend-cap rules; a unit refund never reduces it.

### Charging rules (O-26 and O-27 policies; specified accounting)

| Event | Allowance effect |
|---|---|
| `POST …/comparisons` accepted (202) | Reserve `standard` units, no charge yet; insufficient available units → `429 allowance_exhausted`, or `spend_cap_reached` when paused |
| Input rejected (unsupported, oversize, no text) | None (AC-21, Status row) |
| Worker starts the first paid stage | Check `remaining ≥ standard`, then charge `heavy` if either version is heavy (O-8), else `standard`. Serialise the check and charge across workers for the same tenant and allowance period |
| Server-side failure after charging, terminal after retries are exhausted | Automatically restore the original charge exactly once; actual provider expenditure still counts toward financial spend caps |
| Successful comparison, including a report with no changes | Charge stands |
| Clearly disclosed, usable partial report | Charge stands, following 03 §8; do not classify a failed run as partial merely to retain its charge |
| Comparison retracted | None. No refund |
| Idempotent retry of the same key | No second charge (same comparison). The retry returns before any check, as today |

**Admission and queue reconciliation.** Lock the tenant's allowance-period row before project and
comparison rows, in the same order on every path. Admission checks `available ≥ standard` and inserts
one reservation per comparison in the creation transaction. Idempotent replays return the existing
comparison without another reservation. A rejected input/terminal uncharged run releases its hold.

Charge the oldest **ready, uncharged** comparison by `(created_at, id)` in that tenant/period; a version
still parsing is not ready and does not block others. Workers that claim later jobs yield without paid
work or consuming a retry attempt. Under the period lock: check the financial caps and remaining units,
replace the selected hold with its single standard/heavy charge, then reconcile other holds before commit.
If their total exceeds the new `remaining`, remove holds newest-first `(created_at DESC, id DESC)` until
it fits; those comparisons become `failed(allowance_exhausted)` without a charge or paid stage. This
can include waiting-for-version comparisons. Waking workers/parse completions must not resurrect them.
Already charged work is unaffected. A refund makes capacity available again but never restarts a failed
comparison automatically. `202` promises admission with a minimum hold, not guaranteed heavy-run capacity.

**Grace overdraw (O-26).** A worker with at least `standard` units remaining may charge a heavy run
even when fewer than `heavy` remain. One charge can cross the limit by at most `heavy − standard`
units; while `remaining` is 0, no further run is charged. With limit 20 and weights 1/4, net usage **after
replacement credits** is bounded at 23 units (15% grace), and `remaining` shows 0. In general,
`used ≤ limit + replacement_units + heavy − standard`. This is a free allowance extension: no monetary
charge, no debt and no deduction from next month's allowance. The financial spend caps still apply.
A queued comparison that finds nothing left fails with `allowance_exhausted` and no charge.
A refund reduces the original period's `used`; the bound concerns net usage, not gross attempts.
Example: with 3 units remaining and three 1-unit holds, the oldest ready heavy run charges 4; the other
two holds are released and their runs fail uncharged. Concurrent workers cannot each grant grace.

**Failure refunds (O-27).** Provider outages, worker failures and internal processing errors that
prevent delivery of a report restore the original units automatically after the run is terminal and
retries are exhausted. A server cost/spend-cap stop without a usable report follows the same rule.
Refund the full original charge against its original comparison/period, exactly once. If that period
has ended, the same transaction also grants the same number of **replacement units in the current UTC
month**. They expire at that month's end; unused ordinary units do not roll over. This compensation
can include a heavy run's grace units and is therefore shown separately from the 20-unit base allowance.
Lock the original/current period rows in ascending period order, then the comparison; use one server
timestamp for the target period and refund time. Replaying a refund returns its existing grant, even
after another month boundary. A new comparison made after failure is a new intent and charges normally.
Existing pre-reset reservations may settle in their original period; no new intent can reserve in a
past month. Expiry prevents carrying unused replacement units into later-period admissions.

Example: a 4-unit November charge refunded on 1 December gets a 4-unit November refund and 4 December
replacement units. December's base remains 20; its capacity is 24 before use, with at most 3 grace units.
There is no reduction to January's allowance. A November refund issued during November grants no extra
replacement units. Neither operation erases provider expenditure or bypasses the spend caps.

**Storage.** Add tenant-scoped `allowance_periods` (unique tenant/period start, frozen settings),
`allowance_reservations` (unique comparison, period, minimum units), and append-only `allowance_entries`
(id, tenant, comparison ID, period start, kind, positive units, timestamp, source entry ID).
Kinds are `charge`, `refund`, `replacement_credit`; unique `(tenant, comparison, kind)` prevents duplicate
effects. A refund references its original charge and must equal its units; a replacement credit
references that refund and must equal its units. Settlement removes the hold atomically with the
charge; terminal failure records status, refund and any replacement credit in one transaction.
Reconcile terminal orphan holds/refunds after worker crashes using these same idempotent operations.
Rows use RLS and contain no document text. Project deletion does not cascade away accounting: retain
content-free comparison IDs as tombstones so deleting a project cannot reset quota. Keep rows while
needed for current-period totals, outstanding jobs/refunds or retained comparison receipts; purge
settled expired-period rows once none of those needs or retained source-entry references remains.
Account deletion freezes work and removes allowance rows after reconciliation, alongside the existing
deletion workflow.

### Changes to existing routes (additive)

- `POST /projects/{id}/comparisons` → `429 allowance_exhausted`, body
  `{…problem, "resets_at": "…"}`, and a `Retry-After` header with the seconds until `resets_at`, like the
  existing rate limiter. Nothing is created and nothing is charged. The check goes next to the
  spend-cap check (`comparisons.py`, the I-14 marker comment). `allowance_exhausted` is added to
  `errors.py` TITLES.
- `GET /comparisons/{id}` gains `allowance_units` (original positive integer charge, null if never
  charged), `allowance_period_start` (UTC month start, set on reservation), `allowance_net_units`
  (0 before charging/after refund, otherwise the original charge), `retracted_at` (A), and
  `allowance_refund` (null until refunded; otherwise the object below). Values come from the ledger;
  keep a receipt with a retained comparison if older ledger rows are compacted.

```jsonc
"allowance_refund": {
  "units": 4, "refunded_at": "2026-12-01T00:05:00Z", "reason": "server_failure",
  "replacement_credit": { "units": 4, "period_start": "2026-12-01T00:00:00Z",
                          "expires_at": "2027-01-01T00:00:00Z" }
} // replacement_credit is null for a refund within its original period
```

- A comparison whose worker finds the allowance used up at its start becomes `failed` with
  `warnings: [{"code": "allowance_exhausted"}]` and no charge. This is the existing warnings pattern:
  a run stopped by the spend cap or kill switch already ends `failed` with
  `warnings: [{"code": "spend_cap_reached"}]` (`worker/__init__.py`). No `failure_reason` field is added.
- The server records each `allowance_exhausted` rejection as a tier-A count for D-18. The app sends nothing.

---

## C. D-18: consent, feedback, worth question

All rows below belong to the account. **Deleting the account (`DELETE /me`, I-18) deletes
`consent_events`, `feedback` and `survey_responses` with it.** Append-only means "never updated in
place", not "kept after deletion".

### C1. Usage-events consent (tier B), which unblocks `consent_screen.dart`

`GET /me/consent`

```jsonc
200 {
  "usage_events": {
    "granted": null,                 // null = not answered for the current policy version
    "policy_version": "2026-11-13",  // the current version the answer applies to
    "decided_at": null
  }
}
```

`PUT /me/consent`. Body `{"usage_events": {"granted": true | false, "policy_version": "2026-11-13"}}`.
`extra="forbid"` and a strict bool, the same as onboarding. It returns the same object.

- Storage: an append-only `consent_events` row (account_id, purpose, granted, policy_version, at).
  The current answer is the newest row. This is the record the onboarding handoff asks for (choice, time, policy version).
- A `policy_version` that isn't the current one gets `409 policy_version_stale`, so the app re-fetches and
  shows the new text. When the policy version changes, `granted` reads `null` again and the screen is shown again.
- `POST /session` gains `"consent": {"usage_events": true | false | null}` next to `onboarding`, so the
  first-launch gate (sign-in → onboarding → consent → Projects) needs no extra call.
- Withdrawal is the same `PUT` with `false` from Settings. It must be as easy as granting.

### C2. Feedback (WP-F report and finding feedback)

`POST /feedback`, with an `Idempotency-Key` header (the app keeps the key on retry, like compare).

```jsonc
{
  "context": { "type": "finding", "id": "uuid" },   // "comparison" | "finding" | "app"; id required unless "app"
  "sentiment": "negative",                          // "positive" | "negative"
  "reasons": ["missed_change"]                      // optional, codes only, max 5
}
→ 201 { "id": "uuid", "created_at": "…" }
```

- **Content-free (AC-23): v1 has codes only and no free text** (owner-decided).
  Reason codes: `missed_change`, `wrong_change`, `wrong_passage`, `hard_to_understand`, `too_slow`, `other`.
- **One opinion per account and context.** A new `POST` for the same `comparison` or `finding` replaces
  the earlier answer, so repeat taps don't inflate the counts. `app` feedback is not replaced: each one is
  a separate answer.
- A voluntary answer (Art. 6(1)(a)) is not tier B, so it **does not** need usage-events consent. The
  privacy policy still names it.
- Same key with a different body → `409 idempotency_conflict` (the code already exists). An unknown or
  other-tenant context id → `not_found`.
- Rate-limited by the existing per-account limiter only.

### C3. "What is it worth to you?" question

`GET /me/survey` returns the following when eligible, or
`200 {"due": false, "question_id": null, "offer": null}` otherwise:

```jsonc
200 {
  "due": true, "question_id": "worth_v1",
  "offer": { "id": "individual_20_v1", "currency": "EUR", "billing_period": "month",
             "vat_basis": "inclusive", "seats": 1, "monthly_units": 20,
             "standard_units": 1, "heavy_units": 4, "heavy_threshold_words": 5000,
             "retention_days_after_last_use": 30 }
}
```

**Eligibility:** at least three distinct real comparisons with terminal status `complete`, whose
**creation dates cover at least two UTC calendar days** (00:00 inclusive to the next 00:00 exclusive).
Use the server's immutable `created_at`, not completion time, device timezone or a rolling 24 hours.
This measures user-initiated comparison days; workers finishing a batch across midnight do not create
a second use day. Exactly midnight belongs to the new day. Failed/partial runs, placeholder-pipeline
results and product/operator-seeded examples do not qualify; complete no-change reports do.
Example origin is server-owned metadata (`user` by default on normal creation, `example` for seeded
examples); it is not inferred by inspecting document content or accepted as a client claim.

**Bookkeeping:** store the initiating account with the comparison at creation. On first qualifying
completion, transactionally insert
`survey_qualifications(account_id, question_id, comparison_id, created_utc_day)` with a unique key on
the first three fields. Under an account/question lock, count distinct comparisons/dates and set
`survey_progress.eligible_at` once both thresholds are met. Retries, polling, repeated opens and
retraction never add observations; only a new qualifying comparison can. Persist eligibility across
devices and source retention. Once eligible, discard the qualification rows and stop collecting them
for that question; the latched progress row prevents a retry from resetting eligibility. A saved answer
also stops collection and clears qualification rows. Progress/responses are unique per account/question.
Before eligibility, retain only these content-free deduplication records, not source text or labels;
remove all survey records on account deletion. GET is read-only and derives `due` from latched eligibility
and the absence of an answer. This reuses server comparison lifecycle data under the existing tier-A
policy; respect its objection handling and do not add app telemetry or require tier-B consent.

**Presentation:** `due` is permission to offer the question, not a modal trigger. The app shows it only
after review or on returning to Projects from a successfully viewed report in the current session.
Use transient navigation state; no new review-completion event is sent. Fresh app launch, background
completion and polling alone never show it. Do not require positive feedback, allowance exhaustion or
Confirm taps. Closing/Skip submits `declined`; merely fetching eligibility does not consume the question.

`POST /me/survey-responses`. Body `{"question_id": "worth_v1", "answer": "eur_5_to_10"}` → `204`.

- **Fixed offer copy:** "One person, 20 comparison units per UTC calendar month. Compare pasted text
  or PDFs with selectable text; view source evidence, review findings and keep project history.
  Standard comparisons use 1 unit; comparisons with either input over 5,000 words use 4 units.
  Documents and comparisons expire 30 days after last use. Up to 200 retained versions per project.
  Online access required."
- **Fixed question:** "If ChangeLens became a paid product, what is the most you would consider paying
  per month for this plan, including any applicable VAT?" All buckets are **total monthly prices**,
  not net prices plus tax. No VAT rate, exemption status or billing-country data is collected.
  Add: "This is pricing research. The current release remains free; this answer does not start a subscription."
- `worth_v1` and `individual_20_v1` freeze this offer, wording, tax basis and buckets in a server-owned
  question catalog; the response stores both IDs. Do not silently follow future allowance config or
  add unbuilt screenshots, sharing or team features. A materially changed offer/question requires a
  new ID and separate analysis. This gross-price survey must not be pooled with older ex-VAT pilot quotes.
- Answers are half-open ranges in euros per month, so no amount falls in two buckets:
  `eur_0` (nothing), `eur_under_5` (more than 0, under 5), `eur_5_to_10` (5 up to under 10),
  `eur_10_to_15` (10 up to under 15), `eur_15_to_20` (15 up to under 20), `eur_20_plus` (20 or more),
  `not_sure` ("Not sure yet"), and `declined` (Skip). This replaces the unimplemented `eur_10_to_20`
  bucket so responses can distinguish the intended €12–15 price region.
- `not_sure` is distinct from zero willingness to pay and from dismissal. Any answer, including
  `not_sure` or `declined`, makes `due` false for this question; no automatic repeat invitation.
- A second answer to the same question → `409 already_answered`.
- An unanswered question whose eligibility threshold has not been met returns `409 survey_not_due`.
- The server validates the question and answer against its catalog; unknown values are
  `422 invalid_request`. The client does not supply prices, VAT treatment or its own offer definition.
- The €9–15/month individual range remains a hypothesis. The €20+ response cannot validate the
  earlier €39–59 team hypothesis; a defined team offer needs separate research. Use survey responses
  to select later price tests, then validate through concrete buying decisions. They are not proof
  of demand and do not change O-20's free launch or authorise billing.

### C4. Tier-B event intake (later, sketch only)

`POST /events` (a batch of `{name, at, props}` with allow-listed names and props) returns
`403 consent_required` unless `usage_events.granted` is true. It isn't needed for any current screen,
so it is listed only so that C1's shape doesn't block it.

---

## Proposed error and warning codes (for later addition to 03 §9.4 and `errors.py`)

| Code | Status | Where |
|---|---|---|
| `allowance_exhausted` | 429 | Compare creation (with `Retry-After`); also a comparison warning code when the worker finds nothing left |
| `policy_version_stale` | 409 | `PUT /me/consent` |
| `already_answered` | 409 | Survey response |
| `consent_required` | 403 | `POST /events` (later) |
| `idempotency_conflict` | 409 | Already built; now also feedback. Missing from 03 §9.4 today |
| `version_limit_reached` | 409 | Both version-creating paths, past the per-project cap (A) |
| `invalid_cursor` | 422 | Malformed, tampered or mismatched timeline cursor |
| `timeline_changed` | 409 | Timeline revision changed between pages; restart paging |
| `survey_not_due` | 409 | Survey response submitted before eligibility |

## Owner decisions

Decided on 2026-11-16:

- **A1** (timeline derived from comparisons, former question 7). Ordering = comparing, and it costs units.
- **Cycles** are resolved by retracting a comparison (A). Retraction itself gives no refund.
- **Allowance** is keyed by tenant. One account = one tenant in v1.
- **Feedback** is codes only in v1 (former question 5).
- **O-25: version cap.** Provisionally 200 retained versions, including reserved pending imports;
  rejected imports release slots. Comparison history is paged separately, and graph
  calculations use all applicable relationships. Revisit the limit with usage/performance evidence.
- **O-26: grace overdraw.** Allow the bounded heavy-run extension (maximum 23 net units after
  replacement credits at 20/1/4),
  with atomic tenant/period accounting, no money owed and no deduction from next month.
- **O-27: server-failure refunds.** Restore the original charge once after terminal failure;
  failed-run expenditure remains in the financial spend meter. Delivered reports and retraction
  retain the charging rules in B.
- **O-28: worth survey.** Three real completed comparisons across at least two days, presented after
  report use; optional, once per question, independent of sentiment and allowance exhaustion.
  Split €10–20 at €15 and distinguish `not_sure`, zero and Skip. Prices remain research hypotheses.
- **Scope of this task:** documentation only in this draft and 06; no runtime or billing changes.

## Contract details resolved in this revision

| Former open item | Specified default | Verification required when implemented |
|---|---|---|
| Heavy definition | Either parsed input >5,000 words; canonical parser count; 4 units total | 5,000/5,001 boundary, 3k+3k, both heavy, cached/retried inputs |
| History and cap recovery | 50 relationships/page (max 100), signed cursor/revision, whole-graph metadata; explicit new project and reimport at cap | Duplicate timestamps, graph edges on later pages, concurrent retraction/deletion, last slot/inline pair race, existing-version comparison at cap |
| Queue/refund accounting | Oldest ready first; newest excess holds fail uncharged; idempotent ledger; late refund plus current-month replacement credit | Concurrent heavy workers, parse/terminal races, crash replay, project/account deletion, refund at/exactly after month boundary, no duplicate grant or reuse in old queued work |
| Survey | Three completed user comparisons created across two UTC dates; latched server eligibility; immutable one-person 20-unit offer, VAT-inclusive totals | Same-day batch across midnight, exact UTC boundary, retry deduplication, examples/partial/no-change cases, cross-device answers, retention/deletion, Skip/Not sure, frozen offer after config change |

These specifications close the four design placeholders. The checks above describe future acceptance;
they have not been run against an implementation by this documentation task. The separate C4 event
intake remains an explicitly deferred sketch, not a dependency of the worth survey.

## Research basis (checked 2026-11-16)

- [Runway: generation errors](https://help.runwayml.com/hc/en-us/articles/32880432736659-Why-am-I-receiving-errors-when-trying-to-generate): automatic credit returns after generation errors support O-27; ChangeLens's allowance/spend separation is already described in 03 §8.
- [Nielsen Norman Group: user-feedback requests](https://www.nngroup.com/articles/user-feedback/): ask after the task, without obstructing it. Three comparisons/two days is our experiment default, not a threshold established by this source.
- [Pew Research Center: writing survey questions](https://www.pewresearch.org/writing-survey-questions/): answer options affect responses and should be exhaustive and non-overlapping.
- [Diffchecker pricing](https://www.diffchecker.com/pricing/) lists Pro + Desktop at US$15/user/month; [Draftable pricing](https://www.draftable.com/pricing) lists Basic Compare at US$129/user/year, billed annually. Different features and terms make these reference points, not evidence of ChangeLens demand.
- [Qualtrics: pricing surveys](https://www.qualtrics.com/articles/strategy-research/pricing-survey-questions/): research uses a defined offer, and stated preference needs validation against purchasing behaviour. The provisional cap and grace overdraw are product/engineering choices, not market benchmarks.
