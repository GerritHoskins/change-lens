"""Atomic, idempotent comparison creation (O-15). Sources stay in memory until object storage.

JSON slots contain either {version_id} or {label, text}. For PDFs, send multipart with
a `comparison` JSON field, slots {label, file: true}, and `earlier_file`/`later_file` parts.
Legacy earlier_id/later_id JSON remains accepted, with the same Idempotency-Key requirement.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import uuid
from dataclasses import dataclass

from fastapi import APIRouter, Depends, Request
from starlette.datastructures import UploadFile
from starlette.exceptions import HTTPException
from starlette.concurrency import run_in_threadpool

from changelens import MODEL_CONFIG_ID, PIPELINE_VERSION, jobs
from changelens.api import uploads
from changelens.api.demo import check_demo_limit
from changelens.api.errors import ApiError, not_found
from changelens.domain.spend import cap_reached
from changelens.domain.comparison_queue import advance_comparison
from changelens.domain.models import Comparison, SourceVersion
from changelens.domain.storage_intents import prepare_write, write_prepared, reconcile_write

router = APIRouter()
log = logging.getLogger("changelens.api.comparisons")
SCOPES = ("complete", "partial", "unknown")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate_json_field")
        result[key] = value
    return result


@dataclass(frozen=True)
class Slot:
    version_id: uuid.UUID | None = None
    label: str | None = None
    data: bytes | None = None
    kind: str | None = None

    def identity(self):
        if self.version_id is not None:
            return {"version_id": str(self.version_id)}
        return {"label": self.label, "kind": self.kind, "sha256": hashlib.sha256(self.data).hexdigest()}


def parse_slot(value, file_data: bytes | None, limits) -> Slot:
    if not isinstance(value, dict):
        raise ApiError(422, "scope_not_confirmed", "both input slots are required")
    if set(value) == {"version_id"} and file_data is None:
        try:
            return Slot(version_id=uuid.UUID(value["version_id"]))
        except (ValueError, TypeError, AttributeError):
            raise ApiError(422, "invalid_request", "invalid version ID") from None
    if set(value) == {"label", "text"} and isinstance(value["text"], str) and file_data is None:
        try:
            data = value["text"].encode("utf-8")
        except UnicodeEncodeError:
            raise ApiError(422, "invalid_request", "text must be valid UTF-8") from None
    elif set(value) == {"label", "file"} and value["file"] is True and file_data is not None:
        data = file_data
    else:
        raise ApiError(422, "invalid_request", "each slot needs exactly one existing version, text or file")
    if not isinstance(value["label"], str):
        raise ApiError(422, "invalid_request", "label must be text")
    try:
        value["label"].encode("utf-8")
    except UnicodeEncodeError:
        raise ApiError(422, "invalid_request", "label must be valid UTF-8") from None
    label = uploads.check_label(value["label"], limits)
    kind = uploads.sniff(data)
    uploads.check_limits(data, kind, limits)
    return Slot(label=label, data=data, kind=kind)


async def read_inputs(request: Request) -> tuple[Slot, Slot, str]:
    limits, files = request.app.state.settings.limits, {}
    try:
        if request.headers.get("content-type", "").split(";")[0].strip() == "application/json":
            payload = json.loads(await request.body(), object_pairs_hook=_unique_object)
        else:
            async with request.form(max_files=2, max_fields=1,
                                    max_part_size=2 * limits.max_text_bytes + 4096) as form:
                names = [name for name, _ in form.multi_items()]
                if len(names) != len(set(names)) or set(names) - {"comparison", "earlier_file", "later_file"}:
                    raise ApiError(422, "invalid_request", "unexpected or duplicate multipart fields")
                payload = json.loads(form.get("comparison", ""), object_pairs_hook=_unique_object)
                for side in ("earlier", "later"):
                    file = form.get(side + "_file")
                    if file is not None:
                        if not isinstance(file, UploadFile):
                            raise ApiError(422, "invalid_request", "file must be a file part")
                        files[side] = await file.read(max(limits.max_pdf_bytes, limits.max_text_bytes) + 1)
    except HTTPException as exc:
        if "maximum size" in str(exc.detail):
            raise ApiError(413, "limit_exceeded", "bytes") from None
        raise ApiError(422, "invalid_request", "malformed multipart body") from None
    except (ValueError, TypeError, UnicodeDecodeError):
        raise ApiError(422, "invalid_request", "invalid comparison body") from None
    if not isinstance(payload, dict):
        raise ApiError(422, "invalid_request", "comparison must be an object")
    if set(payload) == {"earlier_id", "later_id", "scope"}:
        payload = {"earlier": {"version_id": payload["earlier_id"]},
                   "later": {"version_id": payload["later_id"]}, "scope": payload["scope"]}
    if set(payload) != {"earlier", "later", "scope"} or payload["scope"] not in SCOPES:
        raise ApiError(422, "scope_not_confirmed", "both inputs and a complete, partial or unknown scope are required")
    earlier = parse_slot(payload["earlier"], files.get("earlier"), limits)
    later = parse_slot(payload["later"], files.get("later"), limits)
    if earlier.version_id is not None and earlier.version_id == later.version_id:
        raise ApiError(422, "scope_not_confirmed", "earlier and later must differ")
    return earlier, later, payload["scope"]


def create_confirmed(state, tenant, project_id, key: str, earlier: Slot, later: Slot, scope: str):
    identity = {"project_id": str(project_id), "scope": scope,
                "earlier": earlier.identity(), "later": later.identity()}
    fingerprint = hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()
    written = []
    try:
        with state.db.tenant_scope(tenant) as repo:
            repo.lock_project(project_id)
            repo.lock_comparison_key(key)
            if repo.project(project_id) is None:
                raise not_found()
            existing = repo.comparison_by_key(key)
            if existing is not None:
                if existing.request_fingerprint != fingerprint:
                    raise ApiError(409, "idempotency_conflict", "key already used for a different comparison")
                repo.touch_comparison(existing)
                return {"id": str(existing.id), "status": existing.status}
            # The demo limit (docs/demo-wall-handoff.md) and the spend caps (I-8 S6), before anything is
            # written or charged and after the idempotent replay above has returned. The fair-use
            # allowance (I-14) is checked here too, once it exists.
            check_demo_limit(repo, state.settings)
            if cap_reached(repo, state.settings) is not None:
                raise ApiError(429, "spend_cap_reached", "the monthly spend cap is reached")
            # Per-account bounds on queued work and stored bytes (LR-10), after the replay above was answered.
            new = [slot.data for slot in (earlier, later) if slot.version_id is None]
            uploads.check_bounds(repo, state.settings, new_versions=len(new), new_bytes=sum(map(len, new)),
                                 new_comparison=True)
            # Lock existing versions in deterministic order. This prevents a parse completion
            # from racing past creation of its waiting comparison.
            versions = {}
            for vid in sorted({slot.version_id for slot in (earlier, later) if slot.version_id is not None}):
                version = repo.version(vid, lock=True)
                if version is None or version.project_id != project_id:
                    raise not_found()
                versions[vid] = version
            ordered = []
            for slot in (earlier, later):
                if slot.version_id is not None:
                    version = versions[slot.version_id]
                else:
                    ticket = prepare_write(state.db, tenant, project_id, key)
                    written.append(ticket)
                    write_prepared(state.db, state.store, ticket, slot.data)
                    version = repo.add(SourceVersion(project_id=project_id, label=slot.label, kind=slot.kind,
                        original_object_key=ticket.object_key, sha256=hashlib.sha256(slot.data).hexdigest(),
                        size_bytes=len(slot.data), status="uploaded", parse_warnings=[]))
                    jobs.enqueue(repo.s, tenant, "parse", {"version_id": version.id}, state.settings.job_max_attempts)
                ordered.append(version)
            comparison = repo.add(Comparison(project_id=project_id, earlier_id=ordered[0].id,
                later_id=ordered[1].id, scope_snapshot=scope, pipeline_version=PIPELINE_VERSION,
                model_config_id=MODEL_CONFIG_ID, status="waiting_for_versions", idempotency_key=key,
                request_fingerprint=fingerprint, cost_ceiling=state.settings.cost_ceiling_eur, warnings=[]))
            advance_comparison(repo, comparison, state.settings.job_max_attempts)
            repo.touch_comparison(comparison)
            result = {"id": str(comparison.id), "status": comparison.status}
        for ticket in written:
            reconcile_write(state.db, state.store, tenant, ticket.id)
        return result
    except Exception:
        # A lost commit acknowledgement is not proof of rollback. Resolve the key under
        # the same lock before cleanup; otherwise we could delete committed source files.
        recovered = None
        if written:
            try:
                with state.db.tenant_scope(tenant) as repo:
                    repo.lock_comparison_key(key)
                    existing = repo.comparison_by_key(key)
                    if existing is not None and existing.request_fingerprint == fingerprint:
                        recovered = {"id": str(existing.id), "status": existing.status}
            except Exception:
                log.error("comparison commit outcome unknown; originals retained for reconciliation")
                raise
        # The durable intent survives a crash, failed deletion or failed recovery. The
        # reconciler itself takes the request lock and rechecks committed source references.
        for ticket in written:
            reconcile_write(state.db, state.store, tenant, ticket.id)
        if recovered is not None:
            return recovered
        raise


@router.post("/projects/{project_id}/comparisons", status_code=202)
async def create_comparison(project_id: uuid.UUID, request: Request,
                            tenant: uuid.UUID = Depends(uploads.upload_slot)):
    key = request.headers.get("Idempotency-Key", "")
    if re.fullmatch(r"[A-Za-z0-9_-]{16,128}", key) is None:
        raise ApiError(422, "idempotency_key_required", "send a unique Idempotency-Key of 16-128 letters, digits, _ or -")
    earlier, later, scope = await read_inputs(request)
    return await run_in_threadpool(create_confirmed, request.app.state, tenant, project_id,
                                  key, earlier, later, scope)
