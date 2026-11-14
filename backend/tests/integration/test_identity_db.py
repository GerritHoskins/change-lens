"""Migrations and GUARD in Postgres (I-8 S1, §8 items 1, 3 and 5).

Migration tests use their own scratch database, rebuilt per test; GUARD tests use the shared test
database that conftest builds with `upgrade head`.
"""
import uuid

import psycopg
import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine, inspect, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.pool import NullPool

from changelens.db import BASELINE, alembic_config, baseline_diffs, stamp_baseline, upgrade
from changelens.domain.models import Base
from test_reviews import _compared, _findings, _post
from conftest import PG, SUBJECT_A, TENANT_A, TENANT_B, TOKEN_A, auth, reset_schema, db_url

SCRATCH_DB = "changelens_migrations_test"


@pytest.fixture()
def scratch(services):
    with psycopg.connect(PG, connect_timeout=3, autocommit=True) as conn:
        if not conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (SCRATCH_DB,)).fetchone():
            conn.execute("CREATE DATABASE " + SCRATCH_DB)
    url = db_url(SCRATCH_DB)
    reset_schema(url)
    engine = create_engine(url, poolclass=NullPool, hide_parameters=True)
    yield url, engine
    engine.dispose()


def model_diffs(engine) -> list:
    with engine.connect() as conn:
        return compare_metadata(MigrationContext.configure(conn, opts={"compare_type": True}), Base.metadata)


def revision(engine) -> str:
    with engine.connect() as conn:
        return conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()


def build_legacy(engine) -> None:
    """A dev database as `create_schema()` left it at b8e3778: `create_all` without the identity tables."""
    Base.metadata.create_all(engine)
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE account_onboarding DROP CONSTRAINT fk_account_onboarding_user"))
        conn.execute(text("DROP TABLE memberships"))
        conn.execute(text("DROP TABLE users"))


def test_upgrade_head_on_an_empty_database_matches_the_models(scratch):
    url, engine = scratch
    upgrade(url)
    assert revision(engine) == "0002_identity"
    assert model_diffs(engine) == []


def test_the_identity_revision_downgrades_and_upgrades_again(scratch):
    url, engine = scratch
    upgrade(url)
    with engine.begin() as conn:
        command.downgrade(alembic_config(conn), BASELINE)
    assert revision(engine) == BASELINE
    tables = set(inspect(engine).get_table_names())
    assert "users" not in tables and "memberships" not in tables and "account_onboarding" in tables
    assert inspect(engine).get_foreign_keys("account_onboarding") == []
    upgrade(url)
    assert revision(engine) == "0002_identity" and model_diffs(engine) == []


def test_a_create_all_database_is_stamped_at_the_baseline_and_upgrades_cleanly(scratch):
    url, engine = scratch
    build_legacy(engine)
    with engine.begin() as conn:  # dev data keyed on the old tenant-as-account ID
        conn.execute(text("INSERT INTO projects (id, tenant_id, name) VALUES (:id, :t, 'Synthetic')"),
                     {"id": uuid.uuid4(), "t": TENANT_A})
        conn.execute(text("INSERT INTO account_onboarding (account_id, tenant_id, onboarding_step, updated_at) "
                          "VALUES (:t, :t, 3, now())"), {"t": TENANT_A})
    assert stamp_baseline(url) == ([], [])
    assert revision(engine) == BASELINE
    upgrade(url)
    assert revision(engine) == "0002_identity" and model_diffs(engine) == []
    with engine.connect() as conn:
        assert conn.execute(text("SELECT count(*) FROM projects")).scalar_one() == 1  # data kept
        assert conn.execute(text("SELECT count(*) FROM account_onboarding")).scalar_one() == 0  # no user: deleted
        leftovers = conn.execute(text("SELECT count(*) FROM information_schema.schemata "
                                      "WHERE schema_name LIKE 'changelens_baseline%'")).scalar_one()
    assert leftovers == 0  # the comparison's scratch schema was rolled back


def test_legacy_states_create_schema_left_behind_are_adopted_then_stamped(scratch):
    """A database last bootstrapped before O-23 (no account_onboarding) whose comparisons table predates
    the idempotency columns, so DEV_COLUMNS made uq_comparisons_request a unique index."""
    url, engine = scratch
    build_legacy(engine)
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE account_onboarding"))
        conn.execute(text("ALTER TABLE comparisons DROP CONSTRAINT uq_comparisons_request"))
        conn.execute(text("CREATE UNIQUE INDEX uq_comparisons_request ON comparisons (tenant_id, idempotency_key)"))
    with engine.connect() as conn:
        assert baseline_diffs(conn) == []  # the read-only check sees the same outcome
    assert not inspect(engine).has_table("account_onboarding")  # and changed nothing
    diffs, adopted = stamp_baseline(url)
    assert diffs == [] and adopted == ["created table account_onboarding",
                                       "promoted index uq_comparisons_request to a constraint"]
    upgrade(url)
    assert revision(engine) == "0002_identity" and model_diffs(engine) == []


def test_a_database_that_differs_from_the_baseline_is_not_stamped(scratch):
    url, engine = scratch
    build_legacy(engine)
    with engine.begin() as conn:
        conn.execute(text("ALTER TABLE projects DROP COLUMN client_label"))
        conn.execute(text("DROP TABLE account_onboarding"))
    diffs, adopted = stamp_baseline(url)
    assert adopted == [] and any(d[0] == "add_column" and d[2] == "projects" and d[3].name == "client_label" for d in diffs)
    assert not inspect(engine).has_table("alembic_version")
    assert not inspect(engine).has_table("account_onboarding")  # the adoption was rolled back too
    with engine.begin() as conn:  # a database already under Alembic is refused too
        command.stamp(alembic_config(conn), BASELINE)
    with pytest.raises(RuntimeError):
        stamp_baseline(url)


def _user(env, subject=SUBJECT_A):
    return env.users[subject]


def _execute(env, statement, **params):
    with env.db.system_session() as s:
        s.execute(text(statement), params)


def test_a_user_has_at_most_one_active_membership(env):
    with pytest.raises(IntegrityError):
        _execute(env, "INSERT INTO memberships (user_id, tenant_id, role, status) VALUES (:u, :t, 'owner', 'active')",
                u=_user(env), t=TENANT_B)
    _execute(env, "INSERT INTO memberships (user_id, tenant_id, role, status) VALUES (:u, :t, 'member', 'inactive')",
            u=_user(env), t=TENANT_B)  # an inactive second membership is allowed


@pytest.mark.parametrize("statement", [
    "INSERT INTO users (id, idp_subject) VALUES (gen_random_uuid(), '')",
    "INSERT INTO users (id, idp_subject) VALUES (gen_random_uuid(), :subject)",  # duplicate subject
    "INSERT INTO users (id, idp_subject) VALUES (gen_random_uuid(), repeat('s', 201))",
    "UPDATE memberships SET role = 'admin'",
    "UPDATE memberships SET status = 'removed'",
])
def test_the_identity_tables_reject_invalid_rows(env, statement):
    with pytest.raises(Exception) as error:
        _execute(env, statement, subject=SUBJECT_A)
    assert "IntegrityError" in type(error.value).__name__ or "DataError" in type(error.value).__name__


@pytest.mark.parametrize("change", [
    "UPDATE users SET deleted_at = now() WHERE idp_subject = :subject",
    "UPDATE memberships SET status = 'inactive' WHERE user_id = (SELECT id FROM users WHERE idp_subject = :subject)",
    "DELETE FROM memberships WHERE user_id = (SELECT id FROM users WHERE idp_subject = :subject)",
], ids=["deleted-user", "inactive-membership", "no-membership"])
def test_guard_checks_the_user_and_membership_on_every_request(env, change):
    assert env.get("/projects").status_code == 200
    _execute(env, change, subject=SUBJECT_A)
    r = env.get("/projects")
    assert r.status_code == 401 and r.json()["code"] == "unauthenticated"
    assert r.headers["www-authenticate"] == "Bearer" and SUBJECT_A not in r.text and TOKEN_A not in r.text


def test_onboarding_is_keyed_on_the_user_and_reviews_record_the_user_as_actor(env):
    r = env.client.put("/me/onboarding", json={"step": 2}, headers=auth(TOKEN_A))
    assert r.status_code == 200
    assert env.sql("SELECT account_id, tenant_id FROM account_onboarding") == [(_user(env), TENANT_A)]
    assert env.sql("SELECT tenant_id, role, status FROM memberships WHERE user_id = :u", u=_user(env)) == [
        (TENANT_A, "owner", "active")]
    _, _, cid = _compared(env)
    finding = _findings(env, cid)[0]
    assert _post(env, "/findings/%s/reviews" % finding["id"], {"action": "confirmed"}).status_code == 201
    approval = {"evidence_text": "Synthetic approval note", "stated_by": "Client contact",
                "stated_at": "2026-11-14T09:00:00+00:00"}
    assert _post(env, "/findings/%s/client-approvals" % finding["id"], approval).status_code == 201
    assert env.sql("SELECT actor FROM review_events") == [(str(_user(env)),)]
    assert env.sql("SELECT recorded_by FROM client_approvals") == [(str(_user(env)),)]
