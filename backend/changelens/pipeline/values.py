"""Deterministic value and qualifier guards for comparison (03 §4.1, AC-1, AC-8; I-3).

`canonical` turns a fact value into a comparison form, so formatting-only differences ("EUR 12,000"
vs "€12000", "14 March 2027" vs "March 14, 2027") compare equal while any change of number, date or
unit does not. Dates written only with digits and slashes or dots are left as written: their day and
month order is ambiguous (AC-7), so they never compare equal to a spelled-out date.

`qualifiers` extracts the negation, modality and limit words of a passage; a pair whose qualifiers
differ is never equivalent ("must" -> "may", "capped" -> "estimated", "including" -> "excluding").
"""
from __future__ import annotations

import re
from typing import Optional

MONTHS = {m: i for i, m in enumerate(
    ["january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
     "november", "december"], 1)}
MONTHS.update({m[:3]: i for m, i in list(MONTHS.items())})
MONTHS["sept"] = 9
_MONTH = "(" + "|".join(sorted(MONTHS, key=len, reverse=True)) + r")\.?"
_DMY = re.compile(rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?{_MONTH}(?:,?\s+(\d{{4}}))?\b")
_MDY = re.compile(rf"\b{_MONTH}\s+(\d{{1,2}})(?:st|nd|rd|th)?(?:,?\s+(\d{{4}}))?\b")
_CURRENCY = [(re.compile(r"€|\beuros?\b"), " eur "), (re.compile(r"\$|\busd\b|\bdollars?\b"), " usd "),
             (re.compile(r"£|\bgbp\b|\bpounds?\b"), " gbp ")]
_THOUSANDS = re.compile(r"(?<=\d)[,.'   ](?=\d{3}(?!\d))")
_NUM_UNIT = re.compile(r"(\d)([a-z])")
_WS = re.compile(r"\s+")
_TRIM = " \t\r\n.,;:!?\"'()[]*-–"


def _date(day: str, month: str, year: Optional[str]) -> str:
    return f"{year or '----'}-{MONTHS[month.casefold().rstrip('.')]:02d}-{int(day):02d}"


def canonical(value: Optional[str]) -> str:
    if not value:
        return ""
    s = _WS.sub(" ", value).casefold()
    s = _DMY.sub(lambda m: _date(m.group(1), m.group(2), m.group(3)), s)
    s = _MDY.sub(lambda m: _date(m.group(2), m.group(1), m.group(3)), s)
    for pattern, repl in _CURRENCY:
        s = pattern.sub(repl, s)
    s = _THOUSANDS.sub("", s)
    s = _NUM_UNIT.sub(r"\1 \2", s)  # "5days" -> "5 days"
    return _WS.sub(" ", s).strip(_TRIM)


_FIGURE = re.compile(r"\d+(?:[.,/]\d+)*|\b(?:eur|usd|gbp)\b")


def figures(text: Optional[str]) -> list[str]:
    """Numbers, dates (canonical) and currencies in a passage, sorted: the 03 §4.1 rule-1 values."""
    return sorted(_FIGURE.findall(canonical(text)))


# Word groups whose presence changes binding force, polarity or limits (03 §4.1 rule 2, AC-8).
_QUALIFIERS = {
    "negation": r"\b(?:not|no|never|none|without|neither|nor|no longer|n't)\b|n't\b",
    "must": r"\b(?:must|shall|required|mandatory|has to|have to|needs? to|due|is to|are to)\b",
    "should": r"\b(?:should|recommended|ideally|preferably)\b",
    "may": r"\b(?:may|might|optional|optionally|can|could|if possible)\b",
    "only": r"\b(?:only|exclusively|solely)\b",
    "at_least": r"\b(?:at least|minimum|min\.|no less than|or more)\b",
    "at_most": r"\b(?:at most|up to|maximum|max\.|no more than|capped|cap|not exceed)\b",
    "approx": r"\b(?:about|around|approximately|approx\.|roughly|circa|ca\.|estimated|estimate|tbd|tbc)\b",
    "including": r"\b(?:incl\.|including|inclusive|included)\b",
    "excluding": r"\b(?:excl\.|excluding|exclusive|excluded|plus vat|\+ ?vat)\b",
}
_QUAL_RE = {k: re.compile(v, re.I) for k, v in _QUALIFIERS.items()}


def qualifiers(text: str) -> frozenset[str]:
    return frozenset(k for k, rx in _QUAL_RE.items() if rx.search(text or ""))


def qualifiers_differ(a: str, b: str) -> bool:
    return qualifiers(a) != qualifiers(b)
