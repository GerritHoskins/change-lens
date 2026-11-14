"""Schema, role and dev-seed commands (I-8 S1, S3). Run from backend/.

    python -m changelens.db stamp-baseline    # admin URL: adopt a dev database built by the old create_all
    python -m changelens.db bootstrap-roles   # admin URL: create the owner and app roles (S3)
    python -m alembic upgrade head            # migration URL (owner role); processes never migrate on start
    python -m changelens.db seed-dev          # migration URL: the dev token's user and membership (local only)

URLs: CHANGELENS_ADMIN_DATABASE_URL (a superuser), CHANGELENS_MIGRATION_DATABASE_URL (`changelens_owner`),
CHANGELENS_DATABASE_URL (`changelens_app`, the api, worker and retention). Role passwords come from
CHANGELENS_OWNER_DB_PASSWORD and CHANGELENS_APP_DB_PASSWORD; only CHANGELENS_ENV=local falls back to
the dev-only defaults that match the default URLs.

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

import psycopg
from psycopg import sql
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import BLANK_SCHEMA, MetaData, create_engine, inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.pool import NullPool

from changelens.config import (DEV_SUBJECT, DEV_TENANT_ID, admin_database_url_from_env,
                               migration_database_url_from_env)

ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"
BASELINE = "0001_baseline"
_SCRATCH = "changelens_baseline_check"
OWNER_ROLE, APP_ROLE = "changelens_owner", "changelens_app"
DEV_PASSWORDS = {OWNER_ROLE: "changelens-owner-dev-only", APP_ROLE: "changelens-app-dev-only"}
_ROLE_ATTRIBUTES = {
    # The owner owns tables and functions and bypasses RLS; only migrations and seeding connect as it.
    OWNER_ROLE: "LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION BYPASSRLS",
    # The app role is what the api, worker and retention run as: RLS applies to it in full.
    APP_ROLE: "LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS",
}


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


def _libpq(url: str) -> str:
    return url.replace("postgresql+psycopg://", "postgresql://", 1)


def role_passwords(env=None) -> dict:
    env = os.environ if env is None else env
    passwords = {OWNER_ROLE: env.get("CHANGELENS_OWNER_DB_PASSWORD"), APP_ROLE: env.get("CHANGELENS_APP_DB_PASSWORD")}
    for role, password in passwords.items():
        if not password:
            if env.get("CHANGELENS_ENV") != "local":
                raise RuntimeError("set CHANGELENS_OWNER_DB_PASSWORD and CHANGELENS_APP_DB_PASSWORD")
            passwords[role] = DEV_PASSWORDS[role]
        elif len(password) < 16:
            raise RuntimeError("database role passwords need at least 16 characters")
    return passwords


def bootstrap_roles(admin_url: str, passwords: dict) -> list[str]:
    """Create or update the owner and app roles (I-8 S3), grant schema rights, and hand every table and
    function in `public` to the owner. Idempotent; run as a superuser for each database. Returns the
    objects whose owner changed. The passwords travel as SQL literals and are never printed."""
    changed = []
    with psycopg.connect(_libpq(admin_url), autocommit=True) as conn:
        for role, attributes in _ROLE_ATTRIBUTES.items():
            exists = conn.execute("SELECT 1 FROM pg_roles WHERE rolname = %s", (role,)).fetchone()
            verb = "ALTER" if exists else "CREATE"
            conn.execute(sql.SQL("{} ROLE {} " + attributes + " PASSWORD {}").format(
                sql.SQL(verb), sql.Identifier(role), sql.Literal(passwords[role])))
        if conn.execute("SELECT pg_has_role(%s, %s, 'MEMBER')", (APP_ROLE, OWNER_ROLE)).fetchone()[0]:
            conn.execute(sql.SQL("REVOKE {} FROM {}").format(sql.Identifier(OWNER_ROLE), sql.Identifier(APP_ROLE)))
        conn.execute(sql.SQL("GRANT USAGE, CREATE ON SCHEMA public TO {}").format(sql.Identifier(OWNER_ROLE)))
        conn.execute(sql.SQL("GRANT USAGE ON SCHEMA public TO {}").format(sql.Identifier(APP_ROLE)))
        conn.execute(sql.SQL("REVOKE CREATE ON SCHEMA public FROM PUBLIC, {}").format(sql.Identifier(APP_ROLE)))
        tables = conn.execute("SELECT c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                              "WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p', 'v', 'm') "
                              "AND pg_get_userbyid(c.relowner) <> %s ORDER BY 1", (OWNER_ROLE,)).fetchall()
        for (name,) in tables:
            conn.execute(sql.SQL("ALTER TABLE public.{} OWNER TO {}").format(
                sql.Identifier(name), sql.Identifier(OWNER_ROLE)))
            changed.append("table " + name)
        functions = conn.execute("SELECT p.oid::regprocedure::text FROM pg_proc p "
                                 "JOIN pg_namespace n ON n.oid = p.pronamespace WHERE n.nspname = 'public' "
                                 "AND pg_get_userbyid(p.proowner) <> %s ORDER BY 1", (OWNER_ROLE,)).fetchall()
        for (signature,) in functions:
            conn.execute(sql.SQL("ALTER FUNCTION public.{} OWNER TO {}").format(
                sql.SQL(signature), sql.Identifier(OWNER_ROLE)))
            changed.append("function " + signature)
    return changed


def seed_dev(url: str, subject: str = DEV_SUBJECT, tenant=DEV_TENANT_ID) -> None:
    """The dev token's user and owner membership, on the owner role's URL (the app role has no rights on
    `users`)."""
    from sqlalchemy.orm import Session
    from changelens.domain.identity import ensure_member  # imports the models only when needed
    engine = _engine(url)
    try:
        with Session(engine) as session, session.begin():
            ensure_member(session, subject, tenant, "owner")
    finally:
        engine.dispose()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="ChangeLens schema and dev-seed commands.")
    parser.add_argument("command", choices=("stamp-baseline", "bootstrap-roles", "seed-dev"))
    args = parser.parse_args(argv)
    if args.command == "bootstrap-roles":
        try:
            changed = bootstrap_roles(admin_database_url_from_env(), role_passwords())
        except RuntimeError as exc:
            print(str(exc), file=sys.stderr)
            return 1
        for item in changed:
            print("Owner set to %s: %s" % (OWNER_ROLE, item))
        print("Roles %s and %s ready. Next: python -m alembic upgrade head" % (OWNER_ROLE, APP_ROLE))
        return 0
    if args.command == "stamp-baseline":
        diffs, adopted = stamp_baseline(admin_database_url_from_env())
        if diffs:
            print("Not stamped: the database differs from the baseline revision:", file=sys.stderr)
            for diff in diffs:
                print("  %r" % (diff,), file=sys.stderr)
            return 1
        for step in adopted:
            print("Adopted: " + step)
        print("Stamped at %s. Next: python -m changelens.db bootstrap-roles" % BASELINE)
        return 0
    if os.environ.get("CHANGELENS_ENV") != "local":
        print("seed-dev requires CHANGELENS_ENV=local", file=sys.stderr)
        return 1
    seed_dev(migration_database_url_from_env())
    print("Dev user and owner membership present for the dev tenant.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
