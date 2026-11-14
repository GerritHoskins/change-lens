"""Transactional in-memory repository for HTTP comparison tests; no PostgreSQL emulation.

Detached transaction copies commit atomically or roll back. PostgreSQL locks/DDL still need
integration tests; this fixture checks API/worker orchestration through the real HTTP boundary.
"""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from threading import RLock
from types import SimpleNamespace
import uuid
from decimal import Decimal

from fastapi.testclient import TestClient

from changelens import jobs
from changelens.api.app import create_app
from changelens.config import Limits, Settings
from changelens.domain import comparison_lock_id, project_lock_id, used_at
from changelens.domain.models import Comparison, ObjectWriteIntent, Project, SourceVersion
from changelens.storage import MemoryObjectStore, original_key
from changelens.worker import Worker
from helpers import DEV_TOKENS, SUBJECT_A, SUBJECT_B, TOKEN_A, auth
from identity_fixture import SqliteIdentity


class TransactionalDb:
    def __init__(self):
        self.state = {"projects": {}, "versions": {}, "comparisons": {}, "jobs": []}
        self.lock = RLock()
        self.commit_failure = None
        self.intent_commit_failure = None
        self.recovery_unavailable = False
        self.failed = False
        self.intents = {}
        self.active_locks = set()

    @contextmanager
    def tenant_scope(self, tenant):
        with self.lock:
            if self.failed and self.recovery_unavailable:
                raise ConnectionError("database unavailable")
            pending, intents = deepcopy(self.state), deepcopy(self.intents)
            repo = TenantRepo(pending, tenant, intents, self)
            try:
                yield repo
                failure = self.commit_failure if repo.product_dirty else self.intent_commit_failure if repo.intents_dirty else None
                if repo.product_dirty:
                    self.commit_failure = None
                elif repo.intents_dirty:
                    self.intent_commit_failure = None
                if failure != "before":
                    self.state = pending
                    if repo.intents_dirty:
                        self.intents = intents
                if failure:
                    self.failed = True
                    raise ConnectionError("commit acknowledgement lost")
            finally:
                self.active_locks.difference_update(repo.held_locks)

    def pending_object_writes(self, now, limit):
        return [(row.tenant_id, row.id) for row in self.intents.values() if row.next_attempt_at <= now][:limit]

    def write_intent_scope(self, tenant):
        return self.tenant_scope(tenant)


class TenantRepo:
    def __init__(self, state, tenant, intents, db):
        self.state, self.tenant_id = state, tenant
        self.s = SimpleNamespace(state=state, flush=lambda: None, refresh=lambda _: None)
        self.intents, self.db = intents, db
        self.intents_dirty, self.product_dirty = False, False
        self.held_locks = set()

    def month_spend(self, since):
        return Decimal("0")  # spend caps (I-8 S6) are covered by the integration tests

    def global_month_spend(self, since):
        return Decimal("0")

    def _get(self, collection, identifier):
        row = self.state[collection].get(identifier)
        return row if row is not None and row.tenant_id == self.tenant_id else None

    def project(self, identifier):
        row = self._get("projects", identifier)
        return row if row is not None and row.deleted_at is None else None

    def version(self, identifier, lock=False):
        row = self._get("versions", identifier)
        return row if row is not None and self.project(row.project_id) is not None else None

    def comparison(self, identifier, lock=False):
        row = self._get("comparisons", identifier)
        return row if row is not None and self.project(row.project_id) is not None else None

    def comparison_ledger(self, identifier, lock=False):
        return self._get("comparisons", identifier)

    def comparison_cost_tombstone(self, identifier, lock=False):
        return None

    def lock_project(self, identifier, wait=True):
        lock_id = project_lock_id(self.tenant_id, identifier)
        if lock_id in self.held_locks:
            return True
        if lock_id in self.db.active_locks:
            assert not wait, "concurrency requires the real PostgreSQL fixture"
            return False
        self.db.active_locks.add(lock_id)
        self.held_locks.add(lock_id)
        return True

    def lock_for_version(self, identifier):
        row = self.version(identifier)
        return row is not None and self.lock_project(row.project_id)

    def lock_for_comparison(self, identifier):
        row = self.comparison(identifier)
        return row is not None and self.lock_project(row.project_id)

    def touch_version(self, row, now=None):
        row.last_used_at = used_at(row.last_used_at, now or datetime.now(timezone.utc))

    def touch_comparison(self, row, now=None):
        now = now or datetime.now(timezone.utc)
        row.last_used_at = used_at(row.last_used_at, now)
        for identifier in (row.earlier_id, row.later_id):
            version = self.version(identifier)
            if version is not None:
                self.touch_version(version, now)

    def lock_comparison_key(self, key):
        lock_id = comparison_lock_id(self.tenant_id, key)
        assert lock_id not in self.db.active_locks
        self.db.active_locks.add(lock_id)
        self.held_locks.add(lock_id)

    def try_object_write_lock(self, lock_id):
        if lock_id in self.db.active_locks:
            return False
        self.db.active_locks.add(lock_id)
        self.held_locks.add(lock_id)
        return True

    def object_write_intent(self, identifier, lock=False):
        row = self.intents.get(identifier)
        if row is None or row.tenant_id != self.tenant_id:
            return None
        self.intents_dirty = True
        return row

    def object_key_is_referenced(self, key):
        return any(row.tenant_id == self.tenant_id and row.original_object_key == key
                   for row in self.state["versions"].values())

    def remove_object_write_intent(self, intent):
        self.intents_dirty = True
        del self.intents[intent.id]

    def comparison_by_key(self, key):
        return next((c for c in self.state["comparisons"].values()
                     if c.tenant_id == self.tenant_id and c.idempotency_key == key), None)

    def waiting_for_version(self, version_id):
        return [c for c in self.state["comparisons"].values() if c.tenant_id == self.tenant_id
                and c.status == "waiting_for_versions" and version_id in (c.earlier_id, c.later_id)]

    def add(self, row):
        if isinstance(row, ObjectWriteIntent):
            row.id = row.id or uuid.uuid4()
            row.tenant_id = self.tenant_id
            row.created_at = datetime.now(timezone.utc)
            self.intents[row.id] = row
            self.intents_dirty = True
            return row
        self.product_dirty = True
        collection = {Project: "projects", SourceVersion: "versions", Comparison: "comparisons"}[type(row)]
        row.id = row.id or uuid.uuid4()
        row.tenant_id = self.tenant_id
        row.created_at = datetime.now(timezone.utc)
        if isinstance(row, Comparison):
            row.cost_reservations = row.cost_reservations or {}
        if isinstance(row, (Comparison, SourceVersion)):
            row.last_used_at = row.last_used_at or row.created_at
        self.state[collection][row.id] = row
        return row


class Environment:
    def __init__(self, monkeypatch):
        self.tenant, self.other_tenant = uuid.uuid4(), uuid.uuid4()
        self.db, self.store = TransactionalDb(), MemoryObjectStore()
        self.settings = Settings(database_url="unused", s3_endpoint="unused", s3_access_key="unused",
            s3_secret_key="unused", s3_bucket="unused", dev_tokens=DEV_TOKENS,
            limits=Limits(max_pdf_bytes=20_000, max_pdf_pages=2, max_text_bytes=1000, max_text_words=100))
        self.identity = SqliteIdentity()
        self.identity.seed(SUBJECT_A, self.tenant)
        self.identity.seed(SUBJECT_B, self.other_tenant)
        self.db.identity_scope = self.identity.identity_scope
        self.project_id = self.project()
        self.other_project = self.project()
        self.foreign_project = self.project(self.other_tenant)

        def enqueue(session, tenant, kind, payload, max_attempts):
            assert set(payload) == {"version_id" if kind == "parse" else "comparison_id"}
            assert all(isinstance(v, uuid.UUID) for v in payload.values())
            session.state["jobs"].append(dict(tenant_id=tenant, kind=kind, ids=dict(payload), max_attempts=max_attempts))

        monkeypatch.setattr(jobs, "enqueue", enqueue)
        self.client = TestClient(create_app(self.settings, self.db, self.store), raise_server_exceptions=False)
        self.worker = Worker(self.settings, self.db, self.store)

    def project(self, tenant=None):
        with self.db.tenant_scope(tenant or self.tenant) as repo:
            return repo.add(Project(name="Synthetic project")).id

    def version(self, status="parsed", project=None, tenant=None):
        tenant, project = tenant or self.tenant, project or self.project_id
        key = original_key(tenant, project)
        self.store.put(key, b"Existing synthetic brief")
        with self.db.tenant_scope(tenant) as repo:
            return repo.add(SourceVersion(project_id=project, label="Existing", kind="text", status=status,
                original_object_key=key, sha256="unused", size_bytes=24, parse_warnings=[])).id

    def post(self, payload, key="comparison-test-key-0001", project=None, token=TOKEN_A, **kwargs):
        headers = auth(token)
        if key is not None:
            headers["Idempotency-Key"] = key
        return self.client.post(f"/projects/{project or self.project_id}/comparisons", json=payload,
                                headers=headers, **kwargs)

    @property
    def comparisons(self):
        return self.db.state["comparisons"]

    @property
    def versions(self):
        return self.db.state["versions"]

    @property
    def queued(self):
        return self.db.state["jobs"]

    def comparison(self, response):
        assert response.status_code == 202, response.text
        return self.comparisons[uuid.UUID(response.json()["id"])]
