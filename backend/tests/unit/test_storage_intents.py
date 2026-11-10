"""Crash/restart compensation through the real upload helpers, without PostgreSQL or S3."""
from datetime import datetime, timedelta, timezone

import pytest

from changelens.api.comparisons import create_confirmed, parse_slot
from changelens.api.routes import _store_version
from changelens.domain.storage_intents import (
    UNKNOWN_WRITE_GRACE, prepare_write, reconcile_pending_writes, reconcile_write, write_prepared,
)
from changelens.worker import Worker
from comparison_fixture import Environment


class ProcessCrash(BaseException):
    pass


@pytest.fixture
def env(monkeypatch):
    environment = Environment(monkeypatch)
    yield environment
    environment.client.close()


def create(env):
    slots = [parse_slot({"label": label, "text": text}, None, env.settings.limits)
             for label, text in (("before", "Synthetic earlier."), ("after", "Synthetic later."))]
    return create_confirmed(env.client.app.state, env.tenant, env.project_id,
                            "durable-upload-test-key", *slots, "complete")


def abandoned(env, *, acknowledged=True):
    try:
        with env.db.tenant_scope(env.tenant) as repo:
            repo.lock_comparison_key("abandoned-upload-key")
            ticket = prepare_write(env.db, env.tenant, env.project_id, "abandoned-upload-key")
            if acknowledged:
                write_prepared(env.db, env.store, ticket, b"Synthetic private document")
            raise ProcessCrash()
    except ProcessCrash:
        return ticket


def test_write_intent_is_durable_and_content_free_before_put(env, monkeypatch):
    original = env.store.put
    seen = []
    def inspect(key, data):
        intent = next(i for i in env.db.intents.values() if i.object_key == key)
        assert not intent.write_acknowledged
        assert intent.next_attempt_at > datetime.now(timezone.utc)
        assert set(intent.__table__.columns.keys()) == {
            "id", "tenant_id", "object_key", "request_lock_id", "write_acknowledged",
            "next_attempt_at", "attempts", "created_at"}
        seen.append(intent.id)
        original(key, data)
    monkeypatch.setattr(env.store, "put", inspect)
    create(env)
    assert len(seen) == len(env.versions) == len(env.store.objects) == 2
    assert not env.db.intents  # each committed version now owns its object's lifecycle


@pytest.mark.parametrize("failure", ["before", "after"])
def test_intent_commit_failure_prevents_put_even_if_commit_outcome_is_unknown(env, monkeypatch, failure):
    env.db.intent_commit_failure = failure
    def forbidden(*args):
        raise AssertionError("PUT must wait for the intent commit acknowledgement")
    monkeypatch.setattr(env.store, "put", forbidden)
    with pytest.raises(ConnectionError):
        create(env)
    assert not env.store.objects and not env.comparisons and not env.versions
    assert len(env.db.intents) == (1 if failure == "after" else 0)


def test_failed_rollback_purge_is_retried_by_a_new_worker_without_losing_the_keys(env, monkeypatch):
    env.db.commit_failure = "before"
    original = env.store.delete_prefix
    def fail(*args):
        raise ConnectionError("synthetic storage outage")
    monkeypatch.setattr(env.store, "delete_prefix", fail)
    with pytest.raises(ConnectionError):
        create(env)
    assert len(env.store.objects) == len(env.db.intents) == 2
    assert not env.comparisons and not env.versions
    assert all(i.attempts == 1 for i in env.db.intents.values())
    monkeypatch.setattr(env.store, "delete_prefix", original)
    future = datetime.now(timezone.utc) + timedelta(minutes=1)
    monkeypatch.setattr("changelens.domain.storage_intents._now", lambda: future)
    resumed = Worker(env.settings, env.db, env.store)
    assert resumed.reconcile_uploads() == 2
    assert not env.db.intents and not env.store.objects
    create(env)
    assert len(env.versions) == len(env.store.objects) == 2 and not env.db.intents


def test_crash_after_put_before_source_commit_is_recovered_after_restart(env):
    ticket = abandoned(env)
    assert ticket.id in env.db.intents and ticket.object_key in env.store.objects
    assert not env.versions
    assert Worker(env.settings, env.db, env.store).reconcile_uploads() == 1
    assert not env.db.intents and not env.store.objects


def test_unknown_write_keeps_a_tombstone_that_purges_a_late_put(env):
    ticket = abandoned(env, acknowledged=False)
    initial = datetime.now(timezone.utc)
    assert reconcile_pending_writes(env.db, env.store, now=initial) == 0
    first_cleanup = initial + UNKNOWN_WRITE_GRACE + timedelta(seconds=1)
    assert reconcile_pending_writes(env.db, env.store, now=first_cleanup) == 0
    assert ticket.id in env.db.intents  # no current object does not prove PUT can never arrive
    env.store.put(ticket.object_key, b"Delayed synthetic PUT")
    assert reconcile_pending_writes(env.db, env.store, now=first_cleanup + timedelta(hours=2)) == 0
    assert ticket.object_key not in env.store.objects and ticket.id in env.db.intents
    assert env.db.intents[ticket.id].attempts == 2


def test_active_upload_request_lock_blocks_reconciliation(env):
    with env.db.tenant_scope(env.tenant) as repo:
        repo.lock_comparison_key("active-upload-key")
        ticket = prepare_write(env.db, env.tenant, env.project_id, "active-upload-key")
        write_prepared(env.db, env.store, ticket, b"Synthetic active upload")
        assert reconcile_pending_writes(env.db, env.store) == 0
        assert ticket.id in env.db.intents and ticket.object_key in env.store.objects
    assert reconcile_pending_writes(env.db, env.store) == 1
    assert not env.db.intents and not env.store.objects


def test_lost_source_commit_acknowledgement_keeps_referenced_originals(env, monkeypatch):
    env.db.commit_failure, env.db.recovery_unavailable = "after", True
    with pytest.raises(ConnectionError):
        create(env)
    assert len(env.db.intents) == len(env.versions) == len(env.store.objects) == 2
    env.db.recovery_unavailable = False
    def forbidden(*args):
        raise AssertionError("Referenced documents must not be deleted")
    monkeypatch.setattr(env.store, "delete_prefix", forbidden)
    assert Worker(env.settings, env.db, env.store).reconcile_uploads() == 2
    assert len(env.store.objects) == 2 and not env.db.intents


def test_failed_intent_delete_commit_is_safe_to_retry_after_object_was_purged(env):
    ticket = abandoned(env)
    env.db.intent_commit_failure = "before"
    assert not reconcile_write(env.db, env.store, env.tenant, ticket.id)
    assert ticket.object_key not in env.store.objects and ticket.id in env.db.intents
    assert reconcile_write(env.db, env.store, env.tenant, ticket.id)
    assert not env.db.intents


def test_other_tenant_or_tampered_key_cannot_purge_an_object(env):
    ticket = abandoned(env)
    assert reconcile_write(env.db, env.store, env.other_tenant, ticket.id)
    assert ticket.id in env.db.intents and ticket.object_key in env.store.objects
    env.db.intents[ticket.id].object_key = ticket.object_key.replace(str(env.tenant), str(env.other_tenant), 1)
    env.store.put(env.db.intents[ticket.id].object_key, b"Other tenant's synthetic document")
    assert not reconcile_write(env.db, env.store, env.tenant, ticket.id)
    assert len(env.store.objects) == 2 and ticket.id in env.db.intents


def test_legacy_upload_also_uses_durable_write_compensation(env, monkeypatch):
    env.db.commit_failure = "before"
    original = env.store.delete_prefix
    def fail(*args):
        raise ConnectionError("synthetic cleanup failure")
    monkeypatch.setattr(env.store, "delete_prefix", fail)
    with pytest.raises(ConnectionError):
        _store_version(env.client.app.state, env.tenant, env.project_id, b"Synthetic", "v1", "text")
    assert len(env.db.intents) == len(env.store.objects) == 1 and not env.versions
    monkeypatch.setattr(env.store, "delete_prefix", original)
    future = datetime.now(timezone.utc) + timedelta(minutes=1)
    assert reconcile_pending_writes(env.db, env.store, now=future) == 1
    assert not env.db.intents and not env.store.objects
