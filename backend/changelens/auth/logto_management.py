"""Deleting the Logto user behind an account (03a P8 DELETE_ACCOUNT; I-8 S5).

Logto's Management API, with a machine-to-machine app's client credentials:
`POST {endpoint}/oidc/token` (grant `client_credentials`, the management resource, scope `all`), then
`DELETE {endpoint}/api/users/{subject}`. Deleting the user removes its linked identities and sessions.
A 404 counts as done, so a retry after a lost response is safe.

Errors carry an event code only: never the subject, a token or a response body (AC-23).
"""
from __future__ import annotations

import re
import time
from typing import Callable, Optional

import httpx

DEFAULT_RESOURCE = "https://default.logto.app/api"  # Logto OSS management API resource
_USER_ID = re.compile(r"^[A-Za-z0-9_-]{1,200}$")  # Logto user IDs; anything else never reaches a URL


class IdpDeletionFailed(Exception):
    """The IdP user could not be deleted now; the account deletion stays pending and is retried."""


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

    def _access_token(self) -> str:
        if self._token and self._clock() < self._token_expires:
            return self._token
        try:
            r = self._client.post(self._endpoint + "/oidc/token", auth=self._credentials,
                                  data={"grant_type": "client_credentials", "resource": self._resource, "scope": "all"})
        except httpx.HTTPError as exc:
            raise IdpDeletionFailed("token_unreachable:" + type(exc).__name__) from None
        if r.status_code != 200:
            raise IdpDeletionFailed("token_status_%d" % r.status_code)
        try:
            body = r.json()
            token, lifetime = body["access_token"], int(body.get("expires_in", 60))
        except (ValueError, KeyError, TypeError):
            raise IdpDeletionFailed("token_malformed") from None
        if not isinstance(token, str) or not token:
            raise IdpDeletionFailed("token_malformed")
        self._token, self._token_expires = token, self._clock() + max(0, lifetime - 30)
        return token

    def delete_user(self, subject: str) -> None:
        """Delete the Logto user with this subject (its Logto user ID). Raises IdpDeletionFailed."""
        if not isinstance(subject, str) or not _USER_ID.match(subject):
            raise IdpDeletionFailed("invalid_subject")
        token = self._access_token()
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
    """The IdP deleter for these settings: `DevIdp` in dev mode, Logto when configured, otherwise None
    (the Logto step then stays pending instead of being skipped)."""
    if settings.auth_mode == "dev":
        return DevIdp()
    if settings.logto_management_endpoint and settings.logto_m2m_app_id and settings.logto_m2m_app_secret:
        return LogtoManagement(settings.logto_management_endpoint, settings.logto_m2m_app_id,
                               settings.logto_m2m_app_secret, settings.logto_management_resource)
    return None
