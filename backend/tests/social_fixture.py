"""Fakes for native Google and Apple sign-in (I-8 S4): Google's and Apple's token, revoke and key endpoints,
and Logto's Management API, all behind one `httpx.MockTransport`. Nothing contacts a real provider.

Identities, codes and emails are synthetic. `Fakes.code(...)` registers a single-use code whose exchange
returns an ID token with the given claims; Apple codes also return a refresh token.
"""
from __future__ import annotations

import base64
import hashlib
import json
import secrets
import time
import uuid
from urllib.parse import parse_qs

import httpx
import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import ec, rsa

from changelens.auth.apple_tokens import AppleTokenCipher
from changelens.auth.id_tokens import APPLE_ISSUER, apple_policy, google_policy
from changelens.auth.logto_management import LogtoManagement
from changelens.auth.social import (APPLE_JWKS_URL, GOOGLE_JWKS_URL, AppleClient, GoogleClient, provider_keys)
from changelens.domain.social import AppleTokens

GOOGLE_CLIENT = "google-server-client.apps.example.test"
APPLE_CLIENT = "dev.changelens.app"
LOGTO = "https://auth.example.test"
GOOGLE_CRED = "google-client-secret-synthetic"


def rsa_key(kid):
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    public = json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(private.public_key()))
    public.update(kid=kid, alg="RS256", use="sig")
    return private, public


PROVIDER_KEY, OTHER_KEY = rsa_key("provider-1"), rsa_key("not-published")
APPLE_P8 = ec.generate_private_key(ec.SECP256R1())
APPLE_P8_PEM = APPLE_P8.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8,
                                      serialization.NoEncryption()).decode()


def id_token(provider, sub, email, *, key=PROVIDER_KEY, verified=True, **changes):
    now = int(time.time())
    issuer, audience = ("https://accounts.google.com", GOOGLE_CLIENT) if provider == "google" else (APPLE_ISSUER, APPLE_CLIENT)
    claims = {"iss": issuer, "aud": audience, "sub": sub, "iat": now - 2, "exp": now + 600}
    if email is not None:
        claims.update(email=email, email_verified=(verified if provider == "google" else str(verified).lower()))
    claims.update(changes)
    claims = {k: v for k, v in claims.items() if v is not None}
    return jwt.encode(claims, key[0], algorithm="RS256", headers={"kid": key[1]["kid"]})


def apple_nonce(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


class Fakes:
    """Google, Apple and Logto in one transport. Logto users are dicts like the Management API's."""

    def __init__(self):
        self.codes: dict = {}
        self.used: set = set()
        self.revoked: list = []
        self.issued: list = []  # every Apple refresh token handed out
        self.revoke_status = 200
        self.users: dict = {}
        self.one_time_tokens: list = []
        self.requests: list = []
        self.logto_down = False

    # --- setup ---
    def code(self, provider, sub, email, **token_changes) -> str:
        code = "code-" + secrets.token_hex(8)
        self.codes[code] = (provider, id_token(provider, sub, email, **token_changes))
        return code

    def logto_user(self, email, identities=None) -> str:
        user_id = "lu" + secrets.token_hex(6)
        self.users[user_id] = {"id": user_id, "primaryEmail": email, "identities": dict(identities or {})}
        return user_id

    # --- transport ---
    def handler(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        url = str(request.url)
        if url.startswith(GOOGLE_JWKS_URL) or url.startswith(APPLE_JWKS_URL):
            return httpx.Response(200, json={"keys": [PROVIDER_KEY[1]]})
        if url == "https://oauth2.googleapis.com/token":
            return self._exchange("google", request)
        if url == "https://appleid.apple.com/auth/token":
            return self._exchange("apple", request)
        if url == "https://appleid.apple.com/auth/revoke":
            return self._revoke(request)
        if url.startswith(LOGTO):
            return self._logto(request)
        raise AssertionError("unexpected request to " + request.url.host)

    def _form(self, request):
        return {k: v[0] for k, v in parse_qs(request.content.decode()).items()}

    def _exchange(self, provider, request):
        form = self._form(request)
        if provider == "google":
            assert form["client_id"] == GOOGLE_CLIENT and form["client_secret"] == GOOGLE_CRED
        else:
            secret = jwt.decode(form["client_secret"], APPLE_P8.public_key(), algorithms=["ES256"],
                                audience="https://appleid.apple.com")
            assert secret["sub"] == APPLE_CLIENT and secret["iss"] == "TEAM123456"
        code = form["code"]
        if code not in self.codes or code in self.used or self.codes[code][0] != provider:
            return httpx.Response(400, json={"error": "invalid_grant"})
        self.used.add(code)
        body = {"access_token": "at-" + secrets.token_hex(4), "id_token": self.codes[code][1], "token_type": "Bearer"}
        if provider == "apple":
            body["refresh_token"] = "apple-refresh-" + secrets.token_hex(8)
            self.issued.append(body["refresh_token"])
        return httpx.Response(200, json=body)

    def _revoke(self, request):
        form = self._form(request)
        assert form["token_type_hint"] == "refresh_token" and form["client_id"] == APPLE_CLIENT
        if self.revoke_status != 200:
            return httpx.Response(self.revoke_status)
        self.revoked.append(form["token"])
        return httpx.Response(200)

    def _logto(self, request):
        path = request.url.path
        if path == "/oidc/token":
            return httpx.Response(200, json={"access_token": "mgmt", "expires_in": 3600})
        if self.logto_down:
            return httpx.Response(503)
        assert request.headers["authorization"] == "Bearer mgmt"
        params = dict(request.url.params)
        if request.method == "GET" and path == "/api/users":
            if "identityId" in params:
                found = [u for u in self.users.values()
                         if (u["identities"].get(params["identityProvider"]) or {}).get("userId") == params["identityId"]]
            else:
                assert params["mode.primaryEmail"] == "exact"
                found = [u for u in self.users.values()
                         if (u["primaryEmail"] or "").lower() == params["search.primaryEmail"].lower()]
            return httpx.Response(200, json=found)
        if request.method == "DELETE" and path.startswith("/api/users/"):
            return httpx.Response(204 if self.users.pop(path.rsplit("/", 1)[1], None) else 404)
        if request.method == "GET" and path.startswith("/api/users/"):
            user = self.users.get(path.rsplit("/", 1)[1])
            return httpx.Response(200, json=user) if user else httpx.Response(404)
        if request.method == "POST" and path == "/api/users":
            email = json.loads(request.content)["primaryEmail"]
            if any((u["primaryEmail"] or "").lower() == email.lower() for u in self.users.values()):
                return httpx.Response(422, json={"code": "user.email_already_in_use"})
            return httpx.Response(200, json=self.users[self.logto_user(email)])
        if request.method == "PUT" and "/identities/" in path:
            _, _, _, user_id, _, target = path.split("/")
            body = json.loads(request.content)
            if any((u["identities"].get(target) or {}).get("userId") == body["userId"] and u["id"] != user_id
                   for u in self.users.values()):
                return httpx.Response(422, json={"code": "user.identity_already_in_use"})
            created = target not in self.users[user_id]["identities"]
            self.users[user_id]["identities"][target] = {"userId": body["userId"], "details": body["details"]}
            return httpx.Response(201 if created else 200, json=self.users[user_id]["identities"])
        if request.method == "POST" and path == "/api/one-time-tokens":
            body = json.loads(request.content)
            assert body["context"] == {"interactionEvent": "SignIn"} and 0 < body["expiresIn"] <= 600
            token = "ott-" + secrets.token_hex(8)
            self.one_time_tokens.append((body["email"], token))
            return httpx.Response(201, json={"id": "t1", "email": body["email"], "token": token, "status": "active"})
        raise AssertionError("unexpected Logto call %s %s" % (request.method, path))

    # --- clients ---
    def client(self) -> httpx.Client:
        return httpx.Client(transport=httpx.MockTransport(self.handler))

    def logto(self) -> LogtoManagement:
        return LogtoManagement(LOGTO, "m2m-app", "m2m-secret-synthetic", client=self.client())

    def google(self) -> GoogleClient:
        return GoogleClient(GOOGLE_CLIENT, GOOGLE_CRED,
                            provider_keys(google_policy(GOOGLE_CLIENT), GOOGLE_JWKS_URL, self.client()),
                            client=self.client())

    def apple(self) -> AppleClient:
        return AppleClient(APPLE_CLIENT, "TEAM123456", "KEY1234567", APPLE_P8_PEM,
                           provider_keys(apple_policy(APPLE_CLIENT), APPLE_JWKS_URL, self.client()),
                           client=self.client())

    def providers(self) -> dict:
        return {"google": self.google(), "apple": self.apple()}


def cipher() -> AppleTokenCipher:
    return AppleTokenCipher({"k1": b"\x01" * 32}, "k1")


def apple_tokens(fakes: Fakes) -> AppleTokens:
    return AppleTokens(cipher(), fakes.apple())


def keyring_json() -> str:
    return json.dumps({"active": "k1", "keys": {"k1": base64.urlsafe_b64encode(b"\x01" * 32).decode()}})


def new_park_id() -> uuid.UUID:
    return uuid.uuid4()
