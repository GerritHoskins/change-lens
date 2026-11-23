"""The demo limit and feedback in Postgres (docs/demo-wall-handoff.md, migration 0012): the worker's counted
row, admission under the tenant lock, the state, tenant isolation and the migration's count of existing
comparisons. Route validation without services is in tests/unit/test_demo.py and test_demo_limit.py;
account deletion is in test_account_deletion_db.py; the catalog checks are in test_rls_db.py.
"""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import json
import uuid

from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from changelens.db import alembic_config, upgrade
from changelens.domain.models import Comparison, Project, SourceVersion
from conftest import SUBJECT_A, TENANT_A, TENANT_B
from helpers import TOKEN_A, TOKEN_B, auth
from test_identity_db import HEAD, OWNER_URL, model_diffs, revision, scratch  # noqa: F401 (scratch is a fixture)

BEFORE, THIS = "0011_early_bird_hardening", "0012_demo_limit"
GOOD = {"missing": "better_accuracy", "price": "eur_15"}


def _pair(env, token=TOKEN_A, n=0):
    pid = env.project(token, name="Project %d" % n)
    a = env.upload(pid, token, label="v1", text="one\ntwo %d" % n).json()["id"]
    b = env.upload(pid, token, label="v2", text="one\nthree %d" % n).json()["id"]
    env.worker.run_until_idle()
    return pid, a, b


def _done(env, token=TOKEN_A, n=0):
    """One comparison run to its end by the real worker; (project, comparison)."""
    pid, a, b = _pair(env, token, n)
    r = env.compare(pid, a, b, token=token)
    assert r.status_code == 202, r.text
    env.worker.run_until_idle()
    return pid, r.json()["id"]


def _state(env, token=TOKEN_A):
    r = env.get("/me/demo", token)
    assert r.status_code == 200, r.text
    return r.json()


def _refused(r, used, in_flight=0, limit=3):
    assert r.status_code == 403 and r.headers["content-type"].startswith("application/problem+json"), r.text
    body = r.json()
    assert (body["code"], body["used"], body["in_flight"], body["limit"]) == ("demo_limit_reached", used, in_flight,
                                                                              limit)


def _counted(env, tenant=TENANT_A):
    return env.sql("SELECT count(*) FROM demo_comparisons WHERE tenant_id = :t", t=tenant)[0][0]


# The worker's row and the limit ----------------------------------------------------------------------
def test_the_fourth_comparison_is_refused_and_every_earlier_report_still_opens(env_factory):
    env = env_factory(demo_comparison_limit=3)
    done = [_done(env, n=n) for n in range(3)]
    assert env.sql("SELECT comparison_id FROM demo_comparisons ORDER BY 1") == \
        sorted((uuid.UUID(cid),) for _, cid in done)
    assert _state(env) == {"limit": 3, "used": 3, "in_flight": 0, "remaining": 0,
                           "feedback": {"submitted": False, "discount_offered": False}}
    pid, a, b = _pair(env, n=3)  # uploading a version is not a comparison
    before = env.sql("SELECT (SELECT count(*) FROM comparisons), (SELECT count(*) FROM jobs), "
                     "(SELECT count(*) FROM source_versions)")
    _refused(env.compare(pid, a, b), used=3)
    assert env.sql("SELECT (SELECT count(*) FROM comparisons), (SELECT count(*) FROM jobs), "
                   "(SELECT count(*) FROM source_versions)") == before  # nothing written, nothing charged
    for _, cid in done:
        assert env.get("/comparisons/" + cid).json()["status"] in ("complete", "partial")
        assert env.get("/comparisons/%s/findings" % cid).status_code == 200
    assert env.compare(*_pair(env, TOKEN_B), token=TOKEN_B).status_code == 202  # another account is not affected


def test_the_counted_row_is_written_once_with_the_terminal_status(env_factory):
    env = env_factory(demo_comparison_limit=3)
    pid, a, b = _pair(env)
    cid = env.compare(pid, a, b).json()["id"]
    assert _counted(env) == 0 and _state(env)["in_flight"] == 1  # queued: it holds a place, it is not counted
    env.worker.run_until_idle()
    assert env.sql("SELECT d.comparison_id, c.status FROM demo_comparisons d JOIN comparisons c "
                   "ON c.id = d.comparison_id") == [(uuid.UUID(cid), "complete")]
    env.worker.handle_compare(TENANT_A, uuid.UUID(cid))  # a late or repeated job
    with env.db.tenant_scope(TENANT_A) as repo:
        assert repo.record_demo_comparison(uuid.UUID(cid)) is False  # the primary key refuses a second row
    assert _counted(env) == 1 and _state(env) == {**_state(env), "used": 1, "in_flight": 0, "remaining": 2}


def test_a_failed_third_comparison_does_not_count(env_factory):
    env = env_factory(demo_comparison_limit=3)
    _done(env, n=0), _done(env, n=1)
    pid = env.project()
    payload = {"earlier": {"label": "ok", "text": "Budget: EUR 100."}, "later": {"label": "bad PDF", "file": True},
               "scope": "partial"}
    failed = env.client.post("/projects/%s/comparisons" % pid,
                             headers={**auth(TOKEN_A), "Idempotency-Key": str(uuid.uuid4())},
                             data={"comparison": json.dumps(payload)},
                             files={"later_file": ("bad.pdf", b"%PDF-1.7 broken")})
    assert failed.status_code == 202, failed.text
    assert _state(env)["remaining"] == 0  # in flight: it holds the third place
    env.worker.run_until_idle()
    assert env.get("/comparisons/" + failed.json()["id"]).json()["status"] == "failed"
    assert _counted(env) == 2 and _state(env)["remaining"] == 1  # the count is unchanged, the place is free
    _done(env, n=2)
    _refused(env.compare(*_pair(env, n=3)), used=3)


def test_a_job_that_fails_for_good_does_not_count(env_factory):
    env = env_factory(demo_comparison_limit=3)
    pid, a, b = _pair(env)
    cid = env.compare(pid, a, b).json()["id"]
    env.sql("UPDATE jobs SET attempts = max_attempts, status = 'running', "
            "locked_at = now() - interval '1 day' WHERE kind = 'compare' RETURNING id")
    env.worker.run_until_idle()
    assert env.get("/comparisons/" + cid).json()["status"] == "failed"
    assert _counted(env) == 0 and _state(env)["remaining"] == 3


def test_two_simultaneous_starts_at_two_used_admit_exactly_one(env_factory):
    env = env_factory(demo_comparison_limit=3)
    _done(env, n=0), _done(env, n=1)
    pairs = [_pair(env, n=n) for n in (2, 3)]  # two projects: the project lock doesn't serialise them
    start = Barrier(2)

    def submit(pair):
        pid, a, b = pair
        with TestClient(env.client.app, raise_server_exceptions=False) as client:
            start.wait(timeout=5)
            return client.post("/projects/%s/comparisons" % pid, json={"earlier_id": a, "later_id": b, "scope": "complete"},
                               headers={**auth(TOKEN_A), "Idempotency-Key": str(uuid.uuid4())})

    for _ in range(5):  # the race is real: repeat it, restoring two used each time
        with ThreadPoolExecutor(max_workers=2) as pool:
            responses = list(pool.map(submit, pairs))
        assert sorted(r.status_code for r in responses) == [202, 403], [r.text for r in responses]
        assert env.sql("SELECT count(*) FROM comparisons WHERE status IN ('queued', 'waiting_for_versions')") == [(1,)]
        env.sql("DELETE FROM jobs WHERE kind = 'compare' RETURNING id")
        env.sql("DELETE FROM comparisons WHERE status = 'queued' RETURNING id")


def test_an_idempotent_retry_at_the_limit_is_not_refused(env_factory):
    env = env_factory(demo_comparison_limit=3)
    _done(env, n=0), _done(env, n=1)
    pid, a, b = _pair(env, n=2)
    headers = {**auth(TOKEN_A), "Idempotency-Key": str(uuid.uuid4())}
    pair = {"earlier_id": a, "later_id": b, "scope": "complete"}
    first = env.client.post("/projects/%s/comparisons" % pid, json=pair, headers=headers)
    assert first.status_code == 202
    retry = env.client.post("/projects/%s/comparisons" % pid, json=pair, headers=headers)  # in flight, at the limit
    assert retry.status_code == 202 and retry.json()["id"] == first.json()["id"]
    env.worker.run_until_idle()
    again = env.client.post("/projects/%s/comparisons" % pid, json=pair, headers=headers)  # finished, at the limit
    assert again.status_code == 202 and again.json() == {"id": first.json()["id"], "status": "complete"}
    _refused(env.compare(pid, a, b), used=3)
    assert env.sql("SELECT count(*) FROM comparisons") == [(3,)] and _counted(env) == 3


def test_deleting_a_project_gives_nothing_back(env_factory):
    env = env_factory(demo_comparison_limit=3)
    done = [_done(env, n=n) for n in range(3)]
    for pid, _ in done:
        assert env.client.delete("/projects/" + pid, headers=auth(TOKEN_A)).status_code == 204
    assert env.sql("SELECT count(*) FROM comparisons WHERE tenant_id = :t", t=TENANT_A) == [(0,)]
    assert _counted(env) == 3 and _state(env)["remaining"] == 0
    _refused(env.compare(*_pair(env, n=3)), used=3)


def test_deleting_a_project_with_a_comparison_in_flight_frees_its_place(env_factory):
    env = env_factory(demo_comparison_limit=3)
    pid, a, b = _pair(env)
    assert env.compare(pid, a, b).status_code == 202
    assert _state(env)["in_flight"] == 1
    assert env.client.delete("/projects/" + pid, headers=auth(TOKEN_A)).status_code == 204
    assert _state(env) == {**_state(env), "used": 0, "in_flight": 0, "remaining": 3}


def test_limit_zero_refuses_nothing_and_still_counts(env):
    for n in range(4):
        _done(env, n=n)
    assert _counted(env) == 4  # counted, so switching the limit on later starts at the real number
    assert _state(env) == {"limit": None, "used": 4, "in_flight": 0, "remaining": None,
                           "feedback": {"submitted": False, "discount_offered": False}}


# State and feedback ----------------------------------------------------------------------------------
def test_the_session_carries_the_demo_state(env_factory):
    env = env_factory(demo_comparison_limit=3, demo_feedback_discount=True)
    _done(env)
    pid, a, b = _pair(env, n=1)
    assert env.compare(pid, a, b).status_code == 202  # in flight
    expected = {"limit": 3, "used": 1, "in_flight": 1, "remaining": 1,
                "feedback": {"submitted": False, "discount_offered": True}}
    session = env.client.post("/session", headers=auth(TOKEN_A))
    assert session.status_code == 200 and session.json()["demo"] == expected == _state(env)
    assert env.client.post("/session", headers=auth(TOKEN_B)).json()["demo"] == {
        "limit": 3, "used": 0, "in_flight": 0, "remaining": 3, "feedback": {"submitted": False, "discount_offered": True}}


def test_feedback_is_one_row_per_account_and_invisible_to_another_tenant(env_factory):
    env = env_factory(demo_comparison_limit=3)
    body = {"missing": "other", "missing_other": "Ein Export als PDF wäre gut.", "anything_else": "Danke.",
            "price": "eur_10"}
    r = env.client.post("/me/demo-feedback", json=body, headers=auth(TOKEN_A))
    assert r.status_code == 201 and r.json()["feedback"]["submitted"] is True and r.json()["remaining"] == 3
    second = env.client.post("/me/demo-feedback", json=GOOD, headers=auth(TOKEN_A))
    assert second.status_code == 409 and second.json()["code"] == "already_answered"
    assert env.sql("SELECT account_id, tenant_id, missing, missing_other, anything_else, price, plan_id "
                   "FROM demo_feedback") == [(env.users[SUBJECT_A], TENANT_A, "other", "Ein Export als PDF wäre gut.",
                                              "Danke.", "eur_10", "individual_20_v1")]
    assert _state(env, TOKEN_B)["feedback"]["submitted"] is False
    with env.db.tenant_scope(TENANT_B) as repo:
        assert repo.demo_feedback(env.users[SUBJECT_A]) is None and repo.demo_counts() == (0, 0)
    assert env.client.post("/me/demo-feedback", json=GOOD, headers=auth(TOKEN_B)).status_code == 201


def test_two_simultaneous_submissions_store_one_answer(env_factory):
    env = env_factory(demo_comparison_limit=3)
    start = Barrier(2)

    def submit(price):
        with TestClient(env.client.app, raise_server_exceptions=False) as client:
            start.wait(timeout=5)
            return client.post("/me/demo-feedback", json={"missing": "team", "price": price}, headers=auth(TOKEN_A))

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(submit, ("eur_0", "eur_5")))
    assert sorted(r.status_code for r in responses) == [201, 409], [r.text for r in responses]
    assert env.sql("SELECT count(*) FROM demo_feedback") == [(1,)]


def test_the_database_refuses_text_without_other_and_unknown_codes(env):
    import pytest
    from sqlalchemy.exc import IntegrityError
    insert = ("INSERT INTO demo_feedback (account_id, tenant_id, missing, missing_other, price, plan_id, created_at) "
              "VALUES (:u, :t, :m, :o, :p, 'individual_20_v1', now()) RETURNING account_id")
    for missing, other, price in (("team", "text", "eur_0"), ("other", None, "eur_0"), ("nope", None, "eur_0"),
                                  ("team", None, "eur_99")):
        with pytest.raises(IntegrityError):
            env.sql(insert, u=env.users[SUBJECT_A], t=TENANT_A, m=missing, o=other, p=price)


# The migration ---------------------------------------------------------------------------------------
def test_the_migration_counts_existing_finished_comparisons_and_downgrades(scratch):  # noqa: F811
    url, engine = scratch
    upgrade(OWNER_URL, BEFORE)
    statuses = {"complete": None, "partial": None, "failed": None, "running": None, "queued": None}
    with Session(engine) as s, s.begin():  # the compose superuser: rows of two tenants, before the revision
        for tenant in (TENANT_A, TENANT_B):
            project = Project(tenant_id=tenant, name="Existing")
            s.add(project)
            s.flush()
            versions = [SourceVersion(tenant_id=tenant, project_id=project.id, label="v", kind="text",
                                      original_object_key="%s/%s" % (tenant, uuid.uuid4()), sha256="0" * 64,
                                      size_bytes=1, status="parsed", parse_warnings=[]) for _ in range(2)]
            s.add_all(versions)
            s.flush()
            for status in statuses if tenant == TENANT_A else ("partial",):
                row = Comparison(tenant_id=tenant, project_id=project.id, earlier_id=versions[0].id,
                                 later_id=versions[1].id, scope_snapshot="complete", pipeline_version="p",
                                 model_config_id="m", status=status, cost_ceiling=1, warnings=[])
                s.add(row)
                s.flush()
                if tenant == TENANT_A:
                    statuses[status] = row.id
    upgrade(OWNER_URL)
    assert revision(engine) == HEAD == THIS and model_diffs(engine) == []
    with engine.begin() as conn:
        counted = conn.execute(text("SELECT tenant_id, comparison_id FROM demo_comparisons "
                                    "WHERE tenant_id = :t ORDER BY 2"), {"t": TENANT_A}).all()
        assert counted == sorted((TENANT_A, statuses[s]) for s in ("complete", "partial"))
        assert conn.execute(text("SELECT count(*) FROM demo_comparisons WHERE tenant_id = :t"),
                            {"t": TENANT_B}).scalar_one() == 1
        assert conn.execute(text("SELECT count(*) FROM demo_comparisons d JOIN comparisons c ON c.id = d.comparison_id "
                                 "WHERE d.counted_at <> c.updated_at")).scalar_one() == 0
    owner = create_engine(OWNER_URL, poolclass=NullPool, hide_parameters=True)
    with owner.begin() as conn:
        command.downgrade(alembic_config(conn), BEFORE)
    owner.dispose()
    assert revision(engine) == BEFORE
    with engine.begin() as conn:
        tables = {row[0] for row in conn.execute(text(
            "SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'"))}
        assert not tables & {"demo_comparisons", "demo_feedback"}
        assert conn.execute(text("SELECT count(*) FROM comparisons")).scalar_one() == 6  # the comparisons stay
