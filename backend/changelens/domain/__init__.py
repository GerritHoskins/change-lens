"""Database access. Sessions for document data are always tenant-scoped (03 §9.1 `domain`).

`tenant_scope()` opens a transaction, sets `app.tenant_id` with SET LOCAL semantics and returns a
repository whose every query filters on that tenant. Postgres enforces the same boundary below it:
the processes connect as `changelens_app`, and forced row-level security on every tenant table matches
only rows of the tenant in `app.tenant_id` (I-8 S3, 03 §6). With no tenant set nothing matches, so
pre-tenant work (GUARD's identity lookups, queue claims, maintenance scans) calls the narrow
`SECURITY DEFINER` functions of migration 0003, which return IDs only. The schema is owned by Alembic
(`backend/migrations/`); nothing here creates or alters tables.
"""
from __future__ import annotations

import uuid
import hashlib
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from typing import Iterator, Optional

from sqlalchemy import create_engine, delete, func, or_, select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import NullPool

from changelens.domain.identity import IdentityRepo
from changelens.domain.models import (
    AccountOnboarding, ClientApprovalRecord, Comparison, ComparisonCostTombstone, ConsentEvent, FactCacheEntry,
    Finding,
    ObjectWriteIntent, Project, ReviewEvent, SourceVersion,
)


def comparison_lock_id(tenant_id: uuid.UUID, key: str) -> int:
    digest = hashlib.sha256(f"{tenant_id}:{key}".encode()).digest()
    return int.from_bytes(digest[:8], "big", signed=True)


def project_lock_id(tenant_id: uuid.UUID, project_id: uuid.UUID) -> int:
    return comparison_lock_id(tenant_id, "project:" + str(project_id))


def used_at(previous: Optional[datetime], now: datetime) -> datetime:
    """A clock adjustment must never shorten a resource's retention window."""
    if previous is not None and previous.tzinfo is None:
        previous = previous.replace(tzinfo=timezone.utc)
    return max(previous, now) if previous is not None else now


class Database:
    def __init__(self, url: str):
        # echo stays off: SQL parameters can carry document text (AC-23).
        self.engine = create_engine(url, echo=False, hide_parameters=True, pool_pre_ping=True)
        self._sessions = sessionmaker(self.engine, expire_on_commit=False)
        # Uploads hold a request transaction while independently committing write intents.
        # A separate non-pooling engine prevents all checked-out request connections from
        # waiting for another connection from that same exhausted pool.
        self._intent_engine = create_engine(url, echo=False, hide_parameters=True, poolclass=NullPool)
        self._intent_sessions = sessionmaker(self._intent_engine, expire_on_commit=False)

    @contextmanager
    def tenant_scope(self, tenant_id: uuid.UUID) -> Iterator["TenantRepo"]:
        if not isinstance(tenant_id, uuid.UUID):
            raise TypeError("tenant_id must be a UUID")
        with self._sessions() as s, s.begin():
            s.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_id)})
            yield TenantRepo(s, tenant_id)

    @contextmanager
    def _pre_tenant(self) -> Iterator[Session]:
        """A transaction with no tenant set: RLS hides every tenant row, so only the functions work."""
        with self._sessions() as s, s.begin():
            yield s

    @contextmanager
    def identity_scope(self) -> Iterator[IdentityRepo]:
        """Pre-tenant user and membership lookups for GUARD (03a P0); no tenant is set."""
        with self._pre_tenant() as s:
            yield IdentityRepo(s)

    @contextmanager
    def social_scope(self):
        """Pre-tenant parked Apple tokens and pending links for native sign-in (I-8 S4); no tenant is set."""
        from changelens.domain.social import SocialRepo  # social imports the auth package
        with self._pre_tenant() as s:
            yield SocialRepo(s)

    def claim_job(self):
        """The next ready job (IDs only), marked running; None when the queue is empty."""
        from changelens import jobs  # jobs imports the models only
        with self._pre_tenant() as s:
            return jobs.claim(s)

    def reclaim_expired_jobs(self, lease_seconds: int):
        """Requeue jobs past their lease; returns the ones that just failed for good."""
        from changelens import jobs
        with self._pre_tenant() as s:
            return jobs.reclaim_expired(s, lease_seconds)

    def maintenance_candidates(self, now: datetime, limit: int):
        """Retention's three pre-tenant lists of (tenant ID, ID): projects with aged resources, due project
        deletions and due object purges."""
        lists = {"project": [], "deletion": [], "purge": []}
        with self._pre_tenant() as s:
            rows = s.execute(text("SELECT list, tenant_id, item_id FROM maintenance_candidates(:now, :limit)"),
                             {"now": now, "limit": limit})
            for row in rows:
                lists[row.list].append((row.tenant_id, row.item_id))
        return lists["project"], lists["deletion"], lists["purge"]

    def account_deletion_candidates(self, now: datetime, limit: int) -> list[tuple[uuid.UUID, uuid.UUID]]:
        """Due account-deletion receipts as (tenant ID, user ID) (I-8 S5)."""
        with self._pre_tenant() as s:
            rows = s.execute(text("SELECT tenant_id, user_id FROM account_deletion_candidates(:now, :limit)"),
                             {"now": now, "limit": limit})
            return [(row.tenant_id, row.user_id) for row in rows]

    def rate_limit_hit(self, key_hash: str, window_start: datetime) -> int:
        """Count one request in a fixed window; returns the window's count (I-8 S6). Commits at once."""
        with self._pre_tenant() as s:
            return s.execute(text("SELECT rate_limit_hit(:k, :w)"), {"k": key_hash, "w": window_start}).scalar_one()

    def rate_limit_prune(self) -> int:
        with self._pre_tenant() as s:
            return s.execute(text("SELECT rate_limit_prune()")).scalar_one()

    def early_bird_request(self, email: str, locale: str, token_hash: str, pending_days: int) -> bool:
        """Record a sign-up for the early-bird list: a new pending row, or a new link token for a pending
        one. True when a confirmation mail is due; a confirmed address changes nothing and gives False."""
        with self._pre_tenant() as s:
            return s.execute(text("SELECT early_bird_request(:e, :l, :h, :d)"),
                             {"e": email, "l": locale, "h": token_hash, "d": pending_days}).scalar_one()

    def early_bird_mark_sent(self, token_hash: str) -> None:
        with self._pre_tenant() as s:
            s.execute(text("SELECT early_bird_mark_sent(:h)"), {"h": token_hash})

    def early_bird_confirm(self, token_hash: str, pending_days: int) -> Optional[str]:
        """Confirm once by the link token's hash; the sign-up's locale, or None for an unknown, used or
        expired token."""
        with self._pre_tenant() as s:
            return s.execute(text("SELECT early_bird_confirm(:h, :d)"),
                             {"h": token_hash, "d": pending_days}).scalar_one()

    def early_bird_prune(self, pending_days: int) -> int:
        with self._pre_tenant() as s:
            return s.execute(text("SELECT early_bird_prune(:d)"), {"d": pending_days}).scalar_one()

    def assert_app_role(self) -> None:
        """Refuse to run a process as a role that row-level security does not apply to (I-8 S3)."""
        with self.engine.connect() as conn:
            unsafe = conn.execute(text("SELECT rolsuper OR rolbypassrls FROM pg_roles "
                                       "WHERE rolname = current_user")).scalar_one()
        if unsafe:
            raise RuntimeError("CHANGELENS_DATABASE_URL must use the app role (changelens_app): "
                               "this role bypasses row-level security")

    @contextmanager
    def write_intent_scope(self, tenant_id: uuid.UUID) -> Iterator["TenantRepo"]:
        if not isinstance(tenant_id, uuid.UUID):
            raise TypeError("tenant_id must be a UUID")
        with self._intent_sessions() as s, s.begin():
            s.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_id)})
            yield TenantRepo(s, tenant_id)

    def pending_object_writes(self, now: datetime, limit: int) -> list[tuple[uuid.UUID, uuid.UUID]]:
        # Like queue dequeue, this pre-tenant scan returns IDs only. All subsequent access
        # and cleanup rechecks happen in tenant_scope under the upload's advisory lock.
        with self._pre_tenant() as s:
            rows = s.execute(text("SELECT tenant_id, intent_id FROM pending_object_writes(:now, :limit)"),
                             {"now": now, "limit": limit})
            return [(row.tenant_id, row.intent_id) for row in rows]


class DbFactCache:
    """`pipeline.extract.FactCache` over the fact_cache table, for one tenant and version."""

    def __init__(self, db: Database, tenant_id: uuid.UUID, version_id: uuid.UUID):
        self.db, self.tenant_id, self.version_id = db, tenant_id, version_id

    def get(self, key: str) -> Optional[dict]:
        with self.db.tenant_scope(self.tenant_id) as repo:
            return repo.cached_facts(key) if repo.version(self.version_id) is not None else None

    def put(self, key: str, value: dict) -> None:
        with self.db.tenant_scope(self.tenant_id) as repo:
            if repo.lock_for_version(self.version_id):
                repo.cache_facts(self.version_id, key, value)


class TenantRepo:
    """Repository bound to one tenant. Another tenant's row is indistinguishable from a missing one."""

    def __init__(self, session: Session, tenant_id: uuid.UUID):
        self.s = session
        self.tenant_id = tenant_id

    def add(self, obj):
        obj.tenant_id = self.tenant_id
        self.s.add(obj)
        self.s.flush()
        return obj

    def _get(self, model, id_: uuid.UUID, lock: bool = False):
        q = (select(model).where(model.id == id_, model.tenant_id == self.tenant_id)
             .execution_options(populate_existing=True))
        if lock:
            q = q.with_for_update()
        return self.s.scalars(q).one_or_none()

    def project(self, id_: uuid.UUID) -> Optional[Project]:
        p = self._get(Project, id_)
        return p if p is not None and p.deleted_at is None else None

    def projects(self) -> list[Project]:
        q = (select(Project).where(Project.tenant_id == self.tenant_id, Project.deleted_at.is_(None))
             .order_by(Project.created_at.desc()))
        return list(self.s.scalars(q))

    def versions_of(self, project_id: uuid.UUID) -> list[SourceVersion]:
        q = (select(SourceVersion)
             .where(SourceVersion.tenant_id == self.tenant_id, SourceVersion.project_id == project_id)
             .order_by(SourceVersion.created_at))
        return list(self.s.scalars(q))

    def active_comparison_counts(self) -> dict:
        q = (select(Comparison.project_id, Comparison.status, func.count(Comparison.id))
             .where(Comparison.tenant_id == self.tenant_id,
                    Comparison.status.in_(("waiting_for_versions", "queued", "running")))
             .group_by(Comparison.project_id, Comparison.status))
        counts = {}
        for project_id, status, count in self.s.execute(q):
            counts.setdefault(project_id, {})[status] = count
        return counts

    def latest_comparisons(self) -> dict:
        """Project id -> its most recently created comparison (the projects list's summary)."""
        q = (select(Comparison).where(Comparison.tenant_id == self.tenant_id)
             .distinct(Comparison.project_id)
             .order_by(Comparison.project_id, Comparison.created_at.desc(), Comparison.id.desc()))
        return {c.project_id: c for c in self.s.scalars(q)}

    def version_labels(self, ids) -> dict:
        q = select(SourceVersion.id, SourceVersion.label).where(
            SourceVersion.tenant_id == self.tenant_id, SourceVersion.id.in_(list(ids)))
        return dict(self.s.execute(q).all())

    def finding_summary_rows(self, comparison_ids) -> list:
        """Counting columns only, never evidence or explanations."""
        q = select(Finding.id, Finding.comparison_id, Finding.category, Finding.review_group,
                   Finding.supersedes_id).where(Finding.tenant_id == self.tenant_id,
                                                Finding.comparison_id.in_(list(comparison_ids)))
        return list(self.s.execute(q).all())

    def reviewed_finding_ids(self, finding_ids) -> set:
        """Findings with a confirm, correct or dismiss; a note alone is not a review."""
        q = select(ReviewEvent.finding_id).where(ReviewEvent.tenant_id == self.tenant_id,
                                                 ReviewEvent.finding_id.in_(list(finding_ids)),
                                                 ReviewEvent.action != "note").distinct()
        return set(self.s.scalars(q))

    def comparisons_of(self, project_id: uuid.UUID) -> list[Comparison]:
        q = (select(Comparison)
             .where(Comparison.tenant_id == self.tenant_id, Comparison.project_id == project_id)
             .order_by(Comparison.created_at.desc()))
        return list(self.s.scalars(q))

    def version(self, id_: uuid.UUID, lock: bool = False) -> Optional[SourceVersion]:
        row = self._get(SourceVersion, id_, lock)
        return row if row is not None and self.project(row.project_id) is not None else None

    def comparison(self, id_: uuid.UUID, lock: bool = False) -> Optional[Comparison]:
        row = self.comparison_ledger(id_, lock)
        return row if row is not None and self.project(row.project_id) is not None else None

    def comparison_ledger(self, id_: uuid.UUID, lock: bool = False) -> Optional[Comparison]:
        # Cost settlement must work after the project is frozen and until graph transfer.
        return self._get(Comparison, id_, lock)

    def comparison_cost_tombstone(self, id_: uuid.UUID, lock: bool = False) -> Optional[ComparisonCostTombstone]:
        return self._get(ComparisonCostTombstone, id_, lock)

    def lock_project(self, project_id: uuid.UUID, *, wait: bool = True) -> bool:
        function = "pg_advisory_xact_lock" if wait else "pg_try_advisory_xact_lock"
        result = self.s.scalar(text(f"SELECT {function}(:key)"),
                               {"key": project_lock_id(self.tenant_id, project_id)})
        return True if wait else bool(result)

    def _lock_resource_project(self, model, id_: uuid.UUID) -> bool:
        project_id = self.s.scalar(select(model.project_id).where(model.id == id_, model.tenant_id == self.tenant_id))
        if project_id is None:
            return False
        self.lock_project(project_id)
        # Re-read after the lifecycle lock: expiry may have removed the resource meanwhile.
        return self.project(project_id) is not None and self._get(model, id_) is not None

    def lock_for_version(self, id_: uuid.UUID) -> bool:
        return self._lock_resource_project(SourceVersion, id_)

    def lock_for_comparison(self, id_: uuid.UUID) -> bool:
        return self._lock_resource_project(Comparison, id_)

    def lock_for_finding(self, id_: uuid.UUID) -> bool:
        comparison_id = self.s.scalar(select(Finding.comparison_id).where(
            Finding.id == id_, Finding.tenant_id == self.tenant_id))
        return comparison_id is not None and self.lock_for_comparison(comparison_id)

    def touch_version(self, version: SourceVersion, now: Optional[datetime] = None) -> None:
        version.last_used_at = used_at(version.last_used_at, now or datetime.now(timezone.utc))

    def touch_comparison(self, comparison: Comparison, now: Optional[datetime] = None) -> None:
        now = now or datetime.now(timezone.utc)
        comparison.last_used_at = used_at(comparison.last_used_at, now)
        for identifier in sorted({comparison.earlier_id, comparison.later_id}):
            version = self.version(identifier, lock=True)
            if version is not None:
                self.touch_version(version, now)

    def lock_comparison_key(self, key: str) -> None:
        # Serialise the same key across projects before writing objects or versions. The
        # unique constraint remains a second guard; this lock is released on transaction end.
        self.s.execute(text("SELECT pg_advisory_xact_lock(:key)"),
                       {"key": comparison_lock_id(self.tenant_id, key)})

    def try_object_write_lock(self, lock_id: int) -> bool:
        return bool(self.s.scalar(text("SELECT pg_try_advisory_xact_lock(:key)"), {"key": lock_id}))

    def object_write_intent(self, id_: uuid.UUID, lock: bool = False) -> Optional[ObjectWriteIntent]:
        q = select(ObjectWriteIntent).where(ObjectWriteIntent.id == id_, ObjectWriteIntent.tenant_id == self.tenant_id)
        if lock:
            q = q.with_for_update().execution_options(populate_existing=True)
        return self.s.scalars(q).one_or_none()

    def object_key_is_referenced(self, key: str) -> bool:
        q = select(SourceVersion.id).where(SourceVersion.tenant_id == self.tenant_id,
                                            SourceVersion.original_object_key == key).limit(1)
        return self.s.scalar(q) is not None

    def remove_object_write_intent(self, intent: ObjectWriteIntent) -> None:
        self.s.delete(intent)

    def comparison_by_key(self, key: str) -> Optional[Comparison]:
        return self.s.scalars(select(Comparison).where(Comparison.tenant_id == self.tenant_id,
                                                       Comparison.idempotency_key == key)).one_or_none()

    def waiting_for_version(self, version_id: uuid.UUID) -> list[Comparison]:
        query = (select(Comparison).where(Comparison.tenant_id == self.tenant_id,
                    Comparison.status == "waiting_for_versions",
                    or_(Comparison.earlier_id == version_id, Comparison.later_id == version_id))
                 .order_by(Comparison.id).with_for_update())
        return list(self.s.scalars(query))

    def findings(self, comparison_id: uuid.UUID) -> list[Finding]:
        q = (select(Finding)
             .where(Finding.comparison_id == comparison_id, Finding.tenant_id == self.tenant_id)
             .order_by(Finding.priority))
        return list(self.s.scalars(q))

    def finding(self, id_: uuid.UUID, lock: bool = False) -> Optional[Finding]:
        row = self._get(Finding, id_, lock)
        return row if row is not None and self.comparison(row.comparison_id) is not None else None

    def reviews(self, finding_ids) -> list[ReviewEvent]:
        q = (select(ReviewEvent).where(ReviewEvent.tenant_id == self.tenant_id,
                                       ReviewEvent.finding_id.in_(list(finding_ids)))
             .order_by(ReviewEvent.created_at, ReviewEvent.id))
        return list(self.s.scalars(q))

    def approvals(self, finding_ids) -> list[ClientApprovalRecord]:
        q = (select(ClientApprovalRecord).where(ClientApprovalRecord.tenant_id == self.tenant_id,
                                                ClientApprovalRecord.finding_id.in_(list(finding_ids)))
             .order_by(ClientApprovalRecord.created_at, ClientApprovalRecord.id))
        return list(self.s.scalars(q))

    def cached_facts(self, key: str) -> Optional[dict]:
        q = select(FactCacheEntry.result).where(FactCacheEntry.tenant_id == self.tenant_id,
                                                FactCacheEntry.cache_key == key)
        return self.s.scalars(q).one_or_none()

    def cache_facts(self, version_id: uuid.UUID, key: str, result: dict) -> None:
        """First writer wins; a concurrent duplicate for the same key is dropped."""
        if self.cached_facts(key) is None:
            try:
                with self.s.begin_nested():  # savepoint: a lost race rolls back only this insert
                    self.add(FactCacheEntry(source_version_id=version_id, cache_key=key, result=result))
            except IntegrityError:
                pass

    def onboarding(self, account_id: uuid.UUID, lock: bool = False) -> Optional[AccountOnboarding]:
        """Onboarding state (O-23). No row means not started; reads never create one."""
        q = (select(AccountOnboarding).where(AccountOnboarding.account_id == account_id,
                                             AccountOnboarding.tenant_id == self.tenant_id)
             .execution_options(populate_existing=True))
        if lock:
            q = q.with_for_update()
        return self.s.scalars(q).one_or_none()

    def record_onboarding(self, account_id: uuid.UUID, *, step: Optional[int] = None, completed: bool = False,
                          now: Optional[datetime] = None) -> Optional[AccountOnboarding]:
        """Last step write wins; completion is set once by the server clock and never cleared.
        The row lock serialises a step write against a completion, so the step can't reopen it."""
        if (step is None) != completed:
            raise ValueError("exactly one of step or completed")
        now = now or datetime.now(timezone.utc)
        row = self.onboarding(account_id, lock=True)
        if row is None:  # the first write creates the row
            try:
                with self.s.begin_nested():  # savepoint: a lost first-write race rolls back only this insert
                    row = self.add(AccountOnboarding(account_id=account_id, updated_at=now))
            except IntegrityError:
                row = self.onboarding(account_id, lock=True)  # the winner has committed; lock its row
                if row is None:
                    return None
        if row.onboarding_completed_at is None:
            if completed:
                row.onboarding_completed_at, row.onboarding_step = now, None
            else:
                row.onboarding_step = step
            row.updated_at = now
            self.s.flush()
        return row

    def consent(self, account_id: uuid.UUID, purpose: str) -> Optional[ConsentEvent]:
        """The newest consent answer for one purpose, or None (D-18 tier B). Reads never write."""
        return self.s.scalars(
            select(ConsentEvent).where(ConsentEvent.account_id == account_id, ConsentEvent.purpose == purpose,
                                       ConsentEvent.tenant_id == self.tenant_id)
            .order_by(ConsentEvent.decided_at.desc()).limit(1)).one_or_none()

    def record_consent(self, account_id: uuid.UUID, purpose: str, granted: bool, policy_version: str,
                       now: Optional[datetime] = None) -> ConsentEvent:
        """Append one answer; earlier answers stay as they were (the record of choice, time and version)."""
        row = self.add(ConsentEvent(account_id=account_id, purpose=purpose, granted=granted,
                                    policy_version=policy_version, decided_at=now or datetime.now(timezone.utc)))
        self.s.flush()
        return row

    def delete_consent(self, account_id: uuid.UUID) -> int:
        """For 03a P8 DELETE_ACCOUNT: append-only means never updated, not kept after the account is gone."""
        result = self.s.execute(delete(ConsentEvent).where(ConsentEvent.account_id == account_id,
                                                           ConsentEvent.tenant_id == self.tenant_id))
        return result.rowcount

    def month_spend(self, since: datetime) -> Decimal:
        """This tenant's spend since `since`: actual costs plus open reservations, tombstones included."""
        from changelens.domain.spend import tenant_spend
        return tenant_spend(self.s, self.tenant_id, since)

    def global_month_spend(self, since: datetime) -> Decimal:
        """All tenants' spend since `since`, for the kill switch: one number, no rows (I-8 S6)."""
        from changelens.domain.spend import global_spend
        return global_spend(self.s, since)

    def delete_onboarding(self, account_id: uuid.UUID) -> int:
        """For 03a P8 DELETE_ACCOUNT (and DELETE_TENANT per member); no route until I-8.
        Project deletion and retention never call this: it is account data, not project data."""
        result = self.s.execute(delete(AccountOnboarding).where(AccountOnboarding.account_id == account_id,
                                                                AccountOnboarding.tenant_id == self.tenant_id))
        return result.rowcount

    def replace_findings(self, comparison_id: uuid.UUID, findings: list[Finding]) -> None:
        """Retries never duplicate findings (03 §7): the old set is replaced in the same transaction."""
        self.s.execute(delete(Finding).where(Finding.comparison_id == comparison_id,
                                             Finding.tenant_id == self.tenant_id))
        for f in findings:
            self.add(f)
