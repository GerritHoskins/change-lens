"""Account deletion (03a P8 DELETE_ACCOUNT and DELETE_TENANT; I-8 S5).

In v1 every account is the sole owner of its own tenant, so deleting the account deletes the tenant.
Steps, each resumable, so a crash anywhere leaves a pending receipt that maintenance finishes:

1. freeze: the receipt, `users.deleted_at` and an inactive membership, in one transaction. GUARD
   rejects the user from the next request;
2. Apple revocation: S4 (the token column doesn't exist yet);
3. every project of the tenant through project deletion (rows and every object version);
4. account rows: the onboarding row and the tenant's completed project-deletion receipts;
5. the Logto user (its linked identities and sessions go with it); a 404 counts as done;
6. tombstone: the subject is cleared, the membership deleted, the receipt `complete`.

User rows change only through the account_* functions of migration 0004. Logs carry event codes only.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy import delete, select, text, update
from sqlalchemy.dialects.postgresql import insert

from changelens.domain.models import AccountDeletion, Membership, Project, ProjectDeletion
from changelens.domain.retention import process_project_deletion, request_project_deletion

log = logging.getLogger("changelens.accounts")


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _receipt(repo, user_id, lock=False) -> Optional[AccountDeletion]:
    q = (select(AccountDeletion).where(AccountDeletion.user_id == user_id,
                                       AccountDeletion.tenant_id == repo.tenant_id)
         .execution_options(populate_existing=True))
    return repo.s.scalars(q.with_for_update() if lock else q).one_or_none()


def _backoff(receipt, now) -> None:
    receipt.attempts += 1
    receipt.next_attempt_at = now + timedelta(seconds=min(3600, 30 * 2 ** min(receipt.attempts - 1, 7)))


def request_account_deletion(db, principal, *, now=None) -> None:
    """Step 1, in one transaction. Idempotent: an existing receipt is kept."""
    now = now or utcnow()
    with db.tenant_scope(principal.tenant_id) as repo:
        repo.s.execute(insert(AccountDeletion).values(
            user_id=principal.user_id, tenant_id=principal.tenant_id, status="pending", requested_at=now,
            next_attempt_at=now, attempts=0).on_conflict_do_nothing(index_elements=["user_id"]))
        if not repo.s.execute(text("SELECT account_freeze(:u)"), {"u": principal.user_id}).scalar_one():
            raise RuntimeError("account_freeze_refused")
        repo.s.execute(update(Membership).where(Membership.user_id == principal.user_id,
                                                Membership.tenant_id == principal.tenant_id)
                       .values(status="inactive"))
    log.info("account deletion requested")


def _projects(db, store, tenant_id, now) -> bool:
    """Delete every project, including frozen ones and receipts whose object purge is still pending."""
    with db.tenant_scope(tenant_id) as repo:
        live = set(repo.s.scalars(select(Project.id).where(Project.tenant_id == tenant_id)))
        receipts = set(repo.s.scalars(select(ProjectDeletion.project_id).where(
            ProjectDeletion.tenant_id == tenant_id, ProjectDeletion.status == "pending")))
    done = True
    for project_id in sorted(live | receipts):
        status = request_project_deletion(db, tenant_id, project_id, now=now) if project_id in live else "pending"
        if status != "complete":
            done = process_project_deletion(db, store, tenant_id, project_id, now=now) and done
    return done


def _projects_gone(repo, tenant_id) -> bool:
    return (repo.s.scalar(select(Project.id).where(Project.tenant_id == tenant_id).limit(1)) is None
            and repo.s.scalar(select(ProjectDeletion.project_id).where(
                ProjectDeletion.tenant_id == tenant_id, ProjectDeletion.status == "pending").limit(1)) is None)


def process_account_deletion(db, store, idp, tenant_id: uuid.UUID, user_id: uuid.UUID, *, now=None) -> bool:
    """Steps 3-6 for a pending receipt. True once the receipt is complete; False while a step is pending,
    with the receipt backed off. `idp` deletes the Logto user (None: not configured, so it stays pending)."""
    now = now or utcnow()
    try:
        with db.tenant_scope(tenant_id) as repo:
            receipt = _receipt(repo, user_id)
            if receipt is None:
                return False
            if receipt.status == "complete":
                return True
            if receipt.next_attempt_at > now:
                return False
            idp_done = receipt.idp_deleted_at is not None
        step = "projects"
        if _projects(db, store, tenant_id, now):
            step = "account_rows"
            with db.tenant_scope(tenant_id) as repo:
                if _projects_gone(repo, tenant_id):
                    repo.delete_onboarding(user_id)
                    repo.s.execute(delete(ProjectDeletion).where(ProjectDeletion.tenant_id == tenant_id,
                                                                 ProjectDeletion.status == "complete"))
                    step = "idp"
            if step == "idp" and not idp_done:
                idp_done = _delete_idp_user(db, idp, tenant_id, user_id, now)
            if step == "idp" and idp_done:
                step = "tombstone"
                with db.tenant_scope(tenant_id) as repo:
                    receipt = _receipt(repo, user_id, lock=True)
                    if receipt.status == "complete":
                        return True
                    if not repo.s.execute(text("SELECT account_tombstone(:u)"), {"u": user_id}).scalar_one():
                        raise RuntimeError("account_tombstone_refused")
                    repo.s.execute(delete(Membership).where(Membership.user_id == user_id,
                                                            Membership.tenant_id == tenant_id))
                    receipt.status, receipt.completed_at = "complete", now
                log.info("account deletion complete")
                return True
        _defer(db, tenant_id, user_id, now, step)
        return False
    except Exception as exc:
        log.warning("account deletion deferred: %s", type(exc).__name__)
        try:
            _defer(db, tenant_id, user_id, now, "error")
        except Exception:
            pass
        return False


def _delete_idp_user(db, idp, tenant_id, user_id, now) -> bool:
    if idp is None:
        log.warning("account deletion pending: idp_not_configured")
        return False
    with db.tenant_scope(tenant_id) as repo:
        subject = repo.s.execute(text("SELECT account_deletion_subject(:u)"), {"u": user_id}).scalar_one()
    if subject is not None:  # null: already a tombstone
        try:
            idp.delete_user(subject)
        except Exception as exc:
            log.warning("account deletion pending: idp_delete_failed (%s)", type(exc).__name__)
            return False
    with db.tenant_scope(tenant_id) as repo:
        receipt = _receipt(repo, user_id, lock=True)
        if receipt.idp_deleted_at is None:
            receipt.idp_deleted_at = now
    return True


def _defer(db, tenant_id, user_id, now, step) -> None:
    with db.tenant_scope(tenant_id) as repo:
        receipt = _receipt(repo, user_id, lock=True)
        if receipt is not None and receipt.status == "pending":
            _backoff(receipt, now)
    log.info("account deletion pending: %s", step)


def run_account_deletions(db, store, idp, *, now=None, limit=100) -> tuple[int, int]:
    """Maintenance: retry due receipts. Returns (completed, still pending)."""
    now = now or utcnow()
    completed = pending = 0
    for tenant_id, user_id in db.account_deletion_candidates(now, limit):
        if process_account_deletion(db, store, idp, tenant_id, user_id, now=now):
            completed += 1
        else:
            pending += 1
    return completed, pending
