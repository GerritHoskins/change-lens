"""GET / PUT /me/onboarding and the account deletion function (O-23), with no services.

The routes, GUARD and `TenantRepo` run unchanged over an in-memory SQLite stand-in for the onboarding,
user and membership tables. The account ID is the user ID (I-8 S1).
Row locking and tenant isolation in Postgres are covered in tests/integration/test_onboarding_db.py.
"""
from contextlib import contextmanager
import uuid

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from changelens.api.app import create_app
from changelens.config import Settings
from changelens.domain import TenantRepo
from changelens.domain.models import AccountOnboarding
from changelens.storage import MemoryObjectStore
from helpers import DEV_TOKENS, SUBJECT_A, SUBJECT_B, TOKEN_A, TOKEN_B, auth
from identity_fixture import SqliteIdentity, sqlite_engine

TENANT_A, TENANT_B = uuid.uuid4(), uuid.uuid4()
NOT_STARTED = {"completed": False, "step": None}
COMPLETED = {"completed": True, "step": None}


class OnboardingDb:
    """`Database.tenant_scope` and `identity_scope` without Postgres: same repositories, three tables,
    no set_config. Each dev token's user has an active owner membership in its tenant."""

    def __init__(self):
        self.engine = sqlite_engine()
        self.identity = SqliteIdentity(self.engine)
        self.identity_scope = self.identity.identity_scope
        AccountOnboarding.__table__.create(self.engine)
        self._sessions = sessionmaker(self.engine, expire_on_commit=False)
        self.user_a = self.identity.seed(SUBJECT_A, TENANT_A)
        self.user_b = self.identity.seed(SUBJECT_B, TENANT_B)

    @contextmanager
    def tenant_scope(self, tenant_id):
        with self._sessions() as s, s.begin():
            yield TenantRepo(s, tenant_id)

    def rows(self):
        with self._sessions() as s:
            return list(s.scalars(select(AccountOnboarding)))


@pytest.fixture()
def env():
    settings = Settings(database_url="postgresql+psycopg://nobody@127.0.0.1:1/none", s3_endpoint="http://unused",
                        s3_access_key="x", s3_secret_key="x", s3_bucket="x",
                        dev_tokens=DEV_TOKENS)
    db = OnboardingDb()
    return TestClient(create_app(settings, db, MemoryObjectStore()), raise_server_exceptions=False), db


def get(client, token=TOKEN_A):
    r = client.get("/me/onboarding", headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


def put(client, body, token=TOKEN_A):
    r = client.put("/me/onboarding", json=body, headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


def _is_problem(r, status, code):
    assert r.status_code == status, r.text
    assert r.headers["content-type"].startswith("application/problem+json")
    assert r.json()["code"] == code


def test_no_row_reads_as_not_started_and_reading_creates_nothing(env):
    client, db = env
    assert get(client) == NOT_STARTED
    assert db.rows() == []


def test_step_writes_store_the_last_step_seen_including_going_back(env):
    client, db = env
    assert put(client, {"step": 3}) == {"completed": False, "step": 3}
    assert put(client, {"step": 5}) == {"completed": False, "step": 5}
    assert put(client, {"step": 2}) == {"completed": False, "step": 2}
    assert put(client, {"step": 2}) == {"completed": False, "step": 2}  # idempotent
    assert get(client) == {"completed": False, "step": 2}
    [row] = db.rows()
    assert row.account_id == db.user_a and row.tenant_id == TENANT_A  # the account is the user (I-8 S1)
    assert row.onboarding_completed_at is None and row.updated_at is not None


def test_step_beyond_the_designs_step_count_is_stored_for_the_app_to_clamp(env):
    client, _ = env
    assert put(client, {"step": 32}) == {"completed": False, "step": 32}


def test_completion_sets_the_timestamp_and_clears_the_step(env):
    client, db = env
    put(client, {"step": 4})
    assert put(client, {"completed": True}) == COMPLETED
    assert get(client) == COMPLETED
    [row] = db.rows()
    assert row.onboarding_step is None and row.onboarding_completed_at is not None


def test_completion_without_a_prior_step_creates_the_row(env):
    client, db = env
    assert put(client, {"completed": True}) == COMPLETED  # Skip on step 1 before any step write
    assert len(db.rows()) == 1


def test_completion_is_never_undone_by_either_body(env):
    client, db = env
    put(client, {"completed": True})
    [before] = db.rows()
    for body in ({"step": 1}, {"step": 6}, {"completed": True}):
        assert put(client, body) == COMPLETED
    [after] = db.rows()
    assert after.onboarding_completed_at == before.onboarding_completed_at  # set once
    assert after.updated_at == before.updated_at and after.onboarding_step is None
    assert get(client) == COMPLETED


def test_each_token_reads_and_writes_only_its_own_account(env):
    client, db = env
    put(client, {"step": 4}, TOKEN_A)
    assert get(client, TOKEN_B) == NOT_STARTED
    put(client, {"completed": True}, TOKEN_B)
    assert get(client, TOKEN_A) == {"completed": False, "step": 4}
    assert {row.account_id for row in db.rows()} == {db.user_a, db.user_b}


@pytest.mark.parametrize("body", [
    {"step": 2, "completed": True},
    {"step": 2, "completed": None},
    {},
    {"step": 0},
    {"step": 33},
    {"step": -1},
    {"step": None},
    {"step": "3"},
    {"step": 3.0},
    {"step": 2.5},
    {"step": True},
    {"completed": False},
    {"completed": None},
    {"completed": "true"},
    {"completed": 1},
    {"step": 2, "extra": 1},
    {"version": 2},
    [],
    "step",
    None,
])
def test_bad_bodies_are_rejected_without_writing(env, body):
    client, db = env
    put(client, {"step": 3})
    r = client.put("/me/onboarding", json=body, headers=auth(TOKEN_A))
    _is_problem(r, 422, "invalid_request")
    assert get(client) == {"completed": False, "step": 3}


def test_malformed_json_is_invalid_request(env):
    client, db = env
    r = client.put("/me/onboarding", content=b"{step:", headers={**auth(TOKEN_A), "Content-Type": "application/json"})
    _is_problem(r, 422, "invalid_request")
    assert db.rows() == []


@pytest.mark.parametrize("body", [
    {"step": "MARKER-STEP-123"},
    {"completed": "MARKER-DONE-123"},
    {"step": 2, "MARKER-KEY-123": "MARKER-VALUE-123"},
    {"step": 999999123},
])
def test_error_bodies_do_not_echo_input(env, body):
    client, _ = env
    r = client.put("/me/onboarding", json=body, headers=auth(TOKEN_A))
    _is_problem(r, 422, "invalid_request")
    assert "MARKER" not in r.text and "999999123" not in r.text


@pytest.mark.parametrize("headers", [{}, auth("wrong-token-wrong-token"), {"Authorization": "Basic " + TOKEN_A},
                                     {"Authorization": "Bearer"}])
def test_requests_without_a_valid_token_are_unauthenticated(env, headers):
    client, db = env
    for r in (client.get("/me/onboarding", headers=headers),
              client.put("/me/onboarding", json={"step": 2}, headers=headers),
              client.put("/me/onboarding", json={"step": 99}, headers=headers)):
        _is_problem(r, 401, "unauthenticated")
        assert r.headers["www-authenticate"] == "Bearer"
    assert db.rows() == []


def test_unsupported_methods_are_rejected(env):
    client, _ = env
    for method in ("post", "delete", "patch"):
        _is_problem(getattr(client, method)("/me/onboarding", headers=auth(TOKEN_A)), 405, "method_not_allowed")


def test_responses_are_not_cached(env):
    client, _ = env
    assert client.get("/me/onboarding", headers=auth(TOKEN_A)).headers["cache-control"] == "no-store"
    assert client.put("/me/onboarding", json={"step": 1}, headers=auth(TOKEN_A)).headers["cache-control"] == "no-store"


def test_repository_rejects_a_write_with_both_or_neither_field(env):
    _, db = env
    with db.tenant_scope(TENANT_A) as repo:
        for kwargs in ({}, {"step": 2, "completed": True}):
            with pytest.raises(ValueError):
                repo.record_onboarding(db.user_a, **kwargs)
    assert db.rows() == []


def test_account_deletion_removes_only_that_accounts_row(env):
    client, db = env
    put(client, {"step": 3}, TOKEN_A)
    put(client, {"completed": True}, TOKEN_B)
    with db.tenant_scope(TENANT_A) as repo:
        assert repo.delete_onboarding(db.user_b) == 0  # another tenant's row is invisible
        assert repo.delete_onboarding(db.user_a) == 1
        assert repo.delete_onboarding(db.user_a) == 0  # idempotent
    assert get(client, TOKEN_A) == NOT_STARTED
    assert get(client, TOKEN_B) == COMPLETED
    assert [row.account_id for row in db.rows()] == [db.user_b]


def test_access_log_records_no_onboarding_values(env, caplog):
    client, db = env
    with caplog.at_level("INFO", logger="changelens"):
        put(client, {"step": 27})
        get(client)
    lines = [rec.getMessage() for rec in caplog.records if rec.name.startswith("changelens")]
    assert "PUT /me/onboarding 200" in lines and "GET /me/onboarding 200" in lines
    assert not any("27" in line or str(TENANT_A) in line or str(db.user_a) in line or SUBJECT_A in line
                   for line in lines)
