"""The demo limit at comparison creation and in the worker (docs/demo-wall-handoff.md), with no services.

Creation runs through the real HTTP boundary over the in-memory repository of comparison_fixture.py; the
worker runs over test_worker_budget.py's. Two simultaneous starts, project deletion and the real worker
writing the counted row are in tests/integration/test_demo_db.py.
"""
import dataclasses
from decimal import Decimal
import uuid

import pytest

from changelens.config import Settings
from changelens.storage import MemoryObjectStore
from changelens.worker import Worker
from comparison_fixture import Environment
from helpers import TOKEN_A, TOKEN_B, auth
from test_worker_budget import TransactionalDb as WorkerDb


@pytest.fixture
def env(monkeypatch):
    environment = Environment(monkeypatch, demo_limit=3)
    yield environment
    environment.client.close()


def body(n=0):
    return {"earlier": {"label": "Earlier", "text": "Original synthetic brief %d" % n},
            "later": {"label": "Later", "text": "Updated synthetic brief %d" % n}, "scope": "partial"}


def start(env, n, **kwargs):
    return env.post(body(n), key="demo-limit-test-key-%04d" % n, **kwargs)


def finish(env, response, status):
    """What the worker does at the end of a run: the terminal status and, unless it failed, the counted row."""
    comparison_id = uuid.UUID(response.json()["id"])
    with env.db.tenant_scope(env.tenant) as repo:
        repo.comparison(comparison_id).status = status
        if status != "failed":
            repo.record_demo_comparison(comparison_id)


def refused(response, used, in_flight):
    assert response.status_code == 403, response.text
    assert response.headers["content-type"].startswith("application/problem+json")
    problem = response.json()
    assert (problem["code"], problem["status"], problem["title"]) == ("demo_limit_reached", 403,
                                                                      "Demo comparisons used")
    assert (problem["used"], problem["in_flight"], problem["limit"]) == (used, in_flight, 3)


def test_the_fourth_comparison_is_refused_and_writes_nothing(env):
    for n in range(3):
        finish(env, start(env, n), "complete" if n else "partial")
    written = len(env.versions), len(env.store.objects), len(env.queued)
    refused(start(env, 3), used=3, in_flight=0)
    assert len(env.comparisons) == 3 and (len(env.versions), len(env.store.objects), len(env.queued)) == written
    assert not env.db.intents


def test_in_flight_comparisons_hold_a_place(env):
    for n in range(3):
        assert start(env, n).status_code == 202
    refused(start(env, 3), used=0, in_flight=3)


def test_a_failed_comparison_does_not_count_and_frees_its_place(env):
    finish(env, start(env, 0), "complete")
    finish(env, start(env, 1), "complete")
    third = start(env, 2)
    refused(start(env, 3), used=2, in_flight=1)
    finish(env, third, "failed")
    assert start(env, 4).status_code == 202  # the place of the failed third is free again
    refused(start(env, 5), used=2, in_flight=1)


def test_an_idempotent_retry_at_the_limit_returns_the_same_comparison(env):
    responses = [start(env, n) for n in range(3)]
    finish(env, responses[0], "complete")
    for n, first in enumerate(responses):
        retry = start(env, n)
        assert retry.status_code == 202 and retry.json()["id"] == first.json()["id"]
    refused(start(env, 3), used=1, in_flight=2)
    assert len(env.comparisons) == 3


def test_a_rejected_input_is_not_counted(env):
    bad = env.post({"earlier": {"label": "Earlier", "text": "x"}, "scope": "partial"}, key="demo-limit-test-key-bad1")
    assert bad.status_code == 422
    for n in range(3):
        assert start(env, n).status_code == 202


def test_the_limit_is_per_account(env):
    for n in range(3):
        assert start(env, n).status_code == 202
    other = env.post(body(9), key="demo-limit-test-key-0009", project=env.foreign_project, token=TOKEN_B)
    assert other.status_code == 202


def test_reports_stay_readable_at_the_limit(env):
    responses = [start(env, n) for n in range(3)]
    refused(start(env, 3), used=0, in_flight=3)
    for response in responses:
        r = env.client.get("/comparisons/" + response.json()["id"], headers=auth(TOKEN_A))
        assert r.status_code == 200, r.text


def test_limit_zero_refuses_nothing(monkeypatch):
    env = Environment(monkeypatch, demo_limit=0)
    # The account bounds (LR-10: three unfinished comparisons, eight unparsed versions) would refuse the
    # fourth start here; they have their own suite (test_account_bounds.py).
    env.client.app.state.settings = dataclasses.replace(env.settings, max_unfinished_comparisons=100, max_unparsed_versions=100)
    try:
        for n in range(6):
            assert start(env, n).status_code == 202
    finally:
        env.client.close()


def test_the_default_limit_is_three(monkeypatch):
    env = Environment(monkeypatch)
    try:
        assert Settings.__dataclass_fields__["demo_comparison_limit"].default == 3
        assert env.settings.demo_comparison_limit == 0  # this fixture's own default, for the other suites
    finally:
        env.client.close()


# The worker ------------------------------------------------------------------------------------------
def _settings():
    return Settings(database_url="unused", s3_endpoint="unused", s3_access_key="unused", s3_secret_key="unused",
                    s3_bucket="unused")


def test_the_worker_counts_a_finished_comparison_once_with_its_terminal_status():
    db = WorkerDb()
    worker = Worker(_settings(), db, MemoryObjectStore())
    worker.handle_compare(db.tenant, db.cid)
    assert db.comparison.status in ("complete", "partial") and db.state["demo"] == [db.cid]
    worker.handle_compare(db.tenant, db.cid)  # a late or repeated job: already terminal, nothing more
    worker._finish(db.tenant, db.cid, None, "complete", [])
    assert db.state["demo"] == [db.cid]


def test_the_worker_does_not_count_a_failed_comparison():
    db = WorkerDb()
    # A spend cap of zero stops the run before its first paid stage: it ends `failed` (I-8 S6).
    settings = dataclasses.replace(_settings(), tenant_monthly_spend_cap_eur=Decimal("0"))
    Worker(settings, db, MemoryObjectStore()).handle_compare(db.tenant, db.cid)
    assert db.comparison.status == "failed" and "demo" not in db.state
