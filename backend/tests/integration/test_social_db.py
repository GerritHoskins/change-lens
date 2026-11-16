"""Native Google and Apple sign-in on Postgres (I-8 S4 §6 items 1-4; S5's Apple step): the api in logto
mode with real tables, functions and RLS, and fakes for Google, Apple and Logto (tests/social_fixture.py).
Logto access tokens are signed here and their JWKS served through `httpx.MockTransport`."""
from __future__ import annotations

import logging
import time
import uuid
from datetime import datetime, timedelta, timezone

import httpx
import jwt
import pytest
from fastapi.testclient import TestClient

from changelens.api.app import create_app
from changelens.auth.jwks import JwksKeyHolder
from changelens.auth.jwt_verifier import JwtPolicy
from changelens.domain.accounts import run_account_deletions
from changelens.domain.social import run_apple_parks
from conftest import make_settings
from social_fixture import Fakes, apple_nonce, apple_tokens, rsa_key

ISSUER, AUDIENCE = "https://auth.example.test/oidc", "https://api.example.test"
LOGTO_KEY = rsa_key("logto-1")
EMAIL = "person@example.test"


def bearer(subject: str) -> dict:
    now = int(time.time())
    token = jwt.encode({"iss": ISSUER, "aud": AUDIENCE, "sub": subject, "iat": now - 2, "exp": now + 600},
                       LOGTO_KEY[0], algorithm="RS256", headers={"kid": "logto-1"})
    return {"Authorization": "Bearer " + token}


class Social:
    def __init__(self, env, **overrides):
        self.env, self.db, self.fakes = env, env.db, Fakes()
        settings = make_settings(env.db.engine.url.render_as_string(hide_password=False), auth_mode="logto",
                                 dev_tokens={}, logto_issuer=ISSUER, logto_audience=AUDIENCE,
                                 logto_jwks_url=ISSUER + "/jwks", **overrides)
        keys = JwksKeyHolder(JwtPolicy(ISSUER, AUDIENCE), ISSUER + "/jwks", client=httpx.Client(
            transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"keys": [LOGTO_KEY[1]]}))))
        self.apple = apple_tokens(self.fakes)
        self.idp = self.fakes.logto()
        self.client = TestClient(create_app(settings, env.db, env.store, keys=keys, idp=self.idp,
                                            providers=self.fakes.providers(), apple=self.apple),
                                 raise_server_exceptions=False)

    def sign_in(self, provider, code, nonce=None):
        body = {"provider": provider, "code": code, **({"nonce": nonce} if nonce else {})}
        return self.client.post("/session", json=body)

    def apple_code(self, sub="a-sub-1", email=EMAIL, nonce="raw-nonce-123", **changes):
        return self.fakes.code("apple", sub, email, nonce=apple_nonce(nonce), **changes), nonce

    def session(self, subject, **kwargs):
        return self.client.post("/session", headers=bearer(subject), **kwargs)

    def count(self, table):
        return self.env.sql("SELECT count(*) FROM " + table)[0][0]

    def user_token(self, subject):
        rows = self.env.sql("SELECT id, apple_refresh_token_enc FROM users WHERE idp_subject = :s", s=subject)
        return rows[0] if rows else None


@pytest.fixture()
def social(env):
    return Social(env)


def _unauthenticated(r):
    assert r.status_code == 401 and r.json()["code"] == "unauthenticated", r.text


# 1. Sign-in -------------------------------------------------------------------------------------------
def test_a_new_google_identity_gets_a_logto_user_and_a_one_time_token_then_an_account(social):
    users_before = social.count("users")
    r = social.sign_in("google", social.fakes.code("google", "g-sub-1", EMAIL))
    assert r.status_code == 200, r.text
    body = r.json()
    [(email, token)] = social.fakes.one_time_tokens
    assert body == {"status": "sign_in", "one_time_token": token, "login_hint": EMAIL, "expires_in": 120}
    [logto_user] = social.fakes.users.values()
    assert logto_user["identities"]["google"]["userId"] == "g-sub-1" and email == EMAIL
    assert social.count("users") == users_before  # no account row before the Logto session
    assert social.session(logto_user["id"]).json()["status"] == "active"
    assert social.count("users") == users_before + 1
    again = social.sign_in("google", social.fakes.code("google", "g-sub-1", EMAIL))
    assert again.json()["status"] == "sign_in" and len(social.fakes.users) == 1  # the same Logto user


def test_an_apple_token_is_parked_then_attached_encrypted_to_the_new_user(social):
    code, nonce = social.apple_code()
    assert social.sign_in("apple", code, nonce).json()["status"] == "sign_in"
    [subject] = social.fakes.users
    [(park_subject, envelope)] = social.env.sql("SELECT logto_subject, token_enc FROM apple_token_parks")
    assert park_subject == subject and "apple-refresh" not in envelope
    assert social.session(subject).status_code == 200
    user_id, stored = social.user_token(subject)
    refresh = social.apple.open_user(stored, user_id)
    assert refresh.startswith("apple-refresh-") and refresh not in stored
    assert social.count("apple_token_parks") == 0


@pytest.mark.parametrize("make", [
    lambda s: s.fakes.code("google", "g-sub-2", EMAIL, aud="another-client"),
    lambda s: s.fakes.code("google", "g-sub-2", EMAIL, iss="https://evil.example.test"),
    lambda s: s.fakes.code("google", "g-sub-2", EMAIL, exp=int(time.time()) - 120),
    lambda s: s.fakes.code("google", "g-sub-2", EMAIL, verified=False),
    lambda s: s.fakes.code("google", "g-sub-2", None),
    lambda s: s.fakes.code("google", "g-sub-2", EMAIL, key=rsa_key("unpublished")),
    lambda s: "code-nobody-issued",
])
def test_bad_codes_and_tokens_are_unauthenticated_and_create_nothing(social, make):
    users = social.count("users")
    _unauthenticated(social.sign_in("google", make(social)))
    assert social.fakes.users == {} and social.fakes.one_time_tokens == []
    assert (social.count("users"), social.count("apple_token_parks"), social.count("pending_links")) == (users, 0, 0)


def test_a_reused_apple_code_fails_without_a_second_park(social):
    code, nonce = social.apple_code()
    assert social.sign_in("apple", code, nonce).status_code == 200
    _unauthenticated(social.sign_in("apple", code, nonce))
    assert social.count("apple_token_parks") == 1 and len(social.fakes.one_time_tokens) == 1


def test_malformed_bodies_and_unconfigured_providers_are_invalid(social):
    for body in ({"provider": "google"}, {"provider": "google", "code": 57831}, {"provider": "x", "code": "code-zq81"},
                 {"provider": "apple", "code": "code-zq82", "nonce": "short"},
                 {"provider": "google", "code": "code-zq83", "extra-zq": "value-zq"}):
        r = social.client.post("/session", json=body)
        assert r.status_code == 422 and r.json()["code"] == "invalid_request", body
        assert all(str(v) not in r.text for v in body.values() if v not in ("google", "apple", "x")), body
    assert social.fakes.requests == []


def test_a_logto_outage_is_503_and_the_apple_token_is_not_left_attachable(social):
    social.fakes.logto_down = True
    code, nonce = social.apple_code()
    r = social.sign_in("apple", code, nonce)
    assert r.status_code == 503 and r.json()["code"] == "provider_unavailable"
    assert social.count("apple_token_parks") == 0 and social.count("pending_links") == 0


def test_the_sign_up_cap_counts_new_logto_users(env):
    social = Social(env, signups_per_ip_per_day=1)
    assert social.sign_in("google", social.fakes.code("google", "g-1", "one@example.test")).status_code == 200
    r = social.sign_in("google", social.fakes.code("google", "g-2", "two@example.test"))
    assert r.status_code == 429 and len(social.fakes.users) == 1
    # A returning identity is not a sign-up.
    assert social.sign_in("google", social.fakes.code("google", "g-1", "one@example.test")).status_code == 200


# 2. Linking -------------------------------------------------------------------------------------------
def test_a_verified_email_match_returns_link_required_and_links_only_after_the_target_signs_in(social):
    target = social.fakes.logto_user(EMAIL)
    social.session(target)  # the existing account
    users = social.count("users")
    code, nonce = social.apple_code(sub="a-sub-link")
    r = social.sign_in("apple", code, nonce)
    body = r.json()
    assert r.status_code == 200 and body["status"] == "link_required" and body["methods"] == ["email"]
    assert set(body) == {"status", "methods", "link_id"} and EMAIL not in r.text and "a-sub-link" not in r.text
    assert len(social.fakes.users) == 1 and social.fakes.one_time_tokens == []  # nothing signed in or created
    assert social.count("users") == users and social.fakes.users[target]["identities"] == {}
    assert social.env.sql("SELECT logto_subject FROM apple_token_parks") == [(None,)]  # held by the link only
    done = social.session(target, json={"link_id": body["link_id"]})
    assert done.status_code == 200 and done.json()["status"] == "active"
    assert social.fakes.users[target]["identities"]["apple"]["userId"] == "a-sub-link"
    user_id, stored = social.user_token(target)
    assert social.apple.open_user(stored, user_id).startswith("apple-refresh-")
    assert (social.count("pending_links"), social.count("apple_token_parks")) == (0, 0)
    _unauthenticated(social.session(target, json={"link_id": body["link_id"]}))  # used once
    code, nonce = social.apple_code(sub="a-sub-link")
    assert social.sign_in("apple", code, nonce).json()["status"] == "sign_in"  # now a linked identity


def _link(social, target, sub="g-sub-link"):
    return social.sign_in("google", social.fakes.code("google", sub, EMAIL)).json()["link_id"]


def test_completing_as_another_user_fails_and_deletes_the_link(social):
    target, other = social.fakes.logto_user(EMAIL), social.fakes.logto_user("other@example.test")
    link_id = _link(social, target)
    _unauthenticated(social.session(other, json={"link_id": link_id}))
    assert social.count("pending_links") == 0 and social.fakes.users[target]["identities"] == {}
    _unauthenticated(social.session(target, json={"link_id": link_id}))  # gone for the target too


def test_an_expired_link_fails_and_its_parked_token_expires_for_revocation(social):
    target = social.fakes.logto_user(EMAIL)
    code, nonce = social.apple_code(sub="a-sub-exp")
    link_id = social.sign_in("apple", code, nonce).json()["link_id"]
    social.env.sql("UPDATE pending_links SET expires_at = now() - interval '1 minute' RETURNING id")
    _unauthenticated(social.session(target, json={"link_id": link_id}))
    assert social.count("pending_links") == 0 and social.fakes.users[target]["identities"] == {}
    assert social.env.sql("SELECT expires_at <= now() FROM apple_token_parks") == [(True,)]


@pytest.mark.parametrize("link_id", [str(uuid.uuid4()), "not-a-uuid"])
def test_unknown_link_ids_fail(social, link_id):
    target = social.fakes.logto_user(EMAIL)
    _unauthenticated(social.session(target, json={"link_id": link_id}))


def test_an_account_that_already_has_another_identity_of_the_provider_is_never_relinked(social):
    social.fakes.logto_user(EMAIL, {"google": {"userId": "g-original"}})
    _unauthenticated(social.sign_in("google", social.fakes.code("google", "g-intruder", EMAIL)))
    assert social.count("pending_links") == 0


# 3. Apple tokens: maintenance -------------------------------------------------------------------------
def test_expired_parks_are_revoked_then_deleted_and_a_failed_revoke_keeps_the_record(social):
    code, nonce = social.apple_code()
    social.sign_in("apple", code, nonce)  # never followed by a session: abandoned
    social.env.sql("UPDATE apple_token_parks SET expires_at = now() - interval '1 second', "
                   "next_attempt_at = now() - interval '1 second' RETURNING id")
    social.fakes.revoke_status = 500
    now = datetime.now(timezone.utc)
    assert run_apple_parks(social.db, social.apple, now=now)["pending_parked_apple_tokens"] == 1
    [(attempts, next_at)] = social.env.sql("SELECT attempts, next_attempt_at FROM apple_token_parks")
    assert attempts == 1 and next_at > now and social.fakes.revoked == []
    social.fakes.revoke_status = 200
    result = run_apple_parks(social.db, social.apple, now=now + timedelta(hours=2))
    assert result["revoked_parked_apple_tokens"] == 1 and social.count("apple_token_parks") == 0
    assert len(social.fakes.revoked) == 1 and social.fakes.revoked[0].startswith("apple-refresh-")


def test_expired_pending_links_are_pruned_and_their_tokens_revoked(social):
    social.fakes.logto_user(EMAIL)
    code, nonce = social.apple_code(sub="a-sub-prune")
    social.sign_in("apple", code, nonce)
    later = datetime.now(timezone.utc) + timedelta(hours=1, minutes=1)
    social.env.sql("UPDATE pending_links SET expires_at = now() - interval '1 second' RETURNING id")
    first = run_apple_parks(social.db, social.apple, now=later)
    assert first["pruned_pending_links"] == 1 and social.count("pending_links") == 0
    run_apple_parks(social.db, social.apple, now=later)
    assert social.count("apple_token_parks") == 0 and len(social.fakes.revoked) == 1


# 4. Account deletion's Apple step (S5) ------------------------------------------------------------------
def _apple_account(social):
    code, nonce = social.apple_code()
    social.sign_in("apple", code, nonce)
    [subject] = social.fakes.users
    social.session(subject)
    return subject


def test_deleting_an_account_revokes_its_apple_token_first_then_tombstones(social):
    subject = _apple_account(social)
    user_id, stored = social.user_token(subject)
    token = social.apple.open_user(stored, user_id)
    code, nonce = social.apple_code()  # a second, abandoned sign-in leaves a park for this subject
    social.sign_in("apple", code, nonce)
    r = social.client.delete("/me", headers=bearer(subject))
    assert r.status_code == 204, r.text
    assert social.fakes.revoked == [token] and subject not in social.fakes.users
    assert social.env.sql("SELECT idp_subject, apple_refresh_token_enc FROM users WHERE id = :u", u=user_id) == [(None, None)]
    assert social.env.sql("SELECT expires_at <= now() FROM apple_token_parks") == [(True,)]  # cleanup expired it
    run_apple_parks(social.db, social.apple, now=datetime.now(timezone.utc) + timedelta(seconds=1))
    assert social.count("apple_token_parks") == 0 and len(social.fakes.revoked) == 2


def test_an_apple_failure_keeps_the_token_and_the_deletion_pending_until_apple_confirms(social):
    subject = _apple_account(social)
    user_id, stored = social.user_token(subject)
    social.fakes.revoke_status = 500
    assert social.client.delete("/me", headers=bearer(subject)).status_code == 202
    assert social.user_token(subject) == (user_id, stored)  # kept, and the Logto user too (Apple goes first)
    assert subject in social.fakes.users
    assert social.env.sql("SELECT status FROM account_deletions WHERE user_id = :u", u=user_id) == [("pending",)]
    _unauthenticated(social.client.post("/session", headers=bearer(subject)))  # locked out meanwhile
    social.fakes.revoke_status = 200
    later = datetime.now(timezone.utc) + timedelta(hours=2)
    assert run_account_deletions(social.db, social.env.store, social.idp, now=later, apple=social.apple) == (1, 0)
    assert len(social.fakes.revoked) == 1 and subject not in social.fakes.users
    assert social.env.sql("SELECT apple_refresh_token_enc FROM users WHERE id = :u", u=user_id) == [(None,)]


def test_a_deletion_without_apple_configured_stays_pending_rather_than_dropping_the_token(social):
    subject = _apple_account(social)
    user_id, _ = social.user_token(subject)
    social.client.app.state.apple = None
    assert social.client.delete("/me", headers=bearer(subject)).status_code == 202
    assert social.user_token(subject)[1] is not None


# 5. No leaks ------------------------------------------------------------------------------------------
def test_no_response_log_or_error_holds_a_code_token_subject_or_email(social, caplog):
    secrets_seen = []
    with caplog.at_level(logging.DEBUG):
        target = social.fakes.logto_user("linked@example.test")
        code, nonce = social.apple_code(sub="a-sub-leak", email="linked@example.test")
        link = social.sign_in("apple", code, nonce)
        secrets_seen += [code, nonce, "a-sub-leak", target]
        bad = social.fakes.code("google", "g-sub-leak", "bad@example.test", aud="x")
        failed = social.sign_in("google", bad)
        secrets_seen += [bad, "g-sub-leak", "bad@example.test"]
        social.fakes.revoke_status = 500
        ok_code, ok_nonce = social.apple_code(sub="a-sub-ok", email="ok@example.test")
        social.sign_in("apple", ok_code, ok_nonce)
        [subject] = [u for u in social.fakes.users if u != target]
        social.session(subject)
        social.client.delete("/me", headers=bearer(subject))
        secrets_seen += [ok_code, "a-sub-ok", subject]
    tokens = [t for _, t in social.fakes.one_time_tokens]
    refresh = social.fakes.issued
    assert len(refresh) == 2
    logs = "\n".join(r.getMessage() for r in caplog.records if r.name.startswith("changelens"))
    for value in secrets_seen + tokens + refresh + ["linked@example.test", "ok@example.test", "apple-refresh"]:
        assert value not in logs, value
    for value in secrets_seen:
        assert value not in link.text and value not in failed.text, value
    assert failed.json() == {"type": "urn:changelens:problem:unauthenticated", "title": "Authentication required",
                             "status": 401, "code": "unauthenticated"}


def test_the_app_role_reaches_parks_links_and_the_token_column_only_through_the_functions(social):
    from sqlalchemy import text
    from sqlalchemy.exc import ProgrammingError
    social.fakes.logto_user(EMAIL)
    code, nonce = social.apple_code(sub="a-sub-rls")
    social.sign_in("apple", code, nonce)
    for query in ("SELECT * FROM apple_token_parks", "SELECT * FROM pending_links",
                  "SELECT apple_refresh_token_enc FROM users", "DELETE FROM pending_links"):
        with social.db.engine.connect() as conn, pytest.raises(ProgrammingError) as error:
            conn.execute(text(query))
        assert "permission denied" in str(error.value.orig)
