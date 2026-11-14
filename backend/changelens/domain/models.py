"""SQLAlchemy models for the I-22 subset of 03 §5. Every table has `tenant_id` (AC-19)."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, Numeric, SmallInteger, String, Text,
    UniqueConstraint, func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


def _id() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def _tenant() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), nullable=False, index=True)


def _now() -> Mapped[datetime]:
    return mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class Project(Base):
    __tablename__ = "projects"
    id: Mapped[uuid.UUID] = _id()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    client_label: Mapped[Optional[str]] = mapped_column(String(200))
    created_at: Mapped[datetime] = _now()
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))


class SourceVersion(Base):
    __tablename__ = "source_versions"
    id: Mapped[uuid.UUID] = _id()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    kind: Mapped[str] = mapped_column(String(10), nullable=False)  # text | pdf
    original_object_key: Mapped[str] = mapped_column(String(300), nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)  # never used to dedupe across tenants
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    page_count: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="uploaded")  # uploaded | parsed | rejected
    reject_reason: Mapped[Optional[str]] = mapped_column(String(50))
    # Exact parsed text per page (one entry for text); 07 §4 locators index into it. Immutable (AC-15).
    parsed_pages: Mapped[Optional[list]] = mapped_column(JSONB)
    blocks: Mapped[Optional[list]] = mapped_column(JSONB)
    parse_warnings: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = _now()
    last_used_at: Mapped[datetime] = _now()


class ObjectWriteIntent(Base):
    """Committed before PUT; no FK cascade can erase an outstanding cleanup obligation."""
    __tablename__ = "object_write_intents"
    id: Mapped[uuid.UUID] = _id()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    object_key: Mapped[str] = mapped_column(String(300), nullable=False, unique=True)
    request_lock_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    write_acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    created_at: Mapped[datetime] = _now()


class Comparison(Base):
    __tablename__ = "comparisons"
    __table_args__ = (UniqueConstraint("tenant_id", "idempotency_key", name="uq_comparisons_request"),)
    id: Mapped[uuid.UUID] = _id()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    earlier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_versions.id"), nullable=False)
    later_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_versions.id"), nullable=False)
    scope_snapshot: Mapped[str] = mapped_column(String(10), nullable=False)
    pipeline_version: Mapped[str] = mapped_column(String(40), nullable=False)
    model_config_id: Mapped[str] = mapped_column(String(40), nullable=False)
    # waiting_for_versions | queued | running | complete | partial | failed
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="queued")
    idempotency_key: Mapped[Optional[str]] = mapped_column(String(128))  # null only on legacy rows
    request_fingerprint: Mapped[Optional[str]] = mapped_column(String(64))
    cost_ceiling: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    cost_estimate: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    cost_actual: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 10))
    # Attempt UUID -> reserved EUR as a decimal string. Uncertain/crashed calls retain a hold.
    cost_reservations: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    withheld_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warnings: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    # I-5 verify: changed blocks no finding explains (AC-18) and blocks that only moved (AC-5, AC-6).
    unexplained: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    presentation_only: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = _now()
    last_used_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(),
                                                 onupdate=func.now(), nullable=False)


class ComparisonCostTombstone(Base):
    """Content-free accounting survives graph expiry so late usage can still settle."""
    __tablename__ = "comparison_cost_tombstones"
    id: Mapped[uuid.UUID] = _id()  # original comparison ID; deliberately no cascade FK
    tenant_id: Mapped[uuid.UUID] = _tenant()
    cost_actual: Mapped[Decimal] = mapped_column(Numeric(20, 10), nullable=False)
    cost_reservations: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = _now()


class ObjectPurgeIntent(Base):
    """Committed with source-row deletion; independent of upload-outcome tombstones."""
    __tablename__ = "object_purge_intents"
    id: Mapped[uuid.UUID] = _id()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), nullable=False, index=True)
    object_key: Mapped[str] = mapped_column(String(300), nullable=False, unique=True)
    next_attempt_at: Mapped[datetime] = _now()
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ProjectDeletion(Base):
    """Tenant-scoped deletion receipt; contains identifiers and state, never project content."""
    __tablename__ = "project_deletions"
    project_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = _tenant()
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="pending")
    requested_at: Mapped[datetime] = _now()
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    next_attempt_at: Mapped[datetime] = _now()
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class Finding(Base):
    __tablename__ = "findings"
    id: Mapped[uuid.UUID] = _id()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    comparison_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("comparisons.id"), nullable=False, index=True)
    category: Mapped[str] = mapped_column(String(40), nullable=False)
    change_type: Mapped[str] = mapped_column(String(20), nullable=False)
    evidence: Mapped[list] = mapped_column(JSONB, nullable=False)
    explanation: Mapped[Optional[str]] = mapped_column(Text)
    uncertainty: Mapped[Optional[str]] = mapped_column(String(40))
    note: Mapped[Optional[str]] = mapped_column(String(40))
    review_group: Mapped[str] = mapped_column(String(20), nullable=False, default="other")
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    supersedes_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))


class FactCacheEntry(Base):
    """Extracted facts per version (03 §2, AD-4). The key covers the version hash, the extract
    prompt and schema, and the model config (pipeline.extract.cache_key); tenant-scoped (03 §5)."""
    __tablename__ = "fact_cache"
    __table_args__ = (UniqueConstraint("tenant_id", "cache_key", name="uq_fact_cache_tenant_key"),)
    id: Mapped[uuid.UUID] = _id()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    source_version_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_versions.id"), nullable=False)
    cache_key: Mapped[str] = mapped_column(String(64), nullable=False)
    result: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = _now()


class Job(Base):
    """Postgres queue row. `payload` holds IDs only (AC-23); `last_error` is an error class name."""
    __tablename__ = "jobs"
    __table_args__ = (
        UniqueConstraint("idempotency_key", name="uq_jobs_idempotency_key"),
        Index("ix_jobs_claim", "status", "run_after"),
    )
    id: Mapped[uuid.UUID] = _id()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    kind: Mapped[str] = mapped_column(String(20), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    idempotency_key: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="queued")  # queued | running | done | failed
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, nullable=False)
    run_after: Mapped[datetime] = _now()
    locked_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[Optional[str]] = mapped_column(String(80))
    created_at: Mapped[datetime] = _now()


class ReviewEvent(Base):
    """User review of a finding (02 §5, 03a P6). Append-only; never creates or implies client
    approval (AC-12). `actor` is the dev-token user until I-8 brings real users."""
    __tablename__ = "review_events"
    __table_args__ = (
        CheckConstraint("evidence_mode_before IS NULL OR evidence_mode_before IN "
                        "('pdf_highlight', 'text_fallback', 'text_only')", name="ck_review_evidence_before"),
        CheckConstraint("evidence_mode_after IS NULL OR evidence_mode_after IN "
                        "('pdf_highlight', 'text_fallback', 'text_only')", name="ck_review_evidence_after"),
    )
    id: Mapped[uuid.UUID] = _id()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    finding_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("findings.id"), nullable=False, index=True)
    actor: Mapped[str] = mapped_column(String(80), nullable=False)
    action: Mapped[str] = mapped_column(String(12), nullable=False)  # confirmed | corrected | dismissed | note
    note: Mapped[Optional[str]] = mapped_column(Text)
    # Null on historical rows: the device never reported these observations (I-26 / O-17).
    evidence_mode_before: Mapped[Optional[str]] = mapped_column(String(20))
    evidence_mode_after: Mapped[Optional[str]] = mapped_column(String(20))
    page_opened: Mapped[Optional[bool]] = mapped_column(Boolean)
    created_at: Mapped[datetime] = _now()


class ClientApprovalRecord(Base):
    """Someone stated that the client approved (02 §5). Separate from review and never set by it
    (AC-12); ChangeLens does not verify it. Append-only."""
    __tablename__ = "client_approvals"
    id: Mapped[uuid.UUID] = _id()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    finding_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("findings.id"), nullable=False, index=True)
    evidence_text: Mapped[str] = mapped_column(Text, nullable=False)  # e.g. a pasted e-mail excerpt
    stated_by: Mapped[str] = mapped_column(String(200), nullable=False)
    stated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    recorded_by: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = _now()


class AccountOnboarding(Base):
    """Onboarding state of one account (O-23). Identifiers, a step number and timestamps only (AC-23).
    `account_id` is the tenant ID until I-8 (one tenant per account in v1); I-8 adds the FK to users.id."""
    __tablename__ = "account_onboarding"
    __table_args__ = (
        CheckConstraint("onboarding_step IS NULL OR onboarding_step BETWEEN 1 AND 32", name="ck_onboarding_step"),
        CheckConstraint("onboarding_completed_at IS NULL OR onboarding_step IS NULL", name="ck_onboarding_done"),
    )
    account_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True)
    tenant_id: Mapped[uuid.UUID] = _tenant()
    onboarding_step: Mapped[Optional[int]] = mapped_column(SmallInteger)  # last step reached, 1-based
    onboarding_completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))  # set once
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
