"""The early-bird list's removal link: its token, its URL and the mail headers that carry it.

A token is `<signup id>.<mac>`: the row's UUID and a hex HMAC-SHA256 over
`early-bird-unsubscribe:<signup id>` with `CHANGELENS_EARLY_BIRD_UNSUBSCRIBE_KEY`. Nothing is stored for it
and it never expires: it works as long as the row exists, pending or confirmed, and the key is unchanged.
The key is the list's own, not the rate-limit key: replacing that one is documented as harmless, and it
would end every removal link already mailed.

The token names no address. Whoever holds it can remove that one address and learn nothing else.
Standard library only; nothing here logs.
"""
from __future__ import annotations

import hashlib
import hmac
import re
import uuid
from typing import Optional

PATH = "/early-bird/unsubscribe"
_PREFIX = "early-bird-unsubscribe:"
# Canonical lower-case UUID, a dot, 64 lower-case hex digits; nothing else gets as far as the MAC.
_TOKEN = re.compile(r"([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\.([0-9a-f]{64})")


def _mac(key: str, signup_id: str) -> str:
    return hmac.new(key.encode(), (_PREFIX + signup_id).encode(), hashlib.sha256).hexdigest()


def unsubscribe_token(key: str, signup_id: uuid.UUID) -> str:
    if not isinstance(signup_id, uuid.UUID):
        raise TypeError("signup_id must be a UUID")
    return "%s.%s" % (signup_id, _mac(key, str(signup_id)))


def verify_unsubscribe_token(key: str, token) -> Optional[uuid.UUID]:
    """The signup ID a token was made for, or None for anything that isn't a token made with `key`. The
    format is checked first, the MAC in constant time."""
    if not isinstance(token, str):
        return None
    match = _TOKEN.fullmatch(token)
    if match is None or not hmac.compare_digest(match.group(2), _mac(key, match.group(1))):
        return None
    return uuid.UUID(match.group(1))


def unsubscribe_url(public_api_url: str, key: str, signup_id: uuid.UUID) -> str:
    """The removal link for one row: the visible link in a list mail's body and its `List-Unsubscribe` URL."""
    return public_api_url.rstrip("/") + PATH + "?token=" + unsubscribe_token(key, signup_id)


def list_headers(url: str) -> dict:
    """The two headers every mail to the list carries (RFC 2369, RFC 8058 one-click)."""
    return {"List-Unsubscribe": "<%s>" % url, "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"}
