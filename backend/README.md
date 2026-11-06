# ChangeLens dev comparison API (I-22)

A local development backend: a FastAPI `api` process, a `worker` process, a Postgres job queue and S3-compatible object storage (MinIO). Authentication is a single dev token. **Never deploy this publicly.** I-8 replaces the dev token with Logto JWTs, tenants and row-level security.

The comparison runs the fact pipeline (`pipeline_version = "facts-2"`): parse (I-1), extract (I-2), align and compare (I-3, I-4), verify and report (I-5). By default the worker uses a fake llm that answers every schema deterministically (one fact per line) and costs a configurable amount per explanation; `CHANGELENS_LLM=ionos` uses the real model (§8). Use synthetic documents only.

Module layout follows `docs/03-technical-design.md` §9.1:

| Module | Path | Role |
|---|---|---|
| `api` | `changelens/api/` | Routes, dev-token auth, upload checks, problem+json errors, access log |
| `domain` | `changelens/domain/` | SQLAlchemy models, tenant-scoped sessions and repositories |
| `storage` | `changelens/storage/` | S3 adapter; tenant-prefixed keys; in-memory store for unit tests |
| `jobs` | `changelens/jobs/` | Postgres queue: ID-only payloads, idempotency keys, `SKIP LOCKED`, retries, leases |
| `worker` | `changelens/worker/` | Runs `parse` and `compare` jobs under the cost ceiling |
| `pipeline` | `changelens/pipeline/` | Pure stages: `parse` (I-1) and its sandbox, `extract` (I-2), `align`, `compare` and `values` (I-3), `verify` and `report` (I-5) |
| `llm` | `changelens/llm/` | The `llm` port, the fake adapter, the metered wrapper, the IONOS adapter (`ionos.py`) and output schemas (`schemas.py`) |
| `metering` | `changelens/metering/` | Per-comparison cost meter and ceiling |
| logging | `changelens/logs.py` | Log scrubbing (AC-23) |

## 1. Start Postgres and MinIO

Docker Desktop must be running.

```powershell
cd backend
docker compose up -d --wait
```

This starts Postgres 16 on `127.0.0.1:55432` and MinIO on `127.0.0.1:59000`. The credentials are for local development only. Stop with `docker compose down`, and add `-v` to delete the data.

## 2. Create the venv and install

The venv is created with Python 3.10.11. It is never installed into the global Python.

```powershell
cd backend
python -m venv .venv
.venv\Scripts\python -m pip install --require-hashes -r requirements.txt -r requirements-test.txt
```

Every dependency is pinned with hashes. `httpx` is a runtime dependency (the IONOS adapter); `requirements-test.txt` holds the test-only packages (pytest, reportlab).

## 3. Run the API and the worker

Run each in its own terminal from `backend/`. Both create the schema on start.

```powershell
$env:CHANGELENS_DEV_TOKEN = 'local-dev-token-change-me'   # at least 16 characters
.venv\Scripts\python -m changelens.api --port 8000         # binds to 127.0.0.1 only
.venv\Scripts\python -m changelens.api --port 8000 --lan   # also reachable from the home Wi-Fi (phone tests)
```

```powershell
$env:CHANGELENS_DEV_TOKEN = 'local-dev-token-change-me'
.venv\Scripts\python -m changelens.worker
```

Optional environment variables:

| Variable | Default |
|---|---|
| `CHANGELENS_DATABASE_URL` | `postgresql+psycopg://changelens:changelens@127.0.0.1:55432/changelens` |
| `CHANGELENS_S3_ENDPOINT` | `http://127.0.0.1:59000` |
| `CHANGELENS_S3_ACCESS_KEY` | `changelens` |
| `CHANGELENS_S3_SECRET_KEY` | the compose dev value |
| `CHANGELENS_S3_BUCKET` | `changelens-dev` |
| `CHANGELENS_COST_CEILING_EUR` | `1.50` per comparison |
| `CHANGELENS_FAKE_LLM_COST_EUR` | `0.01` per fake llm explanation (its other answers are free) |

## 4. Example curl sequence (Git Bash)

```bash
H="Authorization: Bearer local-dev-token-change-me"
P=$(curl -s -X POST localhost:8000/projects -H "$H" -H 'Content-Type: application/json' -d '{"name":"Demo"}' | python -c "import sys,json;print(json.load(sys.stdin)['id'])")
A=$(curl -s -X POST localhost:8000/projects/$P/versions -H "$H" -F label=v1 -F 'text=Budget: EUR 12,000
Deadline: 15 March' | python -c "import sys,json;print(json.load(sys.stdin)['id'])")
B=$(curl -s -X POST localhost:8000/projects/$P/versions -H "$H" -F label=v2 -F file=@newer.pdf | python -c "import sys,json;print(json.load(sys.stdin)['id'])")
curl -s localhost:8000/versions/$B -H "$H"          # wait for "status":"parsed"
C=$(curl -s -X POST localhost:8000/projects/$P/comparisons -H "$H" -H 'Content-Type: application/json' \
  -d "{\"earlier_id\":\"$A\",\"later_id\":\"$B\",\"scope\":\"complete\"}" | python -c "import sys,json;print(json.load(sys.stdin)['id'])")
curl -s localhost:8000/comparisons/$C -H "$H"       # queued -> complete | partial | failed
curl -s localhost:8000/comparisons/$C/findings -H "$H"
```

Routes: `POST /projects`, `GET /projects/{id}`, `POST /projects/{id}/versions` (multipart: `label` plus exactly one of `file` or `text`), `GET /versions/{id}`, `POST /projects/{id}/comparisons` (returns 202), `GET /comparisons/{id}` and `GET /comparisons/{id}/findings`. Errors are `application/problem+json` with a stable `code`. Another tenant's resources return `not_found`.

## 5. Parsing (I-1)

- **Text** is decoded as UTF-8 exactly as uploaded, with no newline or BOM changes. Locators are `char_start` and `char_end` offsets into that text, and blocks are its non-empty lines.
- **PDF** text is PDFium's exact `get_text_range()` output for each page, line endings included. Locators are a one-based `page` plus offsets into that page's text: the same rules as the eval records (07 §4).
- **PDF blocks** are lines. A line is split where a run of words on it is hidden.
- **Visibility.** Each block carries a `hidden` flag and a reason, decided by the eval rules (`changelens/pipeline/pdf_ink.py`, a copy of `scripts/eval/pdf_ink.py` that a unit test keeps in sync):
  - `off_page`;
  - `no_ink`: white-on-white text, or text under a plain opaque panel;
  - `tiny`: at most 3 ink rows and glyphs no taller than 0.8 pt;
  - `covered` (backend only, I-6): the span has "ink", but the page rendered again from a second copy with every text object removed (nested form XObjects included) looks the same there, so the ink belongs to an image or shape drawn over the text. One extra render per page. The eval validator does not have this rule; on the dataset's pages it flags nothing extra.
- **Hidden blocks** raise a `hidden_text` warning (SA-9) with the page and span, and are left out of the comparison.
- **Page geometry (I-1c).** Rotated pages (/Rotate 90, 180 or 270), a CropBox and a MediaBox off the origin are measured:
  - glyph boxes are mapped from PDF user space into the rendered page;
  - text outside the CropBox is `off_page`;
  - ink rows and glyph height are taken across the text's displayed direction, so sideways text gets the same tiny-text rule.
- **Fail closed.** Each page's mapping is cross-checked against PDFium's own `FPDF_PageToDevice`. A page where they disagree, an empty visible box, or a page over 40 MP at 144 DPI counts as hidden and is warned `visibility_unchecked`.
- **Eval validator.** `scripts/eval/pdf_ink.py` still refuses rotated and cropped pages; the dataset has none. On plain pages the two agree.
- **Warnings** also cover pages without text (`no_text_layer`), image regions (`unextracted_region` above 15% of a page, otherwise `image_region`), JavaScript or launch actions (`active_content`), automatic actions (`auto_action`) and attachments (`embedded_files`).
- **Nothing is executed or extracted.** The PDFium build has no JavaScript engine, forms are never initialised, and attachments are only counted.
- **Partial comparisons.** `no_text_layer`, `unextracted_region` and `visibility_unchecked` make a comparison `partial`.

The API checks only magic bytes, size and text word count. It never opens a PDF. The worker parses PDFs in a child process (`changelens/pipeline/sandbox.py`):
- The child gets no credentials in its environment. It runs the base interpreter with `-I` and the venv's site-packages added to its path explicitly, because a Windows venv's `python.exe` is a launcher that would start a second process.
- The child checks the page count before any page is parsed.
- On a breach the child is killed and the version is `rejected` with a reason:

| Cap (default) | How | Reason |
|---|---|---|
| Wall clock, 60 s | Parent timeout | `parse_timeout` |
| Memory, 512 MB | Windows Job Object (Linux: `RLIMIT_AS`) | `parse_memory_limit` |
| CPU, 60 s | Windows Job Object (Linux: `RLIMIT_CPU`) | `parse_cpu_limit` |
| One process, kill on close | Windows Job Object | — |
| 20 pages, 10 MB, 15,000 words, 5 M characters | Checked in the child | `limit_exceeded_pages`, `limit_exceeded_bytes`, `limit_exceeded_words`, `limit_exceeded_text` |
| Unreadable file | PDFium refuses it | `malformed_pdf` |

Limitations:
- The child keeps network access on both platforms. It makes no network calls, but production should restrict the worker's outbound traffic.
- The Linux limits are written but have not been run here.
- On Windows the interpreter starts before the job is applied, but before it receives the document.

**Schema change:** `parsed_text` became `parsed_pages`. There are no migrations until I-8, so reset the dev database after pulling: `docker compose down -v; docker compose up -d --wait`. The integration tests rebuild their own schema.

## 6. Tests

Unit tests need no Docker; CI runs them (`scripts/ci.ps1`, backend stage):

```powershell
cd backend
.venv\Scripts\python -m pytest tests/unit -q
```

Integration tests need the compose services. They use a separate database (`changelens_test`) and bucket (`changelens-test`), and are skipped with a reason when the services are down:

```powershell
cd backend
docker compose up -d --wait
.venv\Scripts\python -m pytest tests/integration -q -rs
```

They cover:
- end to end with two text versions and two PDF versions, hidden injected text, and hostile PDFs through the worker;
- AC-23: a unique marker in the uploaded documents and filenames never appears in the logs, the jobs table or the object keys;
- AC-21: the ceiling stops a run as `partial` (some findings explained) or `failed` (none);
- tenant isolation and `not_found`;
- job idempotency, `SKIP LOCKED`, retries, permanent failure and crash recovery after the lease expires.

The constructed-dataset round trip reads the private data in place and is skipped when it is absent. It is not in CI. It reports counts and record IDs only:

```powershell
cd backend
.venv\Scripts\python -m pytest tests/dataset -q -s     # CHANGELENS_EVAL_DATA overrides ../../change-lens-data
```

The unit tests include the hostile-file fixtures, all generated in the tests:
- oversized, truncated and garbage files;
- JavaScript and OpenAction;
- an embedded file;
- a 400 MB deflate bomb in a 0.4 MB file;
- page-count bombs;
- a 14,400 pt page.

They also check the sandbox caps against misbehaving child probes (`tests/unit/sandbox_probes.py`).

## 7. Development split and the D-17 model check

**Split (07 §5.4).** `scripts/eval/split.py` assigns the constructed pairs to 40% development and 60% held-out, stratified by tier and case type. A pair and every pair whose `source.derived_from` names it stay on the same side. It is seeded and deterministic and writes IDs only to `scripts/eval/split.json`, which is kept in git. Held-out pairs are frozen: never used for prompt tuning, D-17 or debugging. From the repository root:

```powershell
python scripts/eval/split.py --data ../change-lens-data --seed 17
python -m unittest discover -s scripts/eval -p test_split.py
```

**IONOS adapter.** `changelens/llm/ionos.py` implements the `llm` port against the OpenAI-compatible IONOS AI Model Hub:
- `response_format` json_schema strict, or `--mode json_object` (the schema goes in the prompt);
- no tools;
- data blocks delimited with a per-call random nonce, and a system prompt that marks them untrusted;
- local schema validation, with one retry on invalid JSON or schema;
- per-call tokens, latency and cost;
- no prompt or response bodies in logs or exceptions; a 401 or 403 is never retried.

Output schemas avoid booleans, because strict decoding of a boolean made Qwen emit whitespace until `max_tokens`. Prices are EUR per million tokens in `PRICES_EUR`, from the IONOS price list on 2026-10-30. Override them per run with `--price-in` and `--price-out`.

**D-17 runner.** `tools/d17_run.py` runs change detection on the **development** pairs only. It refuses any held-out or unassigned pair before a call, and a unit test covers that. Text sides are sent exactly; PDF sides go through the I-1 parser, visible blocks only. Pairs with an image side are skipped (I-1b). The token is read in place from `IONOS_API_TOKEN` or from the env file named by `CHANGELENS_IONOS_ENV_FILE` (or `--env-file`), and never printed. Model outputs and per-pair scores go to `../../change-lens-data/d17/<prompt>/<model>/` (refused inside a Git worktree). Only aggregates go to stdout and `summary.json`. Metric definitions are in the `tools/d17_score.py` docstring. From `backend/`:

```powershell
$env:CHANGELENS_IONOS_ENV_FILE = '..\..\change-lens\backend\.env'
.venv\Scripts\python -m tools.d17_run --model Qwen/Qwen3.5-397B-A17B --runs 2
.venv\Scripts\python -m tools.d17_run --model Qwen/Qwen3.8-27B --runs 2
```

Results and the model choice are in `docs/06-decision-log.md` (D-17, 2026-10-31).

## 8. Fact extraction (I-2)

`changelens/pipeline/extract.py` sends a version's visible blocks, numbered and in chunks of about 6,000 characters, to the `FactList` schema. Hidden blocks are never sent. The model names a block number and a quote; the quote is located in that block's page text, so every locator is computed here and `raw_text` is always the exact parsed slice. Facts whose quote cannot be found are dropped and counted. A chunk whose output is still invalid after the adapter's one retry is marked *unextracted*, and the comparison gets an `unextracted` warning and becomes partial (AC-11). Unavailability and the cost ceiling propagate: there is no fallback model, so the job is retried later.

Results are cached per version in the `fact_cache` table (tenant-scoped). The key covers the version hash, the extract prompt and schema, and the model config, so changing any of them re-extracts. Results with unextracted chunks are never cached.

The worker uses the fake llm unless `CHANGELENS_LLM=ionos` (model `CHANGELENS_LLM_MODEL`, default `Qwen/Qwen3.5-397B-A17B`; token from `CHANGELENS_IONOS_ENV_FILE`). The fake answers `FactList` with one fact per line ("Budget: EUR 12,000" has subject "Budget"), `FactMatches` with no proposals and `SameMeaning` with no verdicts, all at no cost.

**I-2 runner.** `tools/i2_run.py` extracts every distinct version of the usable development pairs once, then runs a second pass that must be answered entirely from the cache. It refuses held-out pairs, like the D-17 runner. It writes per-version results to `../../change-lens-data/i2/<model>/` and aggregates to stdout and `summary.json`. From `backend/`:

```powershell
$env:CHANGELENS_IONOS_ENV_FILE = '..\..\change-lens\backend\.env'
.venv\Scripts\python -m tools.i2_run
```

## 9. Alignment and comparison (I-3)

`changelens/pipeline/align.py` pairs the facts of two versions. A fact's key is its type plus its canonical subject; a key that occurs once on each side is a match, whatever the position, so reordering changes nothing (AC-6). Two different values for one key inside a version are a contradiction: every member is marked ambiguous and paired with every counterpart, never resolved by picking one (AC-7). The remaining facts go to one `FactMatches` call; a proposal becomes a match only with high confidence and when it is one-to-one, otherwise the pair is ambiguous.

`changelens/pipeline/compare.py` turns pairs into draft findings. Each fact carries `context`, the whole sentence or list item around its quote, worked out from the page rather than by the model (extract-v4; only PDF lines can wrap into the next), and the guards compare those sentences (`changelens/pipeline/values.py`): the same sentence after canonicalisation is unchanged and gets no finding; different numbers, dates or currencies, or a different owner or approver, are changed; different negation, modality or limit words are changed (AC-8). Only what passes all three goes to one `SameMeaning` call, and a missing verdict counts as a change. Ambiguous pairs, ambiguous dates and entities, and contradictions are uncertain. Unmatched earlier facts follow the scope (I-4): complete → removed (absent from the replacement), partial → not addressed, unknown → uncertain. Unmatched newer facts are added.

**I-3 runner.** `tools/i3_run.py` reads the I-2 runner's saved facts, aligns and compares every usable development pair, and scores the drafts with `tools/d17_score.py`. The scope is taken from the pair's case type. It also reports reportable findings on reordered pairs (AC-6, must be 0) and uncertain findings on ambiguous pairs (AC-7). Output goes to `../../change-lens-data/i3/<tag>/<model>/`. From `backend/`, after the I-2 runner:

```powershell
.venv\Scripts\python -m tools.i3_run --runs 2 --tag v4-report --report --max-calls 400
```

`--report` also runs verify and report (I-5), so the scores are on what a user would see, and adds the withheld, unexplained and presentation-only counts, the groups, and how often the model's wording was kept.

## 10. Verification and the report (I-5)

`changelens/pipeline/verify.py` makes no model calls. A draft is kept only if every quote equals the parsed text at its locator and its evidence fits its type: a change cites both sides (AC-1), an omission only the earlier side, an addition only the newer side. Anything else is withheld and counted (AC-9, AC-10). Uncertain findings and findings resting on a low-confidence fact go to *needs review*. A block diff of the visible text is then cross-checked: a changed block that no finding covers is an *unexplained difference*, and an equivalent verdict does not count as covering it, so injected text cannot hide a change (AC-18). Blocks that only moved or were reformatted (list marker, capitals) are *presentation-only*.

`changelens/pipeline/report.py` words and ranks. Changes, additions and equivalences get one `Explanation` call each; the wording is replaced by a template if the call fails, if it names a number the quotes do not contain, or if it says removed or cancelled where the quotes do not. Omissions and uncertain findings always get a template, so an omission is never called cancelled (AC-2..4). Groups: *prioritised* (material categories), *needs review*, *other*; `priority` is the display rank in that order. At the cost ceiling the remaining findings keep template wording rather than being dropped, and the comparison is partial with a `cost_ceiling` warning (`stage: report`). A ceiling during extraction or comparison fails the comparison (`stage: extract` or `compare`).

`GET /comparisons/{id}/findings` returns the findings in rank order with `group` and `note`, `withheld_count`, `unexplained_differences`, `presentation_only`, and a `summary` (`selected: true`, the prioritised count and the count of other differences) for the "Selected summary" line (AC-13). The worker adds the new columns to an existing dev database on start.

`tools/i3_run.py --report` runs verify and report on the development split as well (see §9).

## 11. Reviews, client approvals and evidence (I-10)

Routes in `changelens/api/reviews.py`:

- `GET /comparisons/{id}/findings` now returns current revisions only, each with its latest `review`, a `notes` count and `client_approval_recorded`, plus the comparison's `earlier_id`, `later_id` and `scope`.
- `GET /findings/{id}`: the finding with its `revisions`, `reviews` and `client_approvals`.
- `POST /findings/{id}/reviews` with `action` `confirmed`, `corrected`, `dismissed` or `note` (a note needs text). A correction (`correction`: any of `change_type`, `category`, `explanation`) creates a new revision with `supersedes_id` and `revision + 1`; the original row is never changed (AC-15). Reviewing a superseded revision gives 409 `finding_superseded`.
- `POST /findings/{id}/client-approvals` with `evidence_text`, `stated_by` and `stated_at`. It is stored in its own table and shown as "Client approval recorded (not verified by ChangeLens)". A review never creates one and a client approval never counts as a review (AC-12). Evidence is text only for now; file attachments are not built.
- `GET /versions/{id}/text`: the parsed page texts, for the evidence view (409 until parsed).
- `GET /versions/{id}/original`: the uploaded bytes with `Cache-Control: no-store`, so the app can highlight a quote in the PDF. This is a dev shortcut; 03 §9.4 specifies a short-lived signed URL (I-8).

The actor is the fixed `dev-token-user` until real auth (I-8).

## 12. Evaluation harness (I-7)

`tools/i7_run.py` runs the worker's comparison code (`changelens/pipeline/run.py`, shared with the worker) on a constructed split. Each comparison starts from an empty fact cache, so its cost includes extracting both versions. It scores the result with the 04 §5 metrics against the Gate 2 thresholds (04 §6) and the backlog's M1 recall floor. Definitions are in the `tools/i7_metrics.py` docstring. It reports:

- precision, recall and material recall, with 95% bootstrap intervals over pairs;
- false removals, with the rule-of-three bound when there are none;
- evidence-location accuracy and the unsupported rate, with Wilson intervals;
- fabricated scope changes on reordered and no-change pairs;
- statuses, latency, and p90 cost per comparison for typical (≤ 5,000 words) and heavy documents.

`--baseline` also runs the D-17 single-prompt detector on the same pairs as the general-purpose baseline. Pairs with an image side are skipped until I-1b. From `backend/`:

```powershell
$env:CHANGELENS_IONOS_ENV_FILE = ".env"
.venv\Scripts\python -m tools.i7_run --split development --runs 1 --baseline   # try changes here
.venv\Scripts\python -m tools.i7_run --split held_out --runs 2 --baseline      # the gate run
```

**The held-out split is frozen (07 §5.4).** Never use it to tune or debug.

- A held-out run refuses a working tree with uncommitted changes, and records the commit.
- It refuses a second run for the same fingerprint unless `--rerun-reason` gives a reason.
- It writes `../scripts/eval/i7_receipt.json`. The receipt holds aggregates only; per-pair output with quotes stays in `../../change-lens-data/i7/`.

**Regression check.** The fingerprint is a hash of every prompt, output schema, the extraction prompt version, the pipeline version, the model configuration and its prices. `tests/unit/test_i7.py` fails in CI when the committed receipt's fingerprint differs from the current one. A prompt or model change therefore needs a new held-out run and a decision-log row before it can merge.

## What is placeholder or out of scope

- Image (screenshot) parsing and its vision passes (I-1b); image regions in PDFs are only warned.
- Real auth, memberships, RLS, allowance, spend cap and kill switch (I-8, I-14).
- Alembic migrations: the schema is created with `create_all` on start, until I-8.
- Images, notifications, retention, sharing and the remaining 03 §9.4 routes.
