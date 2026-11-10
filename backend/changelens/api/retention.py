"""Explicit use signals are separate from polling; deletion exposes primary-store status only."""
import uuid

from fastapi import APIRouter, Depends, Request, Response

from changelens.api.auth import current_tenant
from changelens.api.errors import not_found
from changelens.domain.retention import process_project_deletion, request_project_deletion

router = APIRouter()


@router.post("/comparisons/{comparison_id}/opened", status_code=204)
def comparison_opened(comparison_id: uuid.UUID, request: Request, tenant: uuid.UUID = Depends(current_tenant)):
    with request.app.state.db.tenant_scope(tenant) as repo:
        if not repo.lock_for_comparison(comparison_id):
            raise not_found()
        comparison = repo.comparison(comparison_id, lock=True)
        if comparison is None:
            raise not_found()
        repo.touch_comparison(comparison)
    return Response(status_code=204)


@router.post("/versions/{version_id}/opened", status_code=204)
def version_opened(version_id: uuid.UUID, request: Request, tenant: uuid.UUID = Depends(current_tenant)):
    with request.app.state.db.tenant_scope(tenant) as repo:
        if not repo.lock_for_version(version_id):
            raise not_found()
        version = repo.version(version_id, lock=True)
        if version is None:
            raise not_found()
        repo.touch_version(version)
    return Response(status_code=204)


@router.delete("/projects/{project_id}", status_code=204)
def delete_project(project_id: uuid.UUID, request: Request, tenant: uuid.UUID = Depends(current_tenant)):
    state = request.app.state
    status = request_project_deletion(state.db, tenant, project_id)
    complete = status == "complete" or process_project_deletion(state.db, state.store, tenant, project_id)
    return Response(status_code=204 if complete else 202)
