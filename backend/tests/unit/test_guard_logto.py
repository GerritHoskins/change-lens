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
from changelens.config import NOT_FOR_THE_WORKER, Settings
from changelens.domain import TenantRepo
from changelens.domain.models import AccountOnboarding, ConsentEvent, Membership, User
from changelens.storage import MemoryObjectStore
from helpers import EARLY_BIRD_ENV
from demo_fixture import create_demo_tables
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
    """Users, memberships, onboarding and consent in one SQLite database; the real repositories."""

    def __init__(self):
        self.engine = sqlite_engine()
        self.identity = SqliteIdentity(self.engine)
        self.identity_scope = self.identity.identity_scope
        AccountOnboarding.__table__.create(self.engine)
        ConsentEvent.__table__.create(self.engine)
        create_demo_tables(self.engine)  # `POST /session` carries the demo state
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


# A deployment's own database, object storage and model: none of them has a default in logto mode.
DEPLOYED = {"CHANGELENS_DATABASE_URL": "postgresql+psycopg://changelens_app:app-password@postgres:5432/changelens",
            "CHANGELENS_S3_ENDPOINT": "https://s3.example.test", "CHANGELENS_S3_ACCESS_KEY": "access-key-0123",
            "CHANGELENS_S3_SECRET_KEY": "secret-key-0123456789", "CHANGELENS_S3_BUCKET": "originals-bucket",
            "CHANGELENS_LLM": "ionos"}
ENV = {"CHANGELENS_ENV": None, "CHANGELENS_AUTH_MODE": None, "CHANGELENS_DEV_TOKEN": None,
       "CHANGELENS_LOGTO_ISSUER": None, "CHANGELENS_LOGTO_AUDIENCE": None, "CHANGELENS_LOGTO_JWKS_URL": None,
       **dict.fromkeys(DEPLOYED), **dict.fromkeys(EARLY_BIRD_ENV), "CHANGELENS_SMTP_PORT": None}
LOGTO = {"CHANGELENS_AUTH_MODE": "logto", "CHANGELENS_LOGTO_ISSUER": ISSUER, "CHANGELENS_LOGTO_AUDIENCE": AUDIENCE,
         "CHANGELENS_LOGTO_JWKS_URL": JWKS_URL, "CHANGELENS_LOGTO_MANAGEMENT_ENDPOINT": "https://auth.example.test",
         "CHANGELENS_LOGTO_M2M_APP_ID": "m2m-app", "CHANGELENS_LOGTO_M2M_APP_SECRET": "m2m-secret-0123456789",
         "CHANGELENS_RATE_LIMIT_KEY": "rate-limit-key-for-tests-0123456789", **DEPLOYED, **EARLY_BIRD_ENV}


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
    # Local development keeps its defaults: the compose database and MinIO, and the fake model.
    assert (dev.llm_provider, dev.s3_bucket, dev.s3_endpoint) == ("fake", "changelens-dev", "http://127.0.0.1:59000")
    _env(monkeypatch, LOGTO)
    logto = Settings.from_env()
    assert (logto.auth_mode, logto.logto_jwks_url, logto.dev_tokens) == ("logto", JWKS_URL, {})
    assert (logto.llm_provider, logto.s3_bucket, logto.s3_endpoint, logto.database_url) == (
        "ionos", "originals-bucket", "https://s3.example.test", DEPLOYED["CHANGELENS_DATABASE_URL"])


@pytest.mark.parametrize("value", [None, "   "])
@pytest.mark.parametrize("name", sorted(DEPLOYED))
def test_a_deployment_without_its_own_database_storage_or_model_does_not_start(monkeypatch, name, value):
    """A missing setting must stop the process, never fall back to a local development default."""
    _env(monkeypatch, {**LOGTO, name: value})
    with pytest.raises(RuntimeError) as raised:
        Settings.from_env()
    message = str(raised.value)
    assert name in message
    assert not any(secret in message for secret in DEPLOYED.values())  # names only, never a value


def test_a_deployment_refuses_the_fake_model(monkeypatch):
    _env(monkeypatch, {**LOGTO, "CHANGELENS_LLM": "fake"})
    with pytest.raises(RuntimeError, match="CHANGELENS_LLM"):
        Settings.from_env()


# The worker's own env file (LR-4): database, storage and model, and nothing about sign-in.
WORKER = {"CHANGELENS_AUTH_MODE": "logto", **DEPLOYED, **dict.fromkeys(NOT_FOR_THE_WORKER)}


def test_a_deployed_worker_starts_without_any_sign_in_setting(monkeypatch):
    _env(monkeypatch, WORKER)
    worker = Settings.from_env(worker=True)
    assert (worker.auth_mode, worker.llm_provider, worker.s3_bucket) == ("logto", "ionos", "originals-bucket")
    assert (worker.logto_m2m_app_id, worker.logto_m2m_app_secret, worker.logto_management_endpoint) == (None,) * 3
    with pytest.raises(RuntimeError):  # the same file starts no api: that one needs the sign-in settings
        Settings.from_env()


@pytest.mark.parametrize("name", NOT_FOR_THE_WORKER)
def test_a_worker_given_a_credential_it_must_not_hold_does_not_start(monkeypatch, name):
    _env(monkeypatch, {**WORKER, name: LOGTO[name]})
    with pytest.raises(RuntimeError) as raised:
        Settings.from_env(worker=True)
    assert name in str(raised.value) and LOGTO[name] not in str(raised.value)  # the name, never the value
    with pytest.raises(ValueError):
        Settings(database_url="unused", s3_endpoint="unused", s3_access_key="unused", s3_secret_key="unused",
                 s3_bucket="unused", auth_mode="logto", worker=True, logto_m2m_app_id="m2m-app",
                 logto_m2m_app_secret=LOGTO["CHANGELENS_LOGTO_M2M_APP_SECRET"],
                 logto_management_endpoint="https://auth.example.test")


@pytest.mark.parametrize("name", sorted(DEPLOYED))
def test_a_deployed_worker_without_its_own_database_storage_or_model_does_not_start(monkeypatch, name):
    _env(monkeypatch, {**WORKER, name: None})
    with pytest.raises(RuntimeError, match=name):
        Settings.from_env(worker=True)


API_DOCS = ("/docs", "/redoc", "/openapi.json")


def test_a_deployment_serves_no_api_documentation(env):
    """In logto mode the three FastAPI documentation paths answer like any path that doesn't exist."""
    client, _, _, _, _ = env
    unknown = client.get("/no-such-path")
    assert unknown.status_code == 404
    for path in API_DOCS:
        r = client.get(path)
        assert (r.status_code, r.json()) == (unknown.status_code, unknown.json()), path
    assert "dev" not in client.app.title.lower()
    assert client.app.openapi()["paths"]  # the schema still exists in process (test_rls_db reads it)


def test_local_development_keeps_its_api_documentation():
    settings = Settings(database_url="unused", s3_endpoint="unused", s3_access_key="x", s3_secret_key="x",
                        s3_bucket="x", dev_tokens={"dev-token-unseeded-0123456789": "dev:unseeded"})
    client = TestClient(create_app(settings, GuardDb(), MemoryObjectStore()), raise_server_exceptions=False)
    for path in API_DOCS:
        assert client.get(path).status_code == 200, path
