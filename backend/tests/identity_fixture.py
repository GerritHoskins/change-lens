"""GUARD's user and membership tables over in-memory SQLite, for unit tests with no services (I-8 S1).

In Postgres, `IdentityRepo` calls the `session_lookup` and `session_bootstrap` functions (migration 0003,
I-8 S3), which SQLite doesn't have. `OrmIdentityRepo` keeps `IdentityRepo`'s interface and outcome
handling and does the functions' lookups with the ORM. The functions themselves, the constraints and the
partial unique index are covered by the integration tests.
"""
from __future__ import annotations

import uuid
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Optional

from sqlalchemy import create_engine, event
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from changelens.domain.identity import IdentityRepo, Principal, active_membership, ensure_member, user_by_subject
from changelens.domain.models import Membership, User


def sqlite_engine():
    engine = create_engine("sqlite://", hide_parameters=True, poolclass=StaticPool,
                           connect_args={"check_same_thread": False})

    # pysqlite's own transaction handling breaks SAVEPOINT; let SQLAlchemy emit BEGIN.
    @event.listens_for(engine, "connect")
    def _connect(dbapi_connection, _):
        dbapi_connection.isolation_level = None

    @event.listens_for(engine, "begin")
    def _begin(conn):
        conn.exec_driver_sql("BEGIN")

    return engine


class OrmIdentityRepo(IdentityRepo):
    """The two SQL functions, done with the ORM for SQLite."""

    def principal(self, subject: str) -> Optional[Principal]:
        user = user_by_subject(self.s, subject)
        if user is None or user.deleted_at is not None:
            return None
        membership = active_membership(self.s, user.id)
        return Principal(user.id, membership.tenant_id, membership.role) if membership else None

    def _bootstrap(self, subject: str, create: bool):
        user, created = user_by_subject(self.s, subject), False
        if user is None:
            if not create:
                return SimpleNamespace(outcome="missing")
            try:
                with self.s.begin_nested():
                    user = User(idp_subject=subject)
                    self.s.add(user)
                    self.s.flush()
                    self.s.add(Membership(user_id=user.id, tenant_id=uuid.uuid4(), role="owner", status="active"))
                    self.s.flush()
                    created = True
            except IntegrityError:
                self.s.expunge_all()
                user = user_by_subject(self.s, subject)
        if user.deleted_at is not None:
            return SimpleNamespace(outcome="deleted")
        membership = active_membership(self.s, user.id)
        if membership is None:
            return SimpleNamespace(outcome="no_membership")
        return SimpleNamespace(outcome="created" if created else "existing", user_id=user.id,
                               tenant_id=membership.tenant_id, member_role=membership.role)


class SqliteIdentity:
    def __init__(self, engine=None):
        self.engine = engine or sqlite_engine()
        User.__table__.create(self.engine)
        Membership.__table__.create(self.engine)
        self._sessions = sessionmaker(self.engine, expire_on_commit=False)

    @contextmanager
    def identity_scope(self):
        with self._sessions() as s, s.begin():
            yield OrmIdentityRepo(s)

    def seed(self, subject: str, tenant: uuid.UUID, role: str = "owner") -> uuid.UUID:
        with self._sessions() as s, s.begin():
            return ensure_member(s, subject, tenant, role).id

    def user(self, subject: str) -> Optional[User]:
        with self._sessions() as s, s.begin():
            return user_by_subject(s, subject)
