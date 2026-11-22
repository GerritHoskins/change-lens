"""The landing page's early-bird list (docs/landing-page-handoff.md): two public routes, no bearer token.

`POST /early-bird`, JSON `{"email": ..., "locale": "en" | "de"}`, nothing else, at most 1 KiB, sent as
`application/json` (so a browser must ask first, see CORS below). Invalid input is `422 invalid_request`
and is never echoed. Every valid request gets the same `202` and the same body, whether the address is
new, waiting for confirmation or already confirmed, so the route can't be used to test for addresses.
The confirmation mail (double opt-in) is sent after the response.

Limits: requests per IP per UTC day (`429 rate_limited` with `Retry-After`), counted before the body is
looked at; and confirmation mails per address per UTC day, keyed through the limiter's HMAC so no counter
holds an address. Over the second limit the answer is still `202` and nothing is sent or changed.

`GET /early-bird/confirm?token=...` confirms once by the token's SHA-256 and always answers `303` to the
landing page: `/#confirmed` (`/de/#confirmed` for a German sign-up) or `/#confirm-failed` for a missing,
unknown, used or expired token and for a rate-limited or failed request. A person opening a mail link
never gets a JSON error.

CORS, for `/early-bird` only (`EarlyBirdCors`): the configured landing origin may `POST` with
`Content-Type`, no credentials. No other route has CORS headers, and with no landing origin configured
(dev) no origin is allowed.

Logs carry event codes and the page language only, never an address, a token or a link. They are also
the server-side counts (handoff, Measurement): `early_bird_accepted` and `early_bird_confirmed` per day
and language.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import secrets
import threading
import time
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.concurrency import run_in_threadpool
from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import RedirectResponse, Response

from changelens.api.errors import ApiError
from changelens.api.limits import DAY, client_ip, limit_ip, limiter
from changelens.mail.confirmation import LOCALES, confirmation_mail

router = APIRouter()
log = logging.getLogger("changelens.early_bird")

PATH = "/early-bird"
MAX_BODY = 1024
MAX_EMAIL = 254
ACCEPTED = {"status": "accepted"}
# Conservative, not RFC 5322: ASCII only, one "@", the usual local-part characters, a dotted host name.
# Whitespace, control characters, quotes, brackets, commas and non-ASCII letters never pass, so the
# address is safe in a mail header as it stands.
_EMAIL = re.compile(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}@[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?")
_TOKEN = re.compile(r"[A-Za-z0-9_-]{32,128}")


def normalise_email(value) -> Optional[str]:
    """The address trimmed and lower-cased, or None when it isn't one we accept."""
    if not isinstance(value, str) or len(value) > 2 * MAX_EMAIL:
        return None
    email = value.strip().lower()
    if len(email) > MAX_EMAIL or not _EMAIL.fullmatch(email):
        return None
    host = email.rsplit("@", 1)[1]
    if "." not in host or ".." in host:
        return None
    return email


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


class MemoryEarlyBird:
    """The list in one process, for tests without services: the same four calls and rules as the
    `early_bird_*` functions of migration 0009 (`Database` has them as methods)."""

    def __init__(self, clock=time.time):
        self.rows: dict = {}
        self._clock, self._lock = clock, threading.Lock()

    def _expired(self, row: dict, pending_days: int) -> bool:
        return row["created_at"] < self._clock() - pending_days * DAY

    def early_bird_request(self, email: str, locale: str, hashed: str, pending_days: int) -> bool:
        with self._lock:
            row = self.rows.get(email)
            if row is None:
                self.rows[email] = {"locale": locale, "status": "pending", "token_hash": hashed,
                                    "created_at": self._clock(), "confirmation_sent_at": None,
                                    "confirmed_at": None}
                return True
            if row["status"] != "pending":
                return False
            if self._expired(row, pending_days):
                row["created_at"] = self._clock()
            row.update(locale=locale, token_hash=hashed)
            return True

    def early_bird_mark_sent(self, hashed: str) -> None:
        with self._lock:
            for row in self.rows.values():
                if row["token_hash"] == hashed and row["status"] == "pending":
                    row["confirmation_sent_at"] = self._clock()

    def early_bird_confirm(self, hashed: str, pending_days: int) -> Optional[str]:
        with self._lock:
            for row in self.rows.values():
                if (row["token_hash"] == hashed and row["status"] == "pending"
                        and not self._expired(row, pending_days)):
                    row.update(status="confirmed", confirmed_at=self._clock(), token_hash=None)
                    return row["locale"]
        return None

    def early_bird_prune(self, pending_days: int) -> int:
        with self._lock:
            gone = [email for email, row in self.rows.items()
                    if row["status"] == "pending" and self._expired(row, pending_days)]
            for email in gone:
                del self.rows[email]
            return len(gone)


class EarlyBirdCors:
    """CORS for `/early-bird` and nothing else: the preflight is answered here, and the route's own
    responses, errors included, get the allow header for the one configured origin."""

    def __init__(self, app, origin: str):
        self.app, self.origin = app, origin

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("path") != PATH:
            return await self.app(scope, receive, send)
        allowed = bool(self.origin) and Headers(scope=scope).get("origin") == self.origin
        if scope["method"] == "OPTIONS":
            headers = {"Vary": "Origin"}
            if allowed:
                headers.update({"Access-Control-Allow-Origin": self.origin, "Access-Control-Allow-Methods": "POST",
                                "Access-Control-Allow-Headers": "Content-Type", "Access-Control-Max-Age": "600"})
            return await Response(status_code=204, headers=headers)(scope, receive, send)

        async def _send(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.add_vary_header("Origin")
                if allowed:
                    headers["Access-Control-Allow-Origin"] = self.origin
            await send(message)

        await self.app(scope, receive, _send)


def _invalid() -> ApiError:
    return ApiError(422, "invalid_request", "send {email, locale} as application/json")


async def _body(request: Request) -> bytes:
    """The body, read up to the route's own small cap (the app-wide cap is sized for documents)."""
    length = request.headers.get("content-length")
    if length is not None and (not length.isdigit() or int(length) > MAX_BODY):
        raise ApiError(413, "limit_exceeded", "bytes")
    chunks, seen = [], 0
    async for chunk in request.stream():
        seen += len(chunk)
        if seen > MAX_BODY:
            raise ApiError(413, "limit_exceeded", "bytes")
        chunks.append(chunk)
    return b"".join(chunks)


def _parse(request: Request, raw: bytes) -> tuple[str, str]:
    # A JSON content type makes a cross-origin browser request ask first (preflight), which only the
    # landing origin passes; a form or text post from another site is refused here.
    if request.headers.get("content-type", "").split(";")[0].strip().lower() != "application/json":
        raise _invalid()
    try:
        body = json.loads(raw)
    except (ValueError, RecursionError):
        raise _invalid() from None
    if not isinstance(body, dict) or set(body) != {"email", "locale"}:
        raise _invalid()
    email, locale = normalise_email(body["email"]), body["locale"]
    if email is None or not isinstance(locale, str) or locale not in LOCALES:
        raise _invalid()
    return email, locale


@router.post(PATH, status_code=202)
async def request_early_bird(request: Request, background: BackgroundTasks):
    raw = await _body(request)
    return await run_in_threadpool(_accept, request, raw, background)


def _accept(request: Request, raw: bytes, background: BackgroundTasks) -> dict:
    state = request.app.state
    settings = state.settings
    limiter(request).check("early-bird", client_ip(request), settings.early_bird_per_ip_per_day, DAY)
    email, locale = _parse(request, raw)
    token = secrets.token_urlsafe(32)
    hashed = token_hash(token)
    try:
        limiter(request).check("early-bird-mail", email, settings.early_bird_mails_per_address_per_day, DAY)
        capped = False
    except ApiError:
        capped = True  # same answer; no new token either, so a link already mailed keeps working
    due = False if capped else state.early_bird.early_bird_request(email, locale, hashed,
                                                                  settings.early_bird_pending_days)
    log.info("early_bird_accepted locale=%s", locale)
    if capped:
        log.info("early_bird_mail_capped")
    if due:
        base = settings.public_api_url or str(request.base_url).rstrip("/")  # the fallback is dev mode only
        background.add_task(_send_confirmation, state, email, locale, base + PATH + "/confirm?token=" + token,
                            hashed)
    return ACCEPTED


def _send_confirmation(state, email: str, locale: str, link: str, hashed: str) -> None:
    """After the response. A failure is logged as an event code; the request was already answered."""
    subject, body = confirmation_mail(locale, link, state.settings.early_bird_pending_days)
    try:
        state.mailer.send(email, subject, body)
        state.early_bird.early_bird_mark_sent(hashed)
    except Exception as exc:  # the class name only: a message could quote the address
        log.error("early_bird_mail_failed reason=%s", getattr(exc, "reason", None) or type(exc).__name__)
        return
    log.info("early_bird_mail_sent locale=%s", locale)


@router.get(PATH + "/confirm")
def confirm_early_bird(request: Request):
    state = request.app.state
    settings = state.settings
    try:
        limit_ip(request)
    except ApiError as exc:
        return _redirect(settings.landing_url, None, exc.headers)
    token, locale = request.query_params.get("token", ""), None
    if _TOKEN.fullmatch(token):
        try:
            locale = state.early_bird.early_bird_confirm(token_hash(token), settings.early_bird_pending_days)
        except Exception as exc:
            log.error("early_bird_confirm_error reason=%s", type(exc).__name__)
    if locale in LOCALES:
        log.info("early_bird_confirmed locale=%s", locale)
    else:
        log.info("early_bird_confirm_failed")
    return _redirect(settings.landing_url, locale)


def _redirect(landing_url: str, locale: Optional[str], headers=None) -> RedirectResponse:
    if locale not in LOCALES:
        target = "/#confirm-failed"  # the language is unknown: the English root
    else:
        target = "/de/#confirmed" if locale == "de" else "/#confirmed"
    # The confirmation URL holds the (now used) token: don't pass it on as a referrer.
    return RedirectResponse(landing_url + target, status_code=303,
                            headers={**(headers or {}), "Referrer-Policy": "no-referrer"})
