"""Placeholder parse and compare, the stage interfaces, and the cost ceiling (no Docker needed)."""
from decimal import Decimal

import pytest

from changelens.config import Limits
from changelens.llm import FakeLlm, MeteredLlm
from changelens.metering import CeilingReached, CostMeter
from changelens.pipeline import stages
from changelens.pipeline.parse import ParseRejected, parse
from changelens.pipeline.types import ParsedDocument
from helpers import EARLIER_LINES, LATER_LINES, make_pdf

LIMITS = Limits()


def text_doc(lines, sep="\n"):
    return parse(sep.join(lines).encode("utf-8"), "text", LIMITS)


def test_text_locators_round_trip():
    doc = parse(b"\xef\xbb\xbf  First line\r\n\r\nSecond  line \r\nThird", "text", LIMITS)
    assert [b.text for b in doc.blocks] == ["First line", "Second  line", "Third"]
    for b in doc.blocks:
        assert doc.text[b.locator.char_start:b.locator.char_end] == b.text
        assert b.locator.page is None


def test_text_must_be_utf8():
    with pytest.raises(ParseRejected) as e:
        parse(b"caf\xe9", "text", LIMITS)
    assert e.value.code == "not_utf8"


def test_pdf_locators_carry_page_and_round_trip():
    doc = parse(make_pdf([["Alpha one", "Alpha two"], [], ["Gamma three"]]), "pdf", LIMITS)
    assert doc.page_count == 3
    assert [(b.text, b.locator.page) for b in doc.blocks] == [("Alpha one", 1), ("Alpha two", 1), ("Gamma three", 3)]
    for b in doc.blocks:
        assert doc.text[b.locator.char_start:b.locator.char_end] == b.text
    assert [(w.code, w.page) for w in doc.warnings] == [("no_text_layer", 2)]


def test_pdf_without_any_text_is_rejected():
    with pytest.raises(ParseRejected) as e:
        parse(make_pdf([[], []]), "pdf", LIMITS)
    assert e.value.code == "no_text_layer"


def test_parse_limits():
    with pytest.raises(ParseRejected) as e:
        parse(make_pdf([["x"]] * 3), "pdf", Limits(max_pdf_pages=2))
    assert e.value.code == "limit_exceeded_pages"
    with pytest.raises(ParseRejected) as e:
        parse(b"one two three", "text", Limits(max_text_words=2))
    assert e.value.code == "limit_exceeded_words"
    with pytest.raises(ParseRejected):
        parse(b"%PDF-1.7 not really", "pdf", LIMITS)


def test_stored_round_trip():
    doc = parse(make_pdf([["Alpha"], ["Beta"]]), "pdf", LIMITS)
    again = ParsedDocument.from_stored("pdf", doc.text, doc.blocks_json(), doc.page_count, [])
    assert again.blocks == doc.blocks


def test_placeholder_compare_reports_both_sides():
    earlier, later = text_doc(EARLIER_LINES), text_doc(LATER_LINES)
    drafts = stages.placeholder_compare(earlier, later)
    assert [d.change_type for d in drafts] == ["changed", "changed"]
    budget = drafts[0]
    assert [(e.side, e.quote) for e in budget.evidence] == [("earlier", "Budget: EUR 12,000"), ("later", "Budget: EUR 15,000")]
    for d in drafts:
        for ev in d.evidence:
            src = earlier if ev.side == "earlier" else later
            assert src.text[ev.locator.char_start:ev.locator.char_end] == ev.quote
    added = stages.placeholder_compare(text_doc(["a"]), text_doc(["a", "b"]))
    removed = stages.placeholder_compare(text_doc(["a", "b"]), text_doc(["a"]))
    assert [d.change_type for d in added] == ["added"] and added[0].evidence[0].side == "later"
    assert [d.change_type for d in removed] == ["removed"] and removed[0].evidence[0].side == "earlier"


def test_unimplemented_stages_are_explicit():
    doc = text_doc(["a"])
    llm = MeteredLlm(FakeLlm(Decimal("0")), CostMeter(Decimal("1")))
    for call in (lambda: stages.extract(doc, llm), lambda: stages.align([], [], llm),
                 lambda: stages.compare([], "complete", llm), lambda: stages.verify([], doc, doc)):
        with pytest.raises(NotImplementedError):
            call()


def test_meter_checks_before_each_call():
    meter = CostMeter(Decimal("1.00"))
    meter.check(Decimal("1.00"))
    meter.record(Decimal("0.70"))
    with pytest.raises(CeilingReached):
        meter.check(Decimal("0.31"))
    assert meter.total == Decimal("0.70") and meter.calls == 1


def test_report_stops_cleanly_at_the_ceiling():
    drafts = stages.placeholder_compare(text_doc(["a", "b", "c", "d", "e"]), text_doc(["A", "b", "C", "d", "E", "f"]))
    assert len(drafts) == 3
    fake = FakeLlm(Decimal("0.60"))
    meter = CostMeter(Decimal("1.50"))
    with pytest.raises(stages.ReportInterrupted) as stop:
        stages.report(drafts, MeteredLlm(fake, meter))
    assert len(stop.value.done) == 2 and stop.value.skipped == 1
    assert fake.calls == 2 and meter.total == Decimal("1.20") <= meter.ceiling
    assert all(f.explanation for f in stop.value.done)


def test_report_explains_every_finding_under_the_ceiling():
    drafts = stages.placeholder_compare(text_doc(EARLIER_LINES), text_doc(LATER_LINES))
    done = stages.report(drafts, MeteredLlm(FakeLlm(Decimal("0.01")), CostMeter(Decimal("1.50"))))
    assert len(done) == len(drafts) and all(f.explanation for f in done)
