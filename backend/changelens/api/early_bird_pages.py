"""What the early-bird list's link routes share: the one-button page, its response headers, the small form
body, the redirect to the landing page and the per-minute limit.

A link in a mail is opened by mail scanners as well as by people, so opening one (`GET`) never changes
anything: it shows a page with one button, and the button's `POST` acts (confirm in `early_bird.py`, remove
in `early_bird_unsubscribe.py`). The page is served by the API: inline CSS only, no script, no outside
request, no address, English and German together so the list is not read to pick a language. Calm Bold
(DESIGN.md): ground, ink, one black 60 px pill; a system font stack, because the page loads nothing.

The per-minute limit of these routes has its own scope and counts an IPv6 client by its /64 network
(`limits.network_key`); the sign-in limits are untouched.
"""
from __future__ import annotations

from html import escape
from typing import Optional

from fastapi import Request
from fastapi.concurrency import run_in_threadpool
from starlette.responses import HTMLResponse, RedirectResponse

from changelens.api.errors import ApiError
from changelens.api.limits import MINUTE, client_ip, limiter, network_key

MAX_BODY = 1024
FORM = "application/x-www-form-urlencoded"
PAGE_HEADERS = {
    "Content-Security-Policy": ("default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; "
                                "base-uri 'none'; frame-ancestors 'none'"),
    "Referrer-Policy": "no-referrer",  # the page's URL holds the token
    "Cache-Control": "no-store",
    "X-Content-Type-Options": "nosniff",
}

# Every `{name}` but `{token}` comes from a route's copy table (keys: title, en_h, en_p, de_h, de_p, en_button,
# de_button, en_note, de_note). The form has no action, so it posts to the address the page was opened at.
_PAGE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="robots" content="noindex">
<meta name="color-scheme" content="light dark">
<title>{title}</title>
<style>
:root {{ --ground: #F5F5F2; --ink: #111114; --muted: #5E5E66; --line: #DCDCD6; --on-action: #FFFFFF;
  --link: #4B3BFF; }}
@media (prefers-color-scheme: dark) {{
  :root {{ --ground: #121214; --ink: #F3F3EF; --muted: #A6A6AE; --line: #34343A; --on-action: #111114;
    --link: #A99FFF; }}
}}
* {{ box-sizing: border-box; }}
html {{ -webkit-text-size-adjust: 100%; }}
body {{ margin: 0; background: var(--ground); color: var(--ink);
  font: 400 1.0625rem/1.41 system-ui, -apple-system, "Segoe UI", "Helvetica Neue", Arial, sans-serif; }}
main {{ max-width: 34rem; margin: 0 auto; padding: 48px 24px 64px; }}
.brand {{ margin: 0 0 40px; font-weight: 700; letter-spacing: -0.01em; }}
h1 {{ margin: 0 0 12px; font-size: 1.75rem; line-height: 1.14; font-weight: 700; letter-spacing: -0.02em;
  text-wrap: balance; }}
p {{ margin: 0; max-width: 60ch; }}
.other {{ margin-top: 28px; padding-top: 28px; border-top: 1px solid var(--line); }}
form {{ margin: 36px 0 0; }}
button {{ display: block; width: 100%; min-height: 60px; padding: 12px 28px; border: 0; border-radius: 999px;
  background: var(--ink); color: var(--on-action); font: inherit; font-weight: 600; cursor: pointer; }}
button:focus-visible {{ outline: 2px solid var(--link); outline-offset: 3px; }}
.meta {{ margin-top: 16px; color: var(--muted); font-size: 0.875rem; line-height: 1.43; }}
</style>
</head>
<body>
<main>
<p class="brand">ChangeLens</p>
<div>
<h1>{en_h}</h1>
<p>{en_p}</p>
</div>
<div class="other" lang="de">
<h1>{de_h}</h1>
<p>{de_p}</p>
</div>
<form method="post">
<input type="hidden" name="token" value="{token}">
<button type="submit"><span>{en_button}</span> · <span lang="de">{de_button}</span></button>
</form>
<p class="meta">{en_note}
<span lang="de">{de_note}</span></p>
</main>
</body>
</html>
"""


def page(copy: dict, token: str) -> HTMLResponse:
    """The one-button page for a token whose form was checked. It never holds an address."""
    values = {name: escape(text, quote=True) for name, text in copy.items()}
    return HTMLResponse(_PAGE.format(token=escape(token, quote=True), **values), headers=PAGE_HEADERS)


def to_landing(landing_url: str, target: str, headers=None) -> RedirectResponse:
    """`303` to a state of the landing page. The address this answers may hold a token: no referrer."""
    return RedirectResponse(landing_url + target, status_code=303,
                            headers={**(headers or {}), "Referrer-Policy": "no-referrer"})


def client_key(request: Request) -> str:
    """What the early-bird limits count a client by: its IPv4 address, or its IPv6 /64 network."""
    return network_key(client_ip(request))


def over_minute_limit(request: Request) -> Optional[dict]:
    """Count one request to a link route; the `Retry-After` headers when the client is over the limit."""
    settings = request.app.state.settings
    try:
        limiter(request).check("early-bird-ip", client_key(request), settings.rate_limit_ip_per_minute, MINUTE)
    except ApiError as exc:
        return dict(exc.headers or {})
    return None


async def counted_body(request: Request) -> tuple[Optional[dict], Optional[bytes]]:
    """For a `POST`: (the limit's headers when over it, the body or None when it is over `MAX_BODY`). The
    request is counted before any of the body is read."""
    limited = await run_in_threadpool(over_minute_limit, request)
    if limited is not None:
        return limited, None
    return None, await read_body(request, MAX_BODY)


async def read_body(request: Request, cap: int) -> Optional[bytes]:
    """The body up to a route's own small cap (the app-wide cap is sized for documents), or None when it
    is larger."""
    length = request.headers.get("content-length")
    if length is not None and (not length.isdigit() or int(length) > cap):
        return None
    chunks, seen = [], 0
    async for chunk in request.stream():
        seen += len(chunk)
        if seen > cap:
            return None
        chunks.append(chunk)
    return b"".join(chunks)


def form_token(request: Request, raw: bytes) -> Optional[str]:
    """The one `token` field of a urlencoded form, undecoded: a token has no character a browser would
    encode, so anything that needed decoding is not one."""
    if request.headers.get("content-type", "").split(";")[0].strip().lower() != FORM:
        return None
    try:
        fields = [pair.partition("=") for pair in raw.decode("ascii").split("&")]
    except UnicodeDecodeError:
        return None
    values = [value for name, _, value in fields if name == "token"]
    return values[0] if len(values) == 1 else None
