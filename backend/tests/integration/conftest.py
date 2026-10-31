"""Integration fixtures: the compose Postgres and MinIO, a separate test database and bucket.

If the services are down, every integration test is skipped with the reason below. Start them
with `docker compose up -d --wait` in backend/.
"""
from __future__ import annotations

import os
import uuid
from decimal import Decimal

import psycopg
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text

from changelens.api.app import create_app
from changelens.config import Settings
from changelens.domain import Database
from changelens.storage import S3ObjectStore
from changelens.worker import Worker
from helpers import TOKEN_A, TOKEN_B, auth

PG = os.environ.get("CHANGELENS_TEST_PG", "postgresql://changelens:changelens@127.0.0.1:55432/changelens")
S3 = os.environ.get("CHANGELENS_TEST_S3", "http://127.0.0.1:59000")
TEST_DB = "changelens_test"
TENANT_A = uuid.UUID("00000000-0000-4000-8000-00000000000a")
TENANT_B = uuid.UUID("00000000-0000-4000-8000-00000000000b")
TABLES = "findings, fact_cache, comparisons, jobs, source_versions, projects"


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
    db = Database(PG.replace("postgresql://", "postgresql+psycopg://").rsplit("/", 1)[0] + "/" + TEST_DB)
    # No migrations yet (I-8): rebuild the disposable test schema so model changes always apply.
    from changelens.domain.models import Base
    Base.metadata.drop_all(db.engine)
    db.create_schema()
    return db, store


def make_settings(db_url: str, **overrides) -> Settings:
    base = dict(database_url=db_url, s3_endpoint=S3, s3_access_key="changelens", s3_secret_key="changelens-dev-only",
                s3_bucket="changelens-test", dev_tokens={TOKEN_A: TENANT_A, TOKEN_B: TENANT_B},
                cost_ceiling_eur=Decimal("1.50"), fake_llm_cost_eur=Decimal("0.01"))
    base.update(overrides)
    return Settings(**base)


class Env:
    def __init__(self, db, store, **overrides):
        self.db, self.store = db, store
        self.settings = make_settings(db.engine.url.render_as_string(hide_password=False), **overrides)
        self.client = TestClient(create_app(self.settings, db, store), raise_server_exceptions=False)
        self.worker = Worker(self.settings, db, store, backoff_seconds=0)

    def sql(self, query: str, **params):
        with self.db.system_session() as s:
            return s.execute(text(query), params).all()

    def project(self, token=TOKEN_A, name="Relaunch") -> str:
        r = self.client.post("/projects", json={"name": name}, headers=auth(token))
        assert r.status_code == 201, r.text
        return r.json()["id"]

    def upload(self, project_id, token=TOKEN_A, label="v", text=None, file=None):
        kw = {"files": {"file": file}} if file else {}
        data = {"label": label} if text is None else {"label": label, "text": text}
        return self.client.post("/projects/%s/versions" % project_id, data=data, headers=auth(token), **kw)

    def compare(self, project_id, earlier, later, scope="complete", token=TOKEN_A):
        return self.client.post("/projects/%s/comparisons" % project_id, headers=auth(token),
                                json={"earlier_id": earlier, "later_id": later, "scope": scope})

    def get(self, path, token=TOKEN_A):
        return self.client.get(path, headers=auth(token))


@pytest.fixture()
def env_factory(services):
    db, store = services
    with db.system_session() as s:
        s.execute(text("TRUNCATE " + TABLES + " CASCADE"))

    def make(**overrides) -> Env:
        return Env(db, store, **overrides)
    return make


@pytest.fixture()
def env(env_factory) -> Env:
    return env_factory()
