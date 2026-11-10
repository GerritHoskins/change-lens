"""Stage data types (03 §3, §9.3). Illustrative shapes; I-1..I-5 refine them."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Literal, Optional

from changelens.topics import topic_for_category

Kind = Literal["text", "pdf"]
Scope = Literal["complete", "partial", "unknown"]


class ParseRejected(Exception):
    """The version cannot be used; `code` is a stable, content-free reason."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class Locator:
    """07 §4 locator. Text: offsets into the exact decoded text (page None). PDF: 1-based `page`,
    offsets into that page's exact PDFium `get_text_range()` output, line endings included."""
    char_start: int
    char_end: int
    page: Optional[int] = None


@dataclass(frozen=True)
class Block:
    text: str
    locator: Locator
    hidden: bool = False
    # off_page | no_ink | tiny (07 §4 rules), covered (I-6: under an image or shape), or page_geometry (mapping failed its PDFium cross-check) | page_too_large (fail closed)
    hidden_reason: Optional[str] = None


@dataclass(frozen=True)
class ParseWarning:
    """Content-free: a code plus, where useful, a page and span. Never the text itself."""
    code: str
    page: Optional[int] = None
    char_start: Optional[int] = None
    char_end: Optional[int] = None


# Warnings that make a comparison partial: some content could not be read or checked (AC-11).
PARTIAL_WARNINGS = frozenset({"no_text_layer", "unextracted_region", "visibility_unchecked"})


@dataclass
class ParsedDocument:
    kind: Kind
    pages: list[str]  # text: one entry; pdf: one entry per page
    blocks: list[Block]
    page_count: Optional[int] = None
    warnings: list[ParseWarning] = field(default_factory=list)

    def slice(self, loc: Locator) -> str:
        page = self.pages[(loc.page or 1) - 1]
        return page[loc.char_start:loc.char_end]

    def word_count(self) -> int:
        return sum(len(p.split()) for p in self.pages)

    def to_json(self) -> dict:
        return {"kind": self.kind, "pages": self.pages, "page_count": self.page_count,
                "blocks": self.blocks_json(), "warnings": [asdict(w) for w in self.warnings]}

    def blocks_json(self) -> list[dict]:
        return [{"locator": asdict(b.locator), "hidden": b.hidden, "hidden_reason": b.hidden_reason}
                for b in self.blocks]

    @classmethod
    def from_json(cls, d: dict) -> "ParsedDocument":
        return cls.from_stored(d["kind"], d["pages"], d["blocks"], d["page_count"], d["warnings"])

    @classmethod
    def from_stored(cls, kind: str, pages: list[str], blocks: list[dict], page_count, warnings: list[dict]) -> "ParsedDocument":
        doc = cls(kind, list(pages), [], page_count, [ParseWarning(**w) for w in warnings])
        for b in blocks:
            loc = Locator(**b["locator"])
            doc.blocks.append(Block(doc.slice(loc), loc, b.get("hidden", False), b.get("hidden_reason")))
        return doc


@dataclass(frozen=True)
class Evidence:
    """`quote` must equal the parsed page text [char_start:char_end] of `side` (AC-9)."""
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
    old_value: Optional[str] = None  # normalised fact values (I-3); content, never logged
    new_value: Optional[str] = None
    note: Optional[str] = None  # wording key for omissions, e.g. absent_from_replacement (02 §3)
    confidence: float = 1.0  # lowest fact confidence; routing only, never shown as evidence (AC-10)
    group: str = "other"  # prioritised | needs_review | other (03a P5.5)

    @property
    def topic(self) -> str:
        return topic_for_category(self.category)


@dataclass(frozen=True)
class ExtractedFact:
    type: str
    raw_text: str
    normalised_value: str
    locator: Locator
    status: Literal["ok", "ambiguous", "unextracted"]
    confidence: float
    subject: str = ""  # normalised subject: the I-3 alignment key is (type, subject)
    ambiguity: Optional[str] = None  # ambiguous_date | ambiguous_entity | ambiguous_value | contradiction
    context: str = ""  # the whole sentence or list item around the quote, whitespace-collapsed

    @property
    def topic(self) -> str:
        return topic_for_category(self.type)


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
    presentation_only: list[Evidence] = field(default_factory=list)  # moved blocks, same text
