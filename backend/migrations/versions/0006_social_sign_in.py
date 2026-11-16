"""Native Google and Apple sign-in (I-8 S4): the stored Apple token, parked tokens and pending links.

- `users.apple_refresh_token_enc`: the user's Apple refresh token, AES-GCM encrypted and bound to the user
  ID (`auth.apple_tokens`; AR-2). A tombstone holds none (`ck_users_tombstone_token`, AR-1).
- `apple_token_parks`: a token from a sign-in that has no user row yet (AR-5), encrypted and bound to the
  park ID, under the Logto subject it will attach to, or under no subject while a pending link holds it.
  It lives one hour; maintenance then revokes it with Apple and deletes it, keeping it until Apple
  confirms (AR-6).
- `pending_links`: `link_required` state (03a P1, O-19): provider, provider subject, the target Logto user
  and the parked token, for one hour, used once. No email.

Both tables are pre-tenant: no `tenant_id`, RLS forced with no policy and no rights for the app role,
like `rate_limit_counters`. The app role reaches them, and the token column, only through the SECURITY
DEFINER functions below. The account_* ones carry 0004's check (a pending deletion receipt and a
membership in the tenant set in `app.tenant_id`), so a request only ever touches its own account.

Revision ID: 0006_social_sign_in
Revises: 0005_limits
Create Date: 2026-11-16
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0006_social_sign_in"
down_revision: Union[str, Sequence[str], None] = "0005_limits"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APP = "changelens_app"
PRE_TENANT_TABLES = ("apple_token_parks", "pending_links")
TENANT = "NULLIF(current_setting('app.tenant_id', true), '')::uuid"
_OWN_PENDING = f"""
        EXISTS (SELECT 1 FROM public.account_deletions d WHERE d.user_id = p_user AND d.status = 'pending'
                AND d.tenant_id = {TENANT})
        AND EXISTS (SELECT 1 FROM public.memberships m WHERE m.user_id = p_user AND m.tenant_id = {TENANT})"""
_INVALID = "RAISE EXCEPTION 'invalid argument' USING ERRCODE = '22023';"
_SUBJECT_OK = "length(%s) BETWEEN 1 AND 200"
_TOKEN_OK = "length(%s) BETWEEN 1 AND 24000"

FUNCTIONS = {
    "apple_park_put(uuid, text, text, timestamp with time zone)": f"""
CREATE FUNCTION apple_park_put(p_id uuid, p_subject text, p_token text, p_expires timestamptz) RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
BEGIN
    IF p_id IS NULL OR (p_subject IS NOT NULL AND NOT {_SUBJECT_OK % "p_subject"})
       OR p_token IS NULL OR NOT {_TOKEN_OK % "p_token"}
       OR p_expires IS NULL OR p_expires <= now() OR p_expires > now() + interval '2 hours' THEN
        {_INVALID}
    END IF;
    INSERT INTO public.apple_token_parks (id, logto_subject, token_enc, expires_at, next_attempt_at, attempts)
        VALUES (p_id, p_subject, p_token, p_expires, p_expires, 0);
END
$$""",
    "apple_parks_for(text)": f"""
CREATE FUNCTION apple_parks_for(p_subject text) RETURNS TABLE (park_id uuid, token_enc text)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
#variable_conflict use_column
BEGIN
    IF p_subject IS NULL OR NOT {_SUBJECT_OK % "p_subject"} THEN
        {_INVALID}
    END IF;
    RETURN QUERY SELECT k.id, k.token_enc FROM public.apple_token_parks k
        WHERE k.logto_subject = p_subject AND k.expires_at > now() ORDER BY k.created_at DESC, k.id LIMIT 10;
END
$$""",
    "apple_park_attach(uuid, text, uuid, text)": f"""
CREATE FUNCTION apple_park_attach(p_user uuid, p_subject text, p_park uuid, p_token text) RETURNS boolean
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
BEGIN
    IF p_user IS NULL OR p_subject IS NULL OR p_park IS NULL OR p_token IS NULL OR NOT {_TOKEN_OK % "p_token"} THEN
        {_INVALID}
    END IF;
    -- The park must still be live and belong to this subject, or to no subject (a pending link's, which
    -- the caller has just completed for this subject); the user must be live and hold the subject.
    DELETE FROM public.apple_token_parks k WHERE k.id = p_park AND k.expires_at > now()
        AND (k.logto_subject = p_subject OR k.logto_subject IS NULL)
        AND EXISTS (SELECT 1 FROM public.users u WHERE u.id = p_user AND u.idp_subject = p_subject
                    AND u.deleted_at IS NULL);
    IF NOT FOUND THEN
        RETURN false;
    END IF;
    UPDATE public.users SET apple_refresh_token_enc = p_token WHERE id = p_user;
    -- Older parks of the same subject are superseded: maintenance revokes them now.
    UPDATE public.apple_token_parks SET expires_at = now(), next_attempt_at = now()
        WHERE logto_subject = p_subject AND expires_at > now();
    RETURN true;
END
$$""",
    "apple_park_expire(uuid)": """
CREATE FUNCTION apple_park_expire(p_park uuid) RETURNS void
LANGUAGE sql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
    UPDATE public.apple_token_parks SET expires_at = LEAST(expires_at, now()), next_attempt_at = now()
    WHERE id = p_park AND expires_at > now()
$$""",
    "apple_parks_due(timestamp with time zone, integer)": f"""
CREATE FUNCTION apple_parks_due(p_now timestamptz, p_limit integer)
RETURNS TABLE (park_id uuid, token_enc text, attempts integer)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
#variable_conflict use_column
BEGIN
    IF p_now IS NULL OR p_limit IS NULL OR p_limit < 1 OR p_limit > 1000 THEN
        {_INVALID}
    END IF;
    RETURN QUERY SELECT k.id, k.token_enc, k.attempts FROM public.apple_token_parks k
        WHERE k.expires_at <= p_now AND k.next_attempt_at <= p_now ORDER BY k.next_attempt_at LIMIT p_limit;
END
$$""",
    "apple_park_revoked(uuid)": """
CREATE FUNCTION apple_park_revoked(p_park uuid) RETURNS boolean
LANGUAGE sql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
    WITH gone AS (DELETE FROM public.apple_token_parks WHERE id = p_park AND expires_at <= now() RETURNING id)
    SELECT EXISTS (SELECT 1 FROM gone)
$$""",
    "apple_park_retry(uuid, timestamp with time zone)": f"""
CREATE FUNCTION apple_park_retry(p_park uuid, p_next timestamptz) RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
BEGIN
    IF p_park IS NULL OR p_next IS NULL OR p_next > now() + interval '2 days' THEN
        {_INVALID}
    END IF;
    UPDATE public.apple_token_parks SET attempts = attempts + 1, next_attempt_at = p_next
        WHERE id = p_park AND expires_at <= now();
END
$$""",
    "pending_link_put(uuid, text, text, text, uuid, timestamp with time zone)": f"""
CREATE FUNCTION pending_link_put(p_id uuid, p_provider text, p_provider_subject text, p_target text, p_park uuid,
                                 p_expires timestamptz) RETURNS void
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
BEGIN
    IF p_id IS NULL OR p_provider NOT IN ('google', 'apple') OR p_provider_subject IS NULL
       OR length(p_provider_subject) NOT BETWEEN 1 AND 255 OR p_target IS NULL OR NOT {_SUBJECT_OK % "p_target"}
       OR p_expires IS NULL OR p_expires <= now() OR p_expires > now() + interval '2 hours' THEN
        {_INVALID}
    END IF;
    INSERT INTO public.pending_links (id, provider, provider_subject, target_subject, park_id, expires_at)
        VALUES (p_id, p_provider, p_provider_subject, p_target, p_park, p_expires);
END
$$""",
    "pending_link_take(uuid)": """
CREATE FUNCTION pending_link_take(p_id uuid)
RETURNS TABLE (provider text, provider_subject text, target_subject text, park_id uuid, park_token text,
               expired boolean)
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
#variable_conflict use_column
BEGIN
    -- Single use: the row is gone whatever the caller decides next. The parked token comes with it while
    -- the park is live, so a completed link can attach it.
    RETURN QUERY
    WITH gone AS (
        DELETE FROM public.pending_links l WHERE l.id = p_id
        RETURNING l.provider, l.provider_subject, l.target_subject, l.park_id, l.expires_at)
    SELECT g.provider::text, g.provider_subject::text, g.target_subject::text, g.park_id, k.token_enc,
           g.expires_at <= now()
    FROM gone g LEFT JOIN public.apple_token_parks k ON k.id = g.park_id AND k.expires_at > now();
END
$$""",
    "pending_links_prune(timestamp with time zone)": f"""
CREATE FUNCTION pending_links_prune(p_now timestamptz) RETURNS integer
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE
    v_count integer;
BEGIN
    IF p_now IS NULL THEN
        {_INVALID}
    END IF;
    UPDATE public.apple_token_parks k SET expires_at = LEAST(k.expires_at, now()), next_attempt_at = now()
        WHERE k.id IN (SELECT l.park_id FROM public.pending_links l WHERE l.expires_at <= p_now)
        AND k.expires_at > now();
    DELETE FROM public.pending_links WHERE expires_at <= p_now;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END
$$""",
    "account_apple_token(uuid)": f"""
CREATE FUNCTION account_apple_token(p_user uuid) RETURNS text
LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
    SELECT u.apple_refresh_token_enc FROM public.users u
    WHERE u.id = p_user AND u.deleted_at IS NOT NULL AND {_OWN_PENDING}
$$""",
    "account_apple_token_clear(uuid, text)": f"""
CREATE FUNCTION account_apple_token_clear(p_user uuid, p_token text) RETURNS boolean
LANGUAGE sql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
    -- Clears only the token that was revoked; a token stored since then stays for the next attempt.
    WITH cleared AS (
        UPDATE public.users u SET apple_refresh_token_enc = NULL
        WHERE u.id = p_user AND u.deleted_at IS NOT NULL AND u.apple_refresh_token_enc = p_token AND {_OWN_PENDING}
        RETURNING u.id)
    SELECT EXISTS (SELECT 1 FROM cleared)
$$""",
    "account_social_cleanup(uuid)": f"""
CREATE FUNCTION account_social_cleanup(p_user uuid) RETURNS integer
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE
    v_subject text;
    v_count integer;
BEGIN
    SELECT u.idp_subject INTO v_subject FROM public.users u
        WHERE u.id = p_user AND u.deleted_at IS NOT NULL AND {_OWN_PENDING};
    IF v_subject IS NULL THEN
        RETURN 0;
    END IF;
    -- Parks are revoked with Apple by maintenance before they are deleted (AR-6), so expire them now.
    UPDATE public.apple_token_parks k SET expires_at = LEAST(k.expires_at, now()), next_attempt_at = now()
        WHERE (k.logto_subject = v_subject
               OR k.id IN (SELECT l.park_id FROM public.pending_links l WHERE l.target_subject = v_subject))
        AND k.expires_at > now();
    DELETE FROM public.pending_links WHERE target_subject = v_subject;
    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END
$$""",
}


def upgrade() -> None:
    op.add_column("users", sa.Column("apple_refresh_token_enc", sa.Text(), nullable=True))
    op.create_check_constraint("ck_users_tombstone_token", "users",
                               "idp_subject IS NOT NULL OR apple_refresh_token_enc IS NULL")
    op.create_table(
        "apple_token_parks",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("logto_subject", sa.String(length=200), nullable=True),
        sa.Column("token_enc", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_apple_token_parks_logto_subject", "apple_token_parks", ["logto_subject"])
    op.create_index("ix_apple_token_parks_next_attempt_at", "apple_token_parks", ["next_attempt_at"])
    op.create_table(
        "pending_links",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("provider", sa.String(length=10), nullable=False),
        sa.Column("provider_subject", sa.String(length=255), nullable=False),
        sa.Column("target_subject", sa.String(length=200), nullable=False),
        sa.Column("park_id", sa.UUID(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint("provider IN ('google', 'apple')", name="ck_pending_links_provider"),
        sa.ForeignKeyConstraint(["park_id"], ["apple_token_parks.id"], name="fk_pending_links_park",
                                ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_pending_links_target_subject", "pending_links", ["target_subject"])
    for table in PRE_TENANT_TABLES:
        op.execute(f"REVOKE ALL ON {table} FROM {APP}")
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    for signature, body in FUNCTIONS.items():
        op.execute(body)
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {APP}")


def downgrade() -> None:
    for signature in FUNCTIONS:
        op.execute(f"DROP FUNCTION {signature}")
    op.drop_table("pending_links")
    op.drop_table("apple_token_parks")
    op.drop_constraint("ck_users_tombstone_token", "users", type_="check")
    op.drop_column("users", "apple_refresh_token_enc")
