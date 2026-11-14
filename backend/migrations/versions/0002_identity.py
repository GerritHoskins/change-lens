"""Identity (I-8 S1): `users`, `memberships`, and `account_onboarding.account_id` -> `users.id`.

`users` is the one pre-tenant table: no `tenant_id`, no email, one Logto subject (I-8 overview,
decisions 3-5). A user has at most one active membership (partial unique index).

Before the foreign key is added, this revision DELETES every `account_onboarding` row whose
`account_id` has no matching user. Until now the account ID was the dev-token tenant ID, so these
rows are local dev data only; there are no real accounts (06, I-8 S1 row). Downgrade drops the
tables and the key but cannot bring the deleted rows back.

Revision ID: 0002_identity
Revises: 0001_baseline
Create Date: 2026-11-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0002_identity"
down_revision: Union[str, Sequence[str], None] = "0001_baseline"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("idp_subject", sa.String(length=200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("idp_subject <> ''", name="ck_users_idp_subject"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("idp_subject", name="uq_users_idp_subject"),
    )
    op.create_table(
        "memberships",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("role", sa.String(length=10), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.CheckConstraint("role IN ('owner', 'member')", name="ck_memberships_role"),
        sa.CheckConstraint("status IN ('active', 'inactive')", name="ck_memberships_status"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_memberships_user"),
        sa.PrimaryKeyConstraint("user_id", "tenant_id"),
    )
    op.create_index(op.f("ix_memberships_tenant_id"), "memberships", ["tenant_id"], unique=False)
    op.create_index("uq_memberships_one_active", "memberships", ["user_id"], unique=True,
                    postgresql_where=sa.text("status = 'active'"))
    # Dev data only (see the docstring): rows keyed on the old tenant-as-account ID have no user.
    op.execute("DELETE FROM account_onboarding o WHERE NOT EXISTS (SELECT 1 FROM users u WHERE u.id = o.account_id)")
    op.create_foreign_key("fk_account_onboarding_user", "account_onboarding", "users", ["account_id"], ["id"])


def downgrade() -> None:
    op.drop_constraint("fk_account_onboarding_user", "account_onboarding", type_="foreignkey")
    op.drop_index("uq_memberships_one_active", table_name="memberships")
    op.drop_index(op.f("ix_memberships_tenant_id"), table_name="memberships")
    op.drop_table("memberships")
    op.drop_table("users")
