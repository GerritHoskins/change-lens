"""Placeholder `parse` stage: text decode, and PDF text through pypdfium2 with page + offset locators.

I-1 replaces this with the full parser (hidden text, image regions, sandbox caps). It is still a pure
function over bytes: no database, storage, network or ambient config.
"""
from __future__ import annotations

from contextlib import closing

import pypdfium2 as pdfium

from changelens.config import Limits
from changelens.pipeline.types import Block, Kind, Locator, ParsedDocument, ParseWarning


class ParseRejected(Exception):
    """The version cannot be used; `code` is a stable, content-free reason."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _line_blocks(text: str, base: int, page, blocks: list[Block]) -> None:
    pos = 0
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped:
            start = base + pos + (len(line) - len(line.lstrip()))
            blocks.append(Block(stripped, Locator(start, start + len(stripped), page)))
        pos += len(line) + 1


def decode_text(data: bytes) -> str:
    if data.startswith(b"\xef\xbb\xbf"):
        data = data[3:]
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        raise ParseRejected("not_utf8") from None
    return text.replace("\r\n", "\n").replace("\r", "\n")


def parse(original: bytes, kind: Kind, limits: Limits) -> ParsedDocument:
    if kind == "text":
        text = decode_text(original)
        blocks: list[Block] = []
        _line_blocks(text, 0, None, blocks)
        doc = ParsedDocument("text", text, blocks)
    elif kind == "pdf":
        doc = _parse_pdf(original, limits)
    else:
        raise ParseRejected("unsupported_type")
    if len(doc.text.split()) > limits.max_text_words:
        raise ParseRejected("limit_exceeded_words")
    return doc


def _parse_pdf(original: bytes, limits: Limits) -> ParsedDocument:
    try:
        pdf = pdfium.PdfDocument(original)
    except pdfium.PdfiumError:
        raise ParseRejected("malformed_pdf") from None
    with closing(pdf):
        n = len(pdf)
        if n > limits.max_pdf_pages:
            raise ParseRejected("limit_exceeded_pages")
        parts: list[str] = []
        blocks: list[Block] = []
        warnings: list[ParseWarning] = []
        base = 0
        for i in range(n):
            page = pdf[i]
            with closing(page), closing(page.get_textpage()) as tp:
                page_text = tp.get_text_range().replace("\r\n", "\n").replace("\r", "\n")
            if not page_text.strip():
                warnings.append(ParseWarning("no_text_layer", i + 1))
            _line_blocks(page_text, base, i + 1, blocks)
            parts.append(page_text)
            base += len(page_text) + 1  # pages joined by "\n"
        if n and len(warnings) == n:
            raise ParseRejected("no_text_layer")
        return ParsedDocument("pdf", "\n".join(parts), blocks, n, warnings)
