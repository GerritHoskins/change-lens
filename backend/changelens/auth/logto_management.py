"""Logto's Management API: deleting the Logto user behind an account (03a P8; I-8 S5), and the user lookups,
identity links and one-time tokens of native Google and Apple sign-in (03a P1; I-8 S4).

A machine-to-machine app's client credentials: `POST {endpoint}/oidc/token` (grant `client_credentials`,
the management resource, scope `all`), then:
- `DELETE /api/users/{id}`: removes the user, its linked identities and sessions; a 404 counts as done;
- `GET /api/users?identityType=social&identityProvider={target}&identityId={sub}`: the user holding an identity;
- `GET /api/users?search.primaryEmail={email}&mode.primaryEmail=exact`: the user with an email (Logto
  lowercases both sides in exact mode unless asked not to);
- `GET /api/users/{id}`, `POST /api/users`: read or create a user;
- `PUT /api/users/{id}/identities/{target}`: link an identity; no connector needed, and Logto refuses an
  identity already on another user (422 `user.identity_already_in_use`);
- `POST /api/one-time-tokens`: a single-use sign-in token bound to the user's email (Logto 1.27+).

The credential can link identities and delete users, so only the api and retention processes load it
(03 §6). Errors carry an event code only: never the subject, an email, a token or a response body (AC-23).
"""
from __future__ import annotations

import re
import time
from typing import Callable, Optional

import httpx

DEFAULT_RESOURCE = "https://default.logto.app/api"  # Logto OSS management API resource
_USER_ID = re.compile(r"^[A-Za-z0-9_-]{1,200}$")  # Logto user IDs; anything else never reaches a URL
TARGETS = ("google", "apple")  # identity targets, named as Logto's own connectors name them
_MAX_RESPONSE = 256 * 1024


class IdpUnavailable(Exception):
    """Logto could not answer now; nothing was decided."""


class IdpDeletionFailed(IdpUnavailable):
    """The IdP user could not be deleted now; the account deletion stays pending and is retried."""


class IdentityInUse(Exception):
    """Logto refused the link: the identity already belongs to another user."""


def _valid_user_id(value) -> bool:
    return isinstance(value, str) and bool(_USER_ID.match(value))


def sign_in_methods(user: dict) -> list[str]:
    """What the account can sign in with today, for `link_required`: email, then linked providers."""
    methods = ["email"] if user.get("primaryEmail") else []
    identities = user.get("identities") if isinstance(user.get("identities"), dict) else {}
    return methods + [target for target in TARGETS if target in identities]


class LogtoManagement:
    def __init__(self, endpoint: str, app_id: str, app_secret: str, resource: str = DEFAULT_RESOURCE, *,
                 client: Optional[httpx.Client] = None, timeout_seconds: float = 5.0,
                 clock: Callable[[], float] = time.monotonic):
        if not endpoint.startswith("https://") or not app_id or not app_secret:
            raise ValueError("Logto management needs an https endpoint and app credentials")
        self._endpoint = endpoint.rstrip("/")
        self._credentials = (app_id, app_secret)
        self._resource = resource
        self._client = client or httpx.Client(timeout=timeout_seconds, follow_redirects=False)
        self._clock = clock
        self._token: Optional[str] = None
        self._token_expires = 0.0

    def __repr__(self) -> str:
        return "LogtoManagement(<configured>)"

    def _access_token(self, error=IdpUnavailable) -> str:
        if self._token and self._clock() < self._token_expires:
            return self._token
        try:
            r = self._client.post(self._endpoint + "/oidc/token", auth=self._credentials,
                                  data={"grant_type": "client_credentials", "resource": self._resource, "scope": "all"})
        except httpx.HTTPError as exc:
            raise error("token_unreachable:" + type(exc).__name__) from None
        if r.status_code != 200:
            raise error("token_status_%d" % r.status_code)
        try:
            body = r.json()
            token, lifetime = body["access_token"], int(body.get("expires_in", 60))
        except (ValueError, KeyError, TypeError):
            raise error("token_malformed") from None
        if not isinstance(token, str) or not token:
            raise error("token_malformed")
        self._token, self._token_expires = token, self._clock() + max(0, lifetime - 30)
        return token

    def _call(self, method: str, path: str, *, params=None, json=None, ok=(200,)) -> httpx.Response:
        token = self._access_token()
        try:
            r = self._client.request(method, self._endpoint + path, params=params, json=json,
                                     headers={"Authorization": "Bearer " + token})
        except httpx.HTTPError as exc:
            raise IdpUnavailable("unreachable:" + type(exc).__name__) from None
        if r.status_code == 401:
            self._token = None
        if r.status_code not in ok or len(r.content) > _MAX_RESPONSE:
            raise IdpUnavailable("status_%d" % r.status_code)
        return r

    @staticmethod
    def _json(r: httpx.Response):
        try:
            return r.json()
        except ValueError:
            raise IdpUnavailable("malformed") from None

    def _one_user(self, params: dict) -> Optional[dict]:
        users = self._json(self._call("GET", "/api/users", params={**params, "page_size": "2"}))
        if not isinstance(users, list) or len(users) > 1 or any(not isinstance(u, dict) for u in users):
            raise IdpUnavailable("ambiguous_users")  # unique by Logto's constraints; anything else is refused
        if users and not _valid_user_id(users[0].get("id")):
            raise IdpUnavailable("malformed")
        return users[0] if users else None

    def user_by_identity(self, target: str, provider_subject: str) -> Optional[dict]:
        if target not in TARGETS:
            raise ValueError("unknown identity target")
        return self._one_user({"identityType": "social", "identityProvider": target, "identityId": provider_subject})

    def user_by_email(self, email: str) -> Optional[dict]:
        user = self._one_user({"search.primaryEmail": email, "mode.primaryEmail": "exact"})
        primary = user.get("primaryEmail") if user else None
        if user is not None and (not isinstance(primary, str) or primary.lower() != email.lower()):
            raise IdpUnavailable("search_mismatch")
        return user

    def user(self, user_id: str) -> Optional[dict]:
        if not _valid_user_id(user_id):
            raise IdpUnavailable("invalid_subject")
        r = self._call("GET", "/api/users/" + user_id, ok=(200, 404))
        if r.status_code == 404:
            return None
        user = self._json(r)
        if not isinstance(user, dict) or user.get("id") != user_id:
            raise IdpUnavailable("malformed")
        return user

    def create_user(self, email: str) -> str:
        """A new Logto user with this verified email. Raises IdentityInUse when the email is taken (a race
        with another sign-up), so the caller looks the user up again."""
        r = self._call("POST", "/api/users", json={"primaryEmail": email}, ok=(200, 201, 422))
        if r.status_code == 422:
            raise IdentityInUse("email_in_use")
        body = self._json(r)
        user_id = body.get("id") if isinstance(body, dict) else None
        if not _valid_user_id(user_id):
            raise IdpUnavailable("malformed")
        return user_id

    def link_identity(self, user_id: str, target: str, provider_subject: str) -> None:
        if target not in TARGETS or not _valid_user_id(user_id):
            raise ValueError("invalid link")
        r = self._call("PUT", "/api/users/%s/identities/%s" % (user_id, target),
                       json={"userId": provider_subject, "details": {}}, ok=(200, 201, 422))
        if r.status_code == 422:
            raise IdentityInUse("identity_in_use")

    def one_time_token(self, email: str, expires_in: int) -> str:
        """A single-use token that signs this email's user in through Logto's normal sign-in (MFA applies)."""
        r = self._call("POST", "/api/one-time-tokens", ok=(200, 201),
                       json={"email": email, "expiresIn": expires_in, "context": {"interactionEvent": "SignIn"}})
        body = self._json(r)
        token = body.get("token") if isinstance(body, dict) else None
        if not isinstance(token, str) or not 1 <= len(token) <= 512:
            raise IdpUnavailable("malformed")
        return token

    def delete_user(self, subject: str) -> None:
        """Delete the Logto user with this subject (its Logto user ID). Raises IdpDeletionFailed."""
        if not _valid_user_id(subject):
            raise IdpDeletionFailed("invalid_subject")
        token = self._access_token(IdpDeletionFailed)
        try:
            r = self._client.delete(self._endpoint + "/api/users/" + subject,
                                    headers={"Authorization": "Bearer " + token})
        except httpx.HTTPError as exc:
            raise IdpDeletionFailed("delete_unreachable:" + type(exc).__name__) from None
        if r.status_code == 401:
            self._token = None  # expired early or revoked: the next attempt fetches a new one
        if r.status_code not in (200, 204, 404):
            raise IdpDeletionFailed("delete_status_%d" % r.status_code)


class DevIdp:
    """Dev mode: dev-token subjects are not IdP users, so there is nothing to delete."""

    def delete_user(self, subject: str) -> None:
        return None


def idp_for(settings):
    """The IdP client for these settings: `DevIdp` in dev mode, Logto when configured, otherwise None
    (the Logto step then stays pending instead of being skipped)."""
    if settings.auth_mode == "dev":
        return DevIdp()
    if settings.logto_management_endpoint and settings.logto_m2m_app_id and settings.logto_m2m_app_secret:
        return LogtoManagement(settings.logto_management_endpoint, settings.logto_m2m_app_id,
                               settings.logto_m2m_app_secret, settings.logto_management_resource)
    return None
