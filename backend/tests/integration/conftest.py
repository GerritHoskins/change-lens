"""Integration fixtures: the compose Postgres and MinIO, a separate test database and bucket.

If the services are down, every integration test is skipped with the reason below. Start them
with `docker compose up -d --wait` in backend/. The test schema is rebuilt with `alembic upgrade head`
on every run, so every run exercises the migrations (I-8 S1).

Roles (I-8 S3): the compose superuser runs `bootstrap_roles`, migrations run as `changelens_owner`, and
the api, worker and retention under test connect as `changelens_app`, so row-level security applies to
everything the tests drive. Fixtures that set up or inspect rows across tenants (`env.sql`, seeding,
truncation) use a separate owner-role engine, which production code never has.
"""
from __future__ import annotations

import os
import uuid
from decimal import Decimal

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session
from sqlalchemy.pool import NullPool

from changelens.api.app import create_app
from changelens.config import Settings
from changelens.db import APP_ROLE, DEV_PASSWORDS, OWNER_ROLE, bootstrap_roles, upgrade
from changelens.domain import Database
from changelens.domain.identity import ensure_member
from changelens.storage import S3ObjectStore
from changelens.worker import Worker
from helpers import DEV_TOKENS, SUBJECT_A, SUBJECT_B, TOKEN_A, TOKEN_B, auth

PG = os.environ.get("CHANGELENS_TEST_PG", "postgresql://changelens:changelens@127.0.0.1:55432/changelens")
S3 = os.environ.get("CHANGELENS_TEST_S3", "http://127.0.0.1:59000")
TEST_DB = "changelens_test"
TENANT_A = uuid.UUID("00000000-0000-4000-8000-00000000000a")
TENANT_B = uuid.UUID("00000000-0000-4000-8000-00000000000b")
TABLES = ("client_approvals, review_events, findings, fact_cache, comparisons, jobs, source_versions, projects, "
          "object_write_intents, object_purge_intents, comparison_cost_tombstones, project_deletions, "
          "account_onboarding, consent_events, account_deletions, memberships, users, rate_limit_counters, pending_links, "
          "apple_token_parks, early_bird_signups")


def pytest_collection_modifyitems(items):
    for item in items:
        if "integration" in str(item.fspath):
            item.add_marker(pytest.mark.integration)


@pytest.fixture(scope="session")
def services():
    try:
        with psycopg.connect(PG, connect_timeout=3, autocommit=True) as conn:
            if not conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (TEST_DB,)).fetchone():
                conn.execute("CREATE DATABASE " + TEST_DB)
    except psycopg.OperationalError:
        pytest.skip("Postgres not reachable at %s: run `docker compose up -d --wait` in backend/" % PG.rsplit("@", 1)[-1])
    store = S3ObjectStore(S3, "changelens", "changelens-dev-only", "changelens-test")
    try:
        store.ensure_bucket()
    except Exception as exc:
        pytest.skip("MinIO not reachable at %s (%s): run `docker compose up -d --wait` in backend/" % (S3, type(exc).__name__))
    reset_schema(db_url())
    bootstrap_roles(db_url(), DEV_PASSWORDS)
    upgrade(db_url(TEST_DB, OWNER_ROLE))
    owner = create_engine(db_url(TEST_DB, OWNER_ROLE), poolclass=NullPool, hide_parameters=True)
    return Database(db_url(TEST_DB, APP_ROLE)), store, owner


def db_url(name: str = TEST_DB, role: str = None) -> str:
    """The test database's URL as the compose superuser, or as `role` with its dev password."""
    url = PG.replace("postgresql://", "postgresql+psycopg://").rsplit("/", 1)[0] + "/" + name
    if role is None:
        return url
    return "postgresql+psycopg://%s:%s@%s" % (role, DEV_PASSWORDS[role], url.split("@", 1)[1])


def reset_schema(url: str) -> None:
    """Drop everything in the disposable test database, including Alembic's version table."""
    with psycopg.connect(url.replace("postgresql+psycopg://", "postgresql://"), autocommit=True) as conn:
        conn.execute("DROP SCHEMA public CASCADE")
        conn.execute("CREATE SCHEMA public")


def seed_users(owner) -> dict:
    """GUARD needs a user and an active owner membership behind each dev token (owner role)."""
    with Session(owner) as s, s.begin():
        return {SUBJECT_A: ensure_member(s, SUBJECT_A, TENANT_A).id,
                SUBJECT_B: ensure_member(s, SUBJECT_B, TENANT_B).id}


def make_settings(db_url: str, **overrides) -> Settings:
    base = dict(database_url=db_url, s3_endpoint=S3, s3_access_key="changelens", s3_secret_key="changelens-dev-only",
                s3_bucket="changelens-test", dev_tokens=DEV_TOKENS,
                cost_ceiling_eur=Decimal("1.50"), fake_llm_cost_eur=Decimal("0.01"),
                # The suites send far more than the real limits; test_limits_db.py sets those (I-8 S6).
                rate_limit_account_per_minute=100_000, rate_limit_ip_per_minute=100_000, signups_per_ip_per_day=100_000)
    base.update(overrides)
    return Settings(**base)


class Env:
    def __init__(self, db, store, owner, users=None, **overrides):
        self.db, self.store, self.owner, self.users = db, store, owner, users or {}
        self.settings = make_settings(db.engine.url.render_as_string(hide_password=False), **overrides)
        self.client = TestClient(create_app(self.settings, db, store), raise_server_exceptions=False)
        self.worker = Worker(self.settings, db, store, backoff_seconds=0)

    def sql(self, query: str, **params):
        """Inspect or set up rows across tenants as the owner role (bypasses RLS; tests only)."""
        with self.owner.begin() as conn:
            return conn.execute(text(query), params).all()

    def owner_session(self) -> Session:
        return Session(self.owner, expire_on_commit=False)

    def project(self, token=TOKEN_A, name="Relaunch") -> str:
        r = self.client.post("/projects", json={"name": name}, headers=auth(token))
        assert r.status_code == 201, r.text
        return r.json()["id"]

    def upload(self, project_id, token=TOKEN_A, label="v", text=None, file=None):
        kw = {"files": {"file": file}} if file else {}
        data = {"label": label} if text is None else {"label": label, "text": text}
        return self.client.post("/projects/%s/versions" % project_id, data=data, headers=auth(token), **kw)

    def compare(self, project_id, earlier, later, scope="complete", token=TOKEN_A):
        return self.client.post("/projects/%s/comparisons" % project_id,
                                headers={**auth(token), "Idempotency-Key": str(uuid.uuid4())},
                                json={"earlier_id": earlier, "later_id": later, "scope": scope})

    def get(self, path, token=TOKEN_A):
        return self.client.get(path, headers=auth(token))


@pytest.fixture()
def env_factory(services):
    db, store, owner = services
    with owner.begin() as conn:
        conn.execute(text("TRUNCATE " + TABLES + " CASCADE"))
    users = seed_users(owner)

    def make(**overrides) -> Env:
        return Env(db, store, owner, users, **overrides)
    return make


@pytest.fixture()
def env(env_factory) -> Env:
    return env_factory()
