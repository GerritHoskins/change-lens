"""The I-22 subset of 03 §9.4. Every route resolves the tenant first and reads through a tenant repo."""
from __future__ import annotations

import hashlib
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException as StarletteHTTPException

from changelens import MODEL_CONFIG_ID, PIPELINE_VERSION, jobs
from changelens.api import uploads
from changelens.api.auth import current_tenant
from changelens.api.errors import ApiError, not_found
from changelens.domain.models import Comparison, Project, SourceVersion
from changelens.storage import original_key

router = APIRouter()
SCOPES = ("complete", "partial", "unknown")


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    client_label: Optional[str] = Field(default=None, max_length=200)


class ComparisonIn(BaseModel):
    earlier_id: uuid.UUID
    later_id: uuid.UUID
    scope: str  # checked by hand so a bad value maps to scope_not_confirmed (AC-14)


def _project_out(p: Project) -> dict:
    return {"id": str(p.id), "name": p.name, "client_label": p.client_label, "created_at": p.created_at.isoformat()}


def _version_out(v: SourceVersion) -> dict:
    return {"id": str(v.id), "project_id": str(v.project_id), "label": v.label, "kind": v.kind,
            "status": v.status, "reject_reason": v.reject_reason, "size_bytes": v.size_bytes,
            "page_count": v.page_count, "sha256": v.sha256, "parse_warnings": v.parse_warnings,
            "created_at": v.created_at.isoformat()}


def _comparison_out(c: Comparison) -> dict:
    return {"id": str(c.id), "project_id": str(c.project_id), "earlier_id": str(c.earlier_id),
            "later_id": str(c.later_id), "scope": c.scope_snapshot, "status": c.status,
            "pipeline_version": c.pipeline_version, "model_config_id": c.model_config_id,
            "placeholder": c.pipeline_version.startswith("placeholder"),
            "cost_ceiling": str(c.cost_ceiling), "cost_actual": None if c.cost_actual is None else str(c.cost_actual),
            "warnings": c.warnings, "created_at": c.created_at.isoformat()}


@router.post("/projects", status_code=201)
def create_project(body: ProjectIn, request: Request, tenant: uuid.UUID = Depends(current_tenant)):
    with request.app.state.db.tenant_scope(tenant) as repo:
        p = repo.add(Project(name=body.name, client_label=body.client_label))
        repo.s.refresh(p)
        return _project_out(p)


@router.get("/projects/{project_id}")
def get_project(project_id: uuid.UUID, request: Request, tenant: uuid.UUID = Depends(current_tenant)):
    with request.app.state.db.tenant_scope(tenant) as repo:
        p = repo.project(project_id)
        if p is None:
            raise not_found()
        return _project_out(p)


async def _read_upload(request: Request) -> tuple[bytes, Optional[str]]:
    """Return (bytes, label) from multipart `file` or `text`, plus `label`. Held in memory only."""
    limits = request.app.state.settings.limits
    try:
        async with request.form(max_files=1, max_fields=2, max_part_size=limits.max_text_bytes + 1) as form:
            label = form.get("label")
            file, text = form.get("file"), form.get("text")
            if (file is None) == (text is None):
                raise ApiError(422, "invalid_request", "send exactly one of file or text")
            if isinstance(file, UploadFile):
                data = await file.read()
            elif isinstance(text, str):
                data = text.encode("utf-8")
            else:
                raise ApiError(422, "invalid_request", "file must be a file part and text a field")
    except StarletteHTTPException as exc:  # Starlette wraps multipart errors as 400
        if "maximum size" in str(exc.detail):
            raise ApiError(413, "limit_exceeded", "bytes") from None
        raise ApiError(422, "invalid_request", "malformed multipart body") from None
    return data, label if isinstance(label, str) else None


@router.post("/projects/{project_id}/versions", status_code=201)
async def upload_version(project_id: uuid.UUID, request: Request, tenant: uuid.UUID = Depends(current_tenant)):
    state = request.app.state
    data, label = await _read_upload(request)
    label = uploads.check_label(label, state.settings.limits)
    kind = uploads.sniff(data)
    uploads.check_limits(data, kind, state.settings.limits)
    with state.db.tenant_scope(tenant) as repo:
        if repo.project(project_id) is None:
            raise not_found()
    key = original_key(tenant, project_id)
    state.store.put(key, data)  # immutable original (AC-15)
    with state.db.tenant_scope(tenant) as repo:
        v = repo.add(SourceVersion(project_id=project_id, label=label, kind=kind, original_object_key=key,
                                   sha256=hashlib.sha256(data).hexdigest(), size_bytes=len(data),
                                   status="uploaded", parse_warnings=[]))
        jobs.enqueue(repo.s, tenant, "parse", {"version_id": v.id}, state.settings.job_max_attempts)
        repo.s.refresh(v)
        return _version_out(v)


@router.get("/versions/{version_id}")
def get_version(version_id: uuid.UUID, request: Request, tenant: uuid.UUID = Depends(current_tenant)):
    with request.app.state.db.tenant_scope(tenant) as repo:
        v = repo.version(version_id)
        if v is None:
            raise not_found()
        return _version_out(v)


@router.post("/projects/{project_id}/comparisons", status_code=202)
def create_comparison(project_id: uuid.UUID, body: ComparisonIn, request: Request,
                      tenant: uuid.UUID = Depends(current_tenant)):
    """This call is the user's order and scope confirmation (AC-14)."""
    settings = request.app.state.settings
    with request.app.state.db.tenant_scope(tenant) as repo:
        if repo.project(project_id) is None:
            raise not_found()
        earlier, later = repo.version(body.earlier_id), repo.version(body.later_id)
        if earlier is None or later is None or earlier.project_id != project_id or later.project_id != project_id:
            raise not_found()
        if body.scope not in SCOPES:
            raise ApiError(422, "scope_not_confirmed", "scope must be complete, partial or unknown")
        if earlier.id == later.id:
            raise ApiError(422, "scope_not_confirmed", "earlier and later must differ")
        if earlier.status != "parsed" or later.status != "parsed":
            raise ApiError(409, "scope_not_confirmed", "both versions must be parsed")
        c = repo.add(Comparison(project_id=project_id, earlier_id=earlier.id, later_id=later.id,
                                scope_snapshot=body.scope, pipeline_version=PIPELINE_VERSION,
                                model_config_id=MODEL_CONFIG_ID, status="queued",
                                cost_ceiling=settings.cost_ceiling_eur, warnings=[]))
        jobs.enqueue(repo.s, tenant, "compare", {"comparison_id": c.id}, settings.job_max_attempts)
        return {"id": str(c.id), "status": c.status}


@router.get("/comparisons/{comparison_id}")
def get_comparison(comparison_id: uuid.UUID, request: Request, tenant: uuid.UUID = Depends(current_tenant)):
    with request.app.state.db.tenant_scope(tenant) as repo:
        c = repo.comparison(comparison_id)
        if c is None:
            raise not_found()
        repo.s.refresh(c)
        return _comparison_out(c)


@router.get("/comparisons/{comparison_id}/findings")
def get_findings(comparison_id: uuid.UUID, request: Request, tenant: uuid.UUID = Depends(current_tenant)):
    with request.app.state.db.tenant_scope(tenant) as repo:
        c = repo.comparison(comparison_id)
        if c is None:
            raise not_found()
        findings = [{"id": str(f.id), "change_type": f.change_type, "category": f.category,
                     "evidence": f.evidence, "explanation": f.explanation, "uncertainty": f.uncertainty,
                     "priority": f.priority, "revision": f.revision} for f in repo.findings(c.id)]
        return {"comparison_id": str(c.id), "status": c.status, "pipeline_version": c.pipeline_version,
                "placeholder": c.pipeline_version.startswith("placeholder"), "findings": findings,
                "withheld_count": c.withheld_count, "unexplained_differences": [], "warnings": c.warnings}
