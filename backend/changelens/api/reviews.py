"""Report, review and evidence routes (03 §9.4; I-10).

Three states are kept apart and never derived from each other (02 §5, AC-12): the AI finding
(immutable), the user's review (append-only `ReviewEvent`s) and a client-approval record (a
separate, append-only `ClientApprovalRecord` that only its own route writes). A correction never
edits a finding: it adds a new revision that supersedes it, and the original stays (AC-15).
The findings list shows the current revision of each finding with its latest review.
"""
from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field

from changelens.api.auth import current_tenant
from changelens.api.errors import ApiError, not_found
from changelens.api.review_evidence import ReviewTelemetryIn, validate_review_evidence, review_evidence_out
from changelens.domain.models import ClientApprovalRecord, Finding, ReviewEvent
from changelens.llm.schemas import CATEGORIES, CHANGE_TYPES
from changelens.topics import canonical_category, topic_counts, topic_for_category

router = APIRouter()
DEV_ACTOR = "dev-token-user"  # I-8 replaces this with the signed-in user
ACTIONS = ("confirmed", "corrected", "dismissed", "note")
REVIEWABLE = ("complete", "partial")
# UI wording for the record; never "approved" or "agreed" (02 §5, AC-12).
APPROVAL_LABEL = "Client approval recorded (not verified by ChangeLens)"


class Correction(BaseModel):
    change_type: Optional[str] = None
    category: Optional[str] = None
    explanation: Optional[str] = Field(default=None, max_length=1000)


class ReviewIn(ReviewTelemetryIn):
    action: str
    note: Optional[str] = Field(default=None, max_length=2000)
    correction: Optional[Correction] = None


class ApprovalIn(BaseModel):
    evidence_text: str = Field(min_length=1, max_length=5000)
    stated_by: str = Field(min_length=1, max_length=200)
    stated_at: datetime


def _review_out(r: ReviewEvent) -> dict:
    return {"id": str(r.id), "finding_id": str(r.finding_id), "action": r.action, "note": r.note,
            "actor": r.actor, "at": r.created_at.isoformat(), **review_evidence_out(r)}


def _approval_out(a: ClientApprovalRecord) -> dict:
    return {"id": str(a.id), "finding_id": str(a.finding_id), "label": APPROVAL_LABEL,
            "evidence_text": a.evidence_text, "stated_by": a.stated_by, "stated_at": a.stated_at.isoformat(),
            "recorded_by": a.recorded_by, "recorded_at": a.created_at.isoformat()}


def _chains(findings: list[Finding]) -> dict[uuid.UUID, list[Finding]]:
    """Current revision id -> its chain, oldest first."""
    by_id = {f.id: f for f in findings}
    superseded = {f.supersedes_id for f in findings if f.supersedes_id}
    chains = {}
    for f in findings:
        if f.id in superseded:
            continue
        chain, cur = [], f
        while cur is not None:
            chain.insert(0, cur)
            cur = by_id.get(cur.supersedes_id) if cur.supersedes_id else None
        chains[f.id] = chain
    return chains


def _finding_out(f: Finding, chain: list[Finding], reviews: list[ReviewEvent],
                 approvals: list[ClientApprovalRecord]) -> dict:
    ids = {x.id for x in chain}
    last = [r for r in reviews if r.finding_id in ids and r.action != "note"]
    return {"id": str(f.id), "change_type": f.change_type, "category": canonical_category(f.category),
            "topic": topic_for_category(f.category), "evidence": f.evidence,
            "explanation": f.explanation, "uncertainty": f.uncertainty, "note": f.note, "group": f.review_group,
            "priority": f.priority, "revision": f.revision,
            "supersedes_id": str(f.supersedes_id) if f.supersedes_id else None,
            "review": _review_out(last[-1]) if last else None,
            "notes": sum(r.finding_id in ids and r.action == "note" for r in reviews),
            "client_approval_recorded": any(a.finding_id in ids for a in approvals)}


@router.get("/comparisons/{comparison_id}/findings")
def get_findings(comparison_id: uuid.UUID, request: Request, tenant: uuid.UUID = Depends(current_tenant)):
    with request.app.state.db.tenant_scope(tenant) as repo:
        if not repo.lock_for_comparison(comparison_id):
            raise not_found()
        c = repo.comparison(comparison_id)
        if c is None:
            raise not_found()
        rows = repo.findings(c.id)
        chains = _chains(rows)
        reviews, approvals = repo.reviews([f.id for f in rows]), repo.approvals([f.id for f in rows])
        findings = [_finding_out(chain[-1], chain, reviews, approvals)
                    for chain in sorted(chains.values(), key=lambda ch: ch[-1].priority)]
        prioritised = sum(f["group"] == "prioritised" for f in findings)
        # AC-13: the prioritised list is a selected summary; everything else stays reachable.
        other = len(findings) - prioritised + len(c.unexplained) + len(c.presentation_only)
        return {"comparison_id": str(c.id), "status": c.status, "pipeline_version": c.pipeline_version,
                "placeholder": c.pipeline_version.startswith("placeholder"), "findings": findings,
                "topic_counts": topic_counts(f["category"] for f in findings),
                "summary": {"selected": True, "prioritised": prioritised, "other_differences": other},
                "withheld_count": c.withheld_count, "unexplained_differences": c.unexplained,
                "presentation_only": c.presentation_only, "warnings": c.warnings,
                "earlier_id": str(c.earlier_id), "later_id": str(c.later_id), "scope": c.scope_snapshot}


def _current(repo, finding_id: uuid.UUID, lock: bool = False) -> tuple[Finding, list[Finding]]:
    f = repo.finding(finding_id, lock)
    if f is None:
        raise not_found()
    chains = _chains(repo.findings(f.comparison_id))
    chain = next((ch for ch in chains.values() if f in ch), None)
    if chain is None or chain[-1].id != f.id:
        raise ApiError(409, "finding_superseded", "review the current revision")
    c = repo.comparison(f.comparison_id)
    if c is None or c.status not in REVIEWABLE:
        raise ApiError(409, "comparison_not_ready")
    return f, chain


@router.get("/findings/{finding_id}")
def get_finding(finding_id: uuid.UUID, request: Request, tenant: uuid.UUID = Depends(current_tenant)):
    """A finding with all its revisions, reviews and client-approval records (history view)."""
    with request.app.state.db.tenant_scope(tenant) as repo:
        if not repo.lock_for_finding(finding_id):
            raise not_found()
        f = repo.finding(finding_id)
        if f is None:
            raise not_found()
        chain = next(ch for ch in _chains(repo.findings(f.comparison_id)).values() if f in ch)
        ids = [x.id for x in chain]
        reviews, approvals = repo.reviews(ids), repo.approvals(ids)
        current = _finding_out(chain[-1], chain, reviews, approvals)
        return {**current, "revisions": [_finding_out(x, [x], [], []) for x in chain],
                "reviews": [_review_out(r) for r in reviews], "client_approvals": [_approval_out(a) for a in approvals]}


@router.post("/findings/{finding_id}/reviews", status_code=201)
def review(finding_id: uuid.UUID, body: ReviewIn, request: Request, tenant: uuid.UUID = Depends(current_tenant)):
    """Confirm, correct, dismiss or note. Writes only ReviewEvents (and, for a correction, a new
    finding revision); there is no path from here to a ClientApprovalRecord (AC-12)."""
    if body.action not in ACTIONS:
        raise ApiError(422, "invalid_request", "action must be confirmed, corrected, dismissed or note")
    if body.action == "note" and not (body.note or "").strip():
        raise ApiError(422, "invalid_request", "a note needs text")
    if (body.action == "corrected") != (body.correction is not None):
        raise ApiError(422, "invalid_request", "a correction is sent with action corrected, and only then")
    with request.app.state.db.tenant_scope(tenant) as repo:
        if not repo.lock_for_finding(finding_id):
            raise not_found()
        f, chain = _current(repo, finding_id, lock=True)
        comparison = repo.comparison(f.comparison_id)
        earlier, later = repo.version(comparison.earlier_id), repo.version(comparison.later_id)
        if earlier is None or later is None:
            raise not_found()
        metadata = validate_review_evidence(body, f.evidence, {"earlier": earlier.kind, "later": later.kind})
        current = f
        if body.correction is not None:
            fix = body.correction
            if fix.change_type is not None and fix.change_type not in CHANGE_TYPES:
                raise ApiError(422, "invalid_request", "unknown change_type")
            if fix.category is not None and canonical_category(fix.category) not in CATEGORIES:
                raise ApiError(422, "invalid_request", "unknown category")
            corrected = fix.model_dump()
            if corrected["category"] is not None:
                corrected["category"] = canonical_category(corrected["category"])
            changed = {k: v for k, v in corrected.items() if v is not None
                       and v != (canonical_category(f.category) if k == "category" else getattr(f, k))}
            if not changed:
                raise ApiError(422, "invalid_request", "the correction changes nothing")
            # AC-15: a new revision; the AI finding and its evidence stay as they were.
            current = repo.add(Finding(
                comparison_id=f.comparison_id, category=changed.get("category", canonical_category(f.category)),
                change_type=changed.get("change_type", f.change_type), evidence=list(f.evidence),
                explanation=changed.get("explanation", f.explanation), uncertainty=f.uncertainty, note=f.note,
                review_group=f.review_group, priority=f.priority, revision=f.revision + 1, supersedes_id=f.id))
        event = repo.add(ReviewEvent(finding_id=f.id, actor=DEV_ACTOR, action=body.action, note=body.note, **metadata))
        repo.touch_comparison(comparison)
        repo.s.refresh(event)
        chain = chain + ([current] if current is not f else [])
        ids = [x.id for x in chain]
        return {"review": _review_out(event),
                "finding": _finding_out(current, chain, repo.reviews(ids), repo.approvals(ids))}


@router.post("/findings/{finding_id}/client-approvals", status_code=201)
def record_client_approval(finding_id: uuid.UUID, body: ApprovalIn, request: Request,
                           tenant: uuid.UUID = Depends(current_tenant)):
    """Record that someone stated the client approved. Writes no ReviewEvent and changes no
    finding (AC-12). Text evidence only for now; attachments follow the upload rules later."""
    with request.app.state.db.tenant_scope(tenant) as repo:
        if not repo.lock_for_finding(finding_id):
            raise not_found()
        f, _ = _current(repo, finding_id)
        a = repo.add(ClientApprovalRecord(finding_id=f.id, evidence_text=body.evidence_text,
                                          stated_by=body.stated_by, stated_at=body.stated_at, recorded_by=DEV_ACTOR))
        repo.s.refresh(a)
        repo.touch_comparison(repo.comparison(f.comparison_id))
        return _approval_out(a)


@router.get("/versions/{version_id}/text")
def version_text(version_id: uuid.UUID, request: Request, tenant: uuid.UUID = Depends(current_tenant)):
    """Parsed text with block locators: the evidence fallback (03 §9.4)."""
    with request.app.state.db.tenant_scope(tenant) as repo:
        if not repo.lock_for_version(version_id):
            raise not_found()
        v = repo.version(version_id)
        if v is None:
            raise not_found()
        if v.status != "parsed":
            raise ApiError(409, "version_not_parsed")
        return {"id": str(v.id), "kind": v.kind, "pages": v.parsed_pages, "blocks": v.blocks}


@router.get("/versions/{version_id}/original")
def version_original(version_id: uuid.UUID, request: Request, tenant: uuid.UUID = Depends(current_tenant)):
    """The original bytes, for the evidence view. Dev deviation from 03 §9.4 (a short-lived signed
    URL): the API streams them, so a phone needs no access to the object store. The app keeps them
    in memory only (AC-25)."""
    with request.app.state.db.tenant_scope(tenant) as repo:
        if not repo.lock_for_version(version_id):
            raise not_found()
        v = repo.version(version_id)
        if v is None:
            raise not_found()
        key, kind = v.original_object_key, v.kind
        data = request.app.state.store.get(key)
    media = {"pdf": "application/pdf", "text": "text/plain; charset=utf-8"}.get(kind, "application/octet-stream")
    return Response(data, media_type=media,
                    headers={"Cache-Control": "no-store", "Content-Disposition": "inline"})
