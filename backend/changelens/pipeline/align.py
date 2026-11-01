"""The `align` stage (03 §2, 03a P5.2; I-3): earlier facts + newer facts -> FactPairs.

0. Contradictions inside one version (same type and subject, two sentences whose values have
   nothing in common) mark every fact of that group ambiguous; they are never resolved by picking
   one (AC-7). Two readings of one sentence are not a contradiction (I-7).
1. Deterministic: a key of (type, subject) that occurs exactly once on each side is a match. Keys
   ignore position, so a reordered brief aligns the same way (AC-6).
2. The rest goes to one `FactMatches` call. A proposal becomes a match only with high confidence and
   when it is one-to-one; anything else is an ambiguous pair, never a forced match (AC-7).
3. A key with a contradiction on either side pairs every earlier member with every newer member as
   ambiguous, so each conflicting value is reported (AC-7). A leftover contradiction member joins
   the counterpart of its group.
4. Whatever is left is unmatched on its side.
"""
from __future__ import annotations

from collections import defaultdict
from dataclasses import replace
from itertools import combinations
from typing import Protocol, Sequence

from changelens.pipeline.types import ExtractedFact, FactPair
from changelens.pipeline.values import canonical

SYSTEM = """You align the facts of two versions of a client brief.

Data block 1 lists facts from the EARLIER version as "[E<n>] type | subject | text"; data block 2
lists facts from the NEWER version as "[L<n>] ...". For every earlier fact that is about the same
item as a newer fact (the same deliverable, amount, date, owner, approval or condition, even if its
value, wording or position changed), return one match with earlier = n of E<n>, later = n of L<n>
and a confidence:
- high: clearly the same item.
- medium or low: possibly the same item, but it could also be a different one.
Do not match facts that are merely similar in topic. An earlier fact that has no counterpart is
left out; never match one fact twice. Return {"matches": []} if nothing corresponds."""


class Llm(Protocol):
    def structured(self, schema: str, system: str, data: Sequence[str]) -> dict: ...


def key(f: ExtractedFact) -> tuple[str, str]:
    return f.type, canonical(f.subject)


def mark_contradictions(facts: list[ExtractedFact]) -> list[ExtractedFact]:
    """A contradiction needs two passages that disagree: two sentences (as in compare's rule 0) whose
    values for the key have nothing in common. Two readings of one sentence ("6" and "record and edit
    6 launch episodes", dev pair P-708) are not one."""
    groups: dict[tuple[str, str], dict[str, set[str]]] = defaultdict(lambda: defaultdict(set))
    for f in facts:
        if f.normalised_value:
            groups[key(f)][canonical(f.context or f.raw_text)].add(canonical(f.normalised_value))
    clash = {k for k, by_sentence in groups.items()
             if any(a.isdisjoint(b) for a, b in combinations(by_sentence.values(), 2))}
    return [replace(f, status="ambiguous", ambiguity="contradiction") if key(f) in clash else f for f in facts]


def _line(prefix: str, i: int, f: ExtractedFact) -> str:
    return f"[{prefix}{i}] {f.type} | {f.subject} | {f.raw_text}"


def align(earlier: list[ExtractedFact], later: list[ExtractedFact], llm: Llm) -> list[FactPair]:
    earlier, later = mark_contradictions(earlier), mark_contradictions(later)
    pairs: list[FactPair] = []
    by_e, by_l = defaultdict(list), defaultdict(list)
    for i, f in enumerate(earlier):
        by_e[key(f)].append(i)
    for j, f in enumerate(later):
        by_l[key(f)].append(j)
    used_e, used_l = set(), set()
    for k, es in by_e.items():
        ls = by_l.get(k, [])
        if es and ls and any(f.ambiguity == "contradiction" for f in [earlier[i] for i in es] + [later[j] for j in ls]):
            pairs += [FactPair("ambiguous", earlier[i], later[j]) for i in es for j in ls]
            used_e.update(es)
            used_l.update(ls)
        elif len(es) == 1 and len(ls) == 1:
            pairs.append(FactPair("matched", earlier[es[0]], later[ls[0]]))
            used_e.add(es[0])
            used_l.add(ls[0])

    rest_e = [i for i in range(len(earlier)) if i not in used_e]
    rest_l = [j for j in range(len(later)) if j not in used_l]
    if rest_e and rest_l:
        data = ["\n".join(_line("E", n, earlier[i]) for n, i in enumerate(rest_e, 1)),
                "\n".join(_line("L", n, later[j]) for n, j in enumerate(rest_l, 1))]
        proposals = [(m["earlier"], m["later"], m["confidence"])
                     for m in llm.structured("FactMatches", SYSTEM, data)["matches"]
                     if 1 <= m["earlier"] <= len(rest_e) and 1 <= m["later"] <= len(rest_l)]
        e_count = defaultdict(int)
        l_count = defaultdict(int)
        for e, l, _ in proposals:
            e_count[e] += 1
            l_count[l] += 1
        for e, l, conf in proposals:
            ei, lj = rest_e[e - 1], rest_l[l - 1]
            if ei in used_e and lj in used_l:
                continue
            unique = e_count[e] == 1 and l_count[l] == 1
            status = "matched" if conf == "high" and unique else "ambiguous"
            pairs.append(FactPair(status, earlier[ei], later[lj]))
            used_e.add(ei)
            used_l.add(lj)

    # Leftover contradiction members join the pair of a member of their group (same key).
    for j in [j for j in range(len(later)) if j not in used_l and later[j].ambiguity == "contradiction"]:
        partners = {id(p.earlier): p.earlier for p in pairs if p.later is not None and p.earlier is not None
                    and key(p.later) == key(later[j])}
        for e in partners.values():
            pairs.append(FactPair("ambiguous", e, later[j]))
            used_l.add(j)
    for i in [i for i in range(len(earlier)) if i not in used_e and earlier[i].ambiguity == "contradiction"]:
        partners = {id(p.later): p.later for p in pairs if p.earlier is not None and p.later is not None
                    and key(p.earlier) == key(earlier[i])}
        for l in partners.values():
            pairs.append(FactPair("ambiguous", earlier[i], l))
            used_e.add(i)
    pairs += [FactPair("unmatched_earlier", earlier[i], None) for i in range(len(earlier)) if i not in used_e]
    pairs += [FactPair("unmatched_later", None, later[j]) for j in range(len(later)) if j not in used_l]
    return pairs
