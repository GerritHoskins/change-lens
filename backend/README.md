# ChangeLens dev comparison API (I-22)

A local development backend: a FastAPI `api` process, a `worker` process, a Postgres job queue and S3-compatible object storage (MinIO). Authentication is a single dev token. **Never deploy this publicly.** I-8 replaces the dev token with Logto JWTs, tenants and row-level security.

The comparison itself is a **placeholder** (`pipeline_version = "placeholder-0"`): a line-level diff of added, removed and changed lines, with a fake LLM that costs a configurable amount per call. The real pipeline arrives with I-1 to I-5. Use synthetic documents only.

Module layout follows `docs/03-technical-design.md` §9.1:

| Module | Path | Role |
|---|---|---|
| `api` | `changelens/api/` | Routes, dev-token auth, upload checks, problem+json errors, access log |
| `domain` | `changelens/domain/` | SQLAlchemy models, tenant-scoped sessions and repositories |
| `storage` | `changelens/storage/` | S3 adapter; tenant-prefixed keys; in-memory store for unit tests |
| `jobs` | `changelens/jobs/` | Postgres queue: ID-only payloads, idempotency keys, `SKIP LOCKED`, retries, leases |
| `worker` | `changelens/worker/` | Runs `parse` and `compare` jobs under the cost ceiling |
| `pipeline` | `changelens/pipeline/` | Pure stages: placeholder `parse` and compare; `extract`, `align`, `compare` and `verify` signatures |
| `llm` | `changelens/llm/` | The `llm` port, the fake adapter and the metered wrapper |
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

Every dependency is pinned with hashes. `requirements-test.txt` holds the test-only packages (pytest, httpx, reportlab).

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

## 5. Tests

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
- end to end with two text versions and two PDF versions;
- AC-23: a unique marker in the uploaded documents and filenames never appears in the logs, the jobs table or the object keys;
- AC-21: the ceiling stops a run as `partial` (some findings explained) or `failed` (none);
- tenant isolation and `not_found`;
- job idempotency, `SKIP LOCKED`, retries, permanent failure and crash recovery after the lease expires.

## What is placeholder or out of scope

- Comparison logic, fact extraction, alignment and verification (I-1 to I-5).
- The parse sandbox with CPU, memory and output caps, hidden-text and image-region checks (I-1).
- Real auth, memberships, RLS, allowance, spend cap and kill switch (I-8, I-14).
- Alembic migrations: the schema is created with `create_all` on start, until I-8.
- Images, notifications, retention, sharing and the remaining 03 §9.4 routes.
