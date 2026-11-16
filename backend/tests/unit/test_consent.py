"""GET / PUT /me/consent: usage-events consent, D-18 tier B (Task 1; docs/api-contracts-draft.md C1).

The routes, GUARD and `TenantRepo` run unchanged over an in-memory SQLite stand-in for the consent, user
and membership tables. Answers are append-only rows; the newest answer for the current policy version is
the account's answer. Tenant isolation in Postgres is covered in tests/integration/test_consent_db.py.
"""
from contextlib import contextmanager
import dataclasses
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from changelens.api.app import create_app
from changelens.config import Settings
from changelens.domain import TenantRepo
from changelens.domain.models import ConsentEvent
from changelens.storage import MemoryObjectStore
from helpers import DEV_TOKENS, SUBJECT_A, SUBJECT_B, TOKEN_A, TOKEN_B, auth
from identity_fixture import SqliteIdentity, sqlite_engine

TENANT_A, TENANT_B = uuid.uuid4(), uuid.uuid4()
CURRENT = "2026-11-13"


class ConsentDb:
    def __init__(self):
        self.engine = sqlite_engine()
        self.identity = SqliteIdentity(self.engine)
        self.identity_scope = self.identity.identity_scope
        ConsentEvent.__table__.create(self.engine)
        self._sessions = sessionmaker(self.engine, expire_on_commit=False)
        self.user_a = self.identity.seed(SUBJECT_A, TENANT_A)
        self.user_b = self.identity.seed(SUBJECT_B, TENANT_B)

    @contextmanager
    def tenant_scope(self, tenant_id):
        with self._sessions() as s, s.begin():
            yield TenantRepo(s, tenant_id)

    def rows(self):
        with self._sessions() as s:
            return list(s.scalars(select(ConsentEvent)))


def _settings(**overrides):
    return Settings(database_url="postgresql+psycopg://nobody@127.0.0.1:1/none", s3_endpoint="http://unused",
                    s3_access_key="x", s3_secret_key="x", s3_bucket="x", dev_tokens=DEV_TOKENS, **overrides)


def _client(settings, db):
    return TestClient(create_app(settings, db, MemoryObjectStore()), raise_server_exceptions=False)


@pytest.fixture()
def env():
    db = ConsentDb()
    return _client(_settings(), db), db


def unanswered(version=CURRENT):
    return {"usage_events": {"granted": None, "policy_version": version, "decided_at": None}}


def get(client, token=TOKEN_A):
    r = client.get("/me/consent", headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


def put(client, granted, version=CURRENT, token=TOKEN_A):
    r = client.put("/me/consent", json={"usage_events": {"granted": granted, "policy_version": version}},
                   headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


def _is_problem(r, status, code):
    assert r.status_code == status, r.text
    assert r.headers["content-type"].startswith("application/problem+json")
    assert r.json()["code"] == code


def test_no_answer_reads_as_unanswered_for_the_current_policy_and_reading_writes_nothing(env):
    client, db = env
    assert get(client) == unanswered()
    assert db.rows() == []


def test_allow_is_stored_with_the_policy_version_and_returned(env):
    client, db = env
    body = put(client, True)
    assert body["usage_events"]["granted"] is True
    assert body["usage_events"]["policy_version"] == CURRENT
    assert body["usage_events"]["decided_at"] is not None
    assert get(client) == body
    [row] = db.rows()
    assert (row.account_id, row.tenant_id, row.purpose, row.granted, row.policy_version) == \
        (db.user_a, TENANT_A, "usage_events", True, CURRENT)


def test_withdrawal_appends_a_row_and_the_newest_answer_wins(env):
    client, db = env
    put(client, True)
    assert put(client, False)["usage_events"]["granted"] is False
    assert get(client)["usage_events"]["granted"] is False
    assert [row.granted for row in sorted(db.rows(), key=lambda r: r.decided_at)] == [True, False]


def test_decline_is_an_answer_not_unanswered(env):
    client, _ = env
    put(client, False)
    assert get(client)["usage_events"]["granted"] is False


def test_a_stale_policy_version_is_refused_and_writes_nothing(env):
    client, db = env
    r = client.put("/me/consent", json={"usage_events": {"granted": True, "policy_version": "2025-01-01"}},
                   headers=auth(TOKEN_A))
    _is_problem(r, 409, "policy_version_stale")
    assert db.rows() == []


def test_a_new_policy_version_makes_an_earlier_answer_unanswered_again(env):
    _, db = env
    put(_client(_settings(), db), True)
    newer = _client(_settings(consent_policy_version="2027-02-01"), db)
    assert get(newer) == unanswered("2027-02-01")
    assert put(newer, False, "2027-02-01")["usage_events"]["granted"] is False


def test_each_token_reads_and_writes_only_its_own_account(env):
    client, db = env
    put(client, True, token=TOKEN_A)
    assert get(client, TOKEN_B) == unanswered()
    put(client, False, token=TOKEN_B)
    assert get(client, TOKEN_A)["usage_events"]["granted"] is True
    assert {row.account_id for row in db.rows()} == {db.user_a, db.user_b}


@pytest.mark.parametrize("body", [
    {},
    {"usage_events": {}},
    {"usage_events": {"granted": True}},
    {"usage_events": {"policy_version": CURRENT}},
    {"usage_events": {"granted": None, "policy_version": CURRENT}},
    {"usage_events": {"granted": "true", "policy_version": CURRENT}},
    {"usage_events": {"granted": 1, "policy_version": CURRENT}},
    {"usage_events": {"granted": True, "policy_version": 20261113}},
    {"usage_events": {"granted": True, "policy_version": ""}},
    {"usage_events": {"granted": True, "policy_version": CURRENT, "extra": 1}},
    {"usage_events": {"granted": True, "policy_version": CURRENT}, "analytics": True},
    {"usage_events": True},
    [],
    None,
])
def test_bad_bodies_are_rejected_without_writing(env, body):
    client, db = env
    r = client.put("/me/consent", json=body, headers=auth(TOKEN_A))
    _is_problem(r, 422, "invalid_request")
    assert db.rows() == []


@pytest.mark.parametrize("body", [
    {"usage_events": {"granted": "MARKER-G-123", "policy_version": CURRENT}},
    {"usage_events": {"granted": True, "policy_version": "MARKER-V-123"}},
    {"usage_events": {"granted": True, "policy_version": CURRENT, "MARKER-K-123": 1}},
])
def test_error_bodies_do_not_echo_input(env, body):
    client, _ = env
    r = client.put("/me/consent", json=body, headers=auth(TOKEN_A))
    assert r.status_code in (409, 422)
    assert "MARKER" not in r.text


@pytest.mark.parametrize("headers", [{}, auth("wrong-token-wrong-token"), {"Authorization": "Bearer"}])
def test_requests_without_a_valid_token_are_unauthenticated(env, headers):
    client, db = env
    for r in (client.get("/me/consent", headers=headers),
              client.put("/me/consent", json={"usage_events": {"granted": True, "policy_version": CURRENT}},
                         headers=headers)):
        _is_problem(r, 401, "unauthenticated")
    assert db.rows() == []


def test_the_policy_version_is_configuration():
    assert Settings.__dataclass_fields__["consent_policy_version"].default == CURRENT
    with pytest.raises(ValueError):
        dataclasses.replace(_settings(), consent_policy_version="")
