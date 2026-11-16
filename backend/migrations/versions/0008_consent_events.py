"""Usage-events consent (D-18 tier B; docs/api-contracts-draft.md C1): `consent_events`.

One append-only row per answer: account, purpose, choice, privacy-policy version and time; no content
(AC-23). The newest row is the account's answer. It is a tenant table: forced RLS, the 0003 policy and
row rights for the app role. Account deletion (03a P8) deletes the rows.

Revision ID: 0008_consent_events
Revises: 0007_dismissal_reason
Create Date: 2026-11-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0008_consent_events"
down_revision: Union[str, Sequence[str], None] = "0007_dismissal_reason"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APP = "changelens_app"
TENANT_TABLES = ("consent_events",)
TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        "consent_events",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("purpose", sa.String(length=32), nullable=False),
        sa.Column("granted", sa.Boolean(), nullable=False),
        sa.Column("policy_version", sa.String(length=32), nullable=False),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("purpose IN ('usage_events')", name="ck_consent_events_purpose"),
        sa.ForeignKeyConstraint(["account_id"], ["users.id"], name="fk_consent_events_user"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_consent_events_tenant_id"), "consent_events", ["tenant_id"], unique=False)
    op.create_index("ix_consent_events_account_purpose", "consent_events",
                    ["account_id", "purpose", "decided_at"], unique=False)
    for table in TENANT_TABLES:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO {APP}")
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY tenant_isolation ON {table} FOR ALL "
                   f"USING (tenant_id = {TENANT}) WITH CHECK (tenant_id = {TENANT})")


def downgrade() -> None:
    op.drop_index("ix_consent_events_account_purpose", table_name="consent_events")
    op.drop_index(op.f("ix_consent_events_tenant_id"), table_name="consent_events")
    op.drop_table("consent_events")
