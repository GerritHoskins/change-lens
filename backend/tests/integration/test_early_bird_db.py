"""The early-bird list in Postgres (migration 0009): the four functions as the app role, row-level security
on the table, the routes on top of them and the maintenance hook. The catalog checks (definer, search path,
grants, argument validation) are in test_rls_db.py."""
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

ADDRESS = "ada@example.test"
LANDING = "https://landing.example.test"


def _hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _rows(env):
    return env.sql("SELECT email, locale, status, token_hash, confirmation_sent_at IS NOT NULL, "
                   "confirmed_at IS NOT NULL FROM early_bird_signups ORDER BY email")


def _age(env, email, days):
    env.sql("UPDATE early_bird_signups SET created_at = now() - make_interval(days => :d) WHERE email = :e "
            "RETURNING id", d=days, e=email)


# The functions -------------------------------------------------------------------------------------
def test_request_inserts_pending_refreshes_pending_and_leaves_confirmed_alone(env):
    db = env.db
    assert db.early_bird_request(ADDRESS, "en", _hash("one"), 7) is True
    assert _rows(env) == [(ADDRESS, "en", "pending", _hash("one"), False, False)]
    db.early_bird_mark_sent(_hash("one"))
    assert _rows(env) == [(ADDRESS, "en", "pending", _hash("one"), True, False)]
    assert db.early_bird_request(ADDRESS, "de", _hash("two"), 7) is True  # a new token and the newer language
    assert _rows(env) == [(ADDRESS, "de", "pending", _hash("two"), True, False)]
    assert db.early_bird_confirm(_hash("one"), 7) is None  # the replaced token is dead
    assert db.early_bird_confirm(_hash("two"), 7) == "de"
    assert _rows(env) == [(ADDRESS, "de", "confirmed", None, True, True)]
    assert db.early_bird_confirm(_hash("two"), 7) is None  # single use
    assert db.early_bird_request(ADDRESS, "en", _hash("three"), 7) is False  # confirmed: nothing changes
    db.early_bird_mark_sent(_hash("three"))
    assert _rows(env) == [(ADDRESS, "de", "confirmed", None, True, True)]


def test_one_row_per_address_and_two_addresses_never_share_a_token(env):
    for token in ("a", "b", "c"):
        assert env.db.early_bird_request(ADDRESS, "en", _hash(token), 7) is True
    assert env.db.early_bird_request("eve@example.test", "en", _hash("d"), 7) is True
    assert [row[0] for row in _rows(env)] == [ADDRESS, "eve@example.test"]
    assert env.db.early_bird_confirm(_hash("d"), 7) == "en"
    assert [(row[0], row[2]) for row in _rows(env)] == [(ADDRESS, "pending"), ("eve@example.test", "confirmed")]


def test_tokens_expire_with_the_pending_period_and_prune_deletes_only_old_pending_rows(env):
    db = env.db
    db.early_bird_request("old@example.test", "en", _hash("old"), 7)
    db.early_bird_request("new@example.test", "en", _hash("new"), 7)
    db.early_bird_request("kept@example.test", "de", _hash("kept"), 7)
    assert db.early_bird_confirm(_hash("kept"), 7) == "de"
    _age(env, "old@example.test", 8)
    _age(env, "kept@example.test", 400)
    assert db.early_bird_confirm(_hash("old"), 7) is None  # expired before maintenance ran
    assert db.early_bird_prune(7) == 1
    assert [(row[0], row[2]) for row in _rows(env)] == [("kept@example.test", "confirmed"),
                                                        ("new@example.test", "pending")]
    assert db.early_bird_prune(7) == 0


def test_an_expired_pending_row_starts_a_new_period_on_the_next_request(env):
    env.db.early_bird_request(ADDRESS, "en", _hash("first"), 7)
    _age(env, ADDRESS, 30)
    assert env.db.early_bird_request(ADDRESS, "en", _hash("second"), 7) is True
    assert env.db.early_bird_confirm(_hash("second"), 7) == "en"


def test_maintenance_prunes_with_the_configured_period(env):
    env.db.early_bird_request(ADDRESS, "en", _hash("t"), 7)
    _age(env, ADDRESS, 3)
    now = datetime.now(timezone.utc)
    assert run_maintenance(env.db, env.store, now=now)["execute"] is False  # preview deletes nothing
    assert len(_rows(env)) == 1
    assert run_maintenance(env.db, env.store, now=now, execute=True)["pruned_early_bird_pending"] == 0
    summary = run_maintenance(env.db, env.store, now=now, execute=True, early_bird_pending_days=2)
    assert summary["pruned_early_bird_pending"] == 1 and _rows(env) == []


# Row-level security --------------------------------------------------------------------------------
@pytest.mark.parametrize("statement", [
    "SELECT email FROM early_bird_signups",
    "INSERT INTO early_bird_signups (id, email, locale, status) VALUES (gen_random_uuid(), 'x@example.test', 'en', 'confirmed')",
    "UPDATE early_bird_signups SET status = 'confirmed'",
    "DELETE FROM early_bird_signups",
])
def test_the_app_role_cannot_touch_the_table_directly(env, statement):
    env.db.early_bird_request(ADDRESS, "en", _hash("t"), 7)
    with env.db.engine.connect() as conn:
        with pytest.raises(ProgrammingError) as error:
            conn.execute(text(statement))
        assert "permission denied" in str(error.value.orig)
    assert _rows(env) == [(ADDRESS, "en", "pending", _hash("t"), False, False)]


# The routes on Postgres ----------------------------------------------------------------------------
def test_sign_up_and_confirmation_through_the_routes(env_factory):
    env = env_factory(landing_url=LANDING, public_api_url="https://api.example.test")
    mailer = RecordingMailer()
    client = TestClient(create_app(env.settings, env.db, env.store, mailer=mailer), raise_server_exceptions=False,
                        follow_redirects=False)
    first = client.post("/early-bird", json={"email": " Ada@Example.TEST", "locale": "de"})
    again = client.post("/early-bird", json={"email": ADDRESS, "locale": "de"})
    assert (first.status_code, first.json()) == (again.status_code, again.json()) == (202, {"status": "accepted"})
    tokens = [re.search(r"token=([A-Za-z0-9_-]+)", m.body).group(1) for m in mailer.sent]
    assert len(tokens) == 2 and [m.to for m in mailer.sent] == [ADDRESS, ADDRESS]
    assert _rows(env) == [(ADDRESS, "de", "pending", _hash(tokens[1]), True, False)]
    stored = str(env.sql("SELECT * FROM early_bird_signups"))
    assert tokens[0] not in stored and tokens[1] not in stored  # hashes only
    assert client.get("/early-bird/confirm?token=" + tokens[0]).headers["location"] == LANDING + "/#confirm-failed"
    assert client.get("/early-bird/confirm?token=" + tokens[1]).headers["location"] == LANDING + "/de/#confirmed"
    assert client.get("/early-bird/confirm?token=" + tokens[1]).headers["location"] == LANDING + "/#confirm-failed"
    confirmed = client.post("/early-bird", json={"email": ADDRESS, "locale": "en"})
    assert (confirmed.status_code, confirmed.json()) == (202, {"status": "accepted"}) and len(mailer.sent) == 2
    assert _rows(env) == [(ADDRESS, "de", "confirmed", None, True, True)]
    counters = str(env.sql("SELECT key_hash FROM rate_limit_counters"))
    assert "ada" not in counters and "example.test" not in counters
