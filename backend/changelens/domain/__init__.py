"""Database access. Sessions for document data are always tenant-scoped (03 §9.1 `domain`).

`tenant_scope()` opens a transaction, sets `app.tenant_id` with SET LOCAL semantics (so RLS can be
switched on in I-8 without changing callers) and returns a repository whose every query filters on
that tenant. `system_session()` exists only for the queue's pre-tenant dequeue (03 §6).
"""
from __future__ import annotations

import uuid
from contextlib import contextmanager
from typing import Iterator, Optional

from sqlalchemy import create_engine, delete, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from changelens.domain.models import Base, Comparison, FactCacheEntry, Finding, Project, SourceVersion


class Database:
    def __init__(self, url: str):
        # echo stays off: SQL parameters can carry document text (AC-23).
        self.engine = create_engine(url, echo=False, hide_parameters=True, pool_pre_ping=True)
        self._sessions = sessionmaker(self.engine, expire_on_commit=False)

    def create_schema(self) -> None:
        """Dev schema bootstrap (no Alembic until I-8; see 06, I-22 row)."""
        Base.metadata.create_all(self.engine)

    @contextmanager
    def tenant_scope(self, tenant_id: uuid.UUID) -> Iterator["TenantRepo"]:
        if not isinstance(tenant_id, uuid.UUID):
            raise TypeError("tenant_id must be a UUID")
        with self._sessions() as s, s.begin():
            s.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_id)})
            yield TenantRepo(s, tenant_id)

    @contextmanager
    def system_session(self) -> Iterator[Session]:
        with self._sessions() as s, s.begin():
            yield s


class DbFactCache:
    """`pipeline.extract.FactCache` over the fact_cache table, for one tenant and version."""

    def __init__(self, db: Database, tenant_id: uuid.UUID, version_id: uuid.UUID):
        self.db, self.tenant_id, self.version_id = db, tenant_id, version_id

    def get(self, key: str) -> Optional[dict]:
        with self.db.tenant_scope(self.tenant_id) as repo:
            return repo.cached_facts(key)

    def put(self, key: str, value: dict) -> None:
        with self.db.tenant_scope(self.tenant_id) as repo:
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
        q = select(model).where(model.id == id_, model.tenant_id == self.tenant_id)
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

    def comparisons_of(self, project_id: uuid.UUID) -> list[Comparison]:
        q = (select(Comparison)
             .where(Comparison.tenant_id == self.tenant_id, Comparison.project_id == project_id)
             .order_by(Comparison.created_at.desc()))
        return list(self.s.scalars(q))

    def version(self, id_: uuid.UUID, lock: bool = False) -> Optional[SourceVersion]:
        return self._get(SourceVersion, id_, lock)

    def comparison(self, id_: uuid.UUID, lock: bool = False) -> Optional[Comparison]:
        return self._get(Comparison, id_, lock)

    def findings(self, comparison_id: uuid.UUID) -> list[Finding]:
        q = (select(Finding)
             .where(Finding.comparison_id == comparison_id, Finding.tenant_id == self.tenant_id)
             .order_by(Finding.priority))
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

    def replace_findings(self, comparison_id: uuid.UUID, findings: list[Finding]) -> None:
        """Retries never duplicate findings (03 §7): the old set is replaced in the same transaction."""
        self.s.execute(delete(Finding).where(Finding.comparison_id == comparison_id,
                                             Finding.tenant_id == self.tenant_id))
        for f in findings:
            self.add(f)
