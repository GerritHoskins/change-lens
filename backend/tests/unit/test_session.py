"""`POST /session` (I-8 S2, §7 items 1, 2, 4-6) with no services: Logto tokens signed in the test,
the JWKS through `httpx.MockTransport`, users, memberships and onboarding in SQLite."""
from datetime import datetime, timezone
import logging
import time

from fastapi.testclient import TestClient
import httpx
import pytest

from changelens.api.app import create_app
from changelens.auth.jwks import JwksKeyHolder
from changelens.auth.jwt_verifier import JwtPolicy
from changelens.domain.models import Membership, User
from changelens.storage import MemoryObjectStore
from test_guard_logto import AUDIENCE, ISSUER, JWKS_URL, KEY_1, KEY_3, GuardDb, Jwks, logto_settings, sign

NEW = {"status": "active", "onboarding": {"completed": False, "step": None}}


@pytest.fixture()
def env():
    db = GuardDb()
    keys = JwksKeyHolder(JwtPolicy(ISSUER, AUDIENCE), JWKS_URL,
                         client=httpx.Client(transport=httpx.MockTransport(Jwks(KEY_1).handler)))
    client = TestClient(create_app(logto_settings(), db, MemoryObjectStore(), keys=keys),
                        raise_server_exceptions=False)
    return client, db


def session(client, token, **kwargs):
    return client.post("/session", headers={"Authorization": "Bearer " + token}, **kwargs)


def rows(db, model):
    with db._sessions() as s:
        return list(s.query(model).all())


def test_the_first_call_creates_one_user_tenant_and_owner_membership(env):
    client, db = env
    r = session(client, sign(sub="new-subject-1"))
    assert r.status_code == 200 and r.json() == NEW
    [user], [membership] = rows(db, User), rows(db, Membership)
    assert user.idp_subject == "new-subject-1" and user.deleted_at is None
    assert (membership.user_id, membership.role, membership.status) == (user.id, "owner", "active")
    assert str(user.id) not in r.text and str(membership.tenant_id) not in r.text and "new-subject-1" not in r.text


def test_later_calls_return_the_same_account_and_its_onboarding_state(env):
    client, db = env
    token = sign(sub="new-subject-2")
    assert session(client, token).json() == NEW
    auth = {"Authorization": "Bearer " + token}
    assert client.put("/me/onboarding", json={"step": 3}, headers=auth).status_code == 200
    assert session(client, token).json() == {"status": "active", "onboarding": {"completed": False, "step": 3}}
    assert client.put("/me/onboarding", json={"completed": True}, headers=auth).status_code == 200
    assert session(client, token).json() == {"status": "active", "onboarding": {"completed": True, "step": None}}
    assert len(rows(db, User)) == 1 and len(rows(db, Membership)) == 1


def test_two_subjects_get_two_tenants_and_see_only_their_own_state(env):
    client, db = env
    a, b = sign(sub="subject-a"), sign(sub="subject-b")
    session(client, a), session(client, b)
    assert len({m.tenant_id for m in rows(db, Membership)}) == 2
    client.put("/me/onboarding", json={"step": 5}, headers={"Authorization": "Bearer " + a})
    assert session(client, b).json() == NEW
    assert session(client, a).json()["onboarding"] == {"completed": False, "step": 5}


def _assert_unauthenticated(r):
    assert r.status_code == 401 and r.json()["code"] == "unauthenticated"
    assert r.headers["www-authenticate"] == "Bearer"


@pytest.mark.parametrize("make", [
    lambda: "not-a-jwt",
    lambda: sign(sub="s", exp=int(time.time()) - 120, iat=int(time.time()) - 600),
    lambda: sign(sub="s", aud="https://other-api.example.test"),
    lambda: sign(KEY_3, sub="s"),
])
def test_invalid_tokens_are_unauthenticated_and_create_nothing(env, make):
    client, db = env
    _assert_unauthenticated(session(client, make()))
    assert rows(db, User) == []


def test_a_deleted_user_or_one_without_an_active_membership_is_rejected_without_leaks(env, caplog):
    client, db = env
    token = sign(sub="subject-gone")
    assert session(client, token).status_code == 200
    with db._sessions() as s, s.begin():
        s.query(Membership).update({"status": "inactive"})
    with caplog.at_level(logging.DEBUG):
        r = session(client, token)
    _assert_unauthenticated(r)
    messages = [rec.getMessage() for rec in caplog.records]
    assert "session rejected: no_active_membership" in messages
    db.update(Membership, status="active")
    db.update(User, deleted_at=datetime.now(timezone.utc))
    with caplog.at_level(logging.DEBUG):
        _assert_unauthenticated(session(client, token))
    assert len(rows(db, User)) == 1 and len(rows(db, Membership)) == 1  # no second tenant, no re-registration
    # Only changelens.* keeps its text past the production scrubber (logs.py); other loggers are dropped.
    logs = "\n".join(rec.getMessage() for rec in caplog.records if rec.name.startswith("changelens"))
    assert "subject-gone" not in logs and token not in logs and token.split(".")[1] not in logs


@pytest.mark.parametrize("kwargs", [{"json": {"invite_choice": "join"}}, {"json": []}, {"content": b"nope"},
                                    {"json": {"a": None}}])
def test_a_body_other_than_empty_or_an_empty_object_is_invalid(env, kwargs):
    client, db = env
    r = session(client, sign(sub="subject-body"), **kwargs)
    assert r.status_code == 422 and r.json()["code"] == "invalid_request"
    assert "invite_choice" not in r.text and "nope" not in r.text
    assert rows(db, User) == []


def test_an_empty_object_body_is_accepted(env):
    client, _ = env
    assert session(client, sign(sub="subject-empty"), json={}).json() == NEW


def test_guard_still_rejects_a_valid_token_before_the_first_session_call(env):
    client, db = env
    token = sign(sub="subject-not-yet")
    _assert_unauthenticated(client.get("/projects", headers={"Authorization": "Bearer " + token}))
    _assert_unauthenticated(client.get("/me/onboarding", headers={"Authorization": "Bearer " + token}))
    assert rows(db, User) == []  # GUARD never creates an account
