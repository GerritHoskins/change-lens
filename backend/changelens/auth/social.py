"""Native Google and Apple sign-in: the backend's code exchange and Apple revocation (I-8 S4; O-19, ADR-0020).

The app sends the provider's authorization code (Google's server auth code, Apple's authorization code);
only this module redeems it, so each code is exchanged once and Apple's refresh token never leaves the
backend. The returned ID token is verified by `auth.id_tokens`; the email comes only from it.

- Google: `POST https://oauth2.googleapis.com/token` with our server client ID and secret.
- Apple: `POST https://appleid.apple.com/auth/token` with a client secret signed (ES256) with the `.p8`
  key, and `POST /auth/revoke` for account deletion and abandoned parked tokens (AR-1, AR-5, AR-6).

`ProviderRejected` means the code or token is bad (the caller answers 401); `ProviderUnavailable` means
the provider or our configuration failed (503, nothing stored). Errors carry event codes only: never a
code, token, subject, email or response body. Secrets come from files named by the environment (03 §6).
"""
from __future__ import annotations

import base64
import binascii
import json
import re
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import httpx
import jwt

from changelens.auth.apple_tokens import AppleTokenCipher
from changelens.auth.id_tokens import (IdTokenRejected, IdTokenVerifier, ProviderIdentity, apple_policy,
                                       google_policy)
from changelens.auth.jwks import JwksKeyHolder
from changelens.auth.jwt_verifier import AccessTokenRejected

PROVIDERS = ("google", "apple")
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_JWKS_URL = "https://www.googleapis.com/oauth2/v3/certs"
APPLE_TOKEN_URL = "https://appleid.apple.com/auth/token"
APPLE_REVOKE_URL = "https://appleid.apple.com/auth/revoke"
APPLE_JWKS_URL = "https://appleid.apple.com/auth/keys"
APPLE_AUDIENCE = "https://appleid.apple.com"
_CODE = re.compile(r"[\x21-\x7e]{1,2048}\Z")  # printable ASCII, no spaces
_NONCE = re.compile(r"[\x21-\x7e]{8,256}\Z")
_MAX_RESPONSE = 64 * 1024


class ProviderRejected(Exception):
    """The code or the returned token is not acceptable: unauthenticated, nothing created."""


class ProviderUnavailable(Exception):
    """The provider, its keys or our configuration failed; the caller may retry later."""


class AppleRevokeFailed(Exception):
    """Apple did not confirm the revocation; the token is kept and retried (AR-6)."""


@dataclass(frozen=True)
class Exchange:
    identity: ProviderIdentity
    refresh_token: Optional[str] = field(default=None, repr=False)  # Apple only


def valid_code(code) -> bool:
    return isinstance(code, str) and bool(_CODE.match(code))


def valid_nonce(nonce) -> bool:
    return isinstance(nonce, str) and bool(_NONCE.match(nonce))


def _post(client: httpx.Client, url: str, data: dict) -> httpx.Response:
    try:
        response = client.post(url, data=data, headers={"Accept": "application/json"})
    except httpx.HTTPError as exc:
        raise ProviderUnavailable("unreachable:" + type(exc).__name__) from None
    if len(response.content) > _MAX_RESPONSE:
        raise ProviderUnavailable("response_too_large")
    return response


def _token_body(response: httpx.Response) -> dict:
    """A 200 body, or the error class: `invalid_grant` (bad, used or expired code) is the caller's fault,
    anything else (bad client credentials, provider errors) is ours or the provider's."""
    if response.status_code == 200:
        try:
            body = response.json()
        except ValueError:
            raise ProviderUnavailable("token_malformed") from None
        if not isinstance(body, dict):
            raise ProviderUnavailable("token_malformed")
        return body
    if response.status_code == 400:
        try:
            error = response.json().get("error")
        except (ValueError, AttributeError):
            error = None
        if error == "invalid_grant":
            raise ProviderRejected("invalid_grant")
    raise ProviderUnavailable("token_status_%d" % response.status_code)


def _identity(keys: JwksKeyHolder, id_token, nonce: Optional[str]) -> ProviderIdentity:
    if not isinstance(id_token, str):
        raise ProviderUnavailable("id_token_missing")
    try:
        identity = keys.verify(id_token, nonce=nonce)
    except (IdTokenRejected, AccessTokenRejected):
        if not keys.ready:
            raise ProviderUnavailable("keys_unavailable") from None
        raise ProviderRejected("id_token_rejected") from None
    if identity.email is None:
        raise ProviderRejected("email_not_verified")  # linking and new accounts need a verified email
    return identity


def provider_keys(policy, url: str, client: Optional[httpx.Client] = None) -> JwksKeyHolder:
    """The provider's signing keys, fetched lazily on the first token and refreshed on an unknown `kid`."""
    return JwksKeyHolder(None, url, client=client, verifier_factory=lambda jwks: IdTokenVerifier(policy, jwks))


class GoogleClient:
    provider = "google"

    def __init__(self, client_id: str, client_secret: str, keys: JwksKeyHolder, *, redirect_uri: str = "",
                 client: Optional[httpx.Client] = None, timeout_seconds: float = 5.0):
        if not client_id or not client_secret:
            raise ValueError("Google sign-in needs a client ID and secret")
        self._client_id, self._secret, self._redirect = client_id, client_secret, redirect_uri
        self._keys = keys
        self._client = client or httpx.Client(timeout=timeout_seconds, follow_redirects=False)

    def __repr__(self) -> str:
        return "GoogleClient(<configured>)"

    def exchange(self, code: str, nonce: Optional[str] = None) -> Exchange:
        if not valid_code(code):
            raise ProviderRejected("invalid_code")
        body = _token_body(_post(self._client, GOOGLE_TOKEN_URL, {
            "grant_type": "authorization_code", "code": code, "client_id": self._client_id,
            "client_secret": self._secret, "redirect_uri": self._redirect}))
        return Exchange(_identity(self._keys, body.get("id_token"), nonce))


class AppleClient:
    provider = "apple"

    def __init__(self, client_id: str, team_id: str, key_id: str, private_key_pem: str, keys: JwksKeyHolder, *,
                 client: Optional[httpx.Client] = None, timeout_seconds: float = 5.0,
                 clock: Callable[[], float] = time.time):
        if not (client_id and team_id and key_id and private_key_pem):
            raise ValueError("Apple sign-in needs a client ID, team ID, key ID and .p8 key")
        self._client_id, self._team, self._kid, self._key = client_id, team_id, key_id, private_key_pem
        self._keys = keys
        self._client = client or httpx.Client(timeout=timeout_seconds, follow_redirects=False)
        self._clock = clock
        self._client_secret()  # a bad key fails at start, not at the first sign-in

    def __repr__(self) -> str:
        return "AppleClient(<configured>)"

    def _client_secret(self) -> str:
        now = int(self._clock())
        try:
            return jwt.encode({"iss": self._team, "iat": now, "exp": now + 300, "aud": APPLE_AUDIENCE,
                               "sub": self._client_id}, self._key, algorithm="ES256", headers={"kid": self._kid})
        except (ValueError, TypeError, jwt.PyJWTError):
            raise ValueError("the Apple .p8 key is not a valid ES256 private key") from None

    def exchange(self, code: str, nonce: Optional[str] = None) -> Exchange:
        if not valid_code(code):
            raise ProviderRejected("invalid_code")
        body = _token_body(_post(self._client, APPLE_TOKEN_URL, {
            "grant_type": "authorization_code", "code": code, "client_id": self._client_id,
            "client_secret": self._client_secret()}))
        identity = _identity(self._keys, body.get("id_token"), nonce)
        refresh = body.get("refresh_token")
        if not isinstance(refresh, str) or not 1 <= len(refresh) <= 4096:
            raise ProviderUnavailable("refresh_token_missing")
        return Exchange(identity, refresh)

    def revoke(self, refresh_token: str) -> None:
        """Revoke a refresh token, which ends the app's Apple authorization for the user. 200 is done; a 400
        `invalid_grant` also counts as done (the token no longer works). Anything else raises."""
        try:
            response = _post(self._client, APPLE_REVOKE_URL, {
                "client_id": self._client_id, "client_secret": self._client_secret(), "token": refresh_token,
                "token_type_hint": "refresh_token"})
        except ProviderUnavailable as exc:
            raise AppleRevokeFailed(str(exc)) from None
        if response.status_code == 200:
            return
        if response.status_code == 400:
            try:
                if response.json().get("error") == "invalid_grant":
                    return
            except (ValueError, AttributeError):
                pass
        raise AppleRevokeFailed("revoke_status_%d" % response.status_code)


def _secret_file(path: Optional[str], what: str) -> str:
    if not path:
        raise RuntimeError(what + " file is not configured")
    try:
        value = Path(path).read_text(encoding="utf-8").strip()
    except OSError:
        raise RuntimeError(what + " file cannot be read") from None  # no path or content in the message
    if not value:
        raise RuntimeError(what + " file is empty")
    return value


def providers_for(settings) -> dict:
    """The configured providers by name: Google when its client ID is set, Apple when its client ID is set.
    Both need logto mode (dev mode signs in with the dev token only). A half configuration refuses to start."""
    providers: dict = {}
    if settings.auth_mode != "logto":
        return providers
    if settings.google_client_id:
        providers["google"] = GoogleClient(
            settings.google_client_id, _secret_file(settings.google_client_secret_file, "Google client secret"),
            provider_keys(google_policy(settings.google_client_id), GOOGLE_JWKS_URL),
            redirect_uri=settings.google_redirect_uri)
    if settings.apple_client_id:
        providers["apple"] = apple_client(settings)
    return providers


def apple_client(settings) -> Optional[AppleClient]:
    """The Apple client for sign-in and revocation (api and retention), or None when Apple isn't configured."""
    if settings.auth_mode != "logto" or not settings.apple_client_id:
        return None
    return AppleClient(settings.apple_client_id, settings.apple_team_id or "", settings.apple_key_id or "",
                       _secret_file(settings.apple_private_key_file, "Apple .p8 key"),
                       provider_keys(apple_policy(settings.apple_client_id), APPLE_JWKS_URL))


def token_cipher_from_file(path: Optional[str]) -> AppleTokenCipher:
    """The Apple-token keyring: `{"active": "<id>", "keys": {"<id>": "<base64url of 32 bytes>"}}`. Rotation
    adds a key and moves `active`; old keys stay for decryption (AR-3)."""
    try:
        data = json.loads(_secret_file(path, "Apple token keyring"))
        keys = {kid: base64.urlsafe_b64decode(value.encode("ascii") + b"=" * (-len(value) % 4))
                for kid, value in data["keys"].items()}
        return AppleTokenCipher(keys, data["active"])
    except (ValueError, KeyError, TypeError, AttributeError, binascii.Error):
        raise RuntimeError("Apple token keyring file is invalid") from None
