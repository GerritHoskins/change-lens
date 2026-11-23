"""Removal from the early-bird list: two public routes, no bearer token. The link is in every mail to the
list (`changelens/mail/unsubscribe.py` makes and checks its token: `<signup id>.<mac>`).

`GET /early-bird/unsubscribe?token=...` changes nothing, ever: mail scanners open links. For a token with a
valid MAC it answers `200` with the one-button page (`early_bird_pages.py`), whose button posts the token
back. The page is in English and German at once, so the list is not read to pick a language, and the page is
the same whether or not the address is still on the list. It shows no address, runs no script and loads
nothing.

`POST /early-bird/unsubscribe` removes. The token comes from the query string (RFC 8058 one-click: the mail
client posts `List-Unsubscribe=One-Click` to the link itself) or, without one there, from the form field
`token` (`application/x-www-form-urlencoded`, at most 1 KiB). A valid MAC deletes the row and answers `303`
to the landing page's `/#unsubscribed` (`/de/#unsubscribed` when the deleted row was German); when the row is
already gone the answer is the same, because the person is not on the list either way.

An invalid token, a body that is too large, a failed database call and a request over the per-minute limit
(with `Retry-After`; counted before the body is read) all answer `303` to `/#unsubscribe-failed`, on both
routes. Nobody gets a JSON error.

No CSRF token: a form posted from another site can only remove an address whose valid token the sender
already holds, and holding the token is the whole permission. No CORS headers either: these are navigations
and mail-client posts, not calls from a page's script.

Logs carry event codes and the page language only (`early_bird_unsubscribed locale=…`, `locale=none` when
the row was already gone; `early_bird_unsubscribe_failed`), never an ID, an address or a token.
"""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool
from starlette.responses import Response

from changelens.api.early_bird_pages import (MAX_BODY, PAGE_HEADERS, counted_body, form_token,  # noqa: F401
                                             over_minute_limit, page, to_landing)
from changelens.mail.confirmation import LOCALES
from changelens.mail.unsubscribe import PATH, verify_unsubscribe_token

router = APIRouter()
log = logging.getLogger("changelens.early_bird")
FAILED = "/#unsubscribe-failed"  # the language is unknown: the English root

# WORDING NEW AND UNREVIEWED (both languages), like the confirmation mail.
COPY = {
    "title": "ChangeLens early-bird list",
    "en_h": "Leave the early-bird list?",
    "en_p": ("Press the button and we delete your email address from the ChangeLens early-bird list. "
             "You will get no more emails from the list."),
    "de_h": "Von der Early-Bird-Liste abmelden?",
    "de_p": ("Mit dem Button löschen wir deine E-Mail-Adresse von der Early-Bird-Liste von ChangeLens. "
             "Du bekommst dann keine E-Mails mehr über die Liste."),
    "en_button": "Unsubscribe",
    "de_button": "Abmelden",
    "en_note": "Nothing changes until you press the button.",
    "de_note": "Solange du den Button nicht drückst, ändert sich nichts.",
}


def _failed(landing_url: str) -> Response:
    log.info("early_bird_unsubscribe_failed")
    return to_landing(landing_url, FAILED)


@router.get(PATH)
def unsubscribe_page(request: Request) -> Response:
    settings = request.app.state.settings
    limited = over_minute_limit(request)
    if limited is not None:
        return to_landing(settings.landing_url, FAILED, limited)
    token = request.query_params.get("token")
    if verify_unsubscribe_token(settings.early_bird_unsubscribe_key, token) is None:
        return _failed(settings.landing_url)
    return page(COPY, token)


@router.post(PATH)
async def unsubscribe(request: Request) -> Response:
    limited, raw = await counted_body(request)
    if limited is not None:
        return to_landing(request.app.state.settings.landing_url, FAILED, limited)
    return await run_in_threadpool(_remove, request, raw)


def _remove(request: Request, raw: Optional[bytes]) -> Response:
    state = request.app.state
    settings = state.settings
    if raw is None:
        return _failed(settings.landing_url)
    token = request.query_params.get("token")
    if token is None:
        token = form_token(request, raw)
    signup_id = verify_unsubscribe_token(settings.early_bird_unsubscribe_key, token)
    if signup_id is None:
        return _failed(settings.landing_url)
    try:
        locale = state.early_bird.early_bird_unsubscribe(signup_id)
    except Exception as exc:
        log.error("early_bird_unsubscribe_error reason=%s", type(exc).__name__)
        return to_landing(settings.landing_url, FAILED)
    locale = locale if locale in LOCALES else None
    log.info("early_bird_unsubscribed locale=%s", locale or "none")
    return to_landing(settings.landing_url, "/de/#unsubscribed" if locale == "de" else "/#unsubscribed")
