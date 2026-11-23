"""The demo period's limit and feedback (docs/demo-wall-handoff.md): the `TenantRepo` methods for them.

- **Used:** rows of `demo_comparisons`, one per comparison that reached `complete` or `partial`. The worker
  writes the row in the transaction that sets that status. Failed comparisons have none.
- **In flight:** the tenant's comparisons in `waiting_for_versions`, `queued` or `running` in a project that
  is not being deleted. They hold a place until they end; a failed one frees it.
- **Admission** (`api/comparisons.py`) reads both numbers in one statement, so one snapshot, under the
  tenant's demo lock: two simultaneous starts are checked one after the other.
- **Feedback:** one row per account in `demo_feedback`; a second one is refused by the primary key.

The free-text fields are passed through and stored, never logged here or anywhere else (AC-23).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import delete, func, select, text
from sqlalchemy.exc import IntegrityError

from changelens.domain.models import Comparison, DemoComparison, DemoFeedback, Project

IN_FLIGHT = ("waiting_for_versions", "queued", "running")
COUNTED = ("complete", "partial")
# The offer the price question describes (the contract draft's old C3). Stored with every answer, so
# answers to a changed offer are never pooled with these.
PLAN_ID = "individual_20_v1"


class DemoRepo:
    """Mixed into `TenantRepo`: `self.s` is the tenant's session, `self.tenant_id` its tenant."""

    def lock_demo(self) -> None:
        """Serialise this tenant's admission checks; released when the transaction ends. Taken after the
        project and key locks of comparison creation, and by nothing else."""
        from changelens.domain import comparison_lock_id  # the package imports this module
        self.s.execute(text("SELECT pg_advisory_xact_lock(:key)"),
                       {"key": comparison_lock_id(self.tenant_id, "demo")})

    def demo_counts(self) -> tuple[int, int]:
        """(used, in flight), read in one statement: a comparison the worker finishes meanwhile is
        counted in exactly one of the two."""
        used = (select(func.count()).select_from(DemoComparison)
                .where(DemoComparison.tenant_id == self.tenant_id).scalar_subquery())
        live = select(Project.id).where(Project.tenant_id == self.tenant_id, Project.deleted_at.is_(None))
        in_flight = (select(func.count()).select_from(Comparison)
                     .where(Comparison.tenant_id == self.tenant_id, Comparison.status.in_(IN_FLIGHT),
                            Comparison.project_id.in_(live)).scalar_subquery())
        row = self.s.execute(select(used, in_flight)).one()
        return int(row[0]), int(row[1])

    def record_demo_comparison(self, comparison_id: uuid.UUID, now: Optional[datetime] = None) -> bool:
        """Count one finished comparison, once: a second write for the same comparison changes nothing."""
        try:
            with self.s.begin_nested():  # savepoint: a duplicate rolls back only this insert
                self.add(DemoComparison(comparison_id=comparison_id, counted_at=now or datetime.now(timezone.utc)))
        except IntegrityError:
            return False
        return True

    def demo_feedback(self, account_id: uuid.UUID) -> Optional[DemoFeedback]:
        return self.s.scalars(select(DemoFeedback).where(DemoFeedback.account_id == account_id,
                                                         DemoFeedback.tenant_id == self.tenant_id)).one_or_none()

    def record_demo_feedback(self, account_id: uuid.UUID, *, missing: str, missing_other: Optional[str],
                             anything_else: Optional[str], price: str,
                             now: Optional[datetime] = None) -> bool:
        """Store the account's one answer. False when it already has one (also from another device)."""
        if self.demo_feedback(account_id) is not None:
            return False
        try:
            with self.s.begin_nested():  # savepoint: a lost race rolls back only this insert
                self.add(DemoFeedback(account_id=account_id, missing=missing, missing_other=missing_other,
                                      anything_else=anything_else, price=price, plan_id=PLAN_ID,
                                      created_at=now or datetime.now(timezone.utc)))
        except IntegrityError:
            return False
        return True

    def delete_demo(self, account_id: uuid.UUID) -> None:
        """For 03a P8 DELETE_ACCOUNT: the account's feedback and its tenant's counted comparisons. Project
        deletion and retention never call this."""
        self.s.execute(delete(DemoFeedback).where(DemoFeedback.account_id == account_id,
                                                  DemoFeedback.tenant_id == self.tenant_id))
        self.s.execute(delete(DemoComparison).where(DemoComparison.tenant_id == self.tenant_id))
