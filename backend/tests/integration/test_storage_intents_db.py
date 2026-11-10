"""Durable compensation with separate PostgreSQL transactions and local MinIO."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from threading import Event
from types import SimpleNamespace
import uuid

from botocore.exceptions import ClientError
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from changelens.api.comparisons import create_confirmed, parse_slot
from changelens.domain import Database
from changelens.domain.models import SourceVersion
from changelens.domain.storage_intents import prepare_write, reconcile_write, write_prepared, UNKNOWN_WRITE_GRACE
from changelens.worker import Worker
from conftest import TENANT_A, TENANT_B
from helpers import TOKEN_A, auth


def payload():
    return {"earlier": {"label": "Before", "text": "Synthetic original."},
            "later": {"label": "After", "text": "Synthetic update."}, "scope": "complete"}


def make_orphan(env, *, acknowledged=True):
    project = uuid.UUID(env.project())
    with env.db.tenant_scope(TENANT_A) as repo:
        repo.lock_comparison_key("integration-storage-intent")
        ticket = prepare_write(env.db, TENANT_A, project, "integration-storage-intent")
        if acknowledged:
            write_prepared(env.db, env.store, ticket, b"Synthetic abandoned original")
    return ticket


def assert_object_absent(env, key):
    with pytest.raises(ClientError) as error:
        env.store.get(key)
    assert error.value.response["Error"]["Code"] == "NoSuchKey"


def test_rollback_and_failed_purge_survive_database_and_worker_restart(env, monkeypatch):
    project = env.project()
    original_purge = env.store.delete_prefix
    def failed_transaction(*args):
        raise RuntimeError("synthetic post-write rollback")
    def failed_purge(*args):
        raise ConnectionError("synthetic object-store outage")
    monkeypatch.setattr("changelens.api.comparisons.advance_comparison", failed_transaction)
    monkeypatch.setattr(env.store, "delete_prefix", failed_purge)
    response = env.client.post(f"/projects/{project}/comparisons", json=payload(),
        headers={**auth(TOKEN_A), "Idempotency-Key": str(uuid.uuid4())})
    assert response.status_code == 500
    assert env.sql("SELECT count(*) FROM source_versions") == [(0,)]
    assert env.sql("SELECT count(*) FROM comparisons") == [(0,)]
    assert env.sql("SELECT count(*) FROM jobs") == [(0,)]
    rows = env.sql("SELECT object_key, attempts, write_acknowledged FROM object_write_intents")
    assert len(rows) == 2 and all(attempts == 1 and acknowledged for _, attempts, acknowledged in rows)
    monkeypatch.setattr(env.store, "delete_prefix", original_purge)
    env.sql("UPDATE object_write_intents SET next_attempt_at = now() - interval '1 second' RETURNING id")
    fresh = Database(env.settings.database_url)
    try:
        assert Worker(env.settings, fresh, env.store).reconcile_uploads() == 2
    finally:
        fresh.engine.dispose()
        fresh._intent_engine.dispose()
    assert env.sql("SELECT count(*) FROM object_write_intents") == [(0,)]
    for key, _, _ in rows:
        assert_object_absent(env, key)


def test_active_upload_lock_prevents_cleanup_then_reference_preserves_original(env):
    project = uuid.UUID(env.project())
    with env.db.tenant_scope(TENANT_A) as repo:
        repo.lock_comparison_key("integration-active-upload")
        ticket = prepare_write(env.db, TENANT_A, project, "integration-active-upload")
        write_prepared(env.db, env.store, ticket, b"Synthetic active upload")
        assert not reconcile_write(env.db, env.store, TENANT_A, ticket.id)
        assert env.store.get(ticket.object_key) == b"Synthetic active upload"
        repo.add(SourceVersion(project_id=project, label="v1", kind="text", status="uploaded",
            original_object_key=ticket.object_key, sha256="0" * 64, size_bytes=23, parse_warnings=[]))
    assert reconcile_write(env.db, env.store, TENANT_A, ticket.id)
    assert env.sql("SELECT count(*) FROM object_write_intents") == [(0,)]
    assert env.store.get(ticket.object_key) == b"Synthetic active upload"


def test_unknown_put_tombstone_catches_late_bytes_after_an_empty_purge(env):
    ticket = make_orphan(env, acknowledged=False)
    future = datetime.now(timezone.utc) + UNKNOWN_WRITE_GRACE + timedelta(seconds=1)
    assert not reconcile_write(env.db, env.store, TENANT_A, ticket.id, now=future)
    assert env.sql("SELECT write_acknowledged FROM object_write_intents") == [(False,)]
    env.store.put(ticket.object_key, b"Delayed synthetic PUT")
    assert not reconcile_write(env.db, env.store, TENANT_A, ticket.id, now=future + timedelta(hours=2))
    assert_object_absent(env, ticket.object_key)
    assert env.sql("SELECT attempts FROM object_write_intents") == [(2,)]


def test_other_tenant_cannot_reconcile_an_intent(env):
    ticket = make_orphan(env)
    assert reconcile_write(env.db, env.store, TENANT_B, ticket.id)
    assert env.sql("SELECT count(*) FROM object_write_intents") == [(1,)]
    assert env.store.get(ticket.object_key) == b"Synthetic abandoned original"
    assert reconcile_write(env.db, env.store, TENANT_A, ticket.id)
    assert_object_absent(env, ticket.object_key)


def test_concurrent_reconcilers_cannot_purge_the_same_intent_twice(env, monkeypatch):
    ticket = make_orphan(env)
    entered, release, deleted = Event(), Event(), []
    original = env.store.delete_prefix
    def slow_purge(key):
        deleted.append(key)
        entered.set()
        assert release.wait(timeout=5)
        return original(key)
    monkeypatch.setattr(env.store, "delete_prefix", slow_purge)
    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(reconcile_write, env.db, env.store, TENANT_A, ticket.id)
        try:
            assert entered.wait(timeout=5)
            assert not reconcile_write(env.db, env.store, TENANT_A, ticket.id)
        finally:
            release.set()
        assert first.result(timeout=5)
    assert deleted == [ticket.object_key]
    assert env.sql("SELECT count(*) FROM object_write_intents") == [(0,)]


def test_intent_commits_do_not_wait_for_another_connection_from_request_pool(env):
    project = uuid.UUID(env.project())
    fresh = Database(env.settings.database_url)
    fresh.engine.dispose()
    fresh.engine = create_engine(env.settings.database_url, pool_size=1, max_overflow=0,
                                pool_timeout=0.2, hide_parameters=True)
    fresh._sessions = sessionmaker(fresh.engine, expire_on_commit=False)
    state = SimpleNamespace(db=fresh, store=env.store, settings=env.settings)
    body = payload()
    slots = [parse_slot(body[side], None, env.settings.limits) for side in ("earlier", "later")]
    try:
        result = create_confirmed(state, TENANT_A, project, str(uuid.uuid4()), *slots, "complete")
        assert result["status"] == "waiting_for_versions"
        assert env.sql("SELECT count(*) FROM source_versions") == [(2,)]
        assert env.sql("SELECT count(*) FROM object_write_intents") == [(0,)]
    finally:
        fresh.engine.dispose()
        fresh._intent_engine.dispose()


def test_queued_work_is_claimed_before_any_cleanup_work(env, monkeypatch):
    project = env.project()
    assert env.upload(project, text="Synthetic parse input").status_code == 201
    def unexpected_cleanup(*args, **kwargs):
        raise AssertionError("Cleanup must not delay a queued parse/compare job")
    monkeypatch.setattr(env.worker, "reconcile_uploads", unexpected_cleanup)
    assert env.worker.run_once()
