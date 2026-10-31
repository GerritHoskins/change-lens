"""Stage data types (03 §3, §9.3). Illustrative shapes; I-1..I-5 refine them."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal, Optional

Kind = Literal["text", "pdf"]
Scope = Literal["complete", "partial", "unknown"]


@dataclass(frozen=True)
class Locator:
    """Character offsets into the version's immutable parsed text; `page` is 1-based for PDFs."""
    char_start: int
    char_end: int
    page: Optional[int] = None


@dataclass(frozen=True)
class Block:
    text: str
    locator: Locator
    hidden: bool = False


@dataclass(frozen=True)
class ParseWarning:
    code: str
    page: Optional[int] = None


@dataclass
class ParsedDocument:
    kind: Kind
    text: str
    blocks: list[Block]
    page_count: Optional[int] = None
    warnings: list[ParseWarning] = field(default_factory=list)

    def blocks_json(self) -> list[dict]:
        return [{"locator": asdict(b.locator), "hidden": b.hidden} for b in self.blocks]

    @classmethod
    def from_stored(cls, kind: str, text: str, blocks: list[dict], page_count, warnings: list[dict]) -> "ParsedDocument":
        rebuilt = []
        for b in blocks:
            loc = Locator(**b["locator"])
            rebuilt.append(Block(text[loc.char_start:loc.char_end], loc, b.get("hidden", False)))
        return cls(kind, text, rebuilt, page_count, [ParseWarning(**w) for w in warnings])


@dataclass(frozen=True)
class Evidence:
    """`quote` must equal parsed_text[char_start:char_end] of `side` (AC-9)."""
    side: Literal["earlier", "later"]
    locator: Locator
    quote: str


@dataclass
class DraftFinding:
    change_type: str
    category: str
    evidence: list[Evidence]
    explanation: Optional[str] = None
    uncertainty: Optional[str] = None
    priority: int = 0


@dataclass(frozen=True)
class ExtractedFact:
    type: str
    raw_text: str
    normalised_value: str
    locator: Locator
    status: Literal["ok", "ambiguous", "unextracted"]
    confidence: float


@dataclass(frozen=True)
class FactPair:
    status: Literal["matched", "unmatched_earlier", "unmatched_later", "ambiguous"]
    earlier: Optional[ExtractedFact]
    later: Optional[ExtractedFact]


@dataclass
class VerifyResult:
    findings: list[DraftFinding]
    withheld_count: int
    unexplained: list[Evidence]
