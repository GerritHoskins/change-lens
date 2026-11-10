"""Development-only regressions for distinct facts sharing one evidence sentence.

These synthetic examples exercise current stages without a model call or held-out data.
"""
from dataclasses import replace

import pytest

from changelens.config import Limits
from changelens.pipeline.align import align
from changelens.pipeline.compare import compare
from changelens.pipeline.parse import parse
from changelens.pipeline.types import ExtractedFact, FactPair, Locator
from changelens.pipeline.verify import verify


class NoModel:
    def structured(self, schema, system, data):
        raise AssertionError(f"unexpected {schema} call")


def fact(text, category, subject, value):
    return ExtractedFact(category, text, value, Locator(0, len(text)), "ok", .9,
                         subject=subject, context=text)


def pairs(old, new, values):
    return [FactPair("matched", fact(old, category, subject, before), fact(new, category, subject, after))
            for category, subject, before, after in values]


@pytest.mark.parametrize("before,after,changed", [
    (("EUR 800", "12 June", "1080p"), ("EUR 900", "12 June", "1080p"), {"budget"}),
    (("EUR 800", "12 June", "1080p"), ("EUR 800", "15 June", "1080p"), {"date_deadline"}),
    (("EUR 800", "12 June", "1080p"), ("EUR 800", "12 June", "4K"), {"deliverable"}),
    (("EUR 800", "12 June", "1080p"), ("EUR 900", "15 June", "1080p"), {"budget", "date_deadline"}),
    (("EUR 800", "12 June", "1080p"), ("EUR 900", "15 June", "4K"), {"budget", "date_deadline", "deliverable"}),
])
def test_only_changed_topics_survive_shared_sentence(before, after, changed):
    old, new = (f"The video in {size} costs {fee} and is due by {date}." for fee, date, size in (before, after))
    values = [(category, subject, a, b) for category, subject, a, b in
              zip(("budget", "date_deadline", "deliverable"), ("fee", "delivery", "video format"), before, after)]
    matched = pairs(old, new, values)
    # Exercise actual deterministic alignment, compare and evidence verification together.
    aligned = align([p.earlier for p in matched], [p.later for p in matched], NoModel())
    docs = [parse(text.encode(), "text", Limits()) for text in (old, new)]
    result = verify(compare(aligned, "complete", NoModel()), *docs)
    assert {finding.category for finding in result.findings} == changed
    assert all(f.change_type == "changed" for f in result.findings)
    assert result.withheld_count == 0
    assert not result.unexplained


def test_fee_only_edit_does_not_invent_deadline_change():
    old, new = "Fee EUR 800 is payable by 12 June.", "Fee EUR 900 is payable by 12 June."
    matched = pairs(old, new, [("budget", "fee", "EUR 800", "EUR 900"),
                               ("date_deadline", "payment deadline", "12 June", "12 June")])
    result = compare(matched, "complete", NoModel())
    assert [(f.category, f.old_value, f.new_value) for f in result] == [("budget", "EUR 800", "EUR 900")]


@pytest.mark.parametrize("qualifier", ["must", "may", "not", "only", "estimated"])
def test_unchanged_value_does_not_hide_context_qualifier_changes(qualifier):
    old = "The video in 1080p costs EUR 800 and is due by 12 June."
    new = f"The video in 1080p costs EUR 900 and is {qualifier} due by 12 June."
    matched = pairs(old, new, [("budget", "fee", "EUR 800", "EUR 900"),
                               ("date_deadline", "deadline", "12 June", "12 June")])
    assert {f.category for f in compare(matched, "complete", NoModel())} == {"budget", "date_deadline"}


@pytest.mark.parametrize("mutation", ["absent_value", "ungrounded", "repeated", "overlap", "ambiguous",
                                      "different_context", "different_subject", "missing_sibling"])
def test_uncertain_attribution_keeps_full_context_guard(mutation):
    old, new = "Fee EUR 800 is payable by 12 June.", "Fee EUR 900 is payable by 12 June."
    own_value = "12 June"
    if mutation == "absent_value":
        own_value = ""
    if mutation == "ungrounded":
        own_value = "13 June"
    if mutation == "repeated":
        old, new = "Fee EUR 800 plus EUR 800 is due by 12 June.", "Fee EUR 900 plus EUR 900 is due by 12 June."
    if mutation == "overlap":
        own_value = "EUR"
    matched = pairs(old, new, [("budget", "fee", "EUR 800", "EUR 900"),
                               ("date_deadline", "deadline", own_value, own_value)])
    if mutation == "ambiguous":
        matched[0] = replace(matched[0], earlier=replace(matched[0].earlier, status="ambiguous", ambiguity="ambiguous_value"))
    if mutation == "different_context":
        matched[0] = replace(matched[0], earlier=replace(matched[0].earlier, context="Another fee is EUR 800."))
    if mutation == "different_subject":
        matched[0] = replace(matched[0], later=replace(matched[0].later, subject="another fee"))
    if mutation == "missing_sibling":
        matched = matched[1:]
    assert "date_deadline" in {f.category for f in compare(matched, "complete", NoModel())}


def test_equal_values_alone_cannot_hide_unattributed_numeric_edit():
    old, new = "Delivery is due by 12 June after 2 reviews.", "Delivery is due by 12 June after 3 reviews."
    matched = pairs(old, new, [("date_deadline", "deadline", "12 June", "12 June")])
    assert [f.change_type for f in compare(matched, "complete", NoModel())] == ["changed"]


def test_other_unattributed_context_wording_is_not_masked_with_a_fee_edit():
    old, new = "Fee EUR 800 is due before 12 June.", "Fee EUR 900 is due after 12 June."
    matched = pairs(old, new, [("budget", "fee", "EUR 800", "EUR 900"),
                               ("date_deadline", "deadline", "12 June", "12 June")])
    assert {f.category for f in compare(matched, "complete", NoModel())} == {"budget", "date_deadline"}


def test_contradiction_in_an_otherwise_unchanged_topic_still_needs_review():
    old, new = "Fee EUR 800 is due by 12 June.", "Fee EUR 900 is due by 12 June."
    matched = pairs(old, new, [("budget", "fee", "EUR 800", "EUR 900"),
                               ("date_deadline", "deadline", "12 June", "12 June")])
    matched[1] = replace(matched[1], earlier=replace(matched[1].earlier, status="ambiguous", ambiguity="contradiction"))
    results = {f.category: f for f in compare(matched, "complete", NoModel())}
    assert results["date_deadline"].change_type == "uncertain"
    assert results["date_deadline"].uncertainty == "contradiction"
