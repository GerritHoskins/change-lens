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
from sqlalchemy.orm import Session, sessionmaker

from changelens.domain.models import Base, Comparison, Finding, Project, SourceVersion


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

    def version(self, id_: uuid.UUID, lock: bool = False) -> Optional[SourceVersion]:
        return self._get(SourceVersion, id_, lock)

    def comparison(self, id_: uuid.UUID, lock: bool = False) -> Optional[Comparison]:
        return self._get(Comparison, id_, lock)

    def findings(self, comparison_id: uuid.UUID) -> list[Finding]:
        q = (select(Finding)
             .where(Finding.comparison_id == comparison_id, Finding.tenant_id == self.tenant_id)
             .order_by(Finding.priority))
        return list(self.s.scalars(q))

    def replace_findings(self, comparison_id: uuid.UUID, findings: list[Finding]) -> None:
        """Retries never duplicate findings (03 §7): the old set is replaced in the same transaction."""
        self.s.execute(delete(Finding).where(Finding.comparison_id == comparison_id,
                                             Finding.tenant_id == self.tenant_id))
        for f in findings:
            self.add(f)
