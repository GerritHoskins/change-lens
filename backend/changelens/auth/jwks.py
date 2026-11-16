"""Signing keys fetched from a configured JWKS URL only: Logto's for `JwtVerifier` (I-8 S1), and Google's
and Apple's for their ID tokens through `verifier_factory` (I-8 S4).

The URL comes from settings, never from a token header (`jku`, `x5u` and friends are rejected by the
verifier). A token whose `kid` is unknown triggers at most one refresh per `refresh_seconds`; a failed
refresh keeps the cached keys. Failures are logged by exception class only: no URL, key or token.
"""
from __future__ import annotations

import json
import logging
import threading
import time
from typing import Callable, Optional

import httpx
import jwt

from changelens.auth.jwt_verifier import AccessTokenRejected, JwtPolicy, JwtVerifier

log = logging.getLogger("changelens.auth")
MAX_JWKS_BYTES = 64 * 1024


class JwksUnavailable(Exception):
    def __init__(self):
        super().__init__("jwks_unavailable")


class JwksKeyHolder:
    def __init__(self, policy: Optional[JwtPolicy], url: str, *, client: Optional[httpx.Client] = None,
                 timeout_seconds: float = 3.0, max_bytes: int = MAX_JWKS_BYTES, refresh_seconds: float = 60.0,
                 clock: Callable[[], float] = time.monotonic, verifier_factory: Optional[Callable] = None):
        self.policy, self.url = policy, url
        # Builds the verifier from a fetched JWKS; any object with `key_ids` and `verify(token)`.
        self._factory = verifier_factory or (lambda jwks: JwtVerifier(policy, jwks))
        self._client = client or httpx.Client(timeout=timeout_seconds, follow_redirects=False)
        self._max_bytes, self._refresh_seconds, self._clock = max_bytes, refresh_seconds, clock
        self._verifier: Optional[JwtVerifier] = None
        self._last_refresh: Optional[float] = None
        self._lock = threading.Lock()
        self.fetches = 0  # observable for tests and diagnostics; never holds key material

    def load(self) -> None:
        """First fetch at startup. The api refuses to start in logto mode if this raises."""
        with self._lock:
            self._verifier = self._fetch()

    @property
    def ready(self) -> bool:
        """Whether any keys are held, so a rejection means a bad token rather than an outage."""
        return self._verifier is not None

    def verify(self, token: str, **kwargs):
        verifier = self._verifier
        kid = _kid(token)
        if kid is not None and (verifier is None or kid not in verifier.key_ids):
            verifier = self._refresh()
        if verifier is None:
            raise AccessTokenRejected()
        return verifier.verify(token, **kwargs)

    def _refresh(self) -> Optional[JwtVerifier]:
        with self._lock:
            now = self._clock()
            if self._last_refresh is None or now - self._last_refresh >= self._refresh_seconds:
                self._last_refresh = now
                try:
                    self._verifier = self._fetch()
                except JwksUnavailable:
                    pass  # keep the cached keys
            return self._verifier

    def _fetch(self) -> JwtVerifier:
        self.fetches += 1
        try:
            with self._client.stream("GET", self.url, headers={"Accept": "application/json"}) as response:
                if response.status_code != 200:
                    raise ValueError("unexpected status")
                declared = response.headers.get("content-length")
                if declared is not None and (not declared.isdigit() or int(declared) > self._max_bytes):
                    raise ValueError("too large")
                body = bytearray()
                for chunk in response.iter_bytes():
                    body += chunk
                    if len(body) > self._max_bytes:
                        raise ValueError("too large")
            return self._factory(json.loads(bytes(body)))
        except Exception as exc:  # network, status, size, JSON or key validation
            log.warning("jwks fetch failed: %s", type(exc).__name__)
            raise JwksUnavailable() from None


def _kid(token) -> Optional[str]:
    """The unverified `kid`, only to decide whether a refresh could help; the verifier re-checks it."""
    try:
        kid = jwt.get_unverified_header(token).get("kid") if isinstance(token, str) and len(token) <= 16384 else None
    except (jwt.PyJWTError, ValueError, TypeError, AttributeError):
        return None
    return kid if isinstance(kid, str) and 1 <= len(kid) <= 200 else None
