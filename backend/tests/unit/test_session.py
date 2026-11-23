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
from changelens.auth.logto_management import IdpUnavailable
from changelens.domain.models import Membership, User
from changelens.storage import MemoryObjectStore
from demo_fixture import fresh
from test_guard_logto import AUDIENCE, ISSUER, JWKS_URL, KEY_1, KEY_3, GuardDb, Jwks, logto_settings, sign

UNANSWERED = {"usage_events": None}
DEMO = fresh()  # the demo state of an account that has done nothing (tests/unit/test_demo.py covers the rest)
NEW = {"status": "active", "onboarding": {"completed": False, "step": None}, "consent": UNANSWERED, "demo": DEMO}


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
    assert session(client, token).json() == {"status": "active", "onboarding": {"completed": False, "step": 3},
                                             "consent": UNANSWERED, "demo": DEMO}
    assert client.put("/me/onboarding", json={"completed": True}, headers=auth).status_code == 200
    assert session(client, token).json() == {"status": "active", "onboarding": {"completed": True, "step": None},
                                             "consent": UNANSWERED, "demo": DEMO}
    assert len(rows(db, User)) == 1 and len(rows(db, Membership)) == 1


def test_two_subjects_get_two_tenants_and_see_only_their_own_state(env):
    client, db = env
    a, b = sign(sub="subject-a"), sign(sub="subject-b")
    session(client, a), session(client, b)
    assert len({m.tenant_id for m in rows(db, Membership)}) == 2
    client.put("/me/onboarding", json={"step": 5}, headers={"Authorization": "Bearer " + a})
    assert session(client, b).json() == NEW
    assert session(client, a).json()["onboarding"] == {"completed": False, "step": 5}


def test_the_session_carries_the_usage_events_answer_for_the_current_policy(env):
    client, _ = env
    token = sign(sub="consent-subject")
    auth = {"Authorization": "Bearer " + token}
    assert session(client, token).json()["consent"] == UNANSWERED
    for granted in (True, False):
        body = {"usage_events": {"granted": granted, "policy_version": "2026-11-13"}}
        assert client.put("/me/consent", json=body, headers=auth).status_code == 200
        assert session(client, token).json()["consent"] == {"usage_events": granted}


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


class KnownUsers:
    """The part of the Logto client the first sign-in uses: whether Logto still has the user."""

    def __init__(self, *subjects, down=False):
        self.known, self.down, self.asked = set(subjects), down, []

    def user(self, subject):
        self.asked.append(subject)
        if self.down:
            raise IdpUnavailable("unreachable:ConnectError")
        return {"id": subject} if subject in self.known else None


def env_with(idp):
    db = GuardDb()
    keys = JwksKeyHolder(JwtPolicy(ISSUER, AUDIENCE), JWKS_URL,
                         client=httpx.Client(transport=httpx.MockTransport(Jwks(KEY_1).handler)))
    return TestClient(create_app(logto_settings(), db, MemoryObjectStore(), keys=keys, idp=idp),
                      raise_server_exceptions=False), db


def test_a_first_sign_in_asks_logto_once_and_a_returning_user_never():
    idp = KnownUsers("subject-1")
    client, db = env_with(idp)
    token = sign(sub="subject-1")
    assert session(client, token).status_code == 200 and session(client, token).status_code == 200
    assert idp.asked == ["subject-1"] and len(rows(db, User)) == 1


def test_a_token_from_before_the_account_was_deleted_creates_nothing():
    """LR-3: deletion clears the subject, and the token stays valid for up to 15 minutes."""
    idp = KnownUsers("subject-1")
    client, db = env_with(idp)
    token = sign(sub="subject-1")
    assert session(client, token).status_code == 200
    # A completed DELETE /me: the Logto user is gone and the row is a tombstone without the subject.
    idp.known.clear()
    db.update(Membership, status="inactive")
    db.update(User, idp_subject=None, deleted_at=datetime.now(timezone.utc))
    for _ in range(2):
        _assert_unauthenticated(session(client, token))
    [tombstone] = rows(db, User)
    assert tombstone.idp_subject is None and len(rows(db, Membership)) == 1  # no new user, no new tenant


def test_a_subject_logto_does_not_know_gets_no_account_and_keeps_its_sign_up_allowance():
    client, db = env_with(KnownUsers("someone-else"))
    for _ in range(8):  # more than the 5 sign-ups an IP may make in a day
        _assert_unauthenticated(session(client, sign(sub="never-existed")))
    assert rows(db, User) == []
    assert session(client, sign(sub="someone-else")).status_code == 200


def test_when_logto_cannot_be_asked_nothing_is_created_and_the_app_may_retry():
    client, db = env_with(KnownUsers("subject-1", down=True))
    r = session(client, sign(sub="subject-1"))
    assert r.status_code == 503 and r.json()["code"] == "provider_unavailable" and r.headers["retry-after"] == "30"
    assert rows(db, User) == []


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
