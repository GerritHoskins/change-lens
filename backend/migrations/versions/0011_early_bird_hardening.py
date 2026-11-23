"""Early-bird list hardening (security review of 2026-11-22, docs/security-review.md EB-1 to EB-13).

Four columns on `early_bird_signups` and new bodies for the four functions of 0009:

- The pending period is fixed here (`PENDING_DAYS`), no longer an argument: the app role can't choose it.
  `early_bird_pending_days()` returns it, so a test can hold it against the constant the mail text uses
  (`changelens.mail.confirmation.PENDING_DAYS`).
- A new link token is stored as the row's *next* token (`next_token_hash`, `next_token_issued_at`).
  `early_bird_mark_sent` promotes it once its mail was handed to the mail server; until then the link
  mailed before keeps working. Both tokens confirm.
- A token's lifetime runs from when it was issued (`token_issued_at`), not from the row's `created_at`, and
  a pending row is pruned by the newer of the two, so "deleted after N days" in the last mail is true.
- `mail_count` counts the mails requested for a pending row; `early_bird_request` stops issuing tokens at
  `p_max_mails`. A row past its period starts again at one.

`early_bird_unsubscribe` (0010) is unchanged. The downgrade restores 0009's functions and drops the columns.

Revision ID: 0011_early_bird_hardening
Revises: 0010_early_bird_unsubscribe
Create Date: 2026-11-22
"""
import importlib.util
from pathlib import Path
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0011_early_bird_hardening"
down_revision: Union[str, Sequence[str], None] = "0010_early_bird_unsubscribe"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APP = "changelens_app"
PENDING_DAYS = 7  # = changelens.mail.confirmation.PENDING_DAYS (tests hold the two together)
REPLACED = ("early_bird_request(text, text, text, integer)", "early_bird_mark_sent(text)",
            "early_bird_confirm(text, integer)", "early_bird_prune(integer)")
_HEADER = "LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$"
_INVALID = "RAISE EXCEPTION 'invalid argument' USING ERRCODE = '22023';"
_HASH_BAD = "(p_token_hash IS NULL OR p_token_hash !~ '^[0-9a-f]{64}$')"
_CUTOFF = f"now() - make_interval(days => {PENDING_DAYS})"
# A pending row's period runs from its creation or from the newest link that was mailed, whichever is later.
_ROW_EXPIRED = f"GREATEST(s.created_at, COALESCE(s.token_issued_at, s.created_at)) < {_CUTOFF}"

FUNCTIONS = {
    "early_bird_pending_days()": f"""
CREATE FUNCTION early_bird_pending_days() RETURNS integer
{_HEADER}
BEGIN
    RETURN {PENDING_DAYS};
END
$$""",
    "early_bird_request(text, text, text, integer)": f"""
CREATE FUNCTION early_bird_request(p_email text, p_locale text, p_token_hash text, p_max_mails integer)
RETURNS boolean
{_HEADER}
DECLARE
    v_id uuid;
BEGIN
    -- The api validates the address more strictly; this is the floor no caller can go below.
    IF p_email IS NULL OR length(p_email) NOT BETWEEN 3 AND 254 OR p_email <> lower(btrim(p_email))
       OR p_email !~ '^[^@[:space:][:cntrl:]]+@[^@[:space:][:cntrl:]]+$'
       OR p_locale IS NULL OR p_locale NOT IN ('en', 'de') OR {_HASH_BAD}
       OR p_max_mails IS NULL OR p_max_mails NOT BETWEEN 1 AND 100 THEN
        {_INVALID}
    END IF;
    INSERT INTO public.early_bird_signups AS s
            (id, email, locale, status, next_token_hash, next_token_issued_at, mail_count)
        VALUES (gen_random_uuid(), p_email, p_locale, 'pending', p_token_hash, now(), 1)
        ON CONFLICT (email) DO UPDATE
            SET locale = EXCLUDED.locale,
                next_token_hash = EXCLUDED.next_token_hash, next_token_issued_at = now(),
                -- A pending row past its period that maintenance has not deleted yet starts again.
                created_at = CASE WHEN {_ROW_EXPIRED} THEN now() ELSE s.created_at END,
                token_hash = CASE WHEN {_ROW_EXPIRED} THEN NULL ELSE s.token_hash END,
                token_issued_at = CASE WHEN {_ROW_EXPIRED} THEN NULL ELSE s.token_issued_at END,
                confirmation_sent_at = CASE WHEN {_ROW_EXPIRED} THEN NULL ELSE s.confirmation_sent_at END,
                mail_count = CASE WHEN {_ROW_EXPIRED} THEN 1 ELSE s.mail_count + 1 END
            -- A confirmed address changes nothing; a pending row gets at most p_max_mails mails.
            WHERE s.status = 'pending' AND (({_ROW_EXPIRED}) OR s.mail_count < p_max_mails)
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
    -- The mail with this token is out: it becomes the row's link, and the one mailed before it ends here.
    UPDATE public.early_bird_signups s
        SET confirmation_sent_at = now(),
            token_hash = p_token_hash,
            token_issued_at = CASE WHEN s.next_token_hash = p_token_hash THEN s.next_token_issued_at
                                   ELSE s.token_issued_at END,
            next_token_hash = CASE WHEN s.next_token_hash = p_token_hash THEN NULL ELSE s.next_token_hash END,
            next_token_issued_at = CASE WHEN s.next_token_hash = p_token_hash THEN NULL
                                        ELSE s.next_token_issued_at END
        WHERE s.status = 'pending' AND (s.next_token_hash = p_token_hash OR s.token_hash = p_token_hash);
END
$$""",
    "early_bird_confirm(text)": f"""
CREATE FUNCTION early_bird_confirm(p_token_hash text) RETURNS text
{_HEADER}
DECLARE
    v_locale text;
BEGIN
    IF {_HASH_BAD} THEN
        {_INVALID}
    END IF;
    -- Single use: both hashes are cleared with the confirmation, so no link matches anything again. Each
    -- token lives for the period from when it was issued.
    UPDATE public.early_bird_signups s
        SET status = 'confirmed', confirmed_at = now(), token_hash = NULL, token_issued_at = NULL,
            next_token_hash = NULL, next_token_issued_at = NULL
        WHERE s.status = 'pending'
          AND ((s.token_hash = p_token_hash AND s.token_issued_at >= {_CUTOFF})
               OR (s.next_token_hash = p_token_hash AND s.next_token_issued_at >= {_CUTOFF}))
        RETURNING s.locale::text INTO v_locale;
    RETURN v_locale;
END
$$""",
    "early_bird_prune()": f"""
CREATE FUNCTION early_bird_prune() RETURNS integer
{_HEADER}
DECLARE
    v_count integer;
BEGIN
    DELETE FROM public.early_bird_signups s WHERE s.status = 'pending' AND {_ROW_EXPIRED};
    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END
$$""",
}


def _grant(signature: str) -> None:
    op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
    op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {APP}")


def upgrade() -> None:
    for signature in REPLACED:
        op.execute(f"DROP FUNCTION {signature}")
    op.add_column("early_bird_signups", sa.Column("token_issued_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("early_bird_signups", sa.Column("next_token_hash", sa.String(length=64), nullable=True))
    op.add_column("early_bird_signups", sa.Column("next_token_issued_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("early_bird_signups", sa.Column("mail_count", sa.Integer(), server_default=sa.text("0"),
                                                  nullable=False))
    op.create_index("ix_early_bird_signups_next_token_hash", "early_bird_signups", ["next_token_hash"], unique=True)
    # Links already mailed keep their lifetime: issued when the row was created, one mail so far.
    op.execute("UPDATE early_bird_signups SET token_issued_at = created_at, mail_count = 1 "
               "WHERE status = 'pending' AND token_hash IS NOT NULL")
    for signature, body in FUNCTIONS.items():
        op.execute(body)
        _grant(signature)


def downgrade() -> None:
    for signature in FUNCTIONS:
        op.execute(f"DROP FUNCTION {signature}")
    # A next token nobody promoted has no place in 0009's table: its link ends with the downgrade.
    op.drop_index("ix_early_bird_signups_next_token_hash", table_name="early_bird_signups")
    for column in ("mail_count", "next_token_issued_at", "next_token_hash", "token_issued_at"):
        op.drop_column("early_bird_signups", column)
    spec = importlib.util.spec_from_file_location("early_bird_0009", Path(__file__).with_name("0009_early_bird.py"))
    before = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(before)
    for signature, body in before.FUNCTIONS.items():
        op.execute(body)
        _grant(signature)
