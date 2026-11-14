"""Database access. Sessions for document data are always tenant-scoped (03 §9.1 `domain`).

`tenant_scope()` opens a transaction, sets `app.tenant_id` with SET LOCAL semantics (so RLS can be
switched on in I-8 without changing callers) and returns a repository whose every query filters on
that tenant. `system_session()` exists only for the queue's pre-tenant dequeue (03 §6), and
`identity_scope()` only for GUARD's user and membership lookups. The schema is owned by Alembic
(`backend/migrations/`); nothing here creates or alters tables.
"""
from __future__ import annotations

import uuid
import hashlib
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Iterator, Optional

from sqlalchemy import create_engine, delete, func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from changelens.domain.identity import IdentityRepo
from changelens.domain.models import (
    AccountOnboarding, ClientApprovalRecord, Comparison, ComparisonCostTombstone, FactCacheEntry, Finding,
    ObjectWriteIntent, Project, ReviewEvent, SourceVersion,
)


def comparison_lock_id(tenant_id: uuid.UUID, key: str) -> int:
    digest = hashlib.sha256(f"{tenant_id}:{key}".encode()).digest()
    return int.from_bytes(digest[:8], "big", signed=True)


def project_lock_id(tenant_id: uuid.UUID, project_id: uuid.UUID) -> int:
    return comparison_lock_id(tenant_id, "project:" + str(project_id))


def used_at(previous: Optional[datetime], now: datetime) -> datetime:
    """A clock adjustment must never shorten a resource's retention window."""
    if previous is not None and previous.tzinfo is None:
        previous = previous.replace(tzinfo=timezone.utc)
    return max(previous, now) if previous is not None else now


class Database:
    def __init__(self, url: str):
        # echo stays off: SQL parameters can carry document text (AC-23).
        self.engine = create_engine(url, echo=False, hide_parameters=True, pool_pre_ping=True)
        self._sessions = sessionmaker(self.engine, expire_on_commit=False)
        # Uploads hold a request transaction while independently committing write intents.
        # A separate non-pooling engine prevents all checked-out request connections from
        # waiting for another connection from that same exhausted pool.
        self._intent_engine = create_engine(url, echo=False, hide_parameters=True, poolclass=NullPool)
        self._intent_sessions = sessionmaker(self._intent_engine, expire_on_commit=False)

    @contextmanager
    def tenant_scope(self, tenant_id: uuid.UUID) -> Iterator["TenantRepo"]:
        if not isinstance(tenant_id, uuid.UUID):
            raise TypeError("tenant_id must be a UUID")
        with self._sessions() as s, s.begin():
            s.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_id)})
            yield TenantRepo(s, tenant_id)

    @contextmanager
    def identity_scope(self) -> Iterator[IdentityRepo]:
        """Pre-tenant user and membership lookups for GUARD (03a P0); no tenant is set."""
        with self._sessions() as s, s.begin():
            yield IdentityRepo(s)

    @contextmanager
    def system_session(self) -> Iterator[Session]:
        with self._sessions() as s, s.begin():
            yield s

    @contextmanager
    def write_intent_scope(self, tenant_id: uuid.UUID) -> Iterator["TenantRepo"]:
        if not isinstance(tenant_id, uuid.UUID):
            raise TypeError("tenant_id must be a UUID")
        with self._intent_sessions() as s, s.begin():
            s.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_id)})
            yield TenantRepo(s, tenant_id)

    def pending_object_writes(self, now: datetime, limit: int) -> list[tuple[uuid.UUID, uuid.UUID]]:
        # Like queue dequeue, this pre-tenant scan returns IDs only. All subsequent access
        # and cleanup rechecks happen in tenant_scope under the upload's advisory lock.
        with self.system_session() as s:
            q = (select(ObjectWriteIntent.tenant_id, ObjectWriteIntent.id)
                 .where(ObjectWriteIntent.next_attempt_at <= now)
                 .order_by(ObjectWriteIntent.next_attempt_at, ObjectWriteIntent.created_at).limit(limit))
            return list(s.execute(q).tuples())


class DbFactCache:
    """`pipeline.extract.FactCache` over the fact_cache table, for one tenant and version."""

    def __init__(self, db: Database, tenant_id: uuid.UUID, version_id: uuid.UUID):
        self.db, self.tenant_id, self.version_id = db, tenant_id, version_id

    def get(self, key: str) -> Optional[dict]:
        with self.db.tenant_scope(self.tenant_id) as repo:
            return repo.cached_facts(key) if repo.version(self.version_id) is not None else None

    def put(self, key: str, value: dict) -> None:
        with self.db.tenant_scope(self.tenant_id) as repo:
            if repo.lock_for_version(self.version_id):
                repo.cache_facts(self.version_id, key, value)


class TenantRepo:
    """Repository bound to one tenant. Another tenant's row is indistinguishable from a missing one."""

    def __init__(self, session: Session, tenant_id: uuid.UUID):
        self.s = session
        self.tenant_id = tenant_id

    def add(self, obj):
        obj.tenant_id = self.tenant_id
        self.s.add(obj)
        self.s.flush()
        return obj

    def _get(self, model, id_: uuid.UUID, lock: bool = False):
        q = (select(model).where(model.id == id_, model.tenant_id == self.tenant_id)
             .execution_options(populate_existing=True))
        if lock:
            q = q.with_for_update()
        return self.s.scalars(q).one_or_none()

    def project(self, id_: uuid.UUID) -> Optional[Project]:
        p = self._get(Project, id_)
        return p if p is not None and p.deleted_at is None else None

    def projects(self) -> list[Project]:
        q = (select(Project).where(Project.tenant_id == self.tenant_id, Project.deleted_at.is_(None))
             .order_by(Project.created_at.desc()))
        return list(self.s.scalars(q))

    def versions_of(self, project_id: uuid.UUID) -> list[SourceVersion]:
        q = (select(SourceVersion)
             .where(SourceVersion.tenant_id == self.tenant_id, SourceVersion.project_id == project_id)
             .order_by(SourceVersion.created_at))
        return list(self.s.scalars(q))

    def active_comparison_counts(self) -> dict:
        q = (select(Comparison.project_id, Comparison.status, func.count(Comparison.id))
             .where(Comparison.tenant_id == self.tenant_id,
                    Comparison.status.in_(("waiting_for_versions", "queued", "running")))
             .group_by(Comparison.project_id, Comparison.status))
        counts = {}
        for project_id, status, count in self.s.execute(q):
            counts.setdefault(project_id, {})[status] = count
        return counts

    def comparisons_of(self, project_id: uuid.UUID) -> list[Comparison]:
        q = (select(Comparison)
             .where(Comparison.tenant_id == self.tenant_id, Comparison.project_id == project_id)
             .order_by(Comparison.created_at.desc()))
        return list(self.s.scalars(q))

    def version(self, id_: uuid.UUID, lock: bool = False) -> Optional[SourceVersion]:
        row = self._get(SourceVersion, id_, lock)
        return row if row is not None and self.project(row.project_id) is not None else None

    def comparison(self, id_: uuid.UUID, lock: bool = False) -> Optional[Comparison]:
        row = self.comparison_ledger(id_, lock)
        return row if row is not None and self.project(row.project_id) is not None else None

    def comparison_ledger(self, id_: uuid.UUID, lock: bool = False) -> Optional[Comparison]:
        # Cost settlement must work after the project is frozen and until graph transfer.
        return self._get(Comparison, id_, lock)

    def comparison_cost_tombstone(self, id_: uuid.UUID, lock: bool = False) -> Optional[ComparisonCostTombstone]:
        return self._get(ComparisonCostTombstone, id_, lock)

    def lock_project(self, project_id: uuid.UUID, *, wait: bool = True) -> bool:
        function = "pg_advisory_xact_lock" if wait else "pg_try_advisory_xact_lock"
        result = self.s.scalar(text(f"SELECT {function}(:key)"),
                               {"key": project_lock_id(self.tenant_id, project_id)})
        return True if wait else bool(result)

    def _lock_resource_project(self, model, id_: uuid.UUID) -> bool:
        project_id = self.s.scalar(select(model.project_id).where(model.id == id_, model.tenant_id == self.tenant_id))
        if project_id is None:
            return False
        self.lock_project(project_id)
        # Re-read after the lifecycle lock: expiry may have removed the resource meanwhile.
        return self.project(project_id) is not None and self._get(model, id_) is not None

    def lock_for_version(self, id_: uuid.UUID) -> bool:
        return self._lock_resource_project(SourceVersion, id_)

    def lock_for_comparison(self, id_: uuid.UUID) -> bool:
        return self._lock_resource_project(Comparison, id_)

    def lock_for_finding(self, id_: uuid.UUID) -> bool:
        comparison_id = self.s.scalar(select(Finding.comparison_id).where(
            Finding.id == id_, Finding.tenant_id == self.tenant_id))
        return comparison_id is not None and self.lock_for_comparison(comparison_id)

    def touch_version(self, version: SourceVersion, now: Optional[datetime] = None) -> None:
        version.last_used_at = used_at(version.last_used_at, now or datetime.now(timezone.utc))

    def touch_comparison(self, comparison: Comparison, now: Optional[datetime] = None) -> None:
        now = now or datetime.now(timezone.utc)
        comparison.last_used_at = used_at(comparison.last_used_at, now)
        for identifier in sorted({comparison.earlier_id, comparison.later_id}):
            version = self.version(identifier, lock=True)
            if version is not None:
                self.touch_version(version, now)

    def lock_comparison_key(self, key: str) -> None:
        # Serialise the same key across projects before writing objects or versions. The
        # unique constraint remains a second guard; this lock is released on transaction end.
        self.s.execute(text("SELECT pg_advisory_xact_lock(:key)"),
                       {"key": comparison_lock_id(self.tenant_id, key)})

    def try_object_write_lock(self, lock_id: int) -> bool:
        return bool(self.s.scalar(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": lock_id}))

    def object_write_intent(self, id_: uuid.UUID, lock: bool = False) -> Optional[ObjectWriteIntent]:
        q = select(ObjectWriteIntent).where(ObjectWriteIntent.id == id_, ObjectWriteIntent.tenant_id == self.tenant_id)
        if lock:
            q = q.with_for_update().execution_options(populate_existing=True)
        return self.s.scalars(q).one_or_none()

    def object_key_is_referenced(self, key: str) -> bool:
        q = select(SourceVersion.id).where(SourceVersion.tenant_id == self.tenant_id,
                                            SourceVersion.original_object_key == key).limit(1)
        return self.s.scalar(q) is not None

    def remove_object_write_intent(self, intent: ObjectWriteIntent) -> None:
        self.s.delete(intent)

    def comparison_by_key(self, key: str) -> Optional[Comparison]:
        return self.s.scalars(select(Comparison).where(Comparison.tenant_id == self.tenant_id,
                                                       Comparison.idempotency_key == key)).one_or_none()

    def waiting_for_version(self, version_id: uuid.UUID) -> list[Comparison]:
        query = (select(Comparison).where(Comparison.tenant_id == self.tenant_id,
                    Comparison.status == "waiting_for_versions",
                    or_(Comparison.earlier_id == version_id, Comparison.later_id == version_id))
                 .order_by(Comparison.id).with_for_update())
        return list(self.s.scalars(query))

    def findings(self, comparison_id: uuid.UUID) -> list[Finding]:
        q = (select(Finding)
             .where(Finding.comparison_id == comparison_id, Finding.tenant_id == self.tenant_id)
             .order_by(Finding.priority))
        return list(self.s.scalars(q))

    def finding(self, id_: uuid.UUID, lock: bool = False) -> Optional[Finding]:
        row = self._get(Finding, id_, lock)
        return row if row is not None and self.comparison(row.comparison_id) is not None else None

    def reviews(self, finding_ids) -> list[ReviewEvent]:
        q = (select(ReviewEvent).where(ReviewEvent.tenant_id == self.tenant_id,
                                       ReviewEvent.finding_id.in_(list(finding_ids)))
             .order_by(ReviewEvent.created_at, ReviewEvent.id))
        return list(self.s.scalars(q))

    def approvals(self, finding_ids) -> list[ClientApprovalRecord]:
        q = (select(ClientApprovalRecord).where(ClientApprovalRecord.tenant_id == self.tenant_id,
                                                ClientApprovalRecord.finding_id.in_(list(finding_ids)))
             .order_by(ClientApprovalRecord.created_at, ClientApprovalRecord.id))
        return list(self.s.scalars(q))

    def cached_facts(self, key: str) -> Optional[dict]:
        q = select(FactCacheEntry.result).where(FactCacheEntry.tenant_id == self.tenant_id,
                                                FactCacheEntry.cache_key == key)
        return self.s.scalars(q).one_or_none()

    def cache_facts(self, version_id: uuid.UUID, key: str, result: dict) -> None:
        """First writer wins; a concurrent duplicate for the same key is dropped."""
        if self.cached_facts(key) is None:
            try:
                with self.s.begin_nested():  # savepoint: a lost race rolls back only this insert
                    self.add(FactCacheEntry(source_version_id=version_id, cache_key=key, result=result))
            except IntegrityError:
                pass

    def onboarding(self, account_id: uuid.UUID, lock: bool = False) -> Optional[AccountOnboarding]:
        """Onboarding state (O-23). No row means not started; reads never create one."""
        q = (select(AccountOnboarding).where(AccountOnboarding.account_id == account_id,
                                             AccountOnboarding.tenant_id == self.tenant_id)
             .execution_options(populate_existing=True))
        if lock:
            q = q.with_for_update()
        return self.s.scalars(q).one_or_none()

    def record_onboarding(self, account_id: uuid.UUID, *, step: Optional[int] = None, completed: bool = False,
                          now: Optional[datetime] = None) -> Optional[AccountOnboarding]:
        """Last step write wins; completion is set once by the server clock and never cleared.
        The row lock serialises a step write against a completion, so the step can't reopen it."""
        if (step is None) != completed:
            raise ValueError("exactly one of step or completed")
        now = now or datetime.now(timezone.utc)
        row = self.onboarding(account_id, lock=True)
        if row is None:  # the first write creates the row
            try:
                with self.s.begin_nested():  # savepoint: a lost first-write race rolls back only this insert
                    row = self.add(AccountOnboarding(account_id=account_id, updated_at=now))
            except IntegrityError:
                row = self.onboarding(account_id, lock=True)  # the winner has committed; lock its row
                if row is None:
                    return None
        if row.onboarding_completed_at is None:
            if completed:
                row.onboarding_completed_at, row.onboarding_step = now, None
            else:
                row.onboarding_step = step
            row.updated_at = now
            self.s.flush()
        return row

    def delete_onboarding(self, account_id: uuid.UUID) -> int:
        """For 03a P8 DELETE_ACCOUNT (and DELETE_TENANT per member); no route until I-8.
        Project deletion and retention never call this: it is account data, not project data."""
        result = self.s.execute(delete(AccountOnboarding).where(AccountOnboarding.account_id == account_id,
                                                                AccountOnboarding.tenant_id == self.tenant_id))
        return result.rowcount

    def replace_findings(self, comparison_id: uuid.UUID, findings: list[Finding]) -> None:
        """Retries never duplicate findings (03 §7): the old set is replaced in the same transaction."""
        self.s.execute(delete(Finding).where(Finding.comparison_id == comparison_id,
                                             Finding.tenant_id == self.tenant_id))
        for f in findings:
            self.add(f)
