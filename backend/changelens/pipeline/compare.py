"""The `compare` stage (03 §4, 03a P5.3; I-3): FactPairs + confirmed scope -> DraftFindings.

Matched pairs, deterministic guards first (03 §4.1):
0. The same sentence on both sides (after canonicalisation) is unchanged and gets no finding: no
   value noise from the extraction can turn unchanged text into a change (AC-6). A contradiction
   stays uncertain even so (AC-7). Any exact-text edit left is caught by verify's block diff.
   A fact also stays unchanged when its grounded value is unchanged and the sentence edits are
   entirely the grounded values of other matched topics, with no qualifier or remaining text edit.
1. The numbers, dates and currencies in the passages differ, or (owners and approvals) the named
   values differ -> changed, whatever the model thinks (AC-1).
2. Negation, modality or limit words differ -> changed, never equivalent (AC-8).
3. The rest goes to one `SameMeaning` call; a missing verdict counts as a change. Equivalent pairs
   keep their raw text on both sides so the difference stays visible (AC-5).

Unmatched earlier facts follow the scope table (03 §4.2; I-4 owns its acceptance): complete ->
`removed` (absent from the replacement, never "cancelled"), partial -> `not_addressed`, unknown ->
`uncertain`. Unmatched newer facts are `added`. Ambiguous pairs and any finding that touches an
ambiguous fact become `uncertain` and are flagged for review (AC-7), except that rule 0 applies to an
ambiguous pair too: two facts in the same sentence are unchanged whichever way they pair up (I-7).
"""
from __future__ import annotations

import re
from typing import Optional, Protocol, Sequence

from changelens.pipeline.types import DraftFinding, Evidence, ExtractedFact, FactPair, Scope
from changelens.pipeline.values import canonical, figures, qualifiers_differ
from changelens.topics import canonical_category

SYSTEM = """You judge whether pairs of passages from two versions of a client brief mean the same.

The data block lists pairs as "[n] EARLIER: ... || NEWER: ...". For each pair return its number and
a verdict:
- equivalent: the newer passage only rewords or reformats the earlier one; every obligation, scope,
  value, party, condition and degree of commitment is unchanged.
- meaning_changed: anything a client or supplier could act on differs (what is delivered, its
  format, style or tone, who does it, when, how binding it is, or any condition).
If in doubt, answer meaning_changed."""

# Extraction ambiguity that makes a finding uncertain (AC-7); a hedged value only adds a note.
UNCERTAIN_REASONS = {"ambiguous_date", "ambiguous_entity", "contradiction"}
NAMED_VALUE_TYPES = {"responsibility_owner", "approval", "approval_wording"}
OMISSION = {"complete": ("removed", "absent_from_replacement"),
            "partial": ("not_addressed", "not_addressed_by_partial_update"),
            "unknown": ("uncertain", "scope_unknown")}


class Llm(Protocol):
    def structured(self, schema: str, system: str, data: Sequence[str]) -> dict: ...


def _ev(side: str, f: Optional[ExtractedFact]) -> list[Evidence]:
    return [] if f is None else [Evidence(side, f.locator, f.raw_text)]


def _draft(change_type: str, pair: FactPair, uncertainty: Optional[str] = None) -> DraftFinding:
    fact = pair.earlier or pair.later
    reasons = [f.ambiguity for f in (pair.earlier, pair.later) if f is not None and f.ambiguity]
    blocking = [r for r in reasons if r in UNCERTAIN_REASONS]
    # AC-7: never a silent guess. A contradiction stays uncertain even where one value is unchanged.
    if blocking and (change_type != "equivalent" or "contradiction" in blocking):
        change_type, uncertainty = "uncertain", uncertainty or blocking[0]
    elif reasons and uncertainty is None:
        uncertainty = reasons[0]
    return DraftFinding(change_type, canonical_category(fact.type), _ev("earlier", pair.earlier) + _ev("later", pair.later),
                        uncertainty=uncertainty,
                        old_value=pair.earlier.normalised_value if pair.earlier else None,
                        new_value=pair.later.normalised_value if pair.later else None,
                        confidence=min(f.confidence for f in (pair.earlier, pair.later) if f is not None))


def _value_span(text: str, value: str) -> Optional[tuple[int, int]]:
    """Locate one unambiguous, whole canonical value; never infer a missing value."""
    if not value:
        return None
    hits = list(re.finditer(rf"(?<!\w){re.escape(value)}(?!\w)", text))
    return hits[0].span() if len(hits) == 1 else None


def _masked_context(text: str, spans: list[tuple[int, int, int]]) -> Optional[tuple]:
    parts, cursor = [], 0
    for start, end, identity in sorted(spans):
        if start < cursor:  # overlapping values cannot establish independent topic edits
            return None
        parts.extend((text[cursor:start], identity))
        cursor = end
    return tuple(parts + [text[cursor:]])


def _only_other_topics_changed(pair: FactPair, pairs: list[FactPair]) -> bool:
    """An unchanged value alone is insufficient: account for every context edit using other
    unambiguous, matched topics in the same two sentences. This prevents a fee edit from changing
    an unchanged deadline, without dropping context-level negation, modality or unknown edits.
    Missing, repeated, overlapping or ungrounded values fall back to the existing guards.
    """
    e, l = pair.earlier, pair.later
    if (canonical_category(e.type) != canonical_category(l.type)
            or canonical(e.subject) != canonical(l.subject)
            or any(f.status != "ok" or f.ambiguity for f in (e, l))):
        return False
    value = canonical(e.normalised_value)
    if not value or value != canonical(l.normalised_value):
        return False
    ec, lc = canonical(e.context or e.raw_text), canonical(l.context or l.raw_text)
    own_e, own_l = _value_span(ec, value), _value_span(lc, value)
    if own_e is None or own_l is None or qualifiers_differ(ec, lc):
        return False
    spans_e, spans_l, seen = [], [], set()
    for sibling in pairs:
        a, b = sibling.earlier, sibling.later
        if (sibling.status != "matched" or a.topic == e.topic
                or canonical_category(a.type) != canonical_category(b.type)
                or canonical(a.subject) != canonical(b.subject)
                or any(f.status != "ok" or f.ambiguity for f in (a, b))
                or canonical(a.context or a.raw_text) != ec or canonical(b.context or b.raw_text) != lc):
            continue
        av, bv = canonical(a.normalised_value), canonical(b.normalised_value)
        if not av or not bv or av == bv:
            continue
        sa, sb = _value_span(ec, av), _value_span(lc, bv)
        if sa is None or sb is None or (sa, sb) in seen:
            continue
        if any(start < own[1] and own[0] < end for (start, end), own in ((sa, own_e), (sb, own_l))):
            continue
        identity = len(seen)
        seen.add((sa, sb))
        spans_e.append((*sa, identity))
        spans_l.append((*sb, identity))
    masked_e, masked_l = _masked_context(ec, spans_e), _masked_context(lc, spans_l)
    return bool(seen) and masked_e is not None and masked_e == masked_l


def compare(pairs: list[FactPair], later_scope: Scope, llm: Llm) -> list[DraftFinding]:
    drafts: list[DraftFinding] = []
    to_judge: list[tuple[int, FactPair]] = []
    for p in pairs:
        e, l = p.earlier, p.later
        if p.status == "matched":
            ec, lc = e.context or e.raw_text, l.context or l.raw_text
            if canonical(ec) == canonical(lc):
                if "contradiction" in (e.ambiguity, l.ambiguity):
                    drafts.append(_draft("equivalent", p))  # becomes uncertain (AC-7)
                # otherwise unchanged: no finding (a case or spacing edit is left to verify's block diff)
            elif _only_other_topics_changed(p, pairs):
                pass  # this fact's value and remaining sentence are unchanged (O-14)
            elif figures(ec) != figures(lc) or (
                    e.type in NAMED_VALUE_TYPES and canonical(e.normalised_value) != canonical(l.normalised_value)):
                drafts.append(_draft("changed", p))
            elif qualifiers_differ(ec, lc):
                drafts.append(_draft("changed", p, "qualifier_changed"))
            else:
                drafts.append(_draft("equivalent", p))  # placeholder until the verdict below
                to_judge.append((len(drafts) - 1, p))
        elif p.status == "ambiguous":
            ec, lc = e.context or e.raw_text, l.context or l.raw_text
            if canonical(ec) == canonical(lc):
                # Rule 0 holds whichever way the facts pair up; contradictions still need review.
                if "contradiction" in (e.ambiguity, l.ambiguity):
                    drafts.append(_draft("equivalent", p))  # becomes uncertain (AC-7)
            else:
                drafts.append(_draft("uncertain", p, "ambiguous_match"))
        elif p.status == "unmatched_earlier":
            change_type, note = OMISSION[later_scope]
            drafts.append(_draft(change_type, p, note if change_type == "uncertain" else None))
            drafts[-1].note = note
        else:
            drafts.append(_draft("added", p))
    if to_judge:
        data = ["\n".join(f"[{n}] EARLIER: {p.earlier.context or p.earlier.raw_text} || "
                          f"NEWER: {p.later.context or p.later.raw_text}"
                          for n, (_, p) in enumerate(to_judge, 1))]
        verdicts = {v["pair"]: v["verdict"] for v in llm.structured("SameMeaning", SYSTEM, data)["verdicts"]}
        for n, (i, p) in enumerate(to_judge, 1):
            # A missing verdict is not evidence of equivalence: treat it as a change (03 §4.1, AC-8).
            if verdicts.get(n) != "equivalent":
                drafts[i] = _draft("changed", p, "meaning_changed")
    for rank, d in enumerate(drafts):
        d.priority = rank
    return drafts
