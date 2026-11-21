"""The I-22 subset of 03 §9.4. Every route resolves the tenant first and reads through a tenant repo."""
from __future__ import annotations

import hashlib
import uuid
from decimal import Decimal
from typing import Optional

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from starlette.datastructures import UploadFile
from starlette.concurrency import run_in_threadpool
from starlette.exceptions import HTTPException as StarletteHTTPException

from changelens import jobs
from changelens.api import uploads
from changelens.api.auth import current_tenant
from changelens.api.errors import ApiError, not_found
from changelens.api.project_summaries import latest_comparison_summaries
from changelens.domain.models import Comparison, Project, SourceVersion
from changelens.domain.storage_intents import prepare_write, write_prepared, reconcile_write

router = APIRouter()
SCOPES = ("complete", "partial", "unknown")


class ProjectIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    client_label: Optional[str] = Field(default=None, max_length=200)


def _project_out(p: Project) -> dict:
    return {"id": str(p.id), "name": p.name, "client_label": p.client_label, "created_at": p.created_at.isoformat()}


def _version_out(v: SourceVersion) -> dict:
    return {"id": str(v.id), "project_id": str(v.project_id), "label": v.label, "kind": v.kind,
            "status": v.status, "reject_reason": v.reject_reason, "size_bytes": v.size_bytes,
            "page_count": v.page_count, "sha256": v.sha256, "parse_warnings": v.parse_warnings,
            "created_at": v.created_at.isoformat()}


def _comparison_out(c: Comparison) -> dict:
    reservations = c.cost_reservations or {}
    return {"id": str(c.id), "project_id": str(c.project_id), "earlier_id": str(c.earlier_id),
            "later_id": str(c.later_id), "scope": c.scope_snapshot, "status": c.status,
            "pipeline_version": c.pipeline_version, "model_config_id": c.model_config_id,
            "placeholder": c.pipeline_version.startswith("placeholder"),
            "cost_ceiling": str(c.cost_ceiling), "cost_actual": None if c.cost_actual is None else str(c.cost_actual),
            "cost_reserved": str(sum((Decimal(value) for value in reservations.values()), Decimal("0"))),
            "cost_pending": bool(reservations),
            "warnings": c.warnings, "created_at": c.created_at.isoformat()}


@router.post("/projects", status_code=201)
def create_project(body: ProjectIn, request: Request, tenant: uuid.UUID = Depends(current_tenant)):
    with request.app.state.db.tenant_scope(tenant) as repo:
        p = repo.add(Project(name=body.name, client_label=body.client_label))
        repo.s.refresh(p)
        return _project_out(p)


@router.get("/projects")
def list_projects(request: Request, tenant: uuid.UUID = Depends(current_tenant)):
    with request.app.state.db.tenant_scope(tenant) as repo:
        counts = repo.active_comparison_counts()
        latest = latest_comparison_summaries(repo)
        return {"projects": [{**_project_out(p), "comparison_counts": counts.get(p.id, {}),
                              "latest_comparison": latest.get(p.id)} for p in repo.projects()]}


@router.get("/projects/{project_id}/versions")
def list_versions(project_id: uuid.UUID, request: Request, tenant: uuid.UUID = Depends(current_tenant)):
    """Upload order only; the app never uses it as the comparison order (AC-14)."""
    with request.app.state.db.tenant_scope(tenant) as repo:
        if repo.project(project_id) is None:
            raise not_found()
        return {"versions": [_version_out(v) for v in repo.versions_of(project_id)]}


@router.get("/projects/{project_id}/comparisons")
def list_comparisons(project_id: uuid.UUID, request: Request, tenant: uuid.UUID = Depends(current_tenant)):
    with request.app.state.db.tenant_scope(tenant) as repo:
        if repo.project(project_id) is None:
            raise not_found()
        return {"comparisons": [_comparison_out(c) for c in repo.comparisons_of(project_id)]}


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
    return await run_in_threadpool(_store_version, state, tenant, project_id, data, label, kind)


def _store_version(state, tenant, project_id, data, label, kind):
    # The legacy single-upload path needs the same crash-safe compensation as I-24.
    # Its random request lock is independent of client-provided comparison keys.
    request_key, ticket = "upload-" + str(uuid.uuid4()), None
    try:
        with state.db.tenant_scope(tenant) as repo:
            repo.lock_project(project_id)
            repo.lock_comparison_key(request_key)
            if repo.project(project_id) is None:
                raise not_found()
            ticket = prepare_write(state.db, tenant, project_id, request_key)
            write_prepared(state.db, state.store, ticket, data)
            v = repo.add(SourceVersion(project_id=project_id, label=label, kind=kind,
                original_object_key=ticket.object_key, sha256=hashlib.sha256(data).hexdigest(), size_bytes=len(data),
                status="uploaded", parse_warnings=[]))
            jobs.enqueue(repo.s, tenant, "parse", {"version_id": v.id}, state.settings.job_max_attempts)
            repo.touch_version(v)
            repo.s.refresh(v)
            result = _version_out(v)
        return result
    finally:
        if ticket is not None:
            reconcile_write(state.db, state.store, tenant, ticket.id)


@router.get("/versions/{version_id}")
def get_version(version_id: uuid.UUID, request: Request, tenant: uuid.UUID = Depends(current_tenant)):
    with request.app.state.db.tenant_scope(tenant) as repo:
        v = repo.version(version_id)
        if v is None:
            raise not_found()
        return _version_out(v)


@router.get("/comparisons/{comparison_id}")
def get_comparison(comparison_id: uuid.UUID, request: Request, tenant: uuid.UUID = Depends(current_tenant)):
    with request.app.state.db.tenant_scope(tenant) as repo:
        c = repo.comparison(comparison_id)
        if c is None:
            raise not_found()
        repo.s.refresh(c)
        return _comparison_out(c)
