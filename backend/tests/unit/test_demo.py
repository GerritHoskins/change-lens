"""`GET /me/demo` and `POST /me/demo-feedback` (docs/demo-wall-handoff.md), with no services.

The routes, GUARD and `TenantRepo` run unchanged over in-memory SQLite (tests/demo_fixture.py). The limit's
admission check is in test_demo_limit.py; the lock, the snapshot, row-level security and account deletion
in Postgres are in tests/integration/test_demo_db.py.
"""
from contextlib import contextmanager
import dataclasses
import logging
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from changelens.api.app import create_app
from changelens.api.demo import OTHER_MIN, TEXT_MAX, clean_text
from changelens.config import Settings
from changelens.domain import TenantRepo
from changelens.domain.demo import PLAN_ID
from changelens.domain.models import DemoFeedback, Project
from changelens.storage import MemoryObjectStore
from demo_fixture import OFF, add_comparison, create_demo_tables, fresh
from helpers import DEV_TOKENS, SUBJECT_A, SUBJECT_B, TOKEN_A, TOKEN_B, auth
from identity_fixture import SqliteIdentity, sqlite_engine

TENANT_A, TENANT_B = uuid.uuid4(), uuid.uuid4()
GOOD = {"missing": "share_report", "price": "eur_10"}
OTHER_TEXT = "x" * OTHER_MIN


class DemoDb:
    def __init__(self):
        self.engine = sqlite_engine()
        self.identity = SqliteIdentity(self.engine)
        self.identity_scope = self.identity.identity_scope
        create_demo_tables(self.engine)
        self._sessions = sessionmaker(self.engine, expire_on_commit=False)
        self.user_a = self.identity.seed(SUBJECT_A, TENANT_A)
        self.user_b = self.identity.seed(SUBJECT_B, TENANT_B)

    @contextmanager
    def tenant_scope(self, tenant_id):
        with self._sessions() as s, s.begin():
            yield TenantRepo(s, tenant_id)

    def rows(self):
        with self._sessions() as s:
            return list(s.scalars(select(DemoFeedback)))

    def project(self, tenant=TENANT_A, deleted=False):
        with self.tenant_scope(tenant) as repo:
            project = repo.add(Project(name="Synthetic project"))
            if deleted:
                project.deleted_at = project.created_at
            return project.id

    def count(self, n, tenant=TENANT_A):
        with self.tenant_scope(tenant) as repo:
            return [repo.record_demo_comparison(uuid.uuid4()) for _ in range(n)]


def _settings(**overrides):
    return Settings(database_url="postgresql+psycopg://nobody@127.0.0.1:1/none", s3_endpoint="http://unused",
                    s3_access_key="x", s3_secret_key="x", s3_bucket="x", dev_tokens=DEV_TOKENS, **overrides)


def _client(db, **overrides):
    return TestClient(create_app(_settings(**overrides), db, MemoryObjectStore()), raise_server_exceptions=False)


@pytest.fixture()
def env():
    db = DemoDb()
    return _client(db), db


def state(client, token=TOKEN_A):
    r = client.get("/me/demo", headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


def send(client, body, token=TOKEN_A):
    return client.post("/me/demo-feedback", json=body, headers=auth(token))


def _is_problem(r, status, code):
    assert r.status_code == status, r.text
    assert r.headers["content-type"].startswith("application/problem+json")
    assert r.json()["code"] == code


# State ---------------------------------------------------------------------------------------------
def test_a_new_account_has_all_its_comparisons_left(env):
    client, _ = env
    assert state(client) == fresh()


def test_remaining_counts_finished_and_in_flight_comparisons_and_never_goes_below_zero(env):
    client, db = env
    project = db.project()
    db.count(1)
    add_comparison(db.engine, TENANT_A, project, "running")
    assert state(client) == {**fresh(), "used": 1, "in_flight": 1, "remaining": 1}
    add_comparison(db.engine, TENANT_A, project, "waiting_for_versions")
    add_comparison(db.engine, TENANT_A, project, "queued")
    assert state(client) == {**fresh(), "used": 1, "in_flight": 3, "remaining": 0}


def test_failed_and_finished_rows_of_the_comparisons_table_are_not_in_flight(env):
    client, db = env
    project = db.project()
    for status in ("failed", "complete", "partial"):
        add_comparison(db.engine, TENANT_A, project, status)
    assert state(client) == fresh()  # finished ones count through `demo_comparisons` only


def test_an_in_flight_comparison_of_a_project_being_deleted_holds_no_place(env):
    client, db = env
    add_comparison(db.engine, TENANT_A, db.project(deleted=True), "running")
    assert state(client) == fresh()


def test_a_comparison_is_counted_once(env):
    client, db = env
    comparison = uuid.uuid4()
    with db.tenant_scope(TENANT_A) as repo:
        assert repo.record_demo_comparison(comparison) is True
        assert repo.record_demo_comparison(comparison) is False
    with db.tenant_scope(TENANT_A) as repo:
        assert repo.record_demo_comparison(comparison) is False
    assert state(client)["used"] == 1


def test_each_account_sees_only_its_own_numbers_and_feedback(env):
    client, db = env
    db.count(2, TENANT_A)
    add_comparison(db.engine, TENANT_A, db.project(TENANT_A), "queued")
    assert send(client, GOOD, TOKEN_A).status_code == 201
    assert state(client, TOKEN_B) == fresh()
    assert state(client, TOKEN_A)["remaining"] == 0


def test_with_the_limit_off_limit_and_remaining_are_null(env):
    _, db = env
    db.count(5)
    assert state(_client(db, demo_comparison_limit=0)) == {**OFF, "used": 5}


def test_the_discount_flag_is_the_setting_and_changes_nothing_else(env):
    _, db = env
    on = _client(db, demo_feedback_discount=True)
    assert state(on) == {**fresh(), "feedback": {"submitted": False, "discount_offered": True}}
    assert send(on, GOOD).json()["feedback"] == {"submitted": True, "discount_offered": True}


# Feedback ------------------------------------------------------------------------------------------
def test_feedback_is_stored_once_with_the_plan_and_returns_the_new_state(env):
    client, db = env
    r = send(client, {**GOOD, "anything_else": "  A calmer export.  "})
    assert r.status_code == 201 and r.json() == {**fresh(), "feedback": {"submitted": True, "discount_offered": False}}
    [row] = db.rows()
    assert (row.account_id, row.tenant_id, row.missing, row.missing_other, row.anything_else, row.price,
            row.plan_id) == (db.user_a, TENANT_A, "share_report", None, "A calmer export.", "eur_10", PLAN_ID)
    assert row.created_at is not None and state(client)["feedback"]["submitted"] is True


def test_feedback_never_gives_a_comparison_back(env):
    client, db = env
    db.count(3)
    assert send(client, GOOD).json()["remaining"] == 0
    assert state(client)["remaining"] == 0


def test_a_second_submission_is_already_answered_and_changes_nothing(env):
    client, db = env
    assert send(client, GOOD).status_code == 201
    _is_problem(send(client, {"missing": "team", "price": "eur_0"}), 409, "already_answered")
    assert [(row.missing, row.price) for row in db.rows()] == [("share_report", "eur_10")]


def test_other_needs_its_text_at_the_minimum_length(env):
    client, db = env
    _is_problem(send(client, {"missing": "other", "price": "eur_5"}), 422, "invalid_request")
    _is_problem(send(client, {"missing": "other", "missing_other": None, "price": "eur_5"}), 422, "invalid_request")
    _is_problem(send(client, {"missing": "other", "missing_other": "x" * 19, "price": "eur_5"}), 422,
                "invalid_request")
    # Padding is not text: 19 characters with spaces around them are still 19.
    _is_problem(send(client, {"missing": "other", "missing_other": "  " + "x" * 19 + "  ", "price": "eur_5"}), 422,
                "invalid_request")
    assert db.rows() == []
    assert send(client, {"missing": "other", "missing_other": OTHER_TEXT, "price": "eur_5"}).status_code == 201
    assert [row.missing_other for row in db.rows()] == [OTHER_TEXT]


def test_free_text_is_limited_after_trimming(env):
    client, db = env
    _is_problem(send(client, {**GOOD, "anything_else": "y" * (TEXT_MAX + 1)}), 422, "invalid_request")
    _is_problem(send(client, {"missing": "other", "missing_other": "y" * (TEXT_MAX + 1), "price": "eur_0"}), 422,
                "invalid_request")
    assert db.rows() == []
    assert send(client, {**GOOD, "anything_else": " " + "y" * TEXT_MAX + " "}).status_code == 201
    assert len(db.rows()[0].anything_else) == TEXT_MAX


def test_control_characters_are_removed_and_the_text_is_stored_as_written_otherwise(env):
    client, db = env
    written = "Zwei Zeilen:\r\nÄpfel \x00und\x07 Birnen\t – “fertig” \U0001f469‍\U0001f4bb  "
    assert send(client, {**GOOD, "anything_else": written}).status_code == 201
    assert db.rows()[0].anything_else == "Zwei Zeilen:\nÄpfel und Birnen – “fertig” \U0001f469‍\U0001f4bb"
    assert clean_text("a\ud800b") == "ab"  # a lone surrogate can't be stored
    assert clean_text(" \x00\t ") is None and clean_text(None) is None


def test_empty_optional_text_is_stored_as_no_text(env):
    client, db = env
    assert send(client, {**GOOD, "anything_else": "   ", "missing_other": None}).status_code == 201
    assert (db.rows()[0].anything_else, db.rows()[0].missing_other) == (None, None)


@pytest.mark.parametrize("body", [
    {},
    {"missing": "share_report"},
    {"price": "eur_10"},
    {"missing": None, "price": "eur_10"},
    {"missing": "share_report", "price": None},
    {"missing": "unknown_code", "price": "eur_10"},
    {"missing": "share_report", "price": "eur_20"},
    {"missing": "share_report", "price": 10},
    {"missing": ["share_report"], "price": "eur_10"},
    {"missing": "share_report", "missing_other": "x" * 30, "price": "eur_10"},  # text without "other"
    {"missing": "share_report", "anything_else": 5, "price": "eur_10"},
    {"missing": "other", "missing_other": 20 * ["x"], "price": "eur_10"},
    {"missing": "share_report", "price": "eur_10", "plan_id": "another_plan"},
    {"missing": "share_report", "price": "eur_10", "email": "someone@example.test"},
    [],
    None,
])
def test_bad_bodies_are_rejected_without_writing(env, body):
    client, db = env
    _is_problem(send(client, body), 422, "invalid_request")
    assert db.rows() == []


MARKER = "MARKER-confidential-client-text-123"


@pytest.mark.parametrize("body", [
    {"missing": "other", "missing_other": MARKER, "price": "eur_20"},
    {"missing": MARKER, "price": "eur_10"},
    {"missing": "share_report", "price": MARKER},
    {"missing": "share_report", "missing_other": MARKER, "price": "eur_10"},
    {"missing": "share_report", "anything_else": MARKER * 20, "price": "eur_10"},
    {"missing": "share_report", "price": "eur_10", MARKER: 1},
])
def test_error_bodies_and_logs_never_carry_the_input(env, body, caplog):
    client, _ = env
    with caplog.at_level(logging.DEBUG):
        r = send(client, body)
    assert r.status_code == 422 and "MARKER" not in r.text
    assert not any("MARKER" in rec.getMessage() for rec in caplog.records if rec.name.startswith("changelens"))


def test_free_text_appears_in_no_log_line(env, caplog):
    client, _ = env
    with caplog.at_level(logging.DEBUG):  # every logger, SQL included: parameters are hidden
        assert send(client, {"missing": "other", "missing_other": MARKER, "anything_else": MARKER + " again",
                             "price": "eur_15"}).status_code == 201
        _is_problem(send(client, {"missing": "other", "missing_other": MARKER, "price": "eur_15"}), 409,
                    "already_answered")
        state(client)
    lines = [rec.getMessage() for rec in caplog.records]
    assert "POST /me/demo-feedback 201" in lines and "POST /me/demo-feedback 409" in lines
    assert not any("MARKER" in line for line in lines)


@pytest.mark.parametrize("headers", [{}, auth("wrong-token-wrong-token"), {"Authorization": "Bearer"}])
def test_requests_without_a_valid_token_are_unauthenticated(env, headers):
    client, db = env
    for r in (client.get("/me/demo", headers=headers), client.post("/me/demo-feedback", json=GOOD, headers=headers)):
        _is_problem(r, 401, "unauthenticated")
    assert db.rows() == []


# Settings ------------------------------------------------------------------------------------------
def test_the_limit_and_the_discount_are_optional_settings(monkeypatch):
    assert Settings.__dataclass_fields__["demo_comparison_limit"].default == 3
    assert Settings.__dataclass_fields__["demo_feedback_discount"].default is False
    for bad in (-1, 1001, True, "3", 2.5):
        with pytest.raises(ValueError):
            dataclasses.replace(_settings(), demo_comparison_limit=bad)
    with pytest.raises(ValueError):
        dataclasses.replace(_settings(), demo_feedback_discount="yes")
    monkeypatch.setenv("CHANGELENS_ENV", "local")
    monkeypatch.setenv("CHANGELENS_DEV_TOKEN", "t" * 20)
    for name in ("CHANGELENS_AUTH_MODE", "CHANGELENS_DEMO_COMPARISON_LIMIT", "CHANGELENS_DEMO_FEEDBACK_DISCOUNT"):
        monkeypatch.delenv(name, raising=False)
    for worker in (False, True):  # the worker starts with and without them: it reads neither
        settings = Settings.from_env(worker=worker)
        assert (settings.demo_comparison_limit, settings.demo_feedback_discount) == (3, False)
    monkeypatch.setenv("CHANGELENS_DEMO_COMPARISON_LIMIT", "0")
    monkeypatch.setenv("CHANGELENS_DEMO_FEEDBACK_DISCOUNT", "true")
    for worker in (False, True):
        settings = Settings.from_env(worker=worker)
        assert (settings.demo_comparison_limit, settings.demo_feedback_discount) == (0, True)
    for name, value in (("CHANGELENS_DEMO_COMPARISON_LIMIT", "three"), ("CHANGELENS_DEMO_FEEDBACK_DISCOUNT", "maybe")):
        monkeypatch.setenv(name, value)
        with pytest.raises(RuntimeError):
            Settings.from_env()
        monkeypatch.delenv(name)
