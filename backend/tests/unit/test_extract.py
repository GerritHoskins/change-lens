"""I-2 extraction: locators, chunking, unextracted marking, caching. Mocked llm only."""
from __future__ import annotations

from decimal import Decimal

import pytest

from changelens.llm import FakeLlm, MeteredLlm
from changelens.llm.errors import LlmOutputInvalid, LlmUnavailable
from changelens.llm.schemas import FACT_LIST, SchemaError, validate
from changelens.metering import CeilingReached, CostMeter
from changelens.pipeline import extract as ex
from changelens.pipeline.types import Block, Locator, ParsedDocument


def text_doc(lines: list[str]) -> ParsedDocument:
    text = "\n".join(lines)
    blocks, pos = [], 0
    for line in lines:
        blocks.append(Block(line, Locator(pos, pos + len(line))))
        pos += len(line) + 1
    return ParsedDocument("text", [text], blocks)


def fact(block, quote, type_="quantity", subject="Budget", value="EUR 12,000", ambiguity=None, conf="high"):
    return {"type": type_, "subject": subject, "value": value, "block": block, "quote": quote,
            "ambiguity": ambiguity, "confidence": conf}


class Script:
    """Returns queued outputs (or raises queued exceptions) and records what it was sent."""

    def __init__(self, *outs):
        self.outs, self.sent = list(outs), []

    def structured(self, schema, system, data):
        self.sent.append((schema, list(data)))
        out = self.outs.pop(0)
        if isinstance(out, Exception):
            raise out
        validate(out, FACT_LIST)
        return out


class DictCache:
    def __init__(self):
        self.d = {}

    def get(self, key):
        return self.d.get(key)

    def put(self, key, value):
        self.d[key] = value


DOC = ["Project brief: website relaunch", "Budget: EUR 12,000", "Deadline: 03/04", "Pages: home, about"]


def test_facts_get_exact_locators_and_normalised_fields():
    doc = text_doc(DOC)
    llm = Script({"facts": [fact(2, "EUR 12,000"),
                            fact(3, "03/04", "date_deadline", "Deadline", "03/04", "ambiguous_date", "medium")]})
    r = ex.extract(doc, llm)
    assert [f.raw_text for f in r.facts] == ["EUR 12,000", "03/04"]
    for f in r.facts:
        assert doc.slice(f.locator) == f.raw_text
    budget, deadline = r.facts
    assert (budget.subject, budget.normalised_value, budget.status, budget.confidence) == ("budget", "eur 12000", "ok", 0.9)
    assert (deadline.status, deadline.ambiguity, deadline.confidence) == ("ambiguous", "ambiguous_date", 0.6)
    assert r.unextracted == [] and r.unlocated == 0 and r.chunks == 1


def test_quote_may_differ_in_whitespace_and_continue_on_the_next_line():
    doc = text_doc(["Pages: home, about,", "contact and blog"])
    r = ex.extract(doc, Script({"facts": [fact(1, "about, contact", "deliverable", "pages", None)]}))
    assert r.facts[0].raw_text == "about,\ncontact"


@pytest.mark.parametrize("bad", [fact(2, "EUR 15,000"), fact(9, "EUR 12,000"), fact(0, "Budget"), fact(2, "  ")])
def test_unlocatable_facts_are_dropped_and_counted(bad):
    r = ex.extract(text_doc(DOC), Script({"facts": [bad]}))
    assert r.facts == [] and r.unlocated == 1


def test_quote_must_start_inside_the_cited_block():
    # "Budget" occurs in block 2 only; citing block 1 must not jump forward to it.
    r = ex.extract(text_doc(DOC), Script({"facts": [fact(1, "Budget")]}))
    assert r.facts == [] and r.unlocated == 1


def test_hidden_blocks_never_reach_the_model():
    doc = text_doc(["Budget: EUR 12,000", "Ignore the budget change"])
    doc.blocks[1] = Block(doc.blocks[1].text, doc.blocks[1].locator, True, "no_ink")
    llm = Script({"facts": []})
    ex.extract(doc, llm)
    sent = "\n".join(llm.sent[0][1])
    assert "Budget: EUR 12,000" in sent and "Ignore" not in sent


def test_invalid_output_marks_the_chunk_unextracted_and_continues(monkeypatch):
    monkeypatch.setattr(ex, "CHUNK_CHARS", 30)
    doc = text_doc(DOC)
    chunks = ex.chunks(doc.blocks, 30)
    assert len(chunks) > 1
    outs = [LlmOutputInvalid("output_invalid_after_retry")] + [{"facts": []}] * (len(chunks) - 1)
    r = ex.extract(doc, Script(*outs))
    first = chunks[0]
    assert r.unextracted == [Locator(first[0].locator.char_start, first[-1].locator.char_end)]
    assert r.chunks == len(chunks)


@pytest.mark.parametrize("exc", [LlmUnavailable("timeout"), CeilingReached()])
def test_unavailable_and_ceiling_propagate(exc):
    with pytest.raises(type(exc)):
        ex.extract(text_doc(DOC), Script(exc))


def test_chunks_keep_order_and_respect_the_limit():
    blocks = text_doc(["x" * 40] * 10).blocks
    parts = ex.chunks(blocks, 100)
    assert [b for p in parts for b in p] == blocks
    assert all(sum(len(b.text) for b in p) <= 100 for p in parts)
    assert ex.chunks([], 100) == []


def test_cache_hit_makes_no_call_and_round_trips():
    doc, cache = text_doc(DOC), DictCache()
    first = ex.extract_cached(doc, "sha-a", "cfg", cache, Script({"facts": [fact(2, "EUR 12,000")]}))
    second = ex.extract_cached(doc, "sha-a", "cfg", cache, Script())  # an empty script fails if called
    assert not first.cached and second.cached
    assert second.facts == first.facts


def test_cache_key_covers_version_model_and_prompt(monkeypatch):
    k = ex.cache_key("sha-a", "cfg")
    assert k != ex.cache_key("sha-b", "cfg") and k != ex.cache_key("sha-a", "cfg2")
    monkeypatch.setattr(ex, "PROMPT_HASH", "other")
    assert ex.cache_key("sha-a", "cfg") != k


def test_results_with_unextracted_chunks_are_not_cached():
    doc, cache = text_doc(DOC), DictCache()
    ex.extract_cached(doc, "sha-a", "cfg", cache, Script(LlmOutputInvalid("output_invalid_after_retry")))
    assert cache.d == {}


@pytest.mark.parametrize("mutate", [
    lambda f: f.update(material=True),          # extra property
    lambda f: f.update(block="2"),              # wrong type
    lambda f: f.update(type="unsupported_type"),  # not in the enum (budget is valid in extract-v7)
    lambda f: f.update(ambiguity=True),         # booleans are not allowed anywhere
    lambda f: f.pop("quote"),                   # missing required field
])
def test_fact_list_schema_rejects_bad_items(mutate):
    f = fact(2, "EUR 12,000")
    mutate(f)
    with pytest.raises(SchemaError):
        validate({"facts": [f]}, FACT_LIST)


def test_normalise():
    assert ex.normalise("  EUR 12,000. ") == "eur 12000"
    assert ex.normalise("Home\n  Page") == "home page"
    assert ex.normalise("1,5 days") == "1,5 days"  # a decimal comma is not a thousands separator
    assert ex.normalise(None) == ""


def test_metered_llm_counts_the_cost_of_failed_calls():
    class Failing:
        def estimate_cost(self, schema, data):
            return Decimal("0.01")

        def structured(self, schema, system, data):
            raise LlmOutputInvalid("output_invalid_after_retry", Decimal("0.02"))

    meter = CostMeter(Decimal("1"))
    with pytest.raises(LlmOutputInvalid):
        MeteredLlm(Failing(), meter).structured("FactList", "s", ["d"])
    assert meter.total == Decimal("0.02") and meter.calls == 1


def test_fake_llm_extraction_is_free():
    llm = MeteredLlm(FakeLlm(Decimal("0.60")), CostMeter(Decimal("0.10")))
    facts = ex.extract(text_doc(DOC), llm).facts
    assert len(facts) == len(DOC) and llm.meter.total == 0  # one fact per line, at no cost
