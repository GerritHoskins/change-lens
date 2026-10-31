"""The `parse` stage (03 §9.3): original bytes -> ParsedDocument with locators, visibility and warnings.

`parse` is pure and runs in-process; the worker calls `sandbox.parse_sandboxed`, which runs PDFs
through `parse` in a capped child process. Text is decoded exactly (no newline or BOM changes), so
07 §4 offsets index straight into it.
"""
from __future__ import annotations

from changelens.config import Limits
from changelens.pipeline.pdf_parse import LINE_BREAK, parse_pdf
from changelens.pipeline.types import Block, Kind, Locator, ParsedDocument, ParseRejected

__all__ = ["ParseRejected", "decode_text", "parse", "parse_text"]
_STRIP = " \t\f\v﻿ "


def decode_text(data: bytes) -> str:
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        raise ParseRejected("not_utf8") from None


def parse_text(data: bytes, limits: Limits) -> ParsedDocument:
    if len(data) > limits.max_text_bytes:
        raise ParseRejected("limit_exceeded_bytes")
    text = decode_text(data)
    blocks: list[Block] = []
    pos = 0
    for m in list(LINE_BREAK.finditer(text)) + [None]:
        end = m.start() if m else len(text)
        line = text[pos:end]
        stripped = line.strip(_STRIP)
        if stripped:
            start = pos + len(line) - len(line.lstrip(_STRIP))
            blocks.append(Block(stripped, Locator(start, start + len(stripped))))
        if m:
            pos = m.end()
    return ParsedDocument("text", [text], blocks)


def parse(original: bytes, kind: Kind, limits: Limits) -> ParsedDocument:
    if kind == "text":
        doc = parse_text(original, limits)
    elif kind == "pdf":
        doc = parse_pdf(original, limits)
    else:
        raise ParseRejected("unsupported_type")
    if doc.word_count() > limits.max_text_words:
        raise ParseRejected("limit_exceeded_words")  # applies to PDFs too (03a P3)
    return doc
