# ChangeLens dev comparison API (I-22)

A local development backend: a FastAPI `api` process, a `worker` process, a Postgres job queue and S3-compatible object storage (MinIO). Authentication is a single dev token. **Never deploy this publicly.** I-8 replaces the dev token with Logto JWTs, tenants and row-level security.

The comparison itself is a **placeholder** (`pipeline_version = "placeholder-0"`): a line-level diff of added, removed and changed lines, with a fake LLM that costs a configurable amount per call. Parsing is real (I-1): exact text with 07 §4 locators, visibility flags for hidden text, and a resource-capped parse sandbox for PDFs. Extraction and comparison arrive with I-2 to I-5. Use synthetic documents only.

Module layout follows `docs/03-technical-design.md` §9.1:

| Module | Path | Role |
|---|---|---|
| `api` | `changelens/api/` | Routes, dev-token auth, upload checks, problem+json errors, access log |
| `domain` | `changelens/domain/` | SQLAlchemy models, tenant-scoped sessions and repositories |
| `storage` | `changelens/storage/` | S3 adapter; tenant-prefixed keys; in-memory store for unit tests |
| `jobs` | `changelens/jobs/` | Postgres queue: ID-only payloads, idempotency keys, `SKIP LOCKED`, retries, leases |
| `worker` | `changelens/worker/` | Runs `parse` and `compare` jobs under the cost ceiling |
| `pipeline` | `changelens/pipeline/` | Pure stages: `parse` (I-1), the parse sandbox, placeholder compare; `extract`, `align`, `compare` and `verify` signatures |
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
| `CHANGELENS_FAKE_LLM_COST_EUR` | `0.01` per fake llm call |

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
  - `no_ink`: white-on-white or covered text;
  - `tiny`: at most 3 ink rows and glyphs no taller than 0.8 pt.
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

Results are cached per version in the `fact_cache` table (tenant-scoped). The key covers the version hash, the extract prompt and schema, and the model config, so changing any of them re-extracts. Results with unextracted chunks are never cached. The worker extracts both versions before the placeholder comparison; the facts are not compared until I-3.

The worker uses the fake llm unless `CHANGELENS_LLM=ionos` (model `CHANGELENS_LLM_MODEL`, default `Qwen/Qwen3.5-397B-A17B`; token from `CHANGELENS_IONOS_ENV_FILE`). The fake answers `FactList` with no facts, at no cost.

**I-2 runner.** `tools/i2_run.py` extracts every distinct version of the usable development pairs once, then runs a second pass that must be answered entirely from the cache. It refuses held-out pairs, like the D-17 runner. It writes per-version results to `../../change-lens-data/i2/<model>/` and aggregates to stdout and `summary.json`. From `backend/`:

```powershell
$env:CHANGELENS_IONOS_ENV_FILE = '..\..\change-lensackend\.env'
.venv\Scripts\python -m tools.i2_run
```

## What is placeholder or out of scope

- Comparison logic, alignment and verification (I-3 to I-5). Facts are extracted (I-2) but not yet compared.
- Image (screenshot) parsing and its vision passes (I-16); image regions in PDFs are only warned.
- Real auth, memberships, RLS, allowance, spend cap and kill switch (I-8, I-14).
- Alembic migrations: the schema is created with `create_all` on start, until I-8.
- Images, notifications, retention, sharing and the remaining 03 §9.4 routes.
