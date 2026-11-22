"""The early-bird list in Postgres (migrations 0009 and 0011): the functions as the app role, row-level
security on the table, the routes on top of them and the maintenance hook. The catalog checks (definer,
search path, grants, argument validation) are in test_rls_db.py; the review fixes of 0011 (next tokens,
lifetimes, the mail bound, the fixed period) in test_early_bird_hardening_db.py."""
import hashlib
import re
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.exc import ProgrammingError

from changelens.api.app import create_app
from changelens.domain.retention import run_maintenance
from changelens.mail import RecordingMailer
from changelens.mail.queue import InlineMailQueue

ADDRESS = "ada@example.test"
LANDING = "https://landing.example.test"


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _rows(env):
    return env.sql("SELECT email, locale, status, token_hash, confirmation_sent_at IS NOT NULL, "
                   "confirmed_at IS NOT NULL FROM early_bird_signups ORDER BY email")


def _age(env, email, days):
    """Move a sign-up, and the links issued for it, `days` into the past."""
    env.sql("UPDATE early_bird_signups SET created_at = created_at - make_interval(days => :d), "
            "token_issued_at = token_issued_at - make_interval(days => :d), "
            "next_token_issued_at = next_token_issued_at - make_interval(days => :d) WHERE email = :e "
            "RETURNING id", d=days, e=email)


def _mailed(db, email, locale, token):
    """A request whose confirmation mail went out: the link is the row's link from then on."""
    due = db.early_bird_request(email, locale, _hash(token), 5)
    db.early_bird_mark_sent(_hash(token))
    return due


# The functions -------------------------------------------------------------------------------------
def test_request_inserts_pending_refreshes_pending_and_leaves_confirmed_alone(env):
    db = env.db
    assert db.early_bird_request(ADDRESS, "en", _hash("one"), 5) is True
    assert _rows(env) == [(ADDRESS, "en", "pending", None, False, False)]  # a next token until its mail is out
    db.early_bird_mark_sent(_hash("one"))
    assert _rows(env) == [(ADDRESS, "en", "pending", _hash("one"), True, False)]
    assert _mailed(db, ADDRESS, "de", "two") is True  # a new token and the newer language
    assert _rows(env) == [(ADDRESS, "de", "pending", _hash("two"), True, False)]
    assert db.early_bird_confirm(_hash("one")) is None  # the replaced token is dead
    assert db.early_bird_confirm(_hash("two")) == "de"
    assert _rows(env) == [(ADDRESS, "de", "confirmed", None, True, True)]
    assert db.early_bird_confirm(_hash("two")) is None  # single use
    assert db.early_bird_request(ADDRESS, "en", _hash("three"), 5) is False  # confirmed: nothing changes
    db.early_bird_mark_sent(_hash("three"))
    assert _rows(env) == [(ADDRESS, "de", "confirmed", None, True, True)]
    assert env.sql("SELECT count(*) FROM early_bird_signups WHERE next_token_hash IS NOT NULL")[0][0] == 0


def test_one_row_per_address_and_two_addresses_never_share_a_token(env):
    for token in ("a", "b", "c"):
        assert _mailed(env.db, ADDRESS, "en", token) is True
    assert _mailed(env.db, "eve@example.test", "en", "d") is True
    assert [row[0] for row in _rows(env)] == [ADDRESS, "eve@example.test"]
    assert env.db.early_bird_confirm(_hash("d")) == "en"
    assert [(row[0], row[2]) for row in _rows(env)] == [(ADDRESS, "pending"), ("eve@example.test", "confirmed")]


def test_tokens_expire_with_the_pending_period_and_prune_deletes_only_old_pending_rows(env):
    db = env.db
    _mailed(db, "old@example.test", "en", "old")
    _mailed(db, "new@example.test", "en", "new")
    _mailed(db, "kept@example.test", "de", "kept")
    assert db.early_bird_confirm(_hash("kept")) == "de"
    _age(env, "old@example.test", 8)
    _age(env, "kept@example.test", 400)
    assert db.early_bird_confirm(_hash("old")) is None  # expired before maintenance ran
    assert db.early_bird_prune() == 1
    assert [(row[0], row[2]) for row in _rows(env)] == [("kept@example.test", "confirmed"),
                                                        ("new@example.test", "pending")]
    assert db.early_bird_prune() == 0


def test_an_expired_pending_row_starts_a_new_period_on_the_next_request(env):
    _mailed(env.db, ADDRESS, "en", "first")
    _age(env, ADDRESS, 30)
    assert _mailed(env.db, ADDRESS, "en", "second") is True
    assert env.db.early_bird_confirm(_hash("second")) == "en"


def test_maintenance_prunes_with_the_period_the_database_fixes(env):
    _mailed(env.db, ADDRESS, "en", "t")
    _age(env, ADDRESS, 3)
    now = datetime.now(timezone.utc)
    assert run_maintenance(env.db, env.store, now=now)["execute"] is False  # preview deletes nothing
    assert len(_rows(env)) == 1
    assert run_maintenance(env.db, env.store, now=now, execute=True)["pruned_early_bird_pending"] == 0
    with pytest.raises(TypeError):  # maintenance can't be given another period any more
        run_maintenance(env.db, env.store, now=now, execute=True, early_bird_pending_days=2)
    _age(env, ADDRESS, 5)  # eight days old now
    summary = run_maintenance(env.db, env.store, now=now, execute=True)
    assert summary["pruned_early_bird_pending"] == 1 and _rows(env) == []


# Row-level security --------------------------------------------------------------------------------
@pytest.mark.parametrize("statement", [
    "SELECT email FROM early_bird_signups",
    "INSERT INTO early_bird_signups (id, email, locale, status) VALUES (gen_random_uuid(), 'x@example.test', 'en', 'confirmed')",
    "UPDATE early_bird_signups SET status = 'confirmed'",
    "DELETE FROM early_bird_signups",
])
def test_the_app_role_cannot_touch_the_table_directly(env, statement):
    _mailed(env.db, ADDRESS, "en", "t")
    with env.db.engine.connect() as conn:
        with pytest.raises(ProgrammingError) as error:
            conn.execute(text(statement))
        assert "permission denied" in str(error.value.orig)
    assert _rows(env) == [(ADDRESS, "en", "pending", _hash("t"), True, False)]


# The routes on Postgres ----------------------------------------------------------------------------
def test_sign_up_and_confirmation_through_the_routes(env_factory):
    env = env_factory(landing_url=LANDING, public_api_url="https://api.example.test")
    mailer = RecordingMailer()
    client = TestClient(create_app(env.settings, env.db, env.store, mailer=mailer, mail_queue=InlineMailQueue()),
                        raise_server_exceptions=False, follow_redirects=False)

    def confirm(token):  # the button on the page the link opens
        return client.post("/early-bird/confirm", content="token=" + token,
                           headers={"Content-Type": "application/x-www-form-urlencoded"}).headers["location"]

    first = client.post("/early-bird", json={"email": " Ada@Example.TEST", "locale": "de"})
    again = client.post("/early-bird", json={"email": ADDRESS, "locale": "de"})
    assert (first.status_code, first.json()) == (again.status_code, again.json()) == (202, {"status": "accepted"})
    tokens = [re.search(r"token=([A-Za-z0-9_-]+)", m.body).group(1) for m in mailer.sent]
    assert len(tokens) == 2 and [m.to for m in mailer.sent] == [ADDRESS, ADDRESS]
    assert _rows(env) == [(ADDRESS, "de", "pending", _hash(tokens[1]), True, False)]
    stored = str(env.sql("SELECT * FROM early_bird_signups"))
    assert tokens[0] not in stored and tokens[1] not in stored  # hashes only
    opened = client.get("/early-bird/confirm?token=" + tokens[1])  # opening the link: the page, no change
    assert opened.status_code == 200 and ADDRESS not in opened.text
    assert _rows(env) == [(ADDRESS, "de", "pending", _hash(tokens[1]), True, False)]
    assert confirm(tokens[0]) == LANDING + "/#confirm-failed"
    assert confirm(tokens[1]) == LANDING + "/de/#confirmed"
    assert confirm(tokens[1]) == LANDING + "/#confirm-failed"
    confirmed = client.post("/early-bird", json={"email": ADDRESS, "locale": "en"})
    assert (confirmed.status_code, confirmed.json()) == (202, {"status": "accepted"}) and len(mailer.sent) == 2
    assert _rows(env) == [(ADDRESS, "de", "confirmed", None, True, True)]
    counters = str(env.sql("SELECT key_hash FROM rate_limit_counters"))
    assert "ada" not in counters and "example.test" not in counters
