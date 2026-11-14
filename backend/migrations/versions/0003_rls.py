"""Row-level security (I-8 S3): forced tenant policies, app-role grants and pre-tenant functions.

Run as `changelens_owner` (the migration role). `python -m changelens.db bootstrap-roles` creates both
roles first and hands existing objects to the owner. Every table with `tenant_id` gets ENABLE and FORCE
ROW LEVEL SECURITY and one policy for all commands:
`tenant_id = NULLIF(current_setting('app.tenant_id', true), '')::uuid`. With no tenant set the setting is
null, or '' on a pooled connection that had one set in an earlier transaction; either way nothing matches. `users` gets RLS with no policy and no grant.

The app role (`changelens_app`) reaches pre-tenant data only through the SECURITY DEFINER functions
below. Each is owned by the owner role, pins `search_path`, validates its arguments and returns IDs and
scalar fields only. EXECUTE is revoked from PUBLIC and granted to the app role.

Revision ID: 0003_rls
Revises: 0002_identity
Create Date: 2026-11-14
"""
from typing import Sequence, Union

from alembic import op

revision: str = "0003_rls"
down_revision: Union[str, Sequence[str], None] = "0002_identity"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

OWNER, APP = "changelens_owner", "changelens_app"
TENANT_TABLES = ("projects", "source_versions", "object_write_intents", "comparisons", "comparison_cost_tombstones",
                 "object_purge_intents", "project_deletions", "findings", "fact_cache", "jobs", "review_events",
                 "client_approvals", "account_onboarding", "memberships")
POLICY = "tenant_isolation"
# Keep in step with changelens.domain.retention.RETENTION (a unit test compares them).
RETENTION_DAYS = 30

FUNCTIONS = {
    "session_lookup(text)": """
CREATE FUNCTION session_lookup(p_subject text)
RETURNS TABLE (user_id uuid, tenant_id uuid, member_role text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
    SELECT u.id, m.tenant_id, m.role::text
    FROM public.users u JOIN public.memberships m ON m.user_id = u.id AND m.status = 'active'
    WHERE u.idp_subject = p_subject AND u.deleted_at IS NULL
$$""",
    "session_bootstrap(text, boolean)": """
CREATE FUNCTION session_bootstrap(p_subject text, p_create boolean)
RETURNS TABLE (outcome text, user_id uuid, tenant_id uuid, member_role text)
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
#variable_conflict use_column
DECLARE
    v_user uuid;
    v_deleted timestamptz;
    v_tenant uuid;
    v_role text;
    v_created boolean := false;
BEGIN
    IF p_subject IS NULL OR p_subject = '' OR length(p_subject) > 200 OR p_create IS NULL THEN
        RAISE EXCEPTION 'invalid argument' USING ERRCODE = '22023';
    END IF;
    SELECT u.id, u.deleted_at INTO v_user, v_deleted FROM public.users u WHERE u.idp_subject = p_subject;
    IF v_user IS NULL THEN
        IF NOT p_create THEN
            RETURN QUERY SELECT 'missing'::text, NULL::uuid, NULL::uuid, NULL::text;
            RETURN;
        END IF;
        -- A concurrent first call waits here for the winner, then inserts nothing and re-reads it.
        INSERT INTO public.users (id, idp_subject) VALUES (gen_random_uuid(), p_subject)
            ON CONFLICT (idp_subject) DO NOTHING RETURNING id INTO v_user;
        IF v_user IS NOT NULL THEN
            INSERT INTO public.memberships (user_id, tenant_id, role, status)
                VALUES (v_user, gen_random_uuid(), 'owner', 'active');
            v_created := true;
        ELSE
            SELECT u.id, u.deleted_at INTO v_user, v_deleted FROM public.users u WHERE u.idp_subject = p_subject;
        END IF;
    END IF;
    IF v_deleted IS NOT NULL THEN
        RETURN QUERY SELECT 'deleted'::text, NULL::uuid, NULL::uuid, NULL::text;
        RETURN;
    END IF;
    SELECT m.tenant_id, m.role INTO v_tenant, v_role
        FROM public.memberships m WHERE m.user_id = v_user AND m.status = 'active';
    IF v_tenant IS NULL THEN
        RETURN QUERY SELECT 'no_membership'::text, NULL::uuid, NULL::uuid, NULL::text;
        RETURN;
    END IF;
    RETURN QUERY SELECT CASE WHEN v_created THEN 'created' ELSE 'existing' END, v_user, v_tenant, v_role;
END
$$""",
    "queue_claim()": """
CREATE FUNCTION queue_claim()
RETURNS TABLE (job_id uuid, tenant_id uuid, kind text, ids jsonb, attempts integer, max_attempts integer)
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
#variable_conflict use_column
BEGIN
    RETURN QUERY
    UPDATE public.jobs j SET status = 'running', attempts = j.attempts + 1, locked_at = now()
    WHERE j.id = (SELECT q.id FROM public.jobs q WHERE q.status = 'queued' AND q.run_after <= now()
                  ORDER BY q.created_at FOR UPDATE SKIP LOCKED LIMIT 1)
    RETURNING j.id, j.tenant_id, j.kind::text, j.payload -> 'ids', j.attempts, j.max_attempts;
END
$$""",
    "queue_reclaim_expired(integer)": """
CREATE FUNCTION queue_reclaim_expired(p_lease_seconds integer)
RETURNS TABLE (job_id uuid, tenant_id uuid, kind text, ids jsonb, attempts integer, max_attempts integer)
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
#variable_conflict use_column
BEGIN
    IF p_lease_seconds IS NULL OR p_lease_seconds < 1 OR p_lease_seconds > 86400 THEN
        RAISE EXCEPTION 'invalid argument' USING ERRCODE = '22023';
    END IF;
    -- Requeues jobs past their lease; returns only the ones that just failed for good.
    RETURN QUERY
    WITH reclaimed AS (
        UPDATE public.jobs j
        SET status = CASE WHEN j.attempts >= j.max_attempts THEN 'failed' ELSE 'queued' END,
            locked_at = NULL, last_error = 'lease_expired', run_after = now()
        WHERE j.status = 'running' AND j.locked_at < now() - make_interval(secs => p_lease_seconds)
        RETURNING j.id, j.tenant_id, j.kind, j.payload, j.attempts, j.max_attempts, j.status)
    SELECT r.id, r.tenant_id, r.kind::text, r.payload -> 'ids', r.attempts, r.max_attempts
    FROM reclaimed r WHERE r.status = 'failed';
END
$$""",
    "pending_object_writes(timestamp with time zone, integer)": """
CREATE FUNCTION pending_object_writes(p_now timestamptz, p_limit integer)
RETURNS TABLE (tenant_id uuid, intent_id uuid)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
#variable_conflict use_column
BEGIN
    IF p_now IS NULL OR p_limit IS NULL OR p_limit < 1 OR p_limit > 1000 THEN
        RAISE EXCEPTION 'invalid argument' USING ERRCODE = '22023';
    END IF;
    RETURN QUERY
    SELECT w.tenant_id, w.id FROM public.object_write_intents w WHERE w.next_attempt_at <= p_now
    ORDER BY w.next_attempt_at, w.created_at LIMIT p_limit;
END
$$""",
    "maintenance_candidates(timestamp with time zone, integer)": """
CREATE FUNCTION maintenance_candidates(p_now timestamptz, p_limit integer)
RETURNS TABLE (list text, tenant_id uuid, item_id uuid)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
#variable_conflict use_column
DECLARE
    v_cutoff timestamptz;
BEGIN
    IF p_now IS NULL OR p_limit IS NULL OR p_limit < 1 OR p_limit > 1000 THEN
        RAISE EXCEPTION 'invalid argument' USING ERRCODE = '22023';
    END IF;
    v_cutoff := p_now - make_interval(days => %(days)d);
    RETURN QUERY
    (SELECT 'project'::text, p.tenant_id, p.id FROM public.projects p
     WHERE p.deleted_at IS NULL AND (
         EXISTS (SELECT 1 FROM public.comparisons c WHERE c.project_id = p.id AND c.tenant_id = p.tenant_id
                 AND c.last_used_at <= v_cutoff)
         OR EXISTS (SELECT 1 FROM public.source_versions v WHERE v.project_id = p.id AND v.tenant_id = p.tenant_id
                    AND v.last_used_at <= v_cutoff
                    AND NOT EXISTS (SELECT 1 FROM public.comparisons l WHERE l.tenant_id = v.tenant_id
                                    AND l.last_used_at > v_cutoff AND (l.earlier_id = v.id OR l.later_id = v.id))))
     ORDER BY p.id LIMIT p_limit)
    UNION ALL
    (SELECT 'deletion'::text, d.tenant_id, d.project_id FROM public.project_deletions d
     WHERE d.status = 'pending' AND d.next_attempt_at <= p_now ORDER BY d.next_attempt_at LIMIT p_limit)
    UNION ALL
    (SELECT 'purge'::text, o.tenant_id, o.id FROM public.object_purge_intents o
     WHERE o.next_attempt_at <= p_now ORDER BY o.next_attempt_at LIMIT p_limit);
END
$$""" % {"days": RETENTION_DAYS},
}


def upgrade() -> None:
    op.execute(f"""
DO $$
BEGIN
    IF current_user <> '{OWNER}' THEN
        RAISE EXCEPTION 'run migrations as {OWNER} (python -m changelens.db bootstrap-roles first)';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP}') THEN
        RAISE EXCEPTION 'role {APP} is missing (python -m changelens.db bootstrap-roles)';
    END IF;
END
$$""")
    tenant = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"
    for table in TENANT_TABLES:
        op.execute(f"GRANT SELECT, INSERT, UPDATE, DELETE ON {table} TO {APP}")
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(f"CREATE POLICY {POLICY} ON {table} FOR ALL "
                   f"USING (tenant_id = {tenant}) WITH CHECK (tenant_id = {tenant})")
    op.execute(f"REVOKE ALL ON users FROM {APP}")
    op.execute("ALTER TABLE users ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE users FORCE ROW LEVEL SECURITY")
    op.execute(f"REVOKE ALL ON alembic_version FROM {APP}")
    for signature, body in FUNCTIONS.items():
        op.execute(body)
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {APP}")


def downgrade() -> None:
    for signature in FUNCTIONS:
        op.execute(f"DROP FUNCTION {signature}")
    op.execute("ALTER TABLE users NO FORCE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE users DISABLE ROW LEVEL SECURITY")
    for table in TENANT_TABLES:
        op.execute(f"DROP POLICY {POLICY} ON {table}")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
        op.execute(f"REVOKE ALL ON {table} FROM {APP}")
