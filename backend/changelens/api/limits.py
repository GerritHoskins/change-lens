"""Rate limits and the client IP (03 §6 Abuse and cost exhaustion, SA-4; I-8 S6).

Fixed windows: per account per minute (every authenticated request), per IP per minute (requests that
fail authentication, and `POST /session`), and new accounts per IP per UTC day (the sign-up cap in
`POST /session`: one counter for new account rows, one for Logto users that native Google or Apple sign-in
creates, so a social sign-up counts once in each). Over a limit is `429 rate_limited` with `Retry-After`.
The upload routes also take one of the process's upload slots (`UploadSlots`), with the same answer when none is free.

Keys are an HMAC-SHA256 of the scope and the account ID or IP with a secret key, so the counters never
hold a raw address. Nothing here logs an IP. Counts live in Postgres (`rate_limit_hit`, migration 0005),
shared by every api process; `MemoryCounters` is the single-process stand-in for tests without services.

The client IP is the socket address, unless that address is a configured trusted proxy: then the
right-most `X-Forwarded-For` entry that isn't a trusted proxy. A spoofed header from anywhere else is
ignored.
"""
from __future__ import annotations

import hashlib
import hmac
import ipaddress
import math
import threading
import time
from datetime import datetime, timezone
from typing import Callable

from fastapi import Request

from changelens.api.errors import ApiError

MINUTE, DAY = 60, 86400


class MemoryCounters:
    def __init__(self):
        self._hits: dict = {}
        self._lock = threading.Lock()

    def __call__(self, key_hash: str, window_start: datetime) -> int:
        with self._lock:
            self._hits[(key_hash, window_start)] = self._hits.get((key_hash, window_start), 0) + 1
            return self._hits[(key_hash, window_start)]


class RateLimiter:
    def __init__(self, hit: Callable[[str, datetime], int], key: str, clock: Callable[[], float] = time.time):
        self._hit, self._key, self._clock = hit, key.encode(), clock

    def key_hash(self, scope: str, ident: str) -> str:
        return hmac.new(self._key, (scope + ":" + ident).encode(), hashlib.sha256).hexdigest()

    def check(self, scope: str, ident: str, limit: int, window: int) -> None:
        """Count one request; raise `429 rate_limited` once the window holds more than `limit`."""
        now = self._clock()
        start = math.floor(now / window) * window
        hits = self._hit(self.key_hash(scope, ident), datetime.fromtimestamp(start, timezone.utc))
        if hits > limit:
            retry = max(1, math.ceil(start + window - now))
            raise ApiError(429, "rate_limited", headers={"Retry-After": str(retry)})


class UploadSlots:
    """Upload requests that hold a body in memory at once, in this process (LR-10). Uploads are never spooled
    to disk, so their number bounds the memory they take. One account gets at most half of the slots, so it
    can't hold all of them with slow uploads."""

    def __init__(self, limit: int):
        self.limit, self.per_account = limit, max(1, limit // 2)
        self.used, self.by_account = 0, {}
        self._lock = threading.Lock()

    def take(self, account) -> bool:
        with self._lock:
            held = self.by_account.get(account, 0)
            if self.used >= self.limit or held >= self.per_account:
                return False
            self.used, self.by_account[account] = self.used + 1, held + 1
            return True

    def release(self, account) -> None:
        with self._lock:
            held = self.by_account.pop(account, 0)
            if held > 1:
                self.by_account[account] = held - 1
            self.used -= 1 if held else 0


def limiter(request: Request) -> RateLimiter:
    return request.app.state.limiter


def client_ip(request: Request) -> str:
    trusted = request.app.state.settings.trusted_proxies
    peer = request.client.host if request.client else ""
    if peer not in trusted:
        return peer
    hops = [h.strip() for h in request.headers.get("x-forwarded-for", "").split(",") if h.strip()]
    for hop in reversed(hops):
        try:
            address = str(ipaddress.ip_address(hop))
        except ValueError:
            return peer  # a malformed chain proves nothing; key on the proxy itself
        if address not in trusted:
            return address
    return peer


def limit_account(request: Request, user_id) -> None:
    settings = request.app.state.settings
    limiter(request).check("account", str(user_id), settings.rate_limit_account_per_minute, MINUTE)


def limit_ip(request: Request) -> None:
    settings = request.app.state.settings
    limiter(request).check("ip", client_ip(request), settings.rate_limit_ip_per_minute, MINUTE)


def limit_signup(request: Request) -> None:
    settings = request.app.state.settings
    limiter(request).check("signup", client_ip(request), settings.signups_per_ip_per_day, DAY)


def limit_signup_idp(request: Request) -> None:
    """Before `POST /session` creates a Logto user for a new Google or Apple identity (I-8 S4)."""
    settings = request.app.state.settings
    limiter(request).check("signup-idp", client_ip(request), settings.signups_per_ip_per_day, DAY)
