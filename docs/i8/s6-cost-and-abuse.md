# I-8 S6: cost and abuse controls

Part of [I-8 in slices](README.md). Needs S1 merged; the sign-up cap needs S2. It can run in its own
worktree alongside S2–S5, with file ownership agreed first (see the overview). Check `git status` and HEAD.

## 1. Goal

Put the cost and abuse limits in place before any external user (03 §6 "Abuse and cost exhaustion", SA-4,
CR-2, AC-21), and make the telemetry rules of AC-23 testable:

- a per-tenant monthly spend cap that counts every run's cost, failed or not;
- a global monthly spend cap that trips a kill switch for new work;
- rate limits per account and per IP, and a cap on new sign-ups per IP;
- the logging and tracing allow-list (03a P9) enforced by tests.

The fair-use allowance (20 comparisons per account per month, heavy documents count as 4) is I-14, not
this slice. Leave a clear place for its check next to the spend-cap check in P4.

## 2. Values

Config values, changeable without a release (06, 2026-11-13; overview decision 7):

| Setting | Starting value |
|---|---|
| Per-tenant monthly spend cap | EUR 5 |
| Global monthly model spend cap (kill switch) | EUR 50 |
| Per-comparison ceiling | EUR 1.50 (exists) |
| Requests per account | 60 per minute |
| Requests per IP, unauthenticated routes and `POST /session` | 20 per minute |
| New accounts per IP | 5 per day |

The request and sign-up numbers are this handoff's proposal; the owner can change them before the slice.

## 3. Behaviour

**Spend.** Month-to-date spend per tenant and globally comes from recorded actual costs plus open
reservations (`comparisons.cost_actual`, `cost_reservations`, `comparison_cost_tombstones`), so deleted
projects and failed runs still count. Months are calendar months in UTC.

- Comparison creation (03a P4) rejects with `spend_cap_reached` when the tenant or the global cap is
  reached. Nothing is charged by the rejection.
- The worker checks both caps again before each paid stage; a run that hits one stops like a ceiling stop
  (AC-21) and is marked failed with a user-facing reason.
- Reaching the global cap is logged once per month as an event code, so the owner can be alerted (S7).

**Rate limits.** A small Postgres-backed counter (fixed windows keyed by account or IP and window start),
so several api processes share it; no new dependency. Over the limit is `429 rate_limited` with
`Retry-After`. Add `rate_limited` and `spend_cap_reached` to `api/errors.py` titles if missing, and record
any new code in 03 §9.4.

**Client IP.** Taken from `X-Forwarded-For` only when the request comes from a configured trusted proxy
address; otherwise the socket address. IPs are used as limiter keys only: store a keyed hash, never the
raw address, and never log it.

**Sign-up cap.** S2's first-sign-in branch checks the per-IP count of new accounts before creating one and
rejects with `429 rate_limited`. Returning users are never blocked by it.

**Telemetry.** Today only `opentelemetry-api` is installed, with no SDK or exporter, so nothing is exported.
Keep it that way in this slice, and add tests that pin it: no exporter is configured; access logs record
method, route template and status only; log records from the api and worker pass through the allow-list
(03a P9) and never contain request bodies, SQL parameters, tokens or IPs.

## 4. Plan documents to update

| File | Change |
|---|---|
| `docs/03-technical-design.md` §6, §8, §9.4 | "Global daily kill switch" → the monthly global cap (06, 2026-11-13); the per-tenant cap value; rate limits; new error codes |
| `docs/03a-pipeline-logic.md` P4 | The spend and rate checks as built |
| `docs/data-inventory.md` | The rate-limit counters: hashed keys, retention of a few days |
| `docs/06-decision-log.md` | One change-log row, with the starting values |

## 5. Out of scope

The fair-use allowance and its UI (I-14), alerting infrastructure (S7), app code, and anything that needs
a new dependency (a Redis limiter, an OpenTelemetry SDK).

## 6. Tests

1. **Tenant cap**: with recorded costs just under the cap, a comparison starts; at the cap, creation
   returns `spend_cap_reached` and creates nothing; failed runs and deleted projects still count.
2. **Global cap**: reaching it rejects every tenant's new comparison and stops a running one before its next
   paid stage, which ends failed with a reason.
3. **Month boundary**: spend from the previous UTC month doesn't count.
4. **Rate limits**: the 61st request in a minute from one account returns `429` with `Retry-After`; another
   account isn't affected; limits hold across two app instances sharing the database.
5. **Client IP**: a spoofed `X-Forwarded-For` from an untrusted address is ignored; the stored key is a hash.
6. **Sign-up cap**: the sixth new account from one IP in a day is rejected; a returning user from that IP
   isn't.
7. **Telemetry**: the pins in §3.
8. **Gates**: backend unit and integration tests and `./scripts/ci.ps1` pass.

## 7. Receiving-agent prompt

> Work in the ChangeLens checkout on `m1-iphone`, with I-8 S1 merged (and S2 for the sign-up cap), in your
> own worktree if another slice is in progress. Verify `git status` and HEAD. Read `docs/i8/README.md` and
> `docs/i8/s6-cost-and-abuse.md`, then 03 §6 and §8, 03a P4 and P9, the 2026-11-13 allowance row in 06,
> review-ledger items SA-4 and CR-2, and `backend/changelens/metering/`, `domain/budget.py`,
> `api/comparisons.py`, `worker/` and `logs.py`. Build the spend caps, rate limits, sign-up cap and telemetry
> pins as specified, with no new dependency. Don't build the fair-use allowance or app code. Don't commit or
> push. Write the §6 tests, run the backend unit and integration tests and `./scripts/ci.ps1`, and return
> the evidence the overview lists or a precise blocker.
