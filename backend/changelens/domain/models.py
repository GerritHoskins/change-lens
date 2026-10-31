"""SQLAlchemy models for the I-22 subset of 03 §5. Every table has `tenant_id` (AC-19)."""
from __future__ import annotations

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Optional

from sqlalchemy import (
    DateTime, ForeignKey, Index, Integer, Numeric, String, Text, UniqueConstraint, func,
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
    parsed_text: Mapped[Optional[str]] = mapped_column(Text)
    blocks: Mapped[Optional[list]] = mapped_column(JSONB)
    parse_warnings: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = _now()


class Comparison(Base):
    __tablename__ = "comparisons"
    id: Mapped[uuid.UUID] = _id()
    tenant_id: Mapped[uuid.UUID] = _tenant()
    project_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("projects.id"), nullable=False)
    earlier_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_versions.id"), nullable=False)
    later_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("source_versions.id"), nullable=False)
    scope_snapshot: Mapped[str] = mapped_column(String(10), nullable=False)
    pipeline_version: Mapped[str] = mapped_column(String(40), nullable=False)
    model_config_id: Mapped[str] = mapped_column(String(40), nullable=False)
    # queued | running | complete | partial | failed
    status: Mapped[str] = mapped_column(String(10), nullable=False, default="queued")
    cost_ceiling: Mapped[Decimal] = mapped_column(Numeric(10, 4), nullable=False)
    cost_estimate: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    cost_actual: Mapped[Optional[Decimal]] = mapped_column(Numeric(10, 4))
    withheld_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    warnings: Mapped[list] = mapped_column(JSONB, nullable=False, default=list)
    created_at: Mapped[datetime] = _now()
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(),
                                                 onupdate=func.now(), nullable=False)


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
    priority: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    supersedes_id: Mapped[Optional[uuid.UUID]] = mapped_column(UUID(as_uuid=True))


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
