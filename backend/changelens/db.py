"""Schema and dev-seed commands (I-8 S1). Run from backend/; the URL is CHANGELENS_DATABASE_URL.

    python -m alembic upgrade head            # migrate (the api and worker never migrate on start)
    python -m changelens.db stamp-baseline    # adopt a dev database built by the old create_all
    python -m changelens.db seed-dev          # the dev token's user and owner membership (local only)

`stamp-baseline` builds the baseline revision in a scratch schema (a savepoint that is rolled back),
adopts the two legacy states `create_schema()` could leave behind (a missing baseline table; the
comparisons idempotency index instead of its constraint), compares the tables with the baseline, and
stamps only if nothing differs. It is all one transaction: on any difference nothing changes.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import BLANK_SCHEMA, MetaData, create_engine, inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.pool import NullPool

from changelens.config import DEV_SUBJECT, DEV_TENANT_ID, database_url_from_env

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"
BASELINE = "0001_baseline"
_SCRATCH = "changelens_baseline_check"


def alembic_config(connection: Connection) -> Config:
    config = Config(str(ALEMBIC_INI))
    config.attributes["connection"] = connection
    return config


def _engine(url: str):
    return create_engine(url, echo=False, hide_parameters=True, poolclass=NullPool)


def upgrade(url: str, revision: str = "head") -> None:
    engine = _engine(url)
    try:
        with engine.begin() as conn:
            command.upgrade(alembic_config(conn), revision)
    finally:
        engine.dispose()


class _Refused(Exception):
    pass


def _baseline_reference(conn: Connection) -> MetaData:
    """The baseline revision's tables, built in a scratch schema inside a savepoint that is always
    rolled back, then reflected into schema-less metadata."""
    savepoint = conn.begin_nested()
    try:
        conn.execute(text(f"CREATE SCHEMA {_SCRATCH}"))
        conn.execute(text(f"SET LOCAL search_path TO {_SCRATCH}"))
        command.upgrade(alembic_config(conn), BASELINE)
        scratch = MetaData()
        scratch.reflect(conn, schema=_SCRATCH)
    finally:
        savepoint.rollback()
    conn.execute(text("SET LOCAL search_path TO DEFAULT"))
    reference = MetaData()
    for table in scratch.tables.values():
        if table.name != "alembic_version":
            table.to_metadata(reference, schema=None, referred_schema_fn=lambda *_: BLANK_SCHEMA)
    return reference


def _adopt_legacy(conn: Connection, reference: MetaData) -> list[str]:
    """Bring two states the old `create_schema()` itself produced up to the baseline, losslessly:
    a baseline table missing entirely (created as `create_all` would have on the next start), and
    `uq_comparisons_request` as a unique index (DEV_COLUMNS) instead of a constraint."""
    done, inspector = [], inspect(conn)
    existing = set(inspector.get_table_names())
    for table in reference.sorted_tables:
        if table.name not in existing:
            table.create(conn)
            done.append("created table " + table.name)
    if "comparisons" in existing:
        constraints = {c["name"] for c in inspector.get_unique_constraints("comparisons")}
        legacy = {i["name"]: i for i in inspector.get_indexes("comparisons")}.get("uq_comparisons_request")
        if ("uq_comparisons_request" not in constraints and legacy is not None and legacy["unique"]
                and legacy["column_names"] == ["tenant_id", "idempotency_key"]):
            conn.execute(text("ALTER TABLE comparisons ADD CONSTRAINT uq_comparisons_request "
                              "UNIQUE USING INDEX uq_comparisons_request"))
            done.append("promoted index uq_comparisons_request to a constraint")
    return done


def _diffs(conn: Connection, reference: MetaData) -> list:
    return compare_metadata(MigrationContext.configure(conn, opts={"compare_type": True}), reference)


def baseline_diffs(conn: Connection) -> list:
    """What `stamp-baseline` would find after adopting the legacy states. Changes nothing: the whole
    check runs in a transaction that is rolled back."""
    outer = conn.get_transaction() if conn.in_transaction() else conn.begin()
    try:
        reference = _baseline_reference(conn)
        _adopt_legacy(conn, reference)
        return _diffs(conn, reference)
    finally:
        outer.rollback()


def stamp_baseline(url: str) -> tuple[list, list[str]]:
    """Adopt a `create_all`-built database and stamp it at the baseline in one transaction, only if it
    then matches the baseline exactly. Returns (differences, adoption steps); on differences nothing
    is changed."""
    engine = _engine(url)
    try:
        with engine.connect() as conn:
            try:
                with conn.begin():
                    if inspect(conn).has_table("alembic_version"):
                        raise RuntimeError("the database is already under Alembic")
                    reference = _baseline_reference(conn)
                    adopted = _adopt_legacy(conn, reference)
                    diffs = _diffs(conn, reference)
                    if diffs:
                        raise _Refused(diffs)
                    command.stamp(alembic_config(conn), BASELINE)
            except _Refused as refused:
                return refused.args[0], []
        return [], adopted
    finally:
        engine.dispose()


def seed_dev(url: str, subject: str = DEV_SUBJECT, tenant=DEV_TENANT_ID) -> None:
    from changelens.domain import Database  # imports the models only when needed
    db = Database(url)
    try:
        with db.identity_scope() as identities:
            identities.ensure_member(subject, tenant, "owner")
    finally:
        db.engine.dispose()
        db._intent_engine.dispose()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="ChangeLens schema and dev-seed commands.")
    parser.add_argument("command", choices=("stamp-baseline", "seed-dev"))
    args = parser.parse_args(argv)
    url = database_url_from_env()
    if args.command == "stamp-baseline":
        diffs, adopted = stamp_baseline(url)
        if diffs:
            print("Not stamped: the database differs from the baseline revision:", file=sys.stderr)
            for diff in diffs:
                print("  %r" % (diff,), file=sys.stderr)
            return 1
        for step in adopted:
            print("Adopted: " + step)
        print("Stamped at %s. Next: python -m alembic upgrade head" % BASELINE)
        return 0
    if os.environ.get("CHANGELENS_ENV") != "local":
        print("seed-dev requires CHANGELENS_ENV=local", file=sys.stderr)
        return 1
    seed_dev(url)
    print("Dev user and owner membership present for the dev tenant.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
