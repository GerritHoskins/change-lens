"""The landing page's early-bird list (docs/landing-page-handoff.md): public routes, no bearer token.

`POST /early-bird`, JSON `{"email": ..., "locale": "en" | "de"}`, nothing else, at most 1 KiB, sent as
`application/json` (so a browser must ask first, see CORS below). Invalid input is `422 invalid_request`
and is never echoed. Every valid request gets the same `202` and the same body, whether the address is
new, waiting for confirmation or already confirmed, and whether or not a mail goes out, so the route can't
be used to test for addresses. The confirmation mail (double opt-in) is sent from the mail queue
(`changelens/mail/queue.py`): two threads of its own, at most 50 mails waiting, one more is dropped.

Limits, all through the rate limiter (keyed hashes, no address or IP in a counter):
- Requests per client per UTC day (`429 rate_limited` with `Retry-After`), counted before any of the body is
  read. A client is an IPv4 address or an IPv6 /64 network.
- Confirmation mails per address per UTC day. The counter's key ignores a `+tag` in the local part, so
  `name+1@host` and `name+2@host` count as one; the stored address keeps its tag.
- Confirmation mails to all addresses together, per hour and per UTC day. These count every request that
  reaches them (valid, under the address limit), also one that then sends nothing.
- Mails per pending sign-up over its whole life (`early_bird_request`, migration 0011).
Over any of the last three the answer is still `202`, nothing is sent and nothing changes.

`GET /early-bird/confirm?token=...` changes nothing: mail scanners open links. A well-formed token gets the
one-button page (`early_bird_pages.py`) without the list being read, so the page says nothing about the
token. `POST /early-bird/confirm` (the page's form, field `token`) confirms once by the token's SHA-256 and
answers `303` to the landing page: `/#confirmed` (`/de/#confirmed` for a German sign-up), or
`/#confirm-failed` for a missing, malformed, unknown, used or expired token and for a rate-limited or failed
request. A person following a mail link never gets a JSON error. A newer link replaces the one mailed
before only once its own mail was handed to the mail server; a link lives for the pending period
(`mail.confirmation.PENDING_DAYS`, fixed in the database) from when it was issued.

Removal from the list (`/early-bird/unsubscribe`) is in `early_bird_unsubscribe.py`.

CORS, for `/early-bird` only (`EarlyBirdCors`): the configured landing origin may `POST` with
`Content-Type`, no credentials. No other route has CORS headers, and with no landing origin configured
(dev) no origin is allowed.

Logs carry event codes and the page language only, never an address, a token or a link. They are also the
server-side counts (handoff, Measurement), per day and language: `early_bird_accepted` is every valid
request to the form (also a repeated one, one for a confirmed address and one over a mail limit);
`early_bird_mail_due` is a request that issued a link and queued a mail, the count of sign-up attempts;
`early_bird_confirmed` is an address that joined the list.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import secrets
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from starlette.datastructures import Headers, MutableHeaders
from starlette.responses import Response

from changelens.api.early_bird_memory import MemoryEarlyBird  # noqa: F401 (imported from here by the app)
from changelens.api.early_bird_pages import (client_key, counted_body, form_token, over_minute_limit, page,
                                             read_body, to_landing)
from changelens.api.errors import ApiError
from changelens.api.limits import DAY, limiter
from changelens.mail import MailError
from changelens.mail.confirmation import LOCALES, confirmation_mail

router = APIRouter()
log = logging.getLogger("changelens.early_bird")

PATH = "/early-bird"
MAX_BODY = 1024
MAX_EMAIL = 254
HOUR = 3600
ACCEPTED = {"status": "accepted"}
CONFIRM_FAILED = "/#confirm-failed"  # the language is unknown: the English root
# Conservative, not RFC 5322: ASCII only, one "@", the usual local-part characters, a dotted host name.
# Whitespace, control characters, quotes, brackets, commas and non-ASCII letters never pass, so the
# address is safe in a mail header as it stands.
_EMAIL = re.compile(r"[a-z0-9.!#$%&'*+/=?^_`{|}~-]{1,64}@[a-z0-9](?:[a-z0-9.-]*[a-z0-9])?")
_TOKEN = re.compile(r"[A-Za-z0-9_-]{32,128}")

# WORDING NEW AND UNREVIEWED (both languages), like the confirmation mail.
CONFIRM_COPY = {
    "title": "ChangeLens early-bird list",
    "en_h": "Join the early-bird list?",
    "en_p": ("Press the button to confirm your email address for the ChangeLens early-bird list. "
             "If you did not ask for this, close this page: the address is deleted by itself."),
    "de_h": "Auf die Early-Bird-Liste setzen?",
    "de_p": ("Mit dem Button bestätigst du deine E-Mail-Adresse für die Early-Bird-Liste von ChangeLens. "
             "Wenn du das nicht warst, schließe diese Seite: Die Adresse wird von selbst gelöscht."),
    "en_button": "Confirm",
    "de_button": "Bestätigen",
    "en_note": "Nothing changes until you press the button.",
    "de_note": "Solange du den Button nicht drückst, ändert sich nichts.",
}


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


def counter_address(email: str) -> str:
    """What the per-address mail limit counts by: the address without a `+tag` in its local part. Only the
    counter's key; the address itself is stored and mailed as it was entered."""
    local, _, host = email.rpartition("@")
    return (local.split("+", 1)[0] or local) + "@" + host


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


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


def _count_request(request: Request) -> None:
    settings = request.app.state.settings
    limiter(request).check("early-bird", client_key(request), settings.early_bird_per_ip_per_day, DAY)


@router.post(PATH, status_code=202)
async def request_early_bird(request: Request):
    await run_in_threadpool(_count_request, request)  # before the body: a large or slow one counts too
    raw = await read_body(request, MAX_BODY)
    if raw is None:
        raise ApiError(413, "limit_exceeded", "bytes")
    return await run_in_threadpool(_accept, request, raw)


def _mail_cap(request: Request, email: str) -> Optional[str]:
    """Which mail limit this request is over, if any. The limits for all addresses come last, so a request
    stopped by the address's own limit doesn't use them up."""
    settings, check = request.app.state.settings, limiter(request).check
    for scope, ident, limit, window, name in (
            ("early-bird-mail", counter_address(email), settings.early_bird_mails_per_address_per_day, DAY, "address"),
            ("early-bird-mail-hour", "all", settings.early_bird_mails_per_hour, HOUR, "all_hour"),
            ("early-bird-mail-day", "all", settings.early_bird_mails_per_day, DAY, "all_day")):
        try:
            check(scope, ident, limit, window)
        except ApiError:
            return name
    return None


def _accept(request: Request, raw: bytes) -> dict:
    state = request.app.state
    settings = state.settings
    email, locale = _parse(request, raw)
    log.info("early_bird_accepted locale=%s", locale)
    capped = _mail_cap(request, email)
    if capped:  # the same answer; no new token either, so a link already mailed keeps working
        log.info("early_bird_mail_capped scope=%s", capped)
        return ACCEPTED
    token = secrets.token_urlsafe(32)
    hashed = token_hash(token)
    if not state.early_bird.early_bird_request(email, locale, hashed, settings.early_bird_mails_per_row):
        return ACCEPTED  # already confirmed, or this pending sign-up has had all its mails
    log.info("early_bird_mail_due locale=%s", locale)
    base = settings.public_api_url or str(request.base_url).rstrip("/")  # the fallback is dev mode only
    link = base + PATH + "/confirm?token=" + token
    if not state.mail_queue.submit(_send_confirmation, state, email, locale, link, hashed):
        log.error("early_bird_mail_failed reason=queue_full")
    return ACCEPTED


def _send_confirmation(state, email: str, locale: str, link: str, hashed: str) -> None:
    """On a mail-queue thread. A failure is logged as an event code; the request was already answered. The
    new link replaces the one mailed before only here, once this mail is out."""
    subject, body = confirmation_mail(locale, link)
    try:
        state.mailer.send(email, subject, body)
        state.early_bird.early_bird_mark_sent(hashed)
    except MailError as exc:  # its reason is an exception class name by construction
        log.error("early_bird_mail_failed reason=%s", exc.reason)
        return
    except Exception as exc:  # the class name only: a message, or a `reason` of its own, could quote the address
        log.error("early_bird_mail_failed reason=%s", type(exc).__name__)
        return
    log.info("early_bird_mail_sent locale=%s", locale)


@router.get(PATH + "/confirm")
def confirm_page(request: Request) -> Response:
    settings = request.app.state.settings
    limited = over_minute_limit(request)
    if limited is not None:
        return to_landing(settings.landing_url, CONFIRM_FAILED, limited)
    token = request.query_params.get("token", "")
    if not _TOKEN.fullmatch(token):
        log.info("early_bird_confirm_failed")
        return to_landing(settings.landing_url, CONFIRM_FAILED)
    return page(CONFIRM_COPY, token)


@router.post(PATH + "/confirm")
async def confirm_early_bird(request: Request) -> Response:
    limited, raw = await counted_body(request)
    if limited is not None:
        return to_landing(request.app.state.settings.landing_url, CONFIRM_FAILED, limited)
    return await run_in_threadpool(_confirm, request, raw)


def _confirm(request: Request, raw: Optional[bytes]) -> Response:
    state = request.app.state
    token, locale = (form_token(request, raw) if raw is not None else None) or "", None
    if _TOKEN.fullmatch(token):
        try:
            locale = state.early_bird.early_bird_confirm(token_hash(token))
        except Exception as exc:
            log.error("early_bird_confirm_error reason=%s", type(exc).__name__)
    if locale not in LOCALES:
        log.info("early_bird_confirm_failed")
        return to_landing(state.settings.landing_url, CONFIRM_FAILED)
    log.info("early_bird_confirmed locale=%s", locale)
    return to_landing(state.settings.landing_url, "/de/#confirmed" if locale == "de" else "/#confirmed")
