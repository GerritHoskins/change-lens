"""PDF parse with provenance (I-1). Runs inside the sandbox child (`sandbox.py`), never in the API.

- Page text is PDFium's exact `get_text_range()` output; locators index into it (07 §4).
- Blocks are lines, split further where a run of words is hidden on an otherwise visible line.
- Visibility uses the eval rules (`pdf_ink.py`): hidden blocks carry a reason and an SA-9
  `hidden_text` warning, and are excluded from comparison input (AC-18). Rotated pages, a CropBox
  and an offset MediaBox are mapped and measured (I-1c); pages whose mapping disagrees with
  PDFium's or that are too large to render fail closed: their text is treated as hidden and the page is warned
  `visibility_unchecked`, which makes the comparison partial.
- Nothing in the document is executed or extracted: the PDFium build has no JavaScript engine,
  forms are never initialised, and attachments are only counted. Both are reported as warnings.
"""
from __future__ import annotations

import re
from contextlib import closing
from typing import Optional

import pypdfium2 as pdfium

from changelens.config import Limits
from changelens.pipeline.pdf_ink import PageInk, Unmeasurable
from changelens.pipeline.types import Block, Locator, ParsedDocument, ParseRejected, ParseWarning

LINE_BREAK = re.compile(r"\r\n|\n|\r")
WORD = re.compile(r"\S+")
ACTIVE = re.compile(rb"/(JavaScript|JS|Launch|SubmitForm|ImportData)(?![A-Za-z])")
AUTO_ACTION = re.compile(rb"/(OpenAction|AA)(?![A-Za-z])")
EMBEDDED = re.compile(rb"/(EmbeddedFiles?|RichMedia)(?![A-Za-z])")
LARGE_IMAGE_SHARE = 0.15  # 03a P3: larger image regions on text pages make the comparison partial


def lines(text: str):
    """(start, end) of each line, excluding the line break."""
    pos = 0
    for m in LINE_BREAK.finditer(text):
        yield pos, m.start()
        pos = m.end()
    yield pos, len(text)


def _block(page_text: str, start: int, end: int, page: int, reason: Optional[str]) -> Block:
    return Block(page_text[start:end], Locator(start, end, page), reason is not None, reason)


def line_blocks(page_text: str, start: int, end: int, page: int, ink: Optional[PageInk],
                unmeasurable: Optional[str]) -> list[Block]:
    words = [(m.start(), m.end()) for m in WORD.finditer(page_text, start, end)]  # absolute offsets
    if not words:
        return []
    first, last = words[0][0], words[-1][1]
    if ink is None:
        return [_block(page_text, first, last, page, unmeasurable)]
    reason = ink.hidden_reason(first, last)
    if reason or len(words) == 1:
        return [_block(page_text, first, last, page, reason)]
    # The line is visible as a whole; look for hidden word runs inside it (text injected into a line).
    runs: list[list] = []  # [start, end, reason]
    for s, e in words:
        r = ink.hidden_reason(s, e)
        if runs and (runs[-1][2] is None) == (r is None):
            runs[-1][1] = e
        else:
            runs.append([s, e, r])
    for run in runs:
        if run[2] is not None:
            # Confirm the run as a whole, and ignore runs without letters or digits (rules, dots).
            run[2] = ink.hidden_reason(run[0], run[1])
            if not any(c.isalnum() for c in page_text[run[0]:run[1]]):
                run[2] = None
    merged: list[list] = []
    for run in runs:
        if merged and merged[-1][2] is None and run[2] is None:
            merged[-1][1] = run[1]
        else:
            merged.append(run)
    return [_block(page_text, s, e, page, r) for s, e, r in merged]


def document_warnings(pdf, data: bytes) -> list[ParseWarning]:
    raw = pdf.raw
    warnings = []
    if pdfium.raw.FPDFDoc_GetJavaScriptActionCount(raw) > 0 or ACTIVE.search(data):
        warnings.append(ParseWarning("active_content"))  # never executed: no JS engine, no forms
    if AUTO_ACTION.search(data):
        warnings.append(ParseWarning("auto_action"))
    if pdfium.raw.FPDFDoc_GetAttachmentCount(raw) > 0 or EMBEDDED.search(data):
        warnings.append(ParseWarning("embedded_files"))  # never extracted
    return warnings


def image_warnings(page, page_no: int, has_text: bool) -> list[ParseWarning]:
    width, height = page.get_size()
    area = max(width * height, 1.0)
    out = []
    for obj in page.get_objects(filter=[pdfium.raw.FPDF_PAGEOBJ_IMAGE]):
        left, bottom, right, top = obj.get_bounds()
        share = max(0.0, min(right, width) - max(left, 0)) * max(0.0, min(top, height) - max(bottom, 0)) / area
        if has_text and share > LARGE_IMAGE_SHARE:
            out.append(ParseWarning("unextracted_region", page_no))
        elif share > 0:
            out.append(ParseWarning("image_region", page_no))
    return out


def parse_pdf(data: bytes, limits: Limits) -> ParsedDocument:
    if len(data) > limits.max_pdf_bytes:
        raise ParseRejected("limit_exceeded_bytes")
    try:
        pdf = pdfium.PdfDocument(data)
        spare = pdfium.PdfDocument(data)  # second copy: its pages lose their text for the cover check
    except pdfium.PdfiumError:
        raise ParseRejected("malformed_pdf") from None
    with closing(pdf), closing(spare):
        n = len(pdf)
        if n == 0:
            raise ParseRejected("malformed_pdf")
        if n > limits.max_pdf_pages:
            raise ParseRejected("limit_exceeded_pages")  # before any page is parsed
        warnings = document_warnings(pdf, data)
        pages: list[str] = []
        blocks: list[Block] = []
        chars = 0
        for i in range(n):
            page_no = i + 1
            with closing(pdf[i]) as page, closing(page.get_textpage()) as tp, closing(spare[i]) as spare_page:
                text = tp.get_text_range()
                chars += len(text)
                if chars > limits.max_extracted_chars:
                    raise ParseRejected("limit_exceeded_text")
                pages.append(text)
                if not text.strip():
                    warnings.append(ParseWarning("no_text_layer", page_no))
                    warnings += image_warnings(page, page_no, False)
                    continue
                ink, unmeasurable = None, None
                try:
                    ink = PageInk(page, tp, limits.max_render_pixels, spare_page)
                except Unmeasurable as u:
                    unmeasurable = u.code
                    warnings.append(ParseWarning("visibility_unchecked", page_no))
                for start, end in lines(text):
                    for b in line_blocks(text, start, end, page_no, ink, unmeasurable):
                        blocks.append(b)
                        if b.hidden and unmeasurable is None:
                            warnings.append(ParseWarning("hidden_text", page_no, b.locator.char_start, b.locator.char_end))
                warnings += image_warnings(page, page_no, True)
        if all(not p.strip() for p in pages):
            raise ParseRejected("no_text_layer")  # scanned PDF (02 §2, 03a P3)
        return ParsedDocument("pdf", pages, blocks, n, warnings)
