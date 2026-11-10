"""Upload checks done before anything is stored (AC-20 basics, AD-3). The client's type is ignored."""
from __future__ import annotations

from changelens.api.errors import ApiError
from changelens.config import Limits

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
