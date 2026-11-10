"""Offline I-7b regression derived only from the documented P-708 development sentence.

Scripted extraction varies the number of readings of an unchanged, wrapped PDF sentence.
This proves the pipeline defect; it does not diagnose or re-run historical held-out pairs.
"""
from dataclasses import replace

import pytest

from changelens.config import Limits
from changelens.pipeline.align import align
from changelens.pipeline.compare import compare
from changelens.pipeline.extract import extract
from changelens.pipeline.parse import parse
from changelens.pipeline.types import DraftFinding, Evidence
from changelens.pipeline.verify import verify
from helpers import make_pdf


SENTENCE = "Record and edit 6 launch episodes."


class Extraction:
    def __init__(self, block, duplicate):
        self.block, self.duplicate = block, duplicate

    def structured(self, schema, system, data):
        assert schema == "FactList"
        fact = {"type": "quantity", "subject": "episodes", "value": "6", "quote": SENTENCE,
                "block": self.block, "ambiguity": None, "confidence": "high"}
        return {"facts": [fact] + ([{**fact, "value": "record and edit 6 launch episodes"}]
                                  if self.duplicate else [])}


class OneMatch:
    def structured(self, schema, system, data):
        assert schema == "FactMatches"
        return {"matches": [{"earlier": 1, "later": 1, "confidence": "high"}]}


@pytest.mark.parametrize("duplicated_side", ["earlier", "later"])
@pytest.mark.parametrize("scope", ["complete", "partial", "unknown"])
@pytest.mark.parametrize("wrapped", [False, True])
def test_reordered_unchanged_pdf_duplicate_reading_never_becomes_a_finding(duplicated_side, scope, wrapped):
    sentence = ["Record and edit 6 launch", "episodes."] if wrapped else [SENTENCE]
    earlier = parse(make_pdf([sentence + ["Fees: EUR 9600"]]), "pdf", Limits())
    later = parse(make_pdf([["Fees: EUR 9600"] + sentence]), "pdf", Limits())
    a = extract(earlier, Extraction(1, duplicated_side == "earlier"))
    b = extract(later, Extraction(2, duplicated_side == "later"))
    assert sorted([len(a.facts), len(b.facts)]) == [1, 2]
    drafts = compare(align(a.facts, b.facts, OneMatch()), scope, OneMatch())
    assert len(drafts) == 1  # the omitted extra reading reaches the real verification guard
    checked = verify(drafts, earlier, later)
    assert checked.findings == []
    assert checked.withheld_count == 0
    assert checked.unexplained == []


def pdf_evidence(doc, side, phrase):
    # locate() is exercised by extract above; these negative cases cite a full source sentence.
    from changelens.pipeline.extract import locate
    loc = locate(doc, doc.blocks[0], phrase)
    assert loc is not None
    return Evidence(side, loc, doc.slice(loc))


@pytest.mark.parametrize("barrier", ["hidden", "page", "unparsed_text", "different_value", "contradiction",
                                   "one_sided_contradiction"])
def test_opposite_fragments_cannot_hide_a_real_or_uncertain_finding(barrier):
    source = parse(make_pdf([[SENTENCE]]), "pdf", Limits())
    lines = ["Record and edit 6 launch", "episodes."]
    if barrier == "page":
        opposite = parse(make_pdf([[lines[0]], [lines[1]]]), "pdf", Limits())
    elif barrier == "different_value":
        opposite = parse(make_pdf([["Record and edit 8 launch", "episodes."]]), "pdf", Limits())
    elif barrier in {"hidden", "unparsed_text"}:
        opposite = parse(make_pdf([[lines[0], "not required", lines[1]]]), "pdf", Limits())
        if barrier == "hidden":
            opposite.blocks[1] = replace(opposite.blocks[1], hidden=True, hidden_reason="no_ink")
        else:
            opposite.blocks.pop(1)  # missing/non-whitespace page text must remain a barrier
    else:
        opposite = parse(make_pdf([lines]), "pdf", Limits())
    evidence = [pdf_evidence(source, "later", SENTENCE)]
    if barrier == "contradiction":
        # Contradictions have two-sided evidence, so an unchanged passage never suppresses them.
        evidence.insert(0, pdf_evidence(opposite, "earlier", SENTENCE))
    contradiction = barrier in {"contradiction", "one_sided_contradiction"}
    finding = DraftFinding("uncertain" if contradiction else "added", "quantity", evidence,
                           uncertainty="contradiction" if contradiction else None)
    assert verify([finding], opposite, source).findings == [finding]


def test_non_whitespace_edit_after_an_unchanged_wrapped_sentence_stays_unexplained():
    earlier = parse(make_pdf([["Record and edit 6 launch", "episodes."]]), "pdf", Limits())
    later = parse(make_pdf([[SENTENCE, "Additionally produce 2 trailers."]]), "pdf", Limits())
    same = DraftFinding("added", "quantity", [pdf_evidence(later, "later", SENTENCE)])
    result = verify([same], earlier, later)
    assert result.findings == []
    assert any(ev.quote == "Additionally produce 2 trailers." for ev in result.unexplained)
