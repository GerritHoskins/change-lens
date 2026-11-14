"""Account deletion (I-8 S5): the receipt table, the user tombstone and four narrow functions.

`account_deletions` is a tenant table: forced RLS, the same policy as 0003, row rights for the app role.
`users.idp_subject` becomes nullable, but only on a deleted user (`ck_users_tombstone`).

The app role still has no rights on `users`. It changes a user row only through these SECURITY DEFINER
functions, and only for a user with a pending receipt and a membership in the tenant set in
`app.tenant_id`, so a request can only ever delete its own account. The membership is deleted last, in
the tombstone's transaction, so the check holds through every step:
- `account_freeze(user)`: set `deleted_at` (GUARD rejects the user from the next request);
- `account_deletion_subject(user)`: the Logto subject, needed once to delete the Logto user;
- `account_tombstone(user)`: clear the subject, leaving ID and timestamps;
- `account_deletion_candidates(now, limit)`: maintenance's (tenant ID, user ID) pairs that are due.

Revision ID: 0004_account_deletion
Revises: 0003_rls
Create Date: 2026-11-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0004_account_deletion"
down_revision: Union[str, Sequence[str], None] = "0003_rls"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APP = "changelens_app"
TENANT_TABLES = ("account_deletions",)
TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"
# A pending receipt for this user in the current tenant, and the user's membership there.
_OWN_PENDING = f"""
        EXISTS (SELECT 1 FROM public.account_deletions d WHERE d.user_id = p_user AND d.status = 'pending'
                AND d.tenant_id = {TENANT})
        AND EXISTS (SELECT 1 FROM public.memberships m WHERE m.user_id = p_user AND m.tenant_id = {TENANT})"""

FUNCTIONS = {
    "account_freeze(uuid)": f"""
CREATE FUNCTION account_freeze(p_user uuid) RETURNS boolean
LANGUAGE sql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
    WITH frozen AS (
        UPDATE public.users u SET deleted_at = COALESCE(u.deleted_at, now())
        WHERE u.id = p_user AND {_OWN_PENDING}
        RETURNING u.id)
    SELECT EXISTS (SELECT 1 FROM frozen)
$$""",
    "account_deletion_subject(uuid)": f"""
CREATE FUNCTION account_deletion_subject(p_user uuid) RETURNS text
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
    SELECT u.idp_subject FROM public.users u
    WHERE u.id = p_user AND u.deleted_at IS NOT NULL AND {_OWN_PENDING}
$$""",
    "account_tombstone(uuid)": f"""
CREATE FUNCTION account_tombstone(p_user uuid) RETURNS boolean
LANGUAGE sql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
    WITH cleared AS (
        UPDATE public.users u SET idp_subject = NULL
        WHERE u.id = p_user AND u.deleted_at IS NOT NULL AND {_OWN_PENDING}
        RETURNING u.id)
    SELECT EXISTS (SELECT 1 FROM cleared)
$$""",
    "account_deletion_candidates(timestamp with time zone, integer)": """
CREATE FUNCTION account_deletion_candidates(p_now timestamptz, p_limit integer)
RETURNS TABLE (tenant_id uuid, user_id uuid)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
#variable_conflict use_column
BEGIN
    IF p_now IS NULL OR p_limit IS NULL OR p_limit < 1 OR p_limit > 1000 THEN
        RAISE EXCEPTION 'invalid argument' USING ERRCODE = '22023';
    END IF;
    RETURN QUERY
    SELECT d.tenant_id, d.user_id FROM public.account_deletions d
    WHERE d.status = 'pending' AND d.next_attempt_at <= p_now ORDER BY d.next_attempt_at LIMIT p_limit;
END
$$""",
}


def upgrade() -> None:
    op.alter_column("users", "idp_subject", existing_type=sa.String(length=200), nullable=True)
    op.create_check_constraint("ck_users_tombstone", "users", "idp_subject IS NOT NULL OR deleted_at IS NOT NULL")
    op.create_table(
        "account_deletions",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("tenant_id", sa.UUID(), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("requested_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.Column("idp_deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("status IN ('pending', 'complete')", name="ck_account_deletions_status"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_account_deletions_user"),
        sa.PrimaryKeyConstraint("user_id"),
    )
    op.create_index(op.f("ix_account_deletions_tenant_id"), "account_deletions", ["tenant_id"], unique=False)
    for table in TENANT_TABLES:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO {APP}")
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY tenant_isolation ON {table} FOR ALL "
                   f"USING (tenant_id = {TENANT}) WITH CHECK (tenant_id = {TENANT})")
    for signature, body in FUNCTIONS.items():
        op.execute(body)
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {APP}")


def downgrade() -> None:
    for signature in FUNCTIONS:
        op.execute(f"DROP FUNCTION {signature}")
    op.drop_index(op.f("ix_account_deletions_tenant_id"), table_name="account_deletions")
    op.drop_table("account_deletions")
    op.drop_constraint("ck_users_tombstone", "users", type_="check")
    # Tombstones have no subject and cannot return to NOT NULL; downgrading removes them first.
    op.execute("DELETE FROM users WHERE idp_subject IS NULL")
    op.alter_column("users", "idp_subject", existing_type=sa.String(length=200), nullable=False)
