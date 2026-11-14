"""GUARD over Logto access tokens (I-8 S1, §8 items 2-4), with no services.

Signing keys are generated in the tests and the JWKS is served through `httpx.MockTransport`; the
user, membership and onboarding tables are in-memory SQLite. Nothing here contacts a real IdP.
"""
from contextlib import contextmanager
from datetime import datetime, timezone
import base64
import json
import logging
import time
import uuid

from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi import Depends
from fastapi.testclient import TestClient
import httpx
import jwt
import pytest
from sqlalchemy.orm import sessionmaker

from changelens.api.app import create_app
from changelens.api.auth import current_principal
from changelens.auth.jwks import JwksKeyHolder, JwksUnavailable
from changelens.auth.jwt_verifier import JwtPolicy
from changelens.config import Settings
from changelens.domain import TenantRepo
from changelens.domain.models import AccountOnboarding, Membership, User
from changelens.storage import MemoryObjectStore
from identity_fixture import SqliteIdentity, sqlite_engine

ISSUER = "https://auth.example.test/oidc"
AUDIENCE = "https://api.example.test"
JWKS_URL = "https://auth.example.test/oidc/jwks"
SUBJECT = "logto-subject-0001"
TENANT = uuid.uuid4()


def new_key(kid):
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key()))
    public.update(kid=kid, alg="RS256", use="sig")
    return private, public


KEY_1, KEY_2, KEY_3 = new_key("key-1"), new_key("key-2"), new_key("key-3")


def claims(**changes):
    now = int(time.time())
    return {"iss": ISSUER, "aud": AUDIENCE, "sub": SUBJECT, "iat": now - 5, "exp": now + 600, **changes}


def sign(key=KEY_1, headers=None, **changes):
    return jwt.encode(claims(**changes), key[0], algorithm="RS256", headers={"kid": key[1]["kid"], **(headers or {})})


class Clock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


class Jwks:
    """The IdP's JWKS endpoint: serves `keys`, records every request, can be made to fail."""

    def __init__(self, *keys):
        self.keys, self.requests, self.fail = list(keys), [], False

    def handler(self, request):
        self.requests.append(str(request.url))
        if self.fail:
            return httpx.Response(503)
        return httpx.Response(200, json={"keys": [k[1] for k in self.keys]})


class GuardDb:
    """Users, memberships and onboarding in one SQLite database; the real repositories."""

    def __init__(self):
        self.engine = sqlite_engine()
        self.identity = SqliteIdentity(self.engine)
        self.identity_scope = self.identity.identity_scope
        AccountOnboarding.__table__.create(self.engine)
        self._sessions = sessionmaker(self.engine, expire_on_commit=False)

    @contextmanager
    def tenant_scope(self, tenant_id):
        with self._sessions() as s, s.begin():
            yield TenantRepo(s, tenant_id)

    def update(self, model, **values):
        with self._sessions() as s, s.begin():
            for row in s.query(model).all():
                for name, value in values.items():
                    setattr(row, name, value)


def logto_settings(**overrides):
    base = dict(database_url="unused", s3_endpoint="unused", s3_access_key="x", s3_secret_key="x", s3_bucket="x",
                auth_mode="logto", logto_issuer=ISSUER, logto_audience=AUDIENCE, logto_jwks_url=JWKS_URL)
    base.update(overrides)
    return Settings(**base)


@pytest.fixture()
def env():
    jwks, clock, db = Jwks(KEY_1), Clock(), GuardDb()
    db.identity.seed(SUBJECT, TENANT)
    keys = JwksKeyHolder(JwtPolicy(ISSUER, AUDIENCE), JWKS_URL,
                         client=httpx.Client(transport=httpx.MockTransport(jwks.handler)), clock=clock)
    app = create_app(logto_settings(), db, MemoryObjectStore(), keys=keys)

    @app.get("/test/principal")
    def principal(p=Depends(current_principal)):
        return {"user_id": str(p.user_id), "tenant_id": str(p.tenant_id), "role": p.role}

    client = TestClient(app, raise_server_exceptions=False)
    return client, jwks, clock, keys, db


def call(client, token, path="/me/onboarding"):
    return client.get(path, headers={"Authorization": "Bearer " + token})


def assert_unauthenticated(r):
    assert r.status_code == 401, r.text
    assert r.headers["www-authenticate"] == "Bearer"
    assert r.json() == {"type": "urn:changelens:problem:unauthenticated", "title": "Authentication required",
                        "status": 401, "code": "unauthenticated"}


def test_a_valid_token_for_a_seeded_user_reaches_the_route_with_the_membership_tenant(env):
    client, jwks, _, _, db = env
    assert call(client, sign()).status_code == 200
    r = call(client, sign(), "/test/principal")
    assert r.json() == {"user_id": str(db.identity.user(SUBJECT).id), "tenant_id": str(TENANT), "role": "owner"}
    assert jwks.requests == [JWKS_URL]  # the startup fetch only


def _alg_none():
    def part(data):
        return base64.urlsafe_b64encode(json.dumps(data).encode()).rstrip(b"=").decode()
    return part({"alg": "none", "typ": "JWT", "kid": "key-1"}) + "." + part(claims()) + "."


@pytest.mark.parametrize("make", [
    lambda: sign(exp=int(time.time()) - 120, iat=int(time.time()) - 600),  # expired
    lambda: sign(iss="https://other.example.test/oidc"),  # wrong issuer
    lambda: sign(aud="https://other-api.example.test"),  # wrong audience
    _alg_none,
    lambda: sign(headers={"jku": "https://attacker.example.test/jwks"}),
    lambda: "not-a-jwt",
    lambda: "a.b.c",
    lambda: sign(KEY_3),  # signed by a key the IdP never published (kid also unknown)
    lambda: sign(KEY_3, headers={"kid": "key-1"}),  # known kid, wrong signature
])
def test_rejected_tokens_are_unauthenticated(env, make):
    client, jwks, _, _, _ = env
    assert_unauthenticated(call(client, make()))
    assert all(url == JWKS_URL for url in jwks.requests)  # never a URL from a token header


def test_an_unknown_kid_refreshes_once_then_succeeds_and_a_second_within_60s_does_not_refetch(env):
    client, jwks, clock, keys, _ = env
    jwks.keys.append(KEY_2)  # the IdP rotates in a new key after our startup fetch
    assert call(client, sign(KEY_2)).status_code == 200
    assert len(jwks.requests) == 2
    assert call(client, sign(KEY_2)).status_code == 200  # cached now
    jwks.keys.append(KEY_3)
    clock.now += 59
    assert_unauthenticated(call(client, sign(KEY_3)))  # unknown kid within 60 s: no refetch
    assert len(jwks.requests) == 2 and keys.fetches == 2
    clock.now += 1
    assert call(client, sign(KEY_3)).status_code == 200  # the window has passed: one refetch
    assert len(jwks.requests) == 3


def test_a_failed_refresh_keeps_the_cached_keys(env):
    client, jwks, clock, _, _ = env
    jwks.fail = True
    assert_unauthenticated(call(client, sign(KEY_2)))
    assert len(jwks.requests) == 2
    assert call(client, sign()).status_code == 200  # key-1 still cached


def test_the_api_refuses_to_start_when_the_first_jwks_fetch_fails(caplog):
    jwks = Jwks(KEY_1)
    jwks.fail = True
    keys = JwksKeyHolder(JwtPolicy(ISSUER, AUDIENCE), JWKS_URL,
                         client=httpx.Client(transport=httpx.MockTransport(jwks.handler)))
    with caplog.at_level(logging.WARNING, logger="changelens"), pytest.raises(JwksUnavailable):
        create_app(logto_settings(), GuardDb(), MemoryObjectStore(), keys=keys)
    assert [r.getMessage() for r in caplog.records] == ["jwks fetch failed: ValueError"]


@pytest.mark.parametrize("response", [
    httpx.Response(200, content=b"x" * (64 * 1024 + 1)),
    httpx.Response(200, content=b"{not json"),
    httpx.Response(200, json={"keys": [{"kty": "oct", "kid": "k", "alg": "HS256", "k": "c2VjcmV0"}]}),
    httpx.Response(302, headers={"location": "https://elsewhere.example.test/jwks"}),
])
def test_oversized_malformed_symmetric_or_redirected_jwks_is_refused(response):
    keys = JwksKeyHolder(JwtPolicy(ISSUER, AUDIENCE), JWKS_URL,
                         client=httpx.Client(transport=httpx.MockTransport(lambda request: response)))
    with pytest.raises(JwksUnavailable):
        keys.load()


@pytest.mark.parametrize("break_identity", [
    lambda db: db.update(User, idp_subject="someone-else"),  # no user for the subject
    lambda db: db.update(User, deleted_at=datetime.now(timezone.utc)),  # deleted user, valid token
    lambda db: db.update(Membership, status="inactive"),
    lambda db: db.update(Membership, tenant_id=uuid.uuid4(), status="inactive"),
], ids=["no-user", "deleted-user", "inactive-membership", "no-active-membership"])
def test_guard_rejects_every_identity_failure_alike_and_never_echoes_token_or_subject(env, caplog, break_identity):
    client, _, _, _, db = env
    token = sign()
    assert call(client, token).status_code == 200
    break_identity(db)
    with caplog.at_level(logging.DEBUG):
        r = call(client, token)
    assert_unauthenticated(r)
    text = r.text + json.dumps(dict(r.headers))
    # Only changelens.* keeps its text past the production scrubber (logs.py); other loggers are dropped.
    logs = "\n".join(rec.getMessage() for rec in caplog.records if rec.name.startswith("changelens"))
    for secret in (token, SUBJECT, token.split(".")[1]):
        assert secret not in text and secret not in logs


def test_guard_rejects_a_user_with_no_membership_row(env):
    client, _, _, _, db = env
    with db._sessions() as s, s.begin():
        s.query(Membership).delete()
    assert_unauthenticated(call(client, sign()))


def test_a_dev_token_is_not_accepted_in_logto_mode(env):
    client, _, _, _, _ = env
    assert_unauthenticated(call(client, "dev-token-tenant-a-0123456789"))
    with pytest.raises(ValueError):
        logto_settings(dev_tokens={"dev-token-tenant-a-0123456789": "dev:tenant-a"})


def test_a_dev_token_whose_subject_has_no_user_is_unauthenticated():
    db = GuardDb()
    settings = Settings(database_url="unused", s3_endpoint="unused", s3_access_key="x", s3_secret_key="x",
                        s3_bucket="x", dev_tokens={"dev-token-unseeded-0123456789": "dev:unseeded"})
    client = TestClient(create_app(settings, db, MemoryObjectStore()), raise_server_exceptions=False)
    assert_unauthenticated(call(client, "dev-token-unseeded-0123456789"))
    db.identity.seed("dev:unseeded", TENANT)
    assert call(client, "dev-token-unseeded-0123456789").status_code == 200


ENV = {"CHANGELENS_ENV": None, "CHANGELENS_AUTH_MODE": None, "CHANGELENS_DEV_TOKEN": None,
       "CHANGELENS_LOGTO_ISSUER": None, "CHANGELENS_LOGTO_AUDIENCE": None, "CHANGELENS_LOGTO_JWKS_URL": None}
LOGTO = {"CHANGELENS_AUTH_MODE": "logto", "CHANGELENS_LOGTO_ISSUER": ISSUER, "CHANGELENS_LOGTO_AUDIENCE": AUDIENCE,
         "CHANGELENS_LOGTO_JWKS_URL": JWKS_URL, "CHANGELENS_LOGTO_MANAGEMENT_ENDPOINT": "https://auth.example.test",
         "CHANGELENS_LOGTO_M2M_APP_ID": "m2m-app", "CHANGELENS_LOGTO_M2M_APP_SECRET": "m2m-secret-0123456789"}


def _env(monkeypatch, values):
    for name, value in {**ENV, **values}.items():
        if value is None:
            monkeypatch.delenv(name, raising=False)
        else:
            monkeypatch.setenv(name, value)


@pytest.mark.parametrize("values", [
    {"CHANGELENS_DEV_TOKEN": "local-dev-token-0123456789"},  # dev is the default mode, but not deployed
    {"CHANGELENS_AUTH_MODE": "dev", "CHANGELENS_ENV": "production", "CHANGELENS_DEV_TOKEN": "local-dev-token-0123456789"},
    {"CHANGELENS_AUTH_MODE": "dev", "CHANGELENS_ENV": "local", "CHANGELENS_DEV_TOKEN": "short"},
    {**LOGTO, "CHANGELENS_LOGTO_JWKS_URL": "http://auth.example.test/oidc/jwks"},
    {**LOGTO, "CHANGELENS_LOGTO_JWKS_URL": "https://user@auth.example.test/oidc/jwks"},
    {**LOGTO, "CHANGELENS_LOGTO_ISSUER": None},
    {**LOGTO, "CHANGELENS_LOGTO_AUDIENCE": None},
    {**LOGTO, "CHANGELENS_DEV_TOKEN": "local-dev-token-0123456789"},
    {"CHANGELENS_AUTH_MODE": "oauth"},
])
def test_unsafe_auth_settings_fail_at_startup(monkeypatch, values):
    _env(monkeypatch, values)
    with pytest.raises(RuntimeError):
        Settings.from_env()


def test_local_dev_and_complete_logto_settings_load(monkeypatch):
    _env(monkeypatch, {"CHANGELENS_ENV": "local", "CHANGELENS_DEV_TOKEN": "local-dev-token-0123456789"})
    dev = Settings.from_env()
    assert dev.auth_mode == "dev" and dev.dev_tokens == {"local-dev-token-0123456789": "dev:default"}
    assert "local-dev-token" not in repr(dev)
    _env(monkeypatch, LOGTO)
    logto = Settings.from_env()
    assert (logto.auth_mode, logto.logto_jwks_url, logto.dev_tokens) == ("logto", JWKS_URL, {})
