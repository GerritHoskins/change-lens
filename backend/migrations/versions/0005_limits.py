"""Cost and abuse limits (I-8 S6): rate-limit counters and the global spend function.

`rate_limit_counters` holds fixed-window counts keyed by an HMAC of the account or IP (never the raw
value), so several api processes share them. It has no `tenant_id`: RLS is forced with no policy and the
app role has no rights on it, so it is reached only through `rate_limit_hit` (count one request) and
`rate_limit_prune` (drop windows older than three days; run by maintenance).

`global_spend_since(since)` returns one number: month-to-date model spend across all tenants (actual
costs plus open reservations of comparisons and their cost tombstones), for the global kill switch.

Revision ID: 0005_limits
Revises: 0004_account_deletion
Create Date: 2026-11-14
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

revision: str = "0005_limits"
down_revision: Union[str, Sequence[str], None] = "0004_account_deletion"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

APP = "changelens_app"
COUNTER_DAYS = 3  # counters older than this are pruned (data inventory)

# Actual cost plus open reservations, per comparison row or cost tombstone created since a time.
SPEND = """
    SELECT COALESCE(sum(amount), 0) FROM (
        SELECT COALESCE(c.cost_actual, 0)
               + COALESCE((SELECT sum(r.value::numeric) FROM jsonb_each_text(c.cost_reservations) r), 0) AS amount
        FROM public.comparisons c WHERE c.created_at >= p_since %(tenant_c)s
        UNION ALL
        SELECT t.cost_actual
               + COALESCE((SELECT sum(r.value::numeric) FROM jsonb_each_text(t.cost_reservations) r), 0)
        FROM public.comparison_cost_tombstones t WHERE t.created_at >= p_since %(tenant_t)s) spend"""

FUNCTIONS = {
    "rate_limit_hit(text, timestamp with time zone)": """
CREATE FUNCTION rate_limit_hit(p_key text, p_window_start timestamptz) RETURNS integer
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE
    v_hits integer;
BEGIN
    IF p_key IS NULL OR p_key !~ '^[0-9a-f]{64}$' OR p_window_start IS NULL
       OR p_window_start < now() - interval '2 days' OR p_window_start > now() + interval '1 minute' THEN
        RAISE EXCEPTION 'invalid argument' USING ERRCODE = '22023';
    END IF;
    INSERT INTO public.rate_limit_counters AS c (key_hash, window_start, hits) VALUES (p_key, p_window_start, 1)
        ON CONFLICT (key_hash, window_start) DO UPDATE SET hits = c.hits + 1
        RETURNING c.hits INTO v_hits;
    RETURN v_hits;
END
$$""",
    "rate_limit_prune()": """
CREATE FUNCTION rate_limit_prune() RETURNS integer
LANGUAGE plpgsql VOLATILE SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE
    v_count integer;
BEGIN
    DELETE FROM public.rate_limit_counters WHERE window_start < now() - make_interval(days => %(days)d);
    GET DIAGNOSTICS v_count = ROW_COUNT;
    RETURN v_count;
END
$$""" % {"days": COUNTER_DAYS},
    "global_spend_since(timestamp with time zone)": """
CREATE FUNCTION global_spend_since(p_since timestamptz) RETURNS numeric
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path = pg_catalog, pg_temp AS $$
DECLARE
    v_total numeric;
BEGIN
    IF p_since IS NULL THEN
        RAISE EXCEPTION 'invalid argument' USING ERRCODE = '22023';
    END IF;
    %(spend)s INTO v_total;
    RETURN v_total;
END
$$""" % {"spend": SPEND % {"tenant_c": "", "tenant_t": ""}},
}


def upgrade() -> None:
    op.create_table(
        "rate_limit_counters",
        sa.Column("key_hash", sa.String(length=64), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("hits", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("key_hash", "window_start"),
    )
    op.execute("ALTER TABLE rate_limit_counters ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE rate_limit_counters FORCE ROW LEVEL SECURITY")
    op.execute(f"REVOKE ALL ON rate_limit_counters FROM {APP}")
    for signature, body in FUNCTIONS.items():
        op.execute(body)
        op.execute(f"REVOKE ALL ON FUNCTION {signature} FROM PUBLIC")
        op.execute(f"GRANT EXECUTE ON FUNCTION {signature} TO {APP}")


def downgrade() -> None:
    for signature in FUNCTIONS:
        op.execute(f"DROP FUNCTION {signature}")
    op.drop_table("rate_limit_counters")
