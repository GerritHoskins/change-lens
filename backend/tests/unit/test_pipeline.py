"""Parse provenance and the cost meter (no Docker needed). Stages: test_align_compare, test_verify_report."""
from decimal import Decimal

import pytest

from changelens.config import Limits
from changelens.metering import CeilingReached, CostMeter
from changelens.pipeline.parse import parse
from changelens.pipeline.types import ParsedDocument, ParseRejected
from helpers import make_pdf

LIMITS = Limits()


def text_doc(lines, sep="\n"):
    return parse(sep.join(lines).encode("utf-8"), "text", LIMITS)


def test_text_is_kept_exactly_and_locators_round_trip():
    raw = "﻿  First line\r\n\r\nSecond  line \r\nThird\rFourth"
    doc = parse(raw.encode("utf-8"), "text", LIMITS)
    assert doc.pages == [raw]  # no newline or BOM normalisation: 07 §4 offsets index the exact text
    assert [b.text for b in doc.blocks] == ["First line", "Second  line", "Third", "Fourth"]
    for b in doc.blocks:
        assert doc.slice(b.locator) == raw[b.locator.char_start:b.locator.char_end] == b.text
        assert b.locator.page is None and not b.hidden


def test_text_must_be_utf8_and_within_limits():
    for data, limits, code in ((b"caf\xe9", LIMITS, "not_utf8"), (b"one two three", Limits(max_text_words=2), "limit_exceeded_words"),
                               (b"x" * 20, Limits(max_text_bytes=10), "limit_exceeded_bytes")):
        with pytest.raises(ParseRejected) as e:
            parse(data, "text", limits)
        assert e.value.code == code


def test_pdf_locators_are_per_page_pdfium_offsets():
    data = make_pdf([["Alpha one", "Alpha two"], [], ["Gamma three"]])
    doc = parse(data, "pdf", LIMITS)
    assert doc.page_count == 3 and len(doc.pages) == 3
    assert "\r\n" in doc.pages[0]  # PDFium's own line endings are kept
    assert [(b.text, b.locator.page) for b in doc.blocks] == [("Alpha one", 1), ("Alpha two", 1), ("Gamma three", 3)]
    assert doc.blocks[1].locator.char_start == len("Alpha one\r\n")
    assert doc.blocks[2].locator.char_start == 0  # offsets restart on each page
    for b in doc.blocks:
        assert doc.slice(b.locator) == b.text
    assert [(w.code, w.page) for w in doc.warnings] == [("no_text_layer", 2)]


def test_pdf_rejections():
    for data, limits, code in ((make_pdf([[], []]), LIMITS, "no_text_layer"),
                               (make_pdf([["x"]] * 3), Limits(max_pdf_pages=2), "limit_exceeded_pages"),
                               (make_pdf([["x " * 30]]), Limits(max_text_words=10), "limit_exceeded_words"),
                               (make_pdf([["long line " * 20]]), Limits(max_extracted_chars=50), "limit_exceeded_text"),
                               (b"%PDF-1.7 not really", LIMITS, "malformed_pdf")):
        with pytest.raises(ParseRejected) as e:
            parse(data, "pdf", limits)
        assert e.value.code == code


def test_json_and_stored_round_trip():
    doc = parse(make_pdf([["Alpha"], ["Beta"]]), "pdf", LIMITS)
    again = ParsedDocument.from_json(doc.to_json())
    assert again.blocks == doc.blocks and again.pages == doc.pages and again.warnings == doc.warnings


def test_meter_checks_before_each_call():
    meter = CostMeter(Decimal("1.00"))
    meter.check(Decimal("1.00"))
    meter.record(Decimal("0.70"))
    with pytest.raises(CeilingReached):
        meter.check(Decimal("0.31"))
    assert meter.total == Decimal("0.70") and meter.calls == 1
