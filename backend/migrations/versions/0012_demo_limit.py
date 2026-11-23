"""The demo period's limit and feedback (docs/demo-wall-handoff.md): `demo_comparisons`, `demo_feedback`.

- `demo_comparisons`: one row per comparison that reached `complete` or `partial`: the comparison's ID (the
  primary key, so once per comparison), the tenant and the time. No foreign key to `comparisons`: deleting a
  project and the 30-day retention give no comparison back. Existing `complete` and `partial` comparisons are
  counted here, so accounts that exist start at their real number.
- `demo_feedback`: one row per account: two codes, the plan the price question referred to, and two free-text
  fields that hold whatever the person typed.

Both are tenant tables: forced RLS, the 0003 policy and row rights for the app role. Account deletion
(03a P8) deletes the rows of both.

Revision ID: 0012_demo_limit
Revises: 0011_early_bird_hardening
Create Date: 2026-11-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0012_demo_limit"
down_revision: Union[str, Sequence[str], None] = "0011_early_bird_hardening"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APP = "changelens_app"
TENANT_TABLES = ("demo_comparisons", "demo_feedback")
TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"


def upgrade() -> None:
    op.create_table(
        "demo_comparisons",
        sa.Column("comparison_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("counted_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("comparison_id"),
    )
    op.create_index(op.f("ix_demo_comparisons_tenant_id"), "demo_comparisons", ["tenant_id"], unique=False)
    op.create_table(
        "demo_feedback",
        sa.Column("account_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("missing", sa.String(length=32), nullable=False),
        sa.Column("missing_other", sa.String(length=500), nullable=True),
        sa.Column("anything_else", sa.String(length=500), nullable=True),
        sa.Column("price", sa.String(length=16), nullable=False),
        sa.Column("plan_id", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("missing IN ('screenshot_import', 'more_file_types', 'share_report', 'better_accuracy', "
                           "'faster_results', 'team', 'other')", name="ck_demo_feedback_missing"),
        sa.CheckConstraint("price IN ('eur_0', 'eur_5', 'eur_10', 'eur_15', 'eur_over_15', 'not_sure')",
                           name="ck_demo_feedback_price"),
        sa.CheckConstraint("(missing = 'other') = (missing_other IS NOT NULL)", name="ck_demo_feedback_other"),
        sa.ForeignKeyConstraint(["account_id"], ["users.id"], name="fk_demo_feedback_user"),
        sa.PrimaryKeyConstraint("account_id"),
    )
    op.create_index(op.f("ix_demo_feedback_tenant_id"), "demo_feedback", ["tenant_id"], unique=False)
    # Existing finished comparisons count. The migration runs as the owner role, which row-level security
    # does not apply to, so this reads every tenant's rows.
    op.execute("INSERT INTO demo_comparisons (comparison_id, tenant_id, counted_at) "
               "SELECT id, tenant_id, updated_at FROM comparisons WHERE status IN ('complete', 'partial')")
    for table in TENANT_TABLES:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO {APP}")
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY tenant_isolation ON {table} FOR ALL "
                   f"USING (tenant_id = {TENANT}) WITH CHECK (tenant_id = {TENANT})")


def downgrade() -> None:
    op.drop_index(op.f("ix_demo_feedback_tenant_id"), table_name="demo_feedback")
    op.drop_table("demo_feedback")
    op.drop_index(op.f("ix_demo_comparisons_tenant_id"), table_name="demo_comparisons")
    op.drop_table("demo_comparisons")
