"""Upload checks done before anything is stored (AC-20 basics, AD-3). The client's type is ignored."""
from __future__ import annotations

import uuid

from fastapi import Depends, Request

from changelens.api.auth import current_tenant
from changelens.api.errors import ApiError
from changelens.config import Limits
from changelens.domain.bounds import bound_reached

# Recognised binary formats that are not accepted in I-22 (image parsing is I-1b, image import I-16).
_BINARY_MAGIC = (b"\x89PNG", b"\xff\xd8\xff", b"GIF8", b"PK\x03\x04", b"\xd0\xcf\x11\xe0", b"RIFF", b"BM")


def sniff(data: bytes) -> str:
    """Return 'pdf' or 'text' from the bytes themselves, or raise unsupported_type."""
    if data.startswith(b"%PDF-"):
        return "pdf"
    if not data or data.startswith(_BINARY_MAGIC) or b"\x00" in data:
        raise ApiError(415, "unsupported_type")
    try:
        data.decode("utf-8")
    except UnicodeDecodeError:
        raise ApiError(415, "unsupported_type", "text must be UTF-8") from None
    return "text"


def check_limits(data: bytes, kind: str, limits: Limits) -> None:
    """Size and word limits only. The API never opens a PDF: page count, extracted-text size and
    malformed files are checked by the parse sandbox in the worker (I-1)."""
    if kind == "text":
        if len(data) > limits.max_text_bytes:
            raise ApiError(413, "limit_exceeded", "bytes")
        if len(data.decode("utf-8", "replace").split()) > limits.max_text_words:
            raise ApiError(413, "limit_exceeded", "words")
        return
    if len(data) > limits.max_pdf_bytes:
        raise ApiError(413, "limit_exceeded", "bytes")


def check_label(label: str | None, limits: Limits) -> str:
    label = (label or "").strip()
    if not label or len(label) > limits.max_label_chars:
        raise ApiError(422, "invalid_request", "label must be 1-%d characters" % limits.max_label_chars)
    return label


async def upload_slot(request: Request, tenant: uuid.UUID = Depends(current_tenant)):
    """The upload routes' tenant, with one of the process's upload slots held until the route is done (LR-10).
    It runs after GUARD and before the route reads the body, so a refused request holds no document in memory."""
    slots = request.app.state.upload_slots
    if not slots.take(tenant):
        raise ApiError(429, "rate_limited", headers={"Retry-After": "2"})
    try:
        yield tenant
    finally:
        slots.release(tenant)


def check_bounds(repo, settings, *, new_versions: int, new_bytes: int, new_comparison: bool = False) -> None:
    """The account's bounds on queued work and stored bytes (LR-10), inside the transaction that would add the
    rows. The detail names the bound and never echoes input."""
    repo.lock_account()
    reason = bound_reached(repo, settings, new_versions=new_versions, new_bytes=new_bytes,
                           new_comparison=new_comparison)
    if reason is not None:
        raise ApiError(429, "account_limit_reached", reason)
