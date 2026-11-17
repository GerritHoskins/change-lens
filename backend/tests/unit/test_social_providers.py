"""Native Google and Apple sign-in, provider side (I-8 S4 §6 item 1), with no services: the code exchange,
ID-token checks, Apple revocation, the Logto Management calls and the configuration. Every provider and
Logto endpoint is a `httpx.MockTransport` fake (tests/social_fixture.py)."""
import json
import time

import httpx
import jwt
import pytest

from changelens.auth.logto_management import IdentityInUse, IdpUnavailable, LogtoManagement, sign_in_methods
from changelens.auth.social import (AppleRevokeFailed, ProviderRejected, ProviderUnavailable, providers_for,
                                    token_cipher_from_file)
from changelens.config import Settings
from social_fixture import APPLE_CLIENT, OTHER_KEY, Fakes, apple_nonce, keyring_json

EMAIL = "person@example.test"


@pytest.fixture()
def fakes():
    return Fakes()


def test_a_valid_google_code_yields_the_verified_identity_once(fakes):
    code = fakes.code("google", "g-sub-1", EMAIL)
    exchange = fakes.google().exchange(code)
    assert (exchange.identity.provider, exchange.identity.subject, exchange.identity.email) == ("google", "g-sub-1", EMAIL)
    assert exchange.refresh_token is None
    with pytest.raises(ProviderRejected):  # the same code twice: the provider refuses it
        fakes.google().exchange(code)


def test_a_valid_apple_code_yields_the_identity_and_a_refresh_token(fakes):
    code = fakes.code("apple", "a-sub-1", EMAIL, nonce=apple_nonce("raw-nonce-123"))
    exchange = fakes.apple().exchange(code, "raw-nonce-123")
    assert exchange.identity.subject == "a-sub-1" and exchange.refresh_token.startswith("apple-refresh-")
    assert "a-sub-1" not in repr(exchange) and EMAIL not in repr(exchange) and "apple-refresh" not in repr(exchange)
    with pytest.raises(ProviderRejected):  # a reused Apple code
        fakes.apple().exchange(code, "raw-nonce-123")


@pytest.mark.parametrize("provider,changes", [
    ("google", {"key": OTHER_KEY}),                               # signed by a key Google doesn't publish
    ("google", {"aud": "someone-elses-client"}),
    ("google", {"iss": "https://evil.example.test"}),
    ("google", {"exp": int(time.time()) - 120, "iat": int(time.time()) - 700}),
    ("google", {"iat": int(time.time()) - 3000}),                 # not from a fresh exchange
    ("apple", {"aud": "dev.other.app"}),
    ("apple", {"iss": "https://accounts.google.com"}),
    ("apple", {"exp": int(time.time()) - 120}),
])
def test_bad_id_tokens_are_rejected(fakes, provider, changes):
    code = fakes.code(provider, "sub-x", EMAIL, **changes)
    with pytest.raises(ProviderRejected):
        getattr(fakes, provider)().exchange(code)


@pytest.mark.parametrize("provider", ["google", "apple"])
@pytest.mark.parametrize("email,verified", [(None, True), (EMAIL, False)])
def test_a_missing_or_unverified_email_is_rejected(fakes, provider, email, verified):
    code = fakes.code(provider, "sub-y", email, verified=verified)
    with pytest.raises(ProviderRejected):
        getattr(fakes, provider)().exchange(code)


def test_apple_nonces_must_match_on_both_sides(fakes):
    for token_nonce, sent in ((apple_nonce("raw-nonce-123"), "other-nonce-456"), (apple_nonce("raw-nonce-123"), None),
                              (None, "raw-nonce-123"), ("raw-nonce-123", "raw-nonce-123")):  # the last: not hashed
        code = fakes.code("apple", "a-sub-2", EMAIL, nonce=token_nonce)
        with pytest.raises(ProviderRejected):
            fakes.apple().exchange(code, sent)


@pytest.mark.parametrize("code", ["", "has space", "x" * 2049, None, 7])
def test_malformed_codes_never_reach_the_provider(fakes, code):
    with pytest.raises(ProviderRejected):
        fakes.google().exchange(code)
    assert fakes.requests == []


def test_provider_and_key_outages_are_unavailable_not_rejections(fakes):
    code = fakes.code("google", "g-sub-3", EMAIL)
    down = Fakes()
    down.handler = lambda request: httpx.Response(503)
    google = fakes.google()
    google._client = down.client()
    with pytest.raises(ProviderUnavailable):
        google.exchange(code)
    google = fakes.google()
    google._keys._client = down.client()  # Google's keys can't be fetched
    with pytest.raises(ProviderUnavailable):
        google.exchange(code)


def test_the_apple_client_secret_is_a_short_lived_es256_jwt(fakes):
    secret = fakes.apple()._client_secret()
    header = jwt.get_unverified_header(secret)
    claims = jwt.decode(secret, options={"verify_signature": False})
    assert header["alg"] == "ES256" and header["kid"] == "KEY1234567"
    assert claims["sub"] == APPLE_CLIENT and claims["aud"] == "https://appleid.apple.com"
    assert 0 < claims["exp"] - claims["iat"] <= 300


def test_apple_revocation_confirms_on_200_and_invalid_grant_and_raises_otherwise(fakes):
    apple = fakes.apple()
    apple.revoke("apple-refresh-1")
    assert fakes.revoked == ["apple-refresh-1"]
    fakes.revoke_status = 500
    with pytest.raises(AppleRevokeFailed) as error:
        apple.revoke("apple-refresh-2")
    assert "apple-refresh-2" not in str(error.value)
    gone = Fakes()
    gone.handler = lambda request: httpx.Response(400, json={"error": "invalid_grant"})
    apple._client = gone.client()
    apple.revoke("apple-refresh-3")  # already invalid: done


# Logto Management API ------------------------------------------------------------------------------
def test_logto_lookups_link_and_one_time_token(fakes):
    logto = fakes.logto()
    user_id = fakes.logto_user(EMAIL)
    assert logto.user_by_identity("apple", "a-sub-9") is None
    assert logto.user_by_email("PERSON@example.test")["id"] == user_id  # case-insensitive, exact
    logto.link_identity(user_id, "apple", "a-sub-9")
    assert logto.user_by_identity("apple", "a-sub-9")["id"] == user_id
    assert sign_in_methods(logto.user(user_id)) == ["email", "apple"]
    other = fakes.logto_user("other@example.test")
    with pytest.raises(IdentityInUse):
        logto.link_identity(other, "apple", "a-sub-9")  # never moves an identity between users
    with pytest.raises(IdentityInUse):
        logto.create_user(EMAIL)
    token = logto.one_time_token(EMAIL, 120)
    assert fakes.one_time_tokens == [(EMAIL, token)]
    identity_query = [r for r in fakes.requests if "identityId" in r.url.params][0].url.params
    assert dict(identity_query)["identityType"] == "social"


def test_logto_failures_carry_codes_only(fakes):
    fakes.logto_down = True
    with pytest.raises(IdpUnavailable) as error:
        fakes.logto().user_by_email(EMAIL)
    assert str(error.value) == "status_503"
    with pytest.raises(ValueError):
        fakes.logto().user_by_identity("facebook", "x")


def test_a_search_that_returns_another_email_is_refused(fakes):
    logto = fakes.logto()
    fakes.logto_user("someone.else@example.test")
    fakes.handler, original = (lambda request: httpx.Response(200, json=list(fakes.users.values()))
                               if request.url.path == "/api/users" else original(request)), fakes.handler
    logto._client = fakes.client()
    with pytest.raises(IdpUnavailable):
        logto.user_by_email(EMAIL)


# Configuration --------------------------------------------------------------------------------------
def _settings(**changes):
    base = dict(database_url="unused", s3_endpoint="unused", s3_access_key="x", s3_secret_key="x", s3_bucket="x",
                auth_mode="logto", logto_issuer="https://auth.example.test/oidc", logto_audience="https://api.example.test",
                logto_jwks_url="https://auth.example.test/oidc/jwks")
    base.update(changes)
    return Settings(**base)


def test_social_settings_must_be_complete_and_need_logto_mode(tmp_path):
    with pytest.raises(ValueError):
        _settings(google_client_id="g")
    with pytest.raises(ValueError):
        _settings(apple_client_id=APPLE_CLIENT, apple_team_id="T", apple_key_id="K")
    with pytest.raises(ValueError):
        Settings(database_url="u", s3_endpoint="u", s3_access_key="x", s3_secret_key="x", s3_bucket="x",
                 google_client_id="g", google_client_secret_file="f")
    assert providers_for(_settings()) == {}


def test_providers_and_keyring_load_from_secret_files(tmp_path):
    from social_fixture import APPLE_P8_PEM
    (tmp_path / "google").write_text("google-secret\n")
    (tmp_path / "p8").write_text(APPLE_P8_PEM)
    (tmp_path / "keys").write_text(keyring_json())
    settings = _settings(google_client_id="g", google_client_secret_file=str(tmp_path / "google"),
                         apple_client_id=APPLE_CLIENT, apple_team_id="T", apple_key_id="K",
                         apple_private_key_file=str(tmp_path / "p8"), apple_token_keys_file=str(tmp_path / "keys"))
    providers = providers_for(settings)
    assert set(providers) == {"google", "apple"} and "google-secret" not in repr(providers)
    cipher = token_cipher_from_file(str(tmp_path / "keys"))
    assert cipher.decrypt(cipher.encrypt("t", issuer="i", subject="s", binding="b"), issuer="i", subject="s",
                          binding="b") == "t"
    (tmp_path / "keys").write_text(json.dumps({"active": "k1", "keys": {"k1": "c2hvcnQ"}}))
    with pytest.raises(RuntimeError) as error:
        token_cipher_from_file(str(tmp_path / "keys"))
    assert str(tmp_path) not in str(error.value)
    with pytest.raises(RuntimeError):
        token_cipher_from_file(str(tmp_path / "missing"))


def test_social_settings_come_from_the_environment(monkeypatch):
    env = {"CHANGELENS_AUTH_MODE": "logto", "CHANGELENS_LOGTO_ISSUER": "https://auth.example.test/oidc",
           "CHANGELENS_LOGTO_AUDIENCE": "https://api.example.test",
           "CHANGELENS_LOGTO_JWKS_URL": "https://auth.example.test/oidc/jwks",
           "CHANGELENS_LOGTO_MANAGEMENT_ENDPOINT": "https://auth.example.test", "CHANGELENS_LOGTO_M2M_APP_ID": "a",
           "CHANGELENS_LOGTO_M2M_APP_SECRET": "s", "CHANGELENS_RATE_LIMIT_KEY": "k" * 40,
           "CHANGELENS_DATABASE_URL": "postgresql+psycopg://changelens_app:pw@postgres:5432/changelens",
           "CHANGELENS_S3_ENDPOINT": "https://s3.example.test", "CHANGELENS_S3_ACCESS_KEY": "a",
           "CHANGELENS_S3_SECRET_KEY": "s", "CHANGELENS_S3_BUCKET": "b", "CHANGELENS_LLM": "ionos",
           "CHANGELENS_GOOGLE_CLIENT_ID": "g", "CHANGELENS_GOOGLE_CLIENT_SECRET_FILE": "/run/secrets/google"}
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    settings = Settings.from_env()
    assert settings.google_client_id == "g" and settings.google_client_secret_file == "/run/secrets/google"
    assert settings.apple_client_id is None
