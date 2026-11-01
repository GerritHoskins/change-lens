"""The `verify` stage (03 §2, 03a P5.4; I-5): deterministic, no model calls.

1. Every evidence quote must equal the parsed text at its locator, on the side it names, and the
   evidence must fit the change type: a change cites both sides (AC-1), an omission cites only the
   earlier side (no absence quotes, AC-2..4, AC-9), an addition only the newer side. Anything else
   is withheld and counted, never shown (AC-9, AC-10).
2. Uncertain or low-confidence findings go to "needs review", never shown as certain (AC-10).
3. A block-level diff of the visible text is cross-checked against the kept findings. A changed
   block that no finding covers is an unexplained difference. An "equivalent" verdict comes from
   the model, so it does not count as an explanation: a false equivalence forced by injected text
   still surfaces (AC-18). Blocks that only moved or were reformatted (list marker, capitals) are
   presentation-only (AC-5, AC-6).
4. A one-sided finding (an addition, or an omission of any scope) whose quoted sentence, ignoring
   list marker, spacing and case, is in a visible block of the other version is dropped: the text
   is on both sides, so nothing was added or left out. This happens when extraction types or
   names the same sentence differently in the two versions, and must not fabricate a change on a
   reordered or unchanged pair (AC-6). Any edit around it is still caught by the block diff (3).
5. An exact duplicate (same change type, category, values and evidence locators as a kept finding)
   is merged into it: it says nothing new. The kept finding takes the lower confidence, so a copy
   that needs review still sends it to review (AC-10). Duplicates arise when one fact is extracted
   twice (I-7).
"""
from __future__ import annotations

import difflib
import re
from collections import Counter

from changelens.pipeline.types import DraftFinding, Evidence, Locator, ParsedDocument, VerifyResult

REVIEW_BELOW = 0.5  # fact confidence under this routes a finding to needs review (medium is 0.6)
SIDES = {"changed": {"earlier", "later"}, "equivalent": {"earlier", "later"},
         "removed": {"earlier"}, "not_addressed": {"earlier"}, "added": {"later"}}


def _quotes_match(f: DraftFinding, docs: dict[str, ParsedDocument]) -> bool:
    return bool(f.evidence) and all(
        0 <= ev.locator.char_start < ev.locator.char_end and docs[ev.side].slice(ev.locator) == ev.quote
        for ev in f.evidence)


def _sides_fit(f: DraftFinding) -> bool:
    sides = {ev.side for ev in f.evidence}
    if f.change_type == "uncertain":  # an omission under unknown scope stays earlier-only
        return sides == {"earlier"} if f.note == "scope_unknown" else bool(sides)
    return sides == SIDES.get(f.change_type, set())


_MARKER = re.compile(r"^(?:[-*+•–]|\d+[.)]|[a-z][.)])\s+", re.I)


def _norm(text: str) -> str:
    return " ".join(text.split())


def _loose(text: str) -> str:
    """Presentation-free form: no list marker, no case. A block equal in this form only moved or
    was reformatted (bullet style, numbering, capitals)."""
    return _MARKER.sub("", _norm(text)).casefold()


def _on_other_side(f: DraftFinding, docs: dict[str, ParsedDocument]) -> bool:
    sides = {ev.side for ev in f.evidence}
    if len(sides) != 1:
        return False
    other = docs["later" if sides == {"earlier"} else "earlier"]
    blocks = [_loose(b.text) for b in other.blocks if not b.hidden]
    for ev in f.evidence:
        q = re.compile(rf"(?<!\w){re.escape(_loose(ev.quote))}(?!\w)")
        if not any(q.search(b) for b in blocks):
            return False
    return True


def _identity(f: DraftFinding) -> tuple:
    return (f.change_type, f.category, f.old_value, f.new_value,
            tuple(sorted((ev.side, ev.locator.page or 0, ev.locator.char_start, ev.locator.char_end)
                         for ev in f.evidence)))


def _overlaps(a: Locator, b: Locator) -> bool:
    return a.page == b.page and a.char_start < b.char_end and b.char_start < a.char_end


def block_diff(earlier: ParsedDocument, later: ParsedDocument) -> tuple[list[Evidence], list[Evidence]]:
    """(changed, presentation-only) visible blocks. A block whose text, ignoring list markers and
    case, is also on the other side only moved or was reformatted; it is not a change."""
    a = [b for b in earlier.blocks if not b.hidden]
    b = [x for x in later.blocks if not x.hidden]
    changed, moved = [], []
    left, right = Counter(_loose(x.text) for x in a), Counter(_loose(x.text) for x in b)
    sm = difflib.SequenceMatcher(a=[_norm(x.text) for x in a], b=[_norm(x.text) for x in b], autojunk=False)
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            continue
        for side, blocks, other in (("earlier", a[i1:i2], right), ("later", b[j1:j2], left)):
            for blk in blocks:
                (moved if other[_loose(blk.text)] else changed).append(Evidence(side, blk.locator, blk.text))
    return changed, moved


def _covered(ev: Evidence, explaining: list[DraftFinding]) -> bool:
    return any(x.side == ev.side and _overlaps(x.locator, ev.locator) for f in explaining for x in f.evidence)


def verify(drafts: list[DraftFinding], earlier: ParsedDocument, later: ParsedDocument) -> VerifyResult:
    docs = {"earlier": earlier, "later": later}
    kept, withheld, seen = [], 0, {}
    for f in drafts:
        if not (_quotes_match(f, docs) and _sides_fit(f)):
            withheld += 1
            continue
        if _on_other_side(f, docs):
            continue
        if (first := seen.get(_identity(f))) is not None:
            f, first.confidence = first, min(first.confidence, f.confidence)
        else:
            seen[_identity(f)] = f
            kept.append(f)
        if f.change_type == "uncertain" or f.confidence < REVIEW_BELOW:
            f.group = "needs_review"
    changed, moved = block_diff(earlier, later)
    explaining = [f for f in kept if f.change_type != "equivalent"]
    unexplained = [ev for ev in changed if not _covered(ev, explaining)]
    return VerifyResult(kept, withheld, unexplained, moved)

