"""Real transaction/queue checks for atomic inputs and concurrent idempotency."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import uuid

from fastapi.testclient import TestClient

from helpers import TOKEN_A, auth


def body():
    return {"earlier": {"label": "earlier", "text": "Budget: EUR 100."},
            "later": {"label": "later", "text": "Budget: EUR 200."}, "scope": "partial"}


def test_atomic_new_versions_wait_then_enqueue_once(env):
    project = env.project()
    key = str(uuid.uuid4())
    headers = {**auth(TOKEN_A), "Idempotency-Key": key}
    path = f"/projects/{project}/comparisons"
    first = env.client.post(path, json=body(), headers=headers)
    assert first.status_code == 202, first.text
    assert first.json()["status"] == "waiting_for_versions"
    assert env.get('/projects').json()['projects'][0]['comparison_counts'] == {'waiting_for_versions': 1}
    assert env.sql("SELECT count(*) FROM source_versions") == [(2,)]
    assert env.sql("SELECT count(*) FROM jobs WHERE kind='compare'") == [(0,)]
    assert env.worker.run_once()  # one parse is insufficient
    assert env.sql("SELECT status FROM comparisons") == [("waiting_for_versions",)]
    assert env.worker.run_once()
    assert env.sql("SELECT status FROM comparisons") == [("queued",)]
    assert env.get('/projects').json()['projects'][0]['comparison_counts'] == {'queued': 1}
    assert env.sql("SELECT count(*) FROM jobs WHERE kind='compare'") == [(1,)]
    retry = env.client.post(path, json=body(), headers=headers)
    assert retry.status_code == 202 and retry.json()["id"] == first.json()["id"]
    assert env.sql("SELECT count(*) FROM source_versions") == [(2,)]
    changed = body()
    changed["scope"] = "complete"
    assert env.client.post(path, json=changed, headers=headers).status_code == 409


def test_concurrent_same_key_creates_one_pair_and_one_comparison(env):
    project, key, start = env.project(), str(uuid.uuid4()), Barrier(2)

    def submit():
        with TestClient(env.client.app, raise_server_exceptions=False) as client:
            start.wait(timeout=5)
            return client.post(f"/projects/{project}/comparisons", json=body(),
                               headers={**auth(TOKEN_A), "Idempotency-Key": key})

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(lambda _: submit(), range(2)))
    assert [r.status_code for r in responses] == [202, 202], [r.text for r in responses]
    assert responses[0].json()["id"] == responses[1].json()["id"]
    assert env.sql("SELECT count(*) FROM comparisons") == [(1,)]
    assert env.sql("SELECT count(*) FROM source_versions") == [(2,)]
    assert env.sql("SELECT count(*) FROM jobs WHERE kind='parse'") == [(2,)]


def test_rejected_new_version_fails_waiting_comparison_without_model_spend(env):
    project = env.project()
    payload = body()
    payload["later"] = {"label": "bad PDF", "file": True}
    import json
    result = env.client.post(f"/projects/{project}/comparisons",
        headers={**auth(TOKEN_A), "Idempotency-Key": str(uuid.uuid4())},
        data={"comparison": json.dumps(payload)}, files={"later_file": ("bad.pdf", b"%PDF-1.7 broken")})
    assert result.status_code == 202, result.text
    env.worker.run_until_idle()
    comparison = env.get("/comparisons/" + result.json()["id"]).json()
    assert comparison["status"] == "failed"
    assert float(comparison["cost_actual"]) == 0
    assert comparison["warnings"][0]["code"] == "version_rejected"
    assert env.sql("SELECT count(*) FROM jobs WHERE kind='compare'") == [(0,)]
