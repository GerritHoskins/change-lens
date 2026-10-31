"""The `compare` stage (03 §4, 03a P5.3; I-3): FactPairs + confirmed scope -> DraftFindings.

Matched pairs, deterministic guards first (03 §4.1):
0. The same passage on both sides (after canonicalisation) is equivalent: no value noise from the
   extraction can turn unchanged text into a change (AC-6).
1. The numbers, dates and currencies in the passages differ, or (owners and approvals) the named
   values differ -> changed, whatever the model thinks (AC-1).
2. Negation, modality or limit words differ -> changed, never equivalent (AC-8).
3. The rest goes to one `SameMeaning` call; a missing verdict counts as a change. Equivalent pairs
   keep their raw text on both sides so the difference stays visible (AC-5).

Unmatched earlier facts follow the scope table (03 §4.2; I-4 owns its acceptance): complete ->
`removed` (absent from the replacement, never "cancelled"), partial -> `not_addressed`, unknown ->
`uncertain`. Unmatched newer facts are `added`. Ambiguous pairs and any finding that touches an
ambiguous fact become `uncertain` and are flagged for review (AC-7).
"""
from __future__ import annotations

from typing import Optional, Protocol, Sequence

from changelens.pipeline.types import DraftFinding, Evidence, ExtractedFact, FactPair, Scope
from changelens.pipeline.values import canonical, figures, qualifiers_differ

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
NAMED_VALUE_TYPES = {"responsibility_owner", "approval"}
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
    return DraftFinding(change_type, fact.type, _ev("earlier", pair.earlier) + _ev("later", pair.later),
                        uncertainty=uncertainty,
                        old_value=pair.earlier.normalised_value if pair.earlier else None,
                        new_value=pair.later.normalised_value if pair.later else None)


def compare(pairs: list[FactPair], later_scope: Scope, llm: Llm) -> list[DraftFinding]:
    drafts: list[DraftFinding] = []
    to_judge: list[tuple[int, FactPair]] = []
    for p in pairs:
        e, l = p.earlier, p.later
        if p.status == "matched":
            ec, lc = e.context or e.raw_text, l.context or l.raw_text
            if canonical(ec) == canonical(lc):
                drafts.append(_draft("equivalent", p))
            elif figures(ec) != figures(lc) or (
                    e.type in NAMED_VALUE_TYPES and canonical(e.normalised_value) != canonical(l.normalised_value)):
                drafts.append(_draft("changed", p))
            elif qualifiers_differ(ec, lc):
                drafts.append(_draft("changed", p, "qualifier_changed"))
            else:
                drafts.append(_draft("equivalent", p))  # placeholder until the verdict below
                to_judge.append((len(drafts) - 1, p))
        elif p.status == "ambiguous":
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
