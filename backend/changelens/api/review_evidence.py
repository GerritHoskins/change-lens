"""I-26 content-free evidence observations supplied by the device, never client approval.

The API can check source kinds and side presence, but cannot prove the device placed a PDF
highlight or opened a page. Historical rows retain null telemetry; absence is not a false value.
"""
from __future__ import annotations

from typing import Literal, Mapping, Sequence

from pydantic import BaseModel, ConfigDict, StrictBool

from changelens.api.errors import ApiError

EvidenceMode = Literal["pdf_highlight", "text_fallback", "text_only"]
SIDE_FIELDS = {"earlier": "before", "later": "after"}
KIND_MODES = {"text": {"text_only"}, "pdf": {"pdf_highlight", "text_fallback"}}


class EvidenceModes(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Both keys are required. Null means no finding evidence on this side, never "not checked".
    before: EvidenceMode | None
    after: EvidenceMode | None


class ReviewTelemetryIn(BaseModel):
    """Inherit in ReviewIn; every new review must carry device observations, with no defaults."""
    model_config = ConfigDict(extra="forbid")

    evidence_mode: EvidenceModes
    page_opened: StrictBool


def validate_review_evidence(body: ReviewTelemetryIn, evidence: Sequence[dict],
                             source_kinds: Mapping[str, str]) -> dict:
    """Return only ReviewEvent metadata columns after checking the tenant-resolved finding.

`source_kinds` comes from this comparison's earlier/later SourceVersions, not request data.
Repeated evidence on one side shares that side's display mode. The current contract supports
text and PDF; image placement needs its own future mode contract rather than guessing one.
"""
    present = set()
    for item in evidence:
        side = item.get("side") if isinstance(item, dict) else None
        if side not in SIDE_FIELDS:
            raise ApiError(422, "invalid_request", "finding evidence side is unsupported")
        present.add(side)
    if not present:
        raise ApiError(422, "invalid_request", "review requires finding evidence")
    modes = body.evidence_mode.model_dump()
    for side, field in SIDE_FIELDS.items():
        mode = modes[field]
        if side not in present:
            if mode is not None:
                raise ApiError(422, "invalid_request", "absent evidence side requires a null mode")
            continue
        allowed = KIND_MODES.get(source_kinds.get(side), set())
        if mode not in allowed:
            raise ApiError(422, "invalid_request", "evidence mode does not match its source kind")
    return {"evidence_mode_before": modes["before"], "evidence_mode_after": modes["after"],
            "page_opened": body.page_opened}


def review_evidence_out(event) -> dict:
    """Keep old observations unknown; never derive a mode or approval from another field."""
    return {"evidence_mode": {"before": event.evidence_mode_before, "after": event.evidence_mode_after},
            "page_opened": event.page_opened}
