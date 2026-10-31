"""The `extract` stage (03 §2, 03a P5.1; I-2): visible blocks -> ExtractedFacts with exact locators.

Visible blocks are sent in chunks, numbered, as untrusted data. The model returns a `FactList`
whose facts name a block number and a quote; the quote is located deterministically in that
block's page text (whitespace-flexible), so every locator is ours and `raw_text` is always the
exact parsed slice. Facts whose quote cannot be found are dropped and counted, never guessed.

A chunk whose output is still invalid after the adapter's one retry is marked unextracted and the
comparison becomes partial (AC-11). Unavailability and the cost ceiling propagate: there is no
fallback model (06, 2026-10-31), so the job is retried later instead.

Results are cached per version (03 §2, AD-4) under a key that covers the version hash, this
stage's prompt and schema, and the model config, so any change invalidates the cache. Results with
unextracted chunks are never cached.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import asdict, dataclass, field
from typing import Optional, Protocol, Sequence

from changelens.llm.errors import LlmOutputInvalid
from changelens.llm.schemas import FACT_LIST
from changelens.pipeline.types import Block, ExtractedFact, Locator, ParsedDocument

EXTRACT_VERSION = "extract-v1"
CHUNK_CHARS = 6000
CONFIDENCE = {"high": 0.9, "medium": 0.6, "low": 0.3}

SYSTEM = """You extract the facts of a client brief so two versions can be compared later.

The data block holds one version's visible text as numbered lines: "[n] text". Return every
fact that a later version could add, change or drop:
- deliverable: a thing to be produced or done (a page, a feature, a service, a document).
- quantity: an amount, count, budget, price, size or other number tied to something.
- date_deadline: a date, deadline, duration or milestone.
- responsibility_owner: who provides, does, hosts, pays for or owns something.
- approval: who signs off, approves or must confirm something, and how.
- other_material: any other requirement or condition that changes the work or the price.

For each fact:
- subject: a short, stable name for what the fact is about, without its value
  (for example "budget", "deadline", "blog page", "hosting"), lower case.
- value: the value as written (amount, date, name, "included", "excluded"), or null if none.
- block: the number n of the line the quote comes from.
- quote: an exact, contiguous copy of the shortest text in that line (it may continue onto the
  next lines) that states the fact. Copy characters exactly; never paraphrase or complete it.
- ambiguity: "ambiguous_date" if a date could be read two ways (03/04, next Friday),
  "ambiguous_entity" if it is unclear who or what is meant, "ambiguous_value" if the value is
  hedged or unclear (around, TBD, ca.), otherwise null.
- confidence: high, medium or low.

List deliverables one by one when a line lists several. Do not invent facts, values or numbers
that are not in the text. Headings, greetings and notes addressed to the reader are not facts.
Return {"facts": []} if there are none."""

# Fingerprint of everything that shapes the output, for the cache key.
PROMPT_HASH = hashlib.sha256((EXTRACT_VERSION + SYSTEM + json.dumps(FACT_LIST, sort_keys=True))
                             .encode()).hexdigest()[:16]


class Llm(Protocol):
    def structured(self, schema: str, system: str, data: Sequence[str]) -> dict: ...


class FactCache(Protocol):
    def get(self, key: str) -> Optional[dict]: ...

    def put(self, key: str, value: dict) -> None: ...


@dataclass
class ExtractionResult:
    facts: list[ExtractedFact] = field(default_factory=list)
    unextracted: list[Locator] = field(default_factory=list)  # first..last block of each failed chunk
    unlocated: int = 0  # model facts whose quote was not found in the cited block's page
    chunks: int = 0
    cached: bool = False

    def to_json(self) -> dict:
        return {"facts": [asdict(f) for f in self.facts],
                "unextracted": [asdict(u) for u in self.unextracted],
                "unlocated": self.unlocated, "chunks": self.chunks}

    @classmethod
    def from_json(cls, d: dict, cached: bool = False) -> "ExtractionResult":
        facts = [ExtractedFact(**{**f, "locator": Locator(**f["locator"])}) for f in d["facts"]]
        return cls(facts, [Locator(**u) for u in d["unextracted"]], d["unlocated"], d["chunks"], cached)


def cache_key(version_sha256: str, model_config_id: str) -> str:
    return hashlib.sha256(f"{version_sha256}|{PROMPT_HASH}|{model_config_id}".encode()).hexdigest()


def chunks(blocks: Sequence[Block], limit: int = CHUNK_CHARS) -> list[list[Block]]:
    out: list[list[Block]] = []
    cur: list[Block] = []
    size = 0
    for b in blocks:
        if cur and size + len(b.text) > limit:
            out.append(cur)
            cur, size = [], 0
        cur.append(b)
        size += len(b.text) + 8
    if cur:
        out.append(cur)
    return out


_WS = re.compile(r"\s+")
_SEP = re.compile(r"(?<=\d)[.,'  ](?=\d{3}\b)")
_TRIM = " \t\r\n.,;:!?\"'()[]*-–"


def normalise(s: Optional[str]) -> str:
    """Comparison form: case-folded, single spaces, digit-group separators removed. I-3 adds dates."""
    if not s:
        return ""
    return _SEP.sub("", _WS.sub(" ", s).strip(_TRIM).casefold())


def locate(doc: ParsedDocument, block: Block, quote: str) -> Optional[Locator]:
    """The quote's exact span on `block`'s page, starting inside the block; None if absent."""
    words = quote.split()
    if not words:
        return None
    page = doc.pages[(block.locator.page or 1) - 1]
    pattern = re.compile(r"\s+".join(re.escape(w) for w in words))
    m = pattern.search(page, block.locator.char_start)
    if m is None or m.start() >= block.locator.char_end:
        return None
    return Locator(m.start(), m.end(), block.locator.page)


def _data(chunk: Sequence[Block]) -> str:
    return "\n".join(f"[{i}] {b.text}" for i, b in enumerate(chunk, 1))


def extract(doc: ParsedDocument, llm: Llm) -> ExtractionResult:
    visible = [b for b in doc.blocks if not b.hidden]  # hidden text never reaches the model (AC-18)
    result = ExtractionResult()
    for chunk in chunks(visible, CHUNK_CHARS):
        result.chunks += 1
        try:
            out = llm.structured("FactList", SYSTEM, [_data(chunk)])
        except LlmOutputInvalid:
            first, last = chunk[0].locator, chunk[-1].locator
            result.unextracted.append(Locator(first.char_start, last.char_end if last.page == first.page
                                              else len(doc.pages[(first.page or 1) - 1]), first.page))
            continue
        for f in out["facts"]:
            n = f["block"]
            loc = locate(doc, chunk[n - 1], f["quote"]) if 1 <= n <= len(chunk) else None
            if loc is None:
                result.unlocated += 1
                continue
            result.facts.append(ExtractedFact(
                type=f["type"], raw_text=doc.slice(loc), normalised_value=normalise(f["value"]),
                locator=loc, status="ambiguous" if f["ambiguity"] else "ok",
                confidence=CONFIDENCE[f["confidence"]], subject=normalise(f["subject"]),
                ambiguity=f["ambiguity"]))
    return result


def extract_cached(doc: ParsedDocument, version_sha256: str, model_config_id: str,
                   cache: FactCache, llm: Llm) -> ExtractionResult:
    key = cache_key(version_sha256, model_config_id)
    hit = cache.get(key)
    if hit is not None:
        return ExtractionResult.from_json(hit, cached=True)
    result = extract(doc, llm)
    if not result.unextracted:
        cache.put(key, result.to_json())
    return result
