"""Tenant scoping (AC-19 basics), queue idempotency, SKIP LOCKED, retries and crash recovery."""
import uuid

from sqlalchemy import text

from changelens import jobs
from conftest import TENANT_A, TENANT_B
from helpers import TOKEN_A, TOKEN_B, auth


def _parsed_pair(env, token=TOKEN_A):
    pid = env.project(token)
    a = env.upload(pid, token, text="one\ntwo").json()["id"]
    b = env.upload(pid, token, text="one\nthree").json()["id"]
    env.worker.run_until_idle()
    return pid, a, b


def test_wrong_or_missing_token_against_real_routes(env):
    pid = env.project()
    for headers in ({}, auth("not-the-dev-token-0000")):
        r = env.client.get("/projects/" + pid, headers=headers)
        assert r.status_code == 401 and r.json()["code"] == "unauthenticated"


def test_other_tenant_sees_not_found(env):
    pid, a, b = _parsed_pair(env)
    cid = env.compare(pid, a, b).json()["id"]
    env.worker.run_until_idle()
    for path in ("/projects/" + pid, "/versions/" + a, "/comparisons/" + cid, "/comparisons/%s/findings" % cid):
        assert env.get(path).status_code == 200
        r = env.get(path, TOKEN_B)
        assert r.status_code == 404 and r.json()["code"] == "not_found", path
    assert env.upload(pid, TOKEN_B, text="x").json()["code"] == "not_found"
    assert env.compare(pid, a, b, token=TOKEN_B).json()["code"] == "not_found"
    own = env.project(TOKEN_B)
    r = env.compare(own, a, b, token=TOKEN_B)
    assert r.status_code == 404 and r.json()["code"] == "not_found"
    # A missing ID looks exactly like another tenant's ID.
    assert env.get("/projects/%s" % uuid.uuid4(), TOKEN_B).json() == env.get("/projects/" + pid, TOKEN_B).json()


def test_worker_ignores_ids_from_another_tenant(env):
    pid = env.project()
    v = env.upload(pid, text="hello").json()["id"]
    env.worker.handle_parse(TENANT_B, uuid.UUID(v))
    assert env.get("/versions/" + v).json()["status"] == "uploaded"


def test_enqueue_is_idempotent_per_tenant(env):
    vid = uuid.uuid4()
    with env.db.system_session() as s:
        assert jobs.enqueue(s, TENANT_A, "parse", {"version_id": vid}, 3) is True
        assert jobs.enqueue(s, TENANT_A, "parse", {"version_id": vid}, 3) is False
        assert jobs.enqueue(s, TENANT_B, "parse", {"version_id": vid}, 3) is True
    assert env.sql("SELECT count(*) FROM jobs")[0][0] == 2


def test_skip_locked_hands_out_each_job_once(env):
    with env.db.system_session() as s:
        for _ in range(2):
            jobs.enqueue(s, TENANT_A, "parse", {"version_id": uuid.uuid4()}, 3)
    with env.db.engine.connect() as c1, env.db.engine.connect() as c2:
        t1, t2 = c1.begin(), c2.begin()
        claim = "SELECT id FROM jobs WHERE status = 'queued' ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1"
        first = c1.execute(text(claim)).scalar()
        second = c2.execute(text(claim)).scalar()
        assert first and second and first != second
        assert c1.execute(text(claim.replace("LIMIT 1", "OFFSET 1 LIMIT 1"))).scalar() is None
        t1.rollback(), t2.rollback()


def test_transient_failure_is_retried(env, monkeypatch):
    pid = env.project()
    v = env.upload(pid, text="hello").json()["id"]
    real_get, calls = env.store.get, []

    def flaky(key):
        calls.append(key)
        if len(calls) == 1:
            raise ConnectionError("storage blip")
        return real_get(key)
    monkeypatch.setattr(env.store, "get", flaky)
    env.worker.run_until_idle()
    assert env.get("/versions/" + v).json()["status"] == "parsed"
    assert env.sql("SELECT status, attempts, last_error FROM jobs") == [("done", 2, "ConnectionError")]


def test_permanent_failure_marks_job_and_version(env, monkeypatch):
    pid = env.project()
    v = env.upload(pid, text="hello").json()["id"]
    monkeypatch.setattr(env.store, "get", lambda key: (_ for _ in ()).throw(ConnectionError("down")))
    env.worker.run_until_idle()
    assert env.sql("SELECT status, attempts FROM jobs") == [("failed", 3)]
    got = env.get("/versions/" + v).json()
    assert got["status"] == "rejected" and got["reject_reason"] == "parse_failed"


def test_crashed_worker_job_is_reclaimed_after_lease(env):
    pid, a, b = _parsed_pair(env)
    cid = env.compare(pid, a, b).json()["id"]
    with env.db.system_session() as s:
        crashed = jobs.claim(s)  # a worker takes the job and dies without finishing
    assert crashed.kind == "compare"
    assert env.worker.run_until_idle() == 0  # still leased: nobody else may take it
    env.sql("UPDATE jobs SET locked_at = now() - interval '1 hour' WHERE id = :id RETURNING id", id=crashed.id)
    assert env.worker.run_until_idle() == 1
    assert env.get("/comparisons/" + cid).json()["status"] == "complete"
    assert env.sql("SELECT status, attempts FROM jobs WHERE id = :id", id=crashed.id) == [("done", 2)]


def test_crash_on_last_attempt_fails_the_comparison(env):
    pid, a, b = _parsed_pair(env)
    cid = env.compare(pid, a, b).json()["id"]
    env.sql("UPDATE jobs SET status = 'running', attempts = max_attempts, locked_at = now() - interval '1 hour' "
            "WHERE kind = 'compare' RETURNING id")
    env.worker.run_once()
    c = env.get("/comparisons/" + cid).json()
    assert c["status"] == "failed" and {"code": "job_failed"} in c["warnings"]


def test_rerun_after_crash_does_not_duplicate_findings(env):
    pid, a, b = _parsed_pair(env)
    cid = env.compare(pid, a, b).json()["id"]
    env.worker.run_until_idle()
    before = len(env.get("/comparisons/%s/findings" % cid).json()["findings"])
    assert before > 0
    # Simulate a crash between persisting findings and the job being marked done.
    env.sql("UPDATE comparisons SET status = 'running' WHERE id = :id RETURNING id", id=cid)
    env.worker.handle_compare(TENANT_A, uuid.UUID(cid))
    assert len(env.get("/comparisons/%s/findings" % cid).json()["findings"]) == before
    assert env.sql("SELECT count(*) FROM findings")[0][0] == before
