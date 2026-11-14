"""Alembic environment. Online mode only: every revision runs against a real Postgres connection.

A caller (tests, `changelens.db`) may pass an open connection in `config.attributes["connection"]`;
otherwise the URL comes from CHANGELENS_MIGRATION_DATABASE_URL (the owner role,
I-8 S3). SQL parameters are never echoed (AC-23).
"""
from alembic import context
from sqlalchemy import create_engine
from sqlalchemy.pool import NullPool

from changelens.config import migration_database_url_from_env
from changelens.domain.models import Base

config = context.config
target_metadata = Base.metadata


def _run(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


connection = config.attributes.get("connection")
if connection is not None:
    _run(connection)
else:
    engine = create_engine(migration_database_url_from_env(), echo=False, hide_parameters=True, poolclass=NullPool)
    try:
        with engine.connect() as conn:
            _run(conn)
            conn.commit()
    finally:
        engine.dispose()
