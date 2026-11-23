"""Removal from the early-bird list in Postgres (migration 0010): the migration itself, the function as the
app role, who can read the list (the owner role's export, never the app role), and the routes on top. The
catalog checks (definer, search path, grants, argument validation) are in test_rls_db.py."""
import csv
import hashlib
import io
import uuid

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, ProgrammingError

from changelens import early_bird_export
from changelens.api.app import create_app
from changelens.db import APP_ROLE, OWNER_ROLE, alembic_config, upgrade
from changelens.mail import RecordingMailer
from changelens.mail.unsubscribe import unsubscribe_token
from conftest import TEST_DB, db_url
from test_identity_db import OWNER_URL, revision, scratch  # noqa: F401 (scratch is a fixture)

ADDRESS = "ada@example.test"
LANDING, API = "https://landing.example.test", "https://api.example.test"
PATH = "/early-bird/unsubscribe"
BEFORE, THIS = "0009_early_bird", "0010_early_bird_unsubscribe"
SIGNATURE = "early_bird_unsubscribe(uuid)"


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _add(env, email=ADDRESS, locale="en", confirm=True) -> uuid.UUID:
    env.db.early_bird_request(email, locale, _hash(email), 5)
    env.db.early_bird_mark_sent(_hash(email))
    if confirm:
        assert env.db.early_bird_confirm(_hash(email)) == locale
    return env.sql("SELECT id FROM early_bird_signups WHERE email = :e", e=email)[0][0]


def _emails(env):
    return [row[0] for row in env.sql("SELECT email FROM early_bird_signups ORDER BY email")]


# The migration -------------------------------------------------------------------------------------
def test_the_migration_applies_from_0009_and_downgrades_without_touching_the_list(scratch):
    url, engine = scratch
    exists = text("SELECT to_regprocedure('public.%s') IS NOT NULL" % SIGNATURE)
    upgrade(OWNER_URL, BEFORE)
    signup = uuid.uuid4()
    with engine.begin() as conn:
        assert conn.execute(exists).scalar_one() is False
        conn.execute(text("INSERT INTO early_bird_signups (id, email, locale, status) "
                          "VALUES (:i, 'kept@example.test', 'de', 'confirmed')"), {"i": signup})
    upgrade(OWNER_URL, THIS)
    assert revision(engine) == THIS
    with engine.begin() as conn:
        assert conn.execute(exists).scalar_one() is True
        owner, definer, config, app_can, public_can = conn.execute(text(
            "SELECT pg_get_userbyid(p.proowner), p.prosecdef, p.proconfig, "
            "has_function_privilege(:app, p.oid, 'EXECUTE'), EXISTS (SELECT 1 FROM aclexplode(p.proacl) a WHERE a.grantee = 0) "
            "FROM pg_proc p WHERE p.oid = to_regprocedure('public.%s')" % SIGNATURE), {"app": APP_ROLE}).one()
        assert (owner, definer, config, app_can, public_can) == (
            OWNER_ROLE, True, ["search_path=pg_catalog, pg_temp"], True, False)
        command.downgrade(alembic_config(conn), BEFORE)
    assert revision(engine) == BEFORE
    with engine.begin() as conn:  # the function is gone; the table and its row are as they were
        assert conn.execute(exists).scalar_one() is False
        assert conn.execute(text("SELECT id, email, locale, status FROM early_bird_signups")).all() == [
            (signup, "kept@example.test", "de", "confirmed")]
        assert conn.execute(text("SELECT count(*) FROM pg_proc WHERE proname LIKE 'early_bird_%'")).scalar_one() == 4
    upgrade(OWNER_URL)  # to the head: later revisions leave this function as it is
    with engine.begin() as conn:
        assert conn.execute(text("SELECT early_bird_unsubscribe(:i)"), {"i": signup}).scalar_one() == "de"
        assert conn.execute(text("SELECT count(*) FROM early_bird_signups")).scalar_one() == 0


# The function --------------------------------------------------------------------------------------
def test_unsubscribe_deletes_that_row_and_returns_its_language(env):
    confirmed = _add(env, ADDRESS, "de")
    pending = _add(env, "pending@example.test", "en", confirm=False)
    _add(env, "stays@example.test", "en")
    assert env.db.early_bird_unsubscribe(confirmed) == "de"
    assert _emails(env) == ["pending@example.test", "stays@example.test"]
    assert env.db.early_bird_unsubscribe(confirmed) is None  # already removed
    assert env.db.early_bird_unsubscribe(uuid.uuid4()) is None  # never existed
    assert env.db.early_bird_unsubscribe(pending) == "en"  # a pending row too, and its link dies with it
    assert env.db.early_bird_confirm(_hash("pending@example.test")) is None
    assert _emails(env) == ["stays@example.test"]
    assert env.db.early_bird_request(ADDRESS, "en", _hash("again"), 5) is True  # nothing was kept: a new sign-up
    assert env.sql("SELECT id FROM early_bird_signups WHERE email = :e", e=ADDRESS)[0][0] != confirmed


def test_the_function_refuses_null_and_anything_that_is_not_a_uuid(env):
    _add(env)
    with env.db.engine.connect() as conn:
        for statement in ("SELECT early_bird_unsubscribe(NULL)", "SELECT early_bird_unsubscribe('not-a-uuid')",
                          "SELECT early_bird_unsubscribe('%s')" % ADDRESS):
            with pytest.raises(DBAPIError):
                conn.execute(text(statement))
            conn.rollback()
    assert _emails(env) == [ADDRESS]


# Who can read the list -----------------------------------------------------------------------------
def test_the_app_role_can_remove_by_id_and_still_cannot_read_or_list_anything(env):
    signup = _add(env)
    with env.db.engine.connect() as conn:
        assert conn.execute(text("SELECT current_user")).scalar_one() == APP_ROLE
        for statement in ("SELECT email FROM early_bird_signups", "SELECT id FROM early_bird_signups",
                          "SELECT count(*) FROM early_bird_signups", "DELETE FROM early_bird_signups WHERE id = :i",
                          "DELETE FROM early_bird_signups RETURNING email"):
            with pytest.raises(ProgrammingError) as error:
                conn.execute(text(statement), {"i": signup})
            assert "permission denied" in str(error.value.orig)
            conn.rollback()
    # No function hands the app role an address or an ID: every early_bird_* result is a flag, a count,
    # a language or nothing.
    results = dict(env.sql("SELECT p.proname, pg_get_function_result(p.oid) FROM pg_proc p "
                           "JOIN pg_namespace n ON n.oid = p.pronamespace "
                           "WHERE n.nspname = 'public' AND p.proname LIKE 'early_bird_%'"))
    assert results == {"early_bird_request": "boolean", "early_bird_mark_sent": "void", "early_bird_confirm": "text",
                       "early_bird_prune": "integer", "early_bird_unsubscribe": "text",
                       "early_bird_pending_days": "integer"}
    assert _emails(env) == [ADDRESS]


def test_the_owner_role_reads_the_list_although_rls_is_forced_and_the_app_role_is_refused(env):
    _add(env, ADDRESS, "de")
    _add(env, "pending@example.test", "en", confirm=False)
    forced, policies = env.sql(
        "SELECT c.relforcerowsecurity, (SELECT count(*) FROM pg_policies p WHERE p.tablename = c.relname) "
        "FROM pg_class c WHERE c.relname = 'early_bird_signups'")[0]
    assert forced is True and policies == 0  # no policy lets anyone in; the owner role bypasses RLS instead
    assert env.sql("SELECT rolname, rolbypassrls, rolsuper FROM pg_roles WHERE rolname IN (:o, :a) ORDER BY 1",
                   o=OWNER_ROLE, a=APP_ROLE) == [(APP_ROLE, False, False), (OWNER_ROLE, True, False)]
    rows = early_bird_export.confirmed_rows(db_url(TEST_DB, OWNER_ROLE))
    assert [(email, locale) for _, email, locale, _ in rows] == [(ADDRESS, "de")]  # confirmed rows only
    assert isinstance(rows[0][0], uuid.UUID) and rows[0][3].tzinfo is not None
    with pytest.raises(early_bird_export.Refused) as refused:
        early_bird_export.confirmed_rows(db_url(TEST_DB, APP_ROLE))
    assert "owner role" in str(refused.value) and ADDRESS not in str(refused.value)
    assert len(_emails(env)) == 2  # the export is read-only


def test_the_export_command_runs_as_the_owner_and_fails_closed_as_the_app_role(env):
    key = env.settings.early_bird_unsubscribe_key
    signup = _add(env, ADDRESS, "de")
    settings = {"CHANGELENS_PUBLIC_API_URL": API, "CHANGELENS_EARLY_BIRD_UNSUBSCRIBE_KEY": key}
    out, err = io.StringIO(), io.StringIO()
    owner = {**settings, "CHANGELENS_MIGRATION_DATABASE_URL": db_url(TEST_DB, OWNER_ROLE)}
    assert early_bird_export.main([], owner, out, err) == 0
    header, row = list(csv.reader(io.StringIO(out.getvalue())))
    assert header == ["email", "locale", "confirmed_at", "unsubscribe_url"]
    assert row[:2] == [ADDRESS, "de"] and row[3] == API + PATH + "?token=" + unsubscribe_token(key, signup)
    assert err.getvalue() == "early_bird_export rows=1 formula_start=0\n"
    out, err = io.StringIO(), io.StringIO()
    app = {**settings, "CHANGELENS_MIGRATION_DATABASE_URL": db_url(TEST_DB, APP_ROLE)}
    assert early_bird_export.main([], app, out, err) == 1
    assert out.getvalue() == "" and "owner role" in err.getvalue() and ADDRESS not in err.getvalue()


# The routes on Postgres ----------------------------------------------------------------------------
def test_export_link_page_and_removal_through_the_routes(env_factory):
    env = env_factory(landing_url=LANDING, public_api_url=API)
    client = TestClient(create_app(env.settings, env.db, env.store, mailer=RecordingMailer()),
                        raise_server_exceptions=False, follow_redirects=False)
    _add(env, ADDRESS, "de")
    _add(env, "pending@example.test", "en", confirm=False)
    _add(env, "stays@example.test", "en")
    out = io.StringIO()
    early_bird_export.write_csv(early_bird_export.confirmed_rows(db_url(TEST_DB, OWNER_ROLE)), API,
                                env.settings.early_bird_unsubscribe_key, out)
    links = {row["email"]: row["unsubscribe_url"] for row in csv.DictReader(io.StringIO(out.getvalue()))}
    assert sorted(links) == [ADDRESS, "stays@example.test"]
    link = links[ADDRESS][len(API):]
    page = client.get(link)
    assert page.status_code == 200 and ADDRESS not in page.text and len(_emails(env)) == 3  # GET removed nothing
    removed = client.post(link, content="List-Unsubscribe=One-Click",
                          headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert removed.status_code == 303 and removed.headers["location"] == LANDING + "/de/#unsubscribed"
    assert _emails(env) == ["pending@example.test", "stays@example.test"]
    again = client.post(PATH, content="token=" + link.split("token=")[1],
                        headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert again.headers["location"] == LANDING + "/#unsubscribed"  # already gone: the same answer
    forged = unsubscribe_token("another-key-" + "0" * 32, uuid.uuid4())
    assert client.post(PATH + "?token=" + forged).headers["location"] == LANDING + "/#unsubscribe-failed"
    pending = env.sql("SELECT id FROM early_bird_signups WHERE email = 'pending@example.test'")[0][0]
    token = unsubscribe_token(env.settings.early_bird_unsubscribe_key, pending)
    assert client.post(PATH + "?token=" + token).headers["location"] == LANDING + "/#unsubscribed"
    assert _emails(env) == ["stays@example.test"]
