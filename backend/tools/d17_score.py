"""D-17 scoring: model findings against the constructed gold findings (07 §4, 04 §5).

Definitions (also in the decision log row):
- **Reportable** findings have change_type `added`, `changed`, `removed` or `uncertain`, in the gold
  labels and in the model output. `equivalent` and `not_addressed` mean "nothing to report" and
  are neither predictions nor gold changes.
- **Match:** same category, and either the values agree (on every side where both the gold
  finding and the model give a value, one normalised value contains the other; at least one side
  compared) or the evidence overlaps (the model's quote, found in that side's text with flexible
  whitespace, overlaps the gold evidence span). Matching is one-to-one, best score first
  (value 2, evidence 1). The change type is not part of the match; its agreement is reported.
  A relaxed variant ignores the category.
- **Invented number or date:** a returned value or quote that contains a number, or a month name,
  that does not occur in that side's text as sent to the model (digit separators ignored).
- **False removal (04 §5):** a model `removed` on a partial-update or unknown-scope pair, or a model
  `removed` that matches (relaxed) a gold `not_addressed` or `uncertain` finding.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from changelens.topics import canonical_category

REPORTABLE = frozenset({"added", "changed", "removed", "uncertain"})
SCOPE_CASES = frozenset({"partial_update", "unknown_scope"})
_NUM = re.compile(r"\d+(?:[.,]\d+)*")
_MONTH = re.compile(r"\b(january|february|march|april|may|june|july|august|september|october|"
                    r"november|december)\b", re.I)
_SEP = re.compile(r"(?<=\d)[.,](?=\d)")
_TRIM = " \t\r\n.,;:!?\"'()[]-*"


@dataclass(frozen=True)
class Side:
    """One version as the model saw it (`sent`) and as the gold locators index it (`pages`)."""
    sent: str
    pages: list  # text: [exact text]; pdf: PDFium page texts


def norm(s: Optional[str]) -> str:
    return " ".join((s or "").split()).casefold().strip(_TRIM)


def value_match(gold: Optional[str], model: Optional[str]) -> bool:
    g, m = norm(gold), norm(model)
    if not g or not m:
        return False
    short, long_ = sorted((g, m), key=len)
    if len(short) >= 3:
        return short in long_
    return re.search(rf"(?<!\w){re.escape(short)}(?!\w)", long_) is not None  # "3" in "3 videos", not in "30"


def find_spans(text: str, quote: Optional[str]) -> list[tuple[int, int]]:
    words = (quote or "").split()
    if not words:
        return []
    pattern = r"\s+".join(re.escape(w) for w in words)
    return [(m.start(), m.end()) for m in re.finditer(pattern, text)]


def evidence_overlap(side: Side, gold_span: Optional[dict], quote: Optional[str]) -> bool:
    if not gold_span or "start" not in gold_span:
        return False
    page = side.pages[(gold_span.get("page") or 1) - 1]
    return any(s < gold_span["end"] and e > gold_span["start"] for s, e in find_spans(page, quote))


def match_score(g: dict, m: dict, old: Side, new: Side, use_category: bool = True) -> int:
    if use_category and canonical_category(g["category"]) != canonical_category(m["category"]):
        return 0
    compared, values_ok = 0, True
    for k in ("old_value", "new_value"):
        if g.get(k) and m.get(k):
            compared += 1
            values_ok = values_ok and value_match(g[k], m[k])
    score = 2 if compared and values_ok else 0
    if evidence_overlap(old, g.get("evidence_old"), m.get("evidence_old")) or \
            evidence_overlap(new, g.get("evidence_new"), m.get("evidence_new")):
        score += 1
    return score


def assign(gold: list[dict], model: list[dict], old: Side, new: Side, use_category=True) -> list[tuple[int, int]]:
    cands = sorted(((match_score(g, m, old, new, use_category), gi, mi)
                    for gi, g in enumerate(gold) for mi, m in enumerate(model)), key=lambda t: (-t[0], t[1], t[2]))
    used_g, used_m, pairs = set(), set(), []
    for score, gi, mi in cands:
        if score and gi not in used_g and mi not in used_m:
            used_g.add(gi)
            used_m.add(mi)
            pairs.append((gi, mi))
    return pairs


def _present(token: str, text: str) -> bool:
    flat = _SEP.sub("", text)
    return re.search(rf"(?<!\d){re.escape(_SEP.sub('', token))}(?!\d)", flat) is not None


def invented(value: Optional[str], side: Side) -> list[str]:
    """Numbers and month names in `value` that do not occur in the side's sent text."""
    if not value:
        return []
    missing = [t for t in _NUM.findall(value) if not _present(t, side.sent)]
    low = side.sent.casefold()
    missing += [mo for mo in _MONTH.findall(value) if mo.casefold() not in low]
    return missing


def score_pair(record: dict, findings: list[dict], old: Side, new: Side) -> dict:
    """Content-free counts for one pair (no values or quotes in the result)."""
    gold = [f for f in record["findings"] if f["change_type"] in REPORTABLE]
    pred = [f for f in findings if f["change_type"] in REPORTABLE]
    pairs = assign(gold, pred, old, new)
    relaxed = assign(gold, pred, old, new, use_category=False)
    type_ok = sum(gold[gi]["change_type"] == pred[mi]["change_type"] for gi, mi in pairs)
    inv = 0
    for f in findings:
        if invented(f.get("old_value"), old) or invented(f.get("evidence_old"), old) or \
                invented(f.get("new_value"), new) or invented(f.get("evidence_new"), new):
            inv += 1
    quotes = [(f.get(k), s) for f in findings for k, s in (("evidence_old", old), ("evidence_new", new)) if f.get(k)]
    verbatim = sum(bool(find_spans(s.sent, q)) for q, s in quotes)
    soft = [f for f in record["findings"] if f["change_type"] in ("not_addressed", "uncertain")]
    removed = [m for m in findings if m["change_type"] == "removed"]
    false_removals = 0
    for m in removed:
        if SCOPE_CASES & set(record["case_types"]) or any(
                match_score(g, m, old, new, use_category=False) for g in soft):
            false_removals += 1
    return {"gold": len(gold), "pred": len(pred), "tp": len(pairs), "tp_relaxed": len(relaxed),
            "type_agree": type_ok, "findings": len(findings), "invented": inv,
            "quotes": len(quotes), "quotes_verbatim": verbatim, "false_removals": false_removals,
            "scope_pair": bool(SCOPE_CASES & set(record["case_types"]))}


def prf(tp: int, pred: int, gold: int) -> tuple[float, float, float]:
    p = tp / pred if pred else (1.0 if not gold else 0.0)
    r = tp / gold if gold else 1.0
    f = 2 * p * r / (p + r) if p + r else 0.0
    return p, r, f


def signature(findings: Optional[list[dict]]) -> Optional[frozenset]:
    if findings is None:
        return None
    return frozenset((f["category"], f["change_type"], norm(f.get("old_value")), norm(f.get("new_value")))
                     for f in findings)


def percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    v = sorted(values)
    k = (len(v) - 1) * q
    lo, hi = int(k), min(int(k) + 1, len(v) - 1)
    return v[lo] + (v[hi] - v[lo]) * (k - lo)
