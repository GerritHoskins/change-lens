"""The early-bird review fixes in Postgres (migration 0011; docs/security-review.md EB-1 to EB-13): the
migration itself, the period the database fixes, next tokens and their promotion, lifetimes from the issue
time, the mail bound per pending sign-up, and the cap for all addresses through the real counters."""
import hashlib
import re

import pytest
from alembic import command
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool
from sqlalchemy.exc import DBAPIError, ProgrammingError

from changelens.api.app import create_app
from changelens.db import alembic_config, upgrade
from changelens.mail import RecordingMailer
from changelens.mail.confirmation import PENDING_DAYS
from changelens.mail.queue import InlineMailQueue
from test_early_bird_db import _age, _mailed
from test_identity_db import HEAD, OWNER_URL, model_diffs, revision, scratch  # noqa: F401 (scratch is a fixture)

ADDRESS = "ada@example.test"
BEFORE = "0010_early_bird_unsubscribe"
NEW_COLUMNS = {"token_issued_at", "next_token_hash", "next_token_issued_at", "mail_count"}


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _row(env, email=ADDRESS):
    rows = env.sql("SELECT status, token_hash, next_token_hash, mail_count, token_issued_at IS NOT NULL, "
                   "confirmation_sent_at IS NOT NULL FROM early_bird_signups WHERE email = :e", e=email)
    return rows[0] if rows else None


def _signatures(conn):
    return sorted(row[0] for row in conn.execute(text(
        "SELECT p.oid::regprocedure::text FROM pg_proc p WHERE p.proname LIKE 'early_bird_%'")))


# The migration -------------------------------------------------------------------------------------
def test_the_migration_applies_from_0010_keeps_mailed_links_and_downgrades(scratch):  # noqa: F811
    url, engine = scratch
    upgrade(OWNER_URL, BEFORE)
    old = ["early_bird_confirm(text,integer)", "early_bird_mark_sent(text)", "early_bird_prune(integer)",
           "early_bird_request(text,text,text,integer)", "early_bird_unsubscribe(uuid)"]
    with engine.begin() as conn:
        assert _signatures(conn) == old
        assert conn.execute(text("SELECT early_bird_request('mailed@example.test', 'de', :h, 7)"),
                            {"h": _hash("mailed")}).scalar_one() is True
        conn.execute(text("UPDATE early_bird_signups SET created_at = now() - interval '2 days'"))
    upgrade(OWNER_URL)
    assert revision(engine) == HEAD and model_diffs(engine) == []  # 0011 and every revision after it
    with engine.begin() as conn:
        assert _signatures(conn) == ["early_bird_confirm(text)", "early_bird_mark_sent(text)",
                                     "early_bird_pending_days()", "early_bird_prune()",
                                     "early_bird_request(text,text,text,integer)", "early_bird_unsubscribe(uuid)"]
        issued, created, count, next_hash = conn.execute(text(
            "SELECT token_issued_at, created_at, mail_count, next_token_hash FROM early_bird_signups")).one()
        assert issued == created and count == 1 and next_hash is None  # the link keeps the lifetime it had
    owner = create_engine(OWNER_URL, poolclass=NullPool, hide_parameters=True)
    with owner.begin() as conn:  # as the owner role, like every migration: it recreates 0009's functions
        command.downgrade(alembic_config(conn), BEFORE)
    owner.dispose()
    assert revision(engine) == BEFORE
    with engine.begin() as conn:
        assert _signatures(conn) == old
        columns = {row[0] for row in conn.execute(text(
            "SELECT column_name FROM information_schema.columns WHERE table_name = 'early_bird_signups'"))}
        assert not columns & NEW_COLUMNS
        granted = conn.execute(text("SELECT has_function_privilege('changelens_app', "
                                    "'early_bird_confirm(text, integer)', 'EXECUTE')")).scalar_one()
        assert granted is True
    upgrade(OWNER_URL)
    with engine.begin() as conn:  # the link mailed before any of this still confirms
        assert conn.execute(text("SELECT early_bird_confirm(:h)"), {"h": _hash("mailed")}).scalar_one() == "de"


# EB-6 (L3): the period -----------------------------------------------------------------------------
def test_the_database_fixes_the_pending_period_and_it_is_the_one_the_mail_states(env):
    assert env.db.early_bird_pending_days() == PENDING_DAYS == 7
    _mailed(env.db, ADDRESS, "en", "t")
    _age(env, ADDRESS, PENDING_DAYS - 1)
    assert env.db.early_bird_prune() == 0
    with env.db.engine.connect() as conn:  # the app role has no way to pass a period of its own
        for call in ("early_bird_prune(365)", "early_bird_prune(1)", "early_bird_confirm(:h, 365)",
                     "early_bird_pending_days(30)"):
            with pytest.raises(ProgrammingError) as error:
                conn.execute(text("SELECT " + call), {"h": _hash("t")})
            assert "does not exist" in str(error.value.orig)
            conn.rollback()
        with pytest.raises(DBAPIError) as error:  # and can't put a function of its own in the way
            conn.execute(text("CREATE OR REPLACE FUNCTION early_bird_pending_days() RETURNS integer "
                              "LANGUAGE sql AS 'SELECT 365'"))
        assert "must be owner" in str(error.value.orig) or "permission denied" in str(error.value.orig)
    _age(env, ADDRESS, 2)
    assert env.db.early_bird_confirm(_hash("t")) is None and env.db.early_bird_prune() == 1


# EB-4 (L1): next tokens ----------------------------------------------------------------------------
def test_a_new_token_is_the_next_one_until_its_mail_is_out_and_the_mailed_link_keeps_working(env):
    db = env.db
    _mailed(db, ADDRESS, "en", "one")
    assert db.early_bird_request(ADDRESS, "en", _hash("two"), 5) is True  # its mail is not out yet
    assert _row(env) == ("pending", _hash("one"), _hash("two"), 2, True, True)
    assert db.early_bird_request(ADDRESS, "en", _hash("three"), 5) is True  # a newer one replaces the unsent one
    assert _row(env)[1:3] == (_hash("one"), _hash("three"))
    assert db.early_bird_confirm(_hash("two")) is None
    assert db.early_bird_confirm(_hash("one")) == "en"  # the link that was mailed still works
    assert _row(env) == ("confirmed", None, None, 3, False, True)


def test_mark_sent_promotes_the_next_token_and_ends_the_one_before(env):
    db = env.db
    _mailed(db, ADDRESS, "en", "one")
    db.early_bird_request(ADDRESS, "de", _hash("two"), 5)
    db.early_bird_mark_sent(_hash("unknown"))  # another token's mail: nothing moves
    assert _row(env)[1:3] == (_hash("one"), _hash("two"))
    db.early_bird_mark_sent(_hash("two"))
    assert _row(env) == ("pending", _hash("two"), None, 2, True, True)
    db.early_bird_mark_sent(_hash("two"))  # again: the same state
    assert _row(env) == ("pending", _hash("two"), None, 2, True, True)
    assert db.early_bird_confirm(_hash("one")) is None and db.early_bird_confirm(_hash("two")) == "de"


def test_a_token_whose_mail_went_out_but_was_never_recorded_still_confirms(env):
    assert env.db.early_bird_request(ADDRESS, "de", _hash("only"), 5) is True
    assert _row(env) == ("pending", None, _hash("only"), 1, False, False)
    assert env.db.early_bird_confirm(_hash("only")) == "de"


# EB-5 (L2): lifetimes ------------------------------------------------------------------------------
def test_a_link_lives_from_when_it_was_issued_and_the_row_is_pruned_by_its_newest_mailed_link(env):
    db = env.db
    _mailed(db, ADDRESS, "en", "one")
    _age(env, ADDRESS, 6)
    _mailed(db, ADDRESS, "en", "two")
    _age(env, ADDRESS, 6)  # the sign-up is 12 days old, its second link 6
    assert db.early_bird_prune() == 0  # the second mail said: deleted after 7 days
    assert db.early_bird_confirm(_hash("two")) == "en"
    _mailed(db, "late@example.test", "en", "first")
    _age(env, "late@example.test", 6)
    db.early_bird_request("late@example.test", "en", _hash("unsent"), 5)  # issued now, its mail not out
    _age(env, "late@example.test", 2)
    assert db.early_bird_confirm(_hash("first")) is None  # eight days after it was issued
    assert db.early_bird_confirm(_hash("unsent")) == "en"  # its own two days are not over


def test_an_unsent_next_token_does_not_keep_a_row_alive(env):
    db = env.db
    _mailed(db, ADDRESS, "en", "first")
    _age(env, ADDRESS, 6)
    db.early_bird_request(ADDRESS, "en", _hash("unsent"), 5)
    _age(env, ADDRESS, 2)  # eight days after the only mail
    assert db.early_bird_prune() == 1 and _row(env) is None


# EB-1 (M1d): mails per pending sign-up ---------------------------------------------------------------
def test_a_pending_row_gets_at_most_the_given_number_of_mails_and_starts_at_one_after_it_expired(env):
    db = env.db
    assert [db.early_bird_request(ADDRESS, "en", _hash("t%d" % i), 5) for i in range(7)] == [True] * 5 + [False] * 2
    assert _row(env) == ("pending", None, _hash("t4"), 5, False, False)  # the refused requests changed nothing
    assert db.early_bird_request(ADDRESS, "en", _hash("more"), 6) is True  # the bound is the caller's setting
    assert db.early_bird_request(ADDRESS, "en", _hash("stop"), 6) is False
    db.early_bird_mark_sent(_hash("more"))
    _age(env, ADDRESS, PENDING_DAYS + 1)  # expired, not pruned yet
    assert db.early_bird_request(ADDRESS, "de", _hash("fresh"), 5) is True
    assert _row(env) == ("pending", None, _hash("fresh"), 1, False, False)  # nothing of the old period is left
    assert db.early_bird_confirm(_hash("more")) is None and db.early_bird_confirm(_hash("fresh")) == "de"
    assert db.early_bird_request(ADDRESS, "en", _hash("x"), 5) is False  # confirmed: no mails at all


# EB-1 (M1a) and EB-2 through the routes, on the real counters -----------------------------------------
def test_the_cap_for_all_addresses_and_the_confirm_button_through_the_routes(env_factory):
    env = env_factory(landing_url="https://landing.example.test", public_api_url="https://api.example.test",
                      early_bird_mails_per_hour=2, early_bird_per_ip_per_day=100)
    mailer = RecordingMailer()
    client = TestClient(create_app(env.settings, env.db, env.store, mailer=mailer, mail_queue=InlineMailQueue()),
                        raise_server_exceptions=False, follow_redirects=False)
    answers = [client.post("/early-bird", json={"email": "p%d+tag@example.test" % i, "locale": "en"}) for i in range(4)]
    assert {(r.status_code, r.text) for r in answers} == {(202, '{"status":"accepted"}')}
    assert [m.to for m in mailer.sent] == ["p0+tag@example.test", "p1+tag@example.test"]
    assert [row[0] for row in env.sql("SELECT email FROM early_bird_signups ORDER BY 1")] == [
        "p0+tag@example.test", "p1+tag@example.test"]  # over the cap nothing was stored
    counters = env.sql("SELECT key_hash FROM rate_limit_counters")
    assert len(counters) == 1 + 4 + 2 and all(  # the client, four addresses, all mails per hour and per day
        re.fullmatch(r"[0-9a-f]{64}", row[0]) for row in counters)
    token = re.search(r"token=([A-Za-z0-9_-]+)", mailer.sent[0].body).group(1)
    assert client.get("/early-bird/confirm?token=" + token).status_code == 200
    assert _row(env, "p0+tag@example.test")[0] == "pending"  # the page confirmed nothing
    confirmed = client.post("/early-bird/confirm", content="token=" + token,
                            headers={"Content-Type": "application/x-www-form-urlencoded"})
    assert confirmed.headers["location"] == "https://landing.example.test/#confirmed"
    assert _row(env, "p0+tag@example.test") == ("confirmed", None, None, 1, False, True)
