"""GUARD's user and membership tables over in-memory SQLite, for unit tests with no services (I-8 S1).

The real `IdentityRepo` runs unchanged, so the unit suites exercise the user and membership checks
instead of a stub. Postgres behaviour (constraints, the partial unique index) is in the integration tests.
"""
from __future__ import annotations

import uuid
from contextlib import contextmanager
from typing import Optional

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from changelens.domain.identity import IdentityRepo
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


class SqliteIdentity:
    def __init__(self, engine=None):
        self.engine = engine or sqlite_engine()
        User.__table__.create(self.engine)
        Membership.__table__.create(self.engine)
        self._sessions = sessionmaker(self.engine, expire_on_commit=False)

    @contextmanager
    def identity_scope(self):
        with self._sessions() as s, s.begin():
            yield IdentityRepo(s)

    def seed(self, subject: str, tenant: uuid.UUID, role: str = "owner") -> uuid.UUID:
        with self.identity_scope() as identities:
            return identities.ensure_member(subject, tenant, role).id

    def user(self, subject: str) -> Optional[User]:
        with self.identity_scope() as identities:
            return identities.user_by_subject(subject)
