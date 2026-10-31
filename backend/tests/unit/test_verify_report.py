"""I-5 verify + report: exact quotes, withholding, needs review, unexplained differences, wording
guards, grouping and the cost ceiling. Mocked llm only (no Docker needed)."""
from __future__ import annotations

from dataclasses import replace
from decimal import Decimal

import pytest

from changelens.config import Limits
from changelens.llm import FakeLlm, MeteredLlm
from changelens.llm.errors import LlmOutputInvalid, LlmUnavailable
from changelens.llm.schemas import EXPLANATION, validate
from changelens.metering import CostMeter
from changelens.pipeline.align import align
from changelens.pipeline.compare import compare
from changelens.pipeline.extract import extract
from changelens.pipeline.parse import parse
from changelens.pipeline.report import report, template
from changelens.pipeline.types import DraftFinding, Evidence
from changelens.pipeline.verify import block_diff, verify
from helpers import EARLIER_LINES, LATER_LINES


def doc(lines):
    return parse("\n".join(lines).encode("utf-8"), "text", Limits())


def ev(d, side, text):
    i = d.pages[0].index(text)
    return Evidence(side, type(d.blocks[0].locator)(i, i + len(text)), text)


E, L = doc(EARLIER_LINES), doc(LATER_LINES)


def budget(**kw):
    return DraftFinding("changed", "quantity", [ev(E, "earlier", "EUR 12,000"), ev(L, "later", "EUR 15,000")], **kw)


class Said:
    """Answers every Explanation call with fixed text (or raises it) and counts the calls."""

    def __init__(self, out):
        self.out, self.calls = out, 0

    def structured(self, schema, system, data):
        assert schema == "Explanation" and all(d.startswith(("EARLIER: ", "LATER: ")) for d in data[1:])
        self.calls += 1
        if isinstance(self.out, Exception):
            raise self.out
        return {"explanation": self.out}


# verify -------------------------------------------------------------------------------------------

def test_exact_quotes_are_kept_and_anything_else_is_withheld():
    tampered = budget()
    tampered.evidence[1] = replace(tampered.evidence[1], quote="EUR 16,000")
    one_sided = DraftFinding("changed", "quantity", [ev(L, "later", "EUR 15,000")])
    absence_quote = DraftFinding("removed", "deliverable", [ev(E, "earlier", "Hosting"), ev(L, "later", "Copywriting")])
    wrong_side = DraftFinding("added", "deliverable", [ev(E, "earlier", "Hosting")])
    no_evidence = DraftFinding("added", "deliverable", [])
    out = verify([budget(), tampered, one_sided, absence_quote, wrong_side, no_evidence], E, L)
    assert [f.change_type for f in out.findings] == ["changed"] and out.withheld_count == 5


def test_uncertain_and_low_confidence_need_review():
    unsure = DraftFinding("uncertain", "deliverable", [ev(E, "earlier", "Hosting")], note="scope_unknown")
    out = verify([unsure, budget(confidence=0.3), budget(confidence=0.6)], E, L)
    assert [f.group for f in out.findings] == ["needs_review", "needs_review", "other"]


def test_unexplained_differences_and_equivalence_does_not_explain():
    changed, moved = block_diff(E, L)
    assert {(x.side, x.quote) for x in changed} == {
        ("earlier", "Budget: EUR 12,000"), ("later", "Budget: EUR 15,000"),
        ("earlier", "Pages: home, about, contact"), ("later", "Pages: home, about, contact, blog"),
        ("earlier", "Hosting is provided by the client"), ("later", "Copywriting is included")} and moved == []
    pages = DraftFinding("equivalent", "deliverable", [ev(E, "earlier", "home, about, contact"),
                                                        ev(L, "later", "home, about, contact, blog")])
    out = verify([budget(), pages], E, L)
    assert {(x.side, x.quote) for x in out.unexplained} == {
        ("earlier", "Pages: home, about, contact"), ("later", "Pages: home, about, contact, blog"),
        ("earlier", "Hosting is provided by the client"), ("later", "Copywriting is included")}


def test_moved_blocks_are_presentation_only_and_hidden_blocks_are_ignored():
    a, b = doc(["one", "two", "three"]), doc(["three", "one", "two", "secret"])
    b.blocks[3] = replace(b.blocks[3], hidden=True, hidden_reason="no_ink")
    out = verify([], a, b)
    assert out.unexplained == []
    assert {(x.side, x.quote) for x in out.presentation_only} == {("earlier", "three"), ("later", "three")}


def test_list_marker_and_case_edits_are_presentation_only():
    a, b = doc(["- Logo as SVG", "1. Brand book", "Due Friday"]), doc(["* Logo as SVG", "a) brand book", "Due Monday"])
    changed, moved = block_diff(a, b)
    assert {x.quote for x in moved} == {"- Logo as SVG", "* Logo as SVG", "1. Brand book", "a) brand book"}
    assert {x.quote for x in changed} == {"Due Friday", "Due Monday"}


# report -------------------------------------------------------------------------------------------

@pytest.mark.parametrize("change_type,note,words", [
    ("removed", "absent_from_replacement", "does not mean it was cancelled"),
    ("not_addressed", "not_addressed_by_partial_update", "marked as partial"),
    ("uncertain", "scope_unknown", "scope of this update is unknown")])
def test_omissions_are_templated_without_a_model_call(change_type, note, words):
    f = DraftFinding(change_type, "deliverable", [ev(E, "earlier", "Hosting is provided by the client")], note=note)
    [out], skipped = report([f], Said("should not be used"))
    assert words in out.explanation and skipped == 0


def test_model_wording_is_used_when_it_stays_with_the_evidence():
    llm = Said("The budget rises from EUR 12,000 to EUR 15,000.")
    validate({"explanation": llm.out}, EXPLANATION)
    [out], _ = report([budget()], llm)
    assert out.explanation == llm.out and llm.calls == 1 and out.group == "prioritised"


@pytest.mark.parametrize("said", ["The budget rises to EUR 18,000.", "The old budget was cancelled.", "",
                                  LlmOutputInvalid("schema"), LlmUnavailable("timeout")])
def test_bad_or_failed_wording_falls_back_to_the_template(said):
    [out], skipped = report([budget()], Said(said))
    assert out.explanation == template(budget()) == "Changed from “EUR 12,000” to “EUR 15,000”." and skipped == 0


def test_groups_and_rank():
    style = DraftFinding("equivalent", "deliverable", [ev(E, "earlier", "Pages"), ev(L, "later", "Pages")])
    unsure = DraftFinding("uncertain", "deliverable", [ev(E, "earlier", "Hosting")], uncertainty="ambiguous_match",
                          group="needs_review")
    other = DraftFinding("added", "other_material", [ev(L, "later", "Copywriting is included")])
    out, _ = report([style, unsure, other, budget()], Said("A change."))
    assert [(f.change_type, f.group, f.priority) for f in out] == [
        ("changed", "prioritised", 0), ("uncertain", "needs_review", 1), ("equivalent", "other", 2), ("added", "other", 3)]
    assert out[1].explanation.startswith("Needs your review: it is not clear which passage")


def test_ceiling_templates_the_rest_instead_of_dropping_them():
    fake, meter = FakeLlm(Decimal("0.60")), CostMeter(Decimal("1.50"))
    out, skipped = report([budget(), budget(), budget()], MeteredLlm(fake, meter))
    assert len(out) == 3 and skipped == 1 and all(f.explanation for f in out)
    assert fake.calls == 2 and meter.total == Decimal("1.20") <= meter.ceiling


# the whole fact pipeline with the fake llm (what the worker runs in tests) ------------------------

def test_fake_pipeline_end_to_end():
    llm = MeteredLlm(FakeLlm(Decimal("0.01")), CostMeter(Decimal("1.50")))
    facts = [extract(d, llm).facts for d in (E, L)]
    checked = verify(compare(align(facts[0], facts[1], llm), "complete", llm), E, L)
    out, skipped = report(checked.findings, llm)
    assert [(f.change_type, [x.quote for x in f.evidence]) for f in out] == [
        ("changed", ["Budget: EUR 12,000", "Budget: EUR 15,000"]),
        ("changed", ["Pages: home, about, contact", "Pages: home, about, contact, blog"]),
        ("removed", ["Hosting is provided by the client"]),
        ("added", ["Copywriting is included"])]
    assert checked.withheld_count == 0 and checked.unexplained == [] and skipped == 0


def test_a_one_sided_finding_whose_sentence_is_on_the_other_side_is_dropped():
    """Extraction typed the same sentence differently in each version: no addition or omission (AC-6)."""
    e = doc(["- Produce 3 short videos for social media.", "Budget: EUR 12,000"])
    l = doc(["Budget: EUR 12,000", "* produce 3 short videos for social media.", "Write 2 blog posts."])
    moved = DraftFinding("added", "quantity", [ev(l, "later", "produce 3 short videos for social media.")])
    gone = DraftFinding("removed", "deliverable", [ev(e, "earlier", "Produce 3 short videos for social media.")])
    new = DraftFinding("added", "deliverable", [ev(l, "later", "Write 2 blog posts.")])
    out = verify([moved, gone, new], e, l)
    assert out.findings == [new] and out.withheld_count == 0
    assert [x.quote for x in out.unexplained] == []  # the blog line is explained by the kept addition


def test_part_of_a_longer_sentence_is_not_on_the_other_side():
    e = doc(["Deliver the logo."])
    l = doc(["Deliver the logo files."])
    gone = DraftFinding("removed", "deliverable", [ev(e, "earlier", "Deliver the logo.")])
    assert verify([gone], e, l).findings == [gone]
