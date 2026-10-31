"""Postgres job queue (03 §9.1 `jobs`). Payloads carry the job kind and IDs only (AC-23).

Claiming uses `SELECT ... FOR UPDATE SKIP LOCKED`, so several workers can poll safely. A job whose
worker died keeps `running` until its lease expires; it is then requeued, or failed once it has used
all its attempts.
"""
from __future__ import annotations

import hashlib
import re
import uuid
from dataclasses import dataclass
from typing import Mapping, Optional

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from changelens import MODEL_CONFIG_ID, PIPELINE_VERSION
from changelens.domain.models import Job

KINDS = ("parse", "compare")
_ID_NAME = re.compile(r"^[a-z]+_id$")


@dataclass(frozen=True)
class ClaimedJob:
    id: uuid.UUID
    tenant_id: uuid.UUID
    kind: str
    ids: dict
    attempts: int
    max_attempts: int


def build_payload(kind: str, ids: Mapping[str, uuid.UUID]) -> dict:
    """Reject anything that is not a known kind plus `*_id` UUIDs, so content cannot ride along."""
    if kind not in KINDS:
        raise ValueError("unknown job kind")
    if not ids:
        raise ValueError("a job needs at least one ID")
    out = {}
    for name, value in ids.items():
        if not _ID_NAME.match(name) or not isinstance(value, uuid.UUID):
            raise ValueError("job payloads carry UUID IDs only")
        out[name] = str(value)
    return {"kind": kind, "ids": out}


def idempotency_key(tenant_id: uuid.UUID, kind: str, ids: Mapping[str, uuid.UUID],
                    pipeline_version: str = PIPELINE_VERSION, model_config_id: str = MODEL_CONFIG_ID) -> str:
    """sha256 of (tenant_id, kind, ids, pipeline_version, model_config_id), 03 §9.1."""
    parts = [str(tenant_id), kind] + ["%s=%s" % (k, ids[k]) for k in sorted(ids)] + [pipeline_version, model_config_id]
    return hashlib.sha256("|".join(parts).encode()).hexdigest()


def enqueue(session: Session, tenant_id: uuid.UUID, kind: str, ids: Mapping[str, uuid.UUID],
            max_attempts: int) -> bool:
    """Insert the job unless an identical one exists. Returns True if a new row was written."""
    stmt = insert(Job).values(
        id=uuid.uuid4(), tenant_id=tenant_id, kind=kind, payload=build_payload(kind, ids),
        idempotency_key=idempotency_key(tenant_id, kind, ids), status="queued", attempts=0,
        max_attempts=max_attempts,
    ).on_conflict_do_nothing(index_elements=["idempotency_key"]).returning(Job.id)
    return session.execute(stmt).first() is not None


def reclaim_expired(session: Session, lease_seconds: int) -> list[ClaimedJob]:
    """Requeue `running` jobs past their lease; return the ones that just failed for good."""
    rows = session.execute(text(
        "UPDATE jobs SET status = CASE WHEN attempts >= max_attempts THEN 'failed' ELSE 'queued' END, "
        "locked_at = NULL, last_error = 'lease_expired', run_after = now() "
        "WHERE status = 'running' AND locked_at < now() - make_interval(secs => :lease) "
        "RETURNING id, tenant_id, kind, payload, attempts, max_attempts, status"), {"lease": lease_seconds})
    return [_claimed(r) for r in rows if r.status == "failed"]


def claim(session: Session) -> Optional[ClaimedJob]:
    row = session.execute(text(
        "UPDATE jobs SET status = 'running', attempts = attempts + 1, locked_at = now() "
        "WHERE id = (SELECT id FROM jobs WHERE status = 'queued' AND run_after <= now() "
        "            ORDER BY created_at FOR UPDATE SKIP LOCKED LIMIT 1) "
        "RETURNING id, tenant_id, kind, payload, attempts, max_attempts")).one_or_none()
    return _claimed(row) if row else None


def complete(session: Session, job_id: uuid.UUID) -> None:
    session.execute(text("UPDATE jobs SET status = 'done', locked_at = NULL WHERE id = :id"), {"id": job_id})


def retry_or_fail(session: Session, job: ClaimedJob, error_name: str, backoff_seconds: float) -> bool:
    """Record a failed attempt. Returns True if the job is now permanently failed."""
    final = job.attempts >= job.max_attempts
    session.execute(text(
        "UPDATE jobs SET status = :st, locked_at = NULL, last_error = :err, "
        "run_after = now() + make_interval(secs => :delay) WHERE id = :id"),
        {"st": "failed" if final else "queued", "err": error_name[:80], "id": job.id,
         "delay": backoff_seconds * (2 ** (job.attempts - 1))})
    return final


def _claimed(row) -> ClaimedJob:
    ids = {k: uuid.UUID(v) for k, v in row.payload["ids"].items()}
    return ClaimedJob(row.id, row.tenant_id, row.kind, ids, row.attempts, row.max_attempts)
