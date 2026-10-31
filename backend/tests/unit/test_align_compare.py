"""I-3 align + compare: value guards, deterministic alignment, AC-6/7/8. Mocked llm only."""
from __future__ import annotations

import pytest

from changelens.llm.schemas import FACT_MATCHES, SAME_MEANING, validate
from changelens.pipeline.align import align, mark_contradictions
from changelens.pipeline.compare import compare
from changelens.pipeline.extract import sentence_of
from changelens.pipeline.types import ExtractedFact, FactPair, Locator
from changelens.pipeline.values import canonical, figures, qualifiers, qualifiers_differ


def fact(text, type_="quantity", subject="budget", value=None, ambiguity=None, context=""):
    return ExtractedFact(type_, text, value if value is not None else text, Locator(0, len(text)),
                         "ambiguous" if ambiguity else "ok", 0.9, subject, ambiguity, context)


class Script:
    """Returns queued outputs per schema and records what it was sent."""

    def __init__(self, **outs):
        self.outs, self.sent = outs, []

    def structured(self, schema, system, data):
        self.sent.append((schema, list(data)))
        return self.outs[schema]


class Never:
    def structured(self, schema, system, data):
        raise AssertionError(f"unexpected {schema} call")


# values -------------------------------------------------------------------------------------------

@pytest.mark.parametrize("a,b", [("EUR 12,000", "€12000"), ("14 March 2027", "March 14, 2027"),
                                 ("5days", "5 days"), ("Due  30 April", "due 30 april")])
def test_canonical_ignores_formatting(a, b):
    assert canonical(a) == canonical(b)


@pytest.mark.parametrize("a,b", [("EUR 12,000", "EUR 12,500"), ("14 March 2027", "15 March 2027"),
                                 ("03/04/2027", "3 April 2027"), ("EUR 100", "USD 100")])
def test_canonical_keeps_value_changes(a, b):
    assert canonical(a) != canonical(b)


def test_figures_are_order_free():
    assert figures("EUR 9,500 by 30 April 2027") == figures("by April 30, 2027: €9500")


@pytest.mark.parametrize("a,b", [("You must deliver logos", "You may deliver logos"),
                                 ("Price including VAT", "Price excluding VAT"),
                                 ("Deliver the icons", "Do not deliver the icons"),
                                 ("Budget capped at EUR 5,000", "Budget estimated at EUR 5,000")])
def test_qualifier_changes_are_detected(a, b):
    assert qualifiers_differ(a, b)


def test_qualifiers_ignore_rewording():
    assert qualifiers("Logos must be supplied as SVG") == qualifiers("The logos have to come as SVG files")


# sentence context ---------------------------------------------------------------------------------

PAGE = ("Project brief\nBudget: EUR 12,000\nFinal files are due on 30 April 2027. All icons must be "
        "delivered\nas SVG files.\n- Pages: home, about")


@pytest.mark.parametrize("quote,sentence", [("30 April 2027", "Final files are due on 30 April 2027."),
                                            ("EUR 12,000", "Budget: EUR 12,000"),
                                            ("SVG files", "All icons must be delivered as SVG files."),
                                            ("about", "- Pages: home, about")])
def test_sentence_of(quote, sentence):
    i = PAGE.index(quote)
    assert sentence_of(PAGE, Locator(i, i + len(quote)), wrapped=True) == sentence


def test_text_lines_never_wrap():
    i = PAGE.index("SVG files")
    assert sentence_of(PAGE, Locator(i, i + 9)) == "as SVG files."


# align --------------------------------------------------------------------------------------------

def test_reordered_facts_align_by_key_without_a_call():
    e = [fact("EUR 12,000"), fact("30 April", "date_deadline", "final files")]
    pairs = align(e, list(reversed(e)), Never())
    assert [p.status for p in pairs] == ["matched", "matched"]
    assert all(p.earlier is p.later for p in pairs)


def test_contradiction_marks_the_group_and_pairs_every_value():
    later = [fact("EUR 12,000"), fact("EUR 15,000")]
    assert {f.ambiguity for f in mark_contradictions(later)} == {"contradiction"}
    pairs = align([fact("EUR 12,000")], later, Never())
    assert [p.status for p in pairs] == ["ambiguous", "ambiguous"]


def test_llm_match_needs_high_confidence_and_one_to_one():
    e = [fact("Logo", "deliverable", "logo"), fact("Icons", "deliverable", "icons")]
    l = [fact("Brand mark", "deliverable", "brand mark"), fact("Icon set", "deliverable", "icon set")]
    out = {"matches": [{"earlier": 1, "later": 1, "confidence": "high"},
                       {"earlier": 2, "later": 2, "confidence": "medium"}]}
    validate(out, FACT_MATCHES)
    pairs = align(e, l, Script(FactMatches=out))
    assert [(p.status, p.earlier.raw_text, p.later.raw_text) for p in pairs] == [
        ("matched", "Logo", "Brand mark"), ("ambiguous", "Icons", "Icon set")]


def test_one_to_many_proposal_keeps_every_candidate_ambiguous_and_bad_indices_are_ignored():
    e = [fact("Logo", "deliverable", "logo")]
    l = [fact("Brand mark", "deliverable", "brand mark"), fact("Wordmark", "deliverable", "wordmark")]
    out = {"matches": [{"earlier": 1, "later": 1, "confidence": "high"},
                       {"earlier": 1, "later": 2, "confidence": "high"},
                       {"earlier": 7, "later": 1, "confidence": "high"}]}
    pairs = align(e, l, Script(FactMatches=out))
    assert [(p.status, p.later.raw_text) for p in pairs] == [("ambiguous", "Brand mark"), ("ambiguous", "Wordmark")]


def test_leftovers_are_unmatched():
    pairs = align([fact("Logo", "deliverable", "logo")], [fact("Video", "deliverable", "video")],
                  Script(FactMatches={"matches": []}))
    assert [p.status for p in pairs] == ["unmatched_earlier", "unmatched_later"]


# compare ------------------------------------------------------------------------------------------

def matched(a, b, **kw):
    return FactPair("matched", fact(a, **kw), fact(b, **kw))


def test_identical_context_is_unchanged_whatever_the_quote():
    p = FactPair("matched", fact("30 April", context="Files are due on 30 April."),
                 fact("Files are due on 30 April.", context="Files are due on 30 April."))
    assert compare([p], "complete", Never()) == []


@pytest.mark.parametrize("a,b,reason", [("Budget EUR 12,000", "Budget EUR 12,500", None),
                                        ("You must deliver logos", "You may deliver logos", "qualifier_changed"),
                                        ("Fee including VAT", "Fee excluding VAT", "qualifier_changed")])
def test_value_and_qualifier_guards_skip_the_model(a, b, reason):
    [d] = compare([matched(a, b)], "complete", Never())
    assert (d.change_type, d.uncertainty) == ("changed", reason)


def test_named_values_compare_by_value():
    p = FactPair("matched", fact("Approval by the client lead", "approval", "sign-off", value="client lead"),
                 fact("Approval by the CEO", "approval", "sign-off", value="ceo"))
    [d] = compare([p], "complete", Never())
    assert d.change_type == "changed"


def test_same_meaning_verdicts_and_missing_verdict_is_a_change():
    pairs = [matched("Logos in SVG", "Logos as SVG files"), matched("Tone: friendly", "Tone: formal"),
             matched("Use the brand font", "Brand font throughout")]
    out = {"verdicts": [{"pair": 1, "verdict": "equivalent"}, {"pair": 2, "verdict": "meaning_changed"}]}
    validate(out, SAME_MEANING)
    llm = Script(SameMeaning=out)
    drafts = compare(pairs, "complete", llm)
    assert [(d.change_type, d.uncertainty) for d in drafts] == [
        ("equivalent", None), ("changed", "meaning_changed"), ("changed", "meaning_changed")]
    assert len(llm.sent) == 1 and llm.sent[0][1][0].count("\n") == 2


@pytest.mark.parametrize("scope,change_type,note", [("complete", "removed", "absent_from_replacement"),
                                                    ("partial", "not_addressed", "not_addressed_by_partial_update"),
                                                    ("unknown", "uncertain", "scope_unknown")])
def test_omissions_follow_the_scope(scope, change_type, note):
    [d] = compare([FactPair("unmatched_earlier", fact("Logo"), None)], scope, Never())
    assert (d.change_type, d.note) == (change_type, note)


def test_added_and_ambiguous():
    drafts = compare([FactPair("unmatched_later", None, fact("Video")),
                      FactPair("ambiguous", fact("Logo"), fact("Mark"))], "complete", Never())
    assert [(d.change_type, d.uncertainty) for d in drafts] == [("added", None), ("uncertain", "ambiguous_match")]


def test_ambiguous_date_or_contradiction_is_never_a_silent_guess():
    date = matched("Due 03/04/2027", "Due 04/03/2027", ambiguity="ambiguous_date")
    same = FactPair("matched", fact("EUR 12,000", ambiguity="contradiction"),
                    fact("EUR 12,000", ambiguity="contradiction"))
    hedged = matched("Around EUR 5,000", "Around EUR 5,000", ambiguity="ambiguous_value")
    drafts = compare([date, same, hedged], "complete", Never())
    assert [(d.change_type, d.uncertainty) for d in drafts] == [
        ("uncertain", "ambiguous_date"), ("uncertain", "contradiction")]  # an unchanged hedged value is no finding
