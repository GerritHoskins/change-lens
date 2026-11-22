"""The landing page's early-bird list (docs/landing-page-handoff.md): `early_bird_signups`.

One row per address: the normalised address (trimmed, lower-cased; unique), the page language, `pending` or
`confirmed`, the SHA-256 of the single-use token in the confirmation link (never the token; cleared on
confirmation) and three times. An address on the list is not an account, so the table has no `tenant_id`:
like `rate_limit_counters` (0005), RLS is forced with no policy and the app role has no rights on it. It is
reached only through four functions:

- `early_bird_request` adds a pending row, or gives a pending row a new token (and a new pending period
  once the old one has run out). A confirmed address changes nothing. It returns whether a mail is due.
- `early_bird_mark_sent` records that the confirmation mail for a token was handed to the mail server.
- `early_bird_confirm` confirms once by the token's hash, within the pending period, and returns the
  row's language; null for an unknown, used or expired token.
- `early_bird_prune` deletes pending rows older than the pending period (run by maintenance).

No function returns an address, and none says whether an address is on the list beyond the mail-due flag
the api never passes on. The downgrade drops the table and with it every address on the list.

Revision ID: 0009_early_bird
Revises: 0008_consent_events
Create Date: 2026-11-22
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0009_early_bird"
down_revision: Union[str, Sequence[str], None] = "0008_consent_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APP = "changelens_app"
PRE_TENANT_TABLES = ("early_bird_signups",)
_HEADER = "LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$"
_INVALID = "RAISE EXCEPTION 'invalid argument' USING ERRCODE = '22023';"
_HASH_BAD = "(p_token_hash IS NULL OR p_token_hash !~ '^[0-9a-f]{64}$')"
_DAYS_BAD = "(p_pending_days IS NULL OR p_pending_days NOT BETWEEN 1 AND 365)"
_EXPIRED = "now() - make_interval(days => p_pending_days)"

FUNCTIONS = {
    "early_bird_request(text, text, text, integer)": f"""
CREATE FUNCTION early_bird_request(p_email text, p_locale text, p_token_hash text, p_pending_days integer)
RETURNS boolean
{_HEADER}
DECLARE
    v_id uuid;
BEGIN
    -- The api validates the address more strictly; this is the floor no caller can go below.
    IF p_email IS NULL OR length(p_email) NOT BETWEEN 3 AND 254 OR p_email <> lower(btrim(p_email))
       OR p_email !~ '^[^@[:space:][:cntrl:]]+@[^@[:space:][:cntrl:]]+$'
       OR p_locale IS NULL OR p_locale NOT IN ('en', 'de') OR {_HASH_BAD} OR {_DAYS_BAD} THEN
        {_INVALID}
    END IF;
    INSERT INTO public.early_bird_signups AS s (id, email, locale, status, token_hash)
        VALUES (gen_random_uuid(), p_email, p_locale, 'pending', p_token_hash)
        ON CONFLICT (email) DO UPDATE
            SET token_hash = EXCLUDED.token_hash, locale = EXCLUDED.locale,
                -- A pending row past its period that maintenance has not deleted yet starts again.
                created_at = CASE WHEN s.created_at < {_EXPIRED} THEN now() ELSE s.created_at END
            WHERE s.status = 'pending'
        RETURNING s.id INTO v_id;
    RETURN v_id IS NOT NULL;
END
$$""",
    "early_bird_mark_sent(text)": f"""
CREATE FUNCTION early_bird_mark_sent(p_token_hash text) RETURNS void
{_HEADER}
BEGIN
    IF {_HASH_BAD} THEN
        {_INVALID}
    END IF;
    UPDATE public.early_bird_signups SET confirmation_sent_at = now()
        WHERE token_hash = p_token_hash AND status = 'pending';
END
$$""",
    "early_bird_confirm(text, integer)": f"""
CREATE FUNCTION early_bird_confirm(p_token_hash text, p_pending_days integer) RETURNS text
{_HEADER}
DECLARE
    v_locale text;
BEGIN
    IF {_HASH_BAD} OR {_DAYS_BAD} THEN
        {_INVALID}
    END IF;
    -- Single use: the hash is cleared with the confirmation, so the same link matches nothing again.
    UPDATE public.early_bird_signups s SET status = 'confirmed', confirmed_at = now(), token_hash = NULL
        WHERE s.token_hash = p_token_hash AND s.status = 'pending' AND s.created_at >= {_EXPIRED}
        RETURNING s.locale::text INTO v_locale;
    RETURN v_locale;
END
$$""",
    "early_bird_prune(integer)": f"""
CREATE FUNCTION early_bird_prune(p_pending_days integer) RETURNS integer
{_HEADER}
DECLARE
    v_count integer;
BEGIN
    IF {_DAYS_BAD} THEN
        {_INVALID}
    END IF;
    DELETE FROM public.early_bird_signups WHERE status = 'pending' AND created_at < {_EXPIRED};
    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END
$$""",
}


def upgrade() -> None:
    op.create_table(
        "early_bird_signups",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("locale", sa.String(length=2), nullable=False),
        sa.Column("status", sa.String(length=10), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("confirmation_sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("locale IN ('en', 'de')", name="ck_early_bird_signups_locale"),
        sa.CheckConstraint("status IN ('pending', 'confirmed')", name="ck_early_bird_signups_status"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_early_bird_signups_email"),
    )
    op.create_index("ix_early_bird_signups_token_hash", "early_bird_signups", ["token_hash"], unique=True)
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
    op.drop_index("ix_early_bird_signups_token_hash", table_name="early_bird_signups")
    op.drop_table("early_bird_signups")
