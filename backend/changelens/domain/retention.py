"""Thirty-day document/report retention and explicit primary project deletion.

Project locks fence writers. Row removal, cost-ledger transfer and exact-key purge intents
commit together; object operations happen afterwards and retry without an attempt limit.
Account/IdP deletion and backup expiry are deliberately outside this primary-store module.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import logging
import uuid

from sqlalchemy import delete, exists, or_, select
from sqlalchemy.dialects.postgresql import insert

from changelens.api.errors import not_found
from changelens.domain.models import (
    ClientApprovalRecord, Comparison, ComparisonCostTombstone, FactCacheEntry, Finding, Job,
    ObjectPurgeIntent, ObjectWriteIntent, Project, ProjectDeletion, ReviewEvent, SourceVersion,
)
from changelens.domain.storage_intents import reconcile_pending_writes

log = logging.getLogger("changelens.retention")
RETENTION = timedelta(days=30)


def utcnow():
    return datetime.now(timezone.utc)


def _receipt(repo, project_id, lock=False):
    query = select(ProjectDeletion).where(ProjectDeletion.project_id == project_id,
                                           ProjectDeletion.tenant_id == repo.tenant_id)
    if lock:
        query = query.with_for_update().execution_options(populate_existing=True)
    return repo.s.scalar(query)


def request_project_deletion(db, tenant_id, project_id, *, now=None) -> str:
    """Freeze immediately, independently of an uploader already holding the lifecycle lock."""
    now = now or utcnow()
    with db.tenant_scope(tenant_id) as repo:
        receipt = _receipt(repo, project_id)
        if receipt is None:
            if repo._get(Project, project_id) is None:
                raise not_found()
            repo.s.execute(insert(ProjectDeletion).values(project_id=project_id, tenant_id=tenant_id,
                status="pending", requested_at=now, next_attempt_at=now, attempts=0)
                .on_conflict_do_nothing(index_elements=["project_id"]))
        receipt = _receipt(repo, project_id, lock=True)
        # A non-key UPDATE is compatible with an in-flight uploader's FK key-share
        # lock. FOR UPDATE here would block the freeze behind its network PUT.
        project = repo._get(Project, project_id)
        if project is not None and project.deleted_at is None:
            project.deleted_at = now
        return receipt.status


def _remove_comparisons(repo, rows):
    for comparison in rows:
        # The comparison row is already locked. Settlement either precedes this snapshot
        # or sees its tombstone in a subsequent READ COMMITTED statement after deletion.
        repo.add(ComparisonCostTombstone(id=comparison.id,
            cost_actual=comparison.cost_actual or Decimal("0"),
            cost_reservations=dict(comparison.cost_reservations)))
        finding_ids = select(Finding.id).where(Finding.tenant_id == repo.tenant_id,
                                                Finding.comparison_id == comparison.id)
        for model in (ClientApprovalRecord, ReviewEvent):
            repo.s.execute(delete(model).where(model.tenant_id == repo.tenant_id,
                                                model.finding_id.in_(finding_ids)))
        repo.s.execute(delete(Finding).where(Finding.tenant_id == repo.tenant_id,
                                              Finding.comparison_id == comparison.id))
        repo.s.execute(delete(Job).where(Job.tenant_id == repo.tenant_id,
            Job.payload["ids"]["comparison_id"].astext == str(comparison.id)))
        repo.s.delete(comparison)
    repo.s.flush()


def _remove_versions(repo, rows, now):
    for version in rows:
        # Separate from ObjectWriteIntent: its reconciler may resolve a referenced upload
        # while this source-deletion transaction is still uncommitted.
        repo.s.execute(insert(ObjectPurgeIntent).values(id=uuid.uuid4(), tenant_id=repo.tenant_id,
            project_id=version.project_id, object_key=version.original_object_key,
            next_attempt_at=now, attempts=0).on_conflict_do_nothing(index_elements=["object_key"]))
        repo.s.execute(delete(FactCacheEntry).where(FactCacheEntry.tenant_id == repo.tenant_id,
                                                    FactCacheEntry.source_version_id == version.id))
        repo.s.execute(delete(Job).where(Job.tenant_id == repo.tenant_id,
            Job.payload["ids"]["version_id"].astext == str(version.id)))
        repo.s.delete(version)
    repo.s.flush()


def expire_project_resources(db, tenant_id, project_id, *, now=None) -> tuple[int, int]:
    now = now or utcnow()
    cutoff = now - RETENTION
    with db.tenant_scope(tenant_id) as repo:
        if not repo.lock_project(project_id, wait=False) or repo.project(project_id) is None:
            return 0, 0
        comparisons = list(repo.s.scalars(select(Comparison).where(
            Comparison.tenant_id == tenant_id, Comparison.project_id == project_id,
            Comparison.last_used_at <= cutoff).order_by(Comparison.id).with_for_update()))
        # Every state expires, including abandoned queued/running work. Worker guards stop
        # new calls/writes, while the content-free ledger still accepts late settlements.
        _remove_comparisons(repo, comparisons)
        retained = exists(select(Comparison.id).where(Comparison.tenant_id == tenant_id,
            or_(Comparison.earlier_id == SourceVersion.id, Comparison.later_id == SourceVersion.id)))
        versions = list(repo.s.scalars(select(SourceVersion).where(
            SourceVersion.tenant_id == tenant_id, SourceVersion.project_id == project_id,
            SourceVersion.last_used_at <= cutoff, ~retained).order_by(SourceVersion.id).with_for_update()))
        _remove_versions(repo, versions, now)
        return len(comparisons), len(versions)


def _backoff(row, now):
    row.attempts += 1
    row.next_attempt_at = now + timedelta(seconds=min(3600, 30 * 2 ** min(row.attempts - 1, 7)))


def _project_leaf(key, tenant_id, project_id):
    parts = key.split("/")
    try:
        return (len(parts) == 3 and parts[:2] == [str(tenant_id), str(project_id)]
                and str(uuid.UUID(parts[2])) == parts[2])
    except (ValueError, AttributeError):
        return False


def process_object_purge(db, store, tenant_id, intent_id, *, now=None) -> bool:
    now = now or utcnow()
    try:
        with db.tenant_scope(tenant_id) as repo:
            intent = repo._get(ObjectPurgeIntent, intent_id)
            if intent is None:
                return True
            if not repo.lock_project(intent.project_id, wait=False):
                return False
            intent = repo._get(ObjectPurgeIntent, intent_id, lock=True)
            if intent is None:
                return True
            if intent.next_attempt_at > now:
                return False
            if not _project_leaf(intent.object_key, tenant_id, intent.project_id):
                raise ValueError("invalid_purge_scope")
            if repo.object_key_is_referenced(intent.object_key):
                _backoff(intent, now)
                return False
            try:
                store.delete_prefix(intent.object_key)
            except Exception:
                _backoff(intent, now)
                log.warning("primary object purge deferred")
                return False
            repo.s.delete(intent)
        return True
    except Exception:
        log.warning("primary object reconciliation deferred")
        return False


def process_project_deletion(db, store, tenant_id, project_id, *, now=None) -> bool:
    now = now or utcnow()
    try:
        # First commit the content removal plus all durable cleanup obligations. No
        # external delete can precede this transaction's acknowledged commit.
        with db.tenant_scope(tenant_id) as repo:
            if not repo.lock_project(project_id, wait=False):
                return False
            receipt = _receipt(repo, project_id, lock=True)
            if receipt is None:
                return False
            if receipt.status == "complete":
                return True
            if receipt.next_attempt_at > now:
                return False
            comparisons = list(repo.s.scalars(select(Comparison).where(
                Comparison.tenant_id == tenant_id, Comparison.project_id == project_id)
                .order_by(Comparison.id).with_for_update()))
            _remove_comparisons(repo, comparisons)
            versions = list(repo.s.scalars(select(SourceVersion).where(
                SourceVersion.tenant_id == tenant_id, SourceVersion.project_id == project_id)
                .order_by(SourceVersion.id).with_for_update()))
            _remove_versions(repo, versions, now)
            project = repo._get(Project, project_id, lock=True)
            if project is not None:
                repo.s.delete(project)
        # The durable freeze prevents new uploads between transactions. A writer that
        # already held the project lock had to finish before phase one could acquire it.
        with db.tenant_scope(tenant_id) as repo:
            if not repo.lock_project(project_id, wait=False):
                return False
            receipt = _receipt(repo, project_id, lock=True)
            if receipt is None or receipt.status == "complete":
                return receipt is not None
            prefix = f"{tenant_id}/{project_id}/"
            try:
                store.delete_prefix(prefix)  # includes legacy/untracked versions and markers
            except Exception:
                _backoff(receipt, now)
                log.warning("primary project purge deferred")
                return False
            repo.s.execute(delete(ObjectPurgeIntent).where(ObjectPurgeIntent.tenant_id == tenant_id,
                                                            ObjectPurgeIntent.project_id == project_id))
            uploads = list(repo.s.scalars(select(ObjectWriteIntent).where(
                ObjectWriteIntent.tenant_id == tenant_id, ObjectWriteIntent.object_key.startswith(prefix))
                .with_for_update()))
            unresolved = False
            for upload in uploads:
                if upload.write_acknowledged:
                    repo.s.delete(upload)
                else:
                    unresolved = True  # a delayed server-side PUT remains possible
            if unresolved:
                receipt.next_attempt_at = now + timedelta(hours=1)
                return False
            receipt.status, receipt.completed_at = "complete", now
        return True
    except Exception:
        log.warning("primary project deletion reconciliation deferred")
        return False


def maintenance_snapshot(db, *, now=None, limit=100):
    """Pre-tenant candidates as (tenant ID, ID) lists, from the `maintenance_candidates` function
    (migration 0003, I-8 S3), which applies the same RETENTION window. Everything after runs in
    tenant_scope."""
    return db.maintenance_candidates(now or utcnow(), limit)


def run_maintenance(db, store, *, now=None, limit=100, execute=False) -> dict:
    """Independent maintenance entry point. Default is a content-free dry run."""
    now = now or utcnow()
    projects, deletions, purges = maintenance_snapshot(db, now=now, limit=limit)
    result = {"execute": execute, "candidate_projects": len(projects), "pending_project_deletions": len(deletions),
              "due_object_purges": len(purges), "expired_comparisons": 0, "expired_sources": 0,
              "completed_project_deletions": 0, "completed_object_purges": 0, "resolved_uploads": 0}
    if not execute:
        return result
    for tenant, project in projects:
        comparisons, versions = expire_project_resources(db, tenant, project, now=now)
        result["expired_comparisons"] += comparisons
        result["expired_sources"] += versions
    result["completed_project_deletions"] = sum(process_project_deletion(db, store, tenant, project, now=now)
                                                for tenant, project in deletions)
    # Include purge intents created by this pass, not only those present in its snapshot.
    _, _, purges = maintenance_snapshot(db, now=now, limit=limit)
    result["completed_object_purges"] = sum(process_object_purge(db, store, tenant, identifier, now=now)
                                            for tenant, identifier in purges)
    result["resolved_uploads"] = reconcile_pending_writes(db, store, now=now, limit=limit)
    return result
