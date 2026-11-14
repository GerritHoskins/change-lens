"""Monthly spend caps (03 §6 Abuse and cost exhaustion, SA-4, CR-2; I-8 S6).

Month-to-date spend is every comparison's actual cost plus its open reservations, counted from the
comparison rows and their cost tombstones, so failed runs and deleted projects still count. A tombstone
carries its comparison's creation time. Months are calendar months in UTC.

- Comparison creation (03a P4) rejects with `spend_cap_reached` when the tenant's or the global cap is
  reached; the fair-use allowance (I-14) will be checked next to it.
- The worker checks both again before each paid stage (`DbCostMeter`); a run that hits one stops like a
  ceiling stop and ends `failed` with the warning `spend_cap_reached`.
Reaching the global cap is logged once per month per process, as an event code only.
"""
from __future__ import annotations

import logging
import threading
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional

from sqlalchemy import text

log = logging.getLogger("changelens.spend")

TENANT_SPEND = text("""
    SELECT COALESCE(sum(amount), 0) FROM (
        SELECT COALESCE(c.cost_actual, 0)
               + COALESCE((SELECT sum(r.value::numeric) FROM jsonb_each_text(c.cost_reservations) r), 0) AS amount
        FROM comparisons c WHERE c.created_at >= :since AND c.tenant_id = :tenant
        UNION ALL
        SELECT t.cost_actual
               + COALESCE((SELECT sum(r.value::numeric) FROM jsonb_each_text(t.cost_reservations) r), 0)
        FROM comparison_cost_tombstones t WHERE t.created_at >= :since AND t.tenant_id = :tenant) spend""")

_logged_months: set = set()
_lock = threading.Lock()


def month_start(now: Optional[datetime] = None) -> datetime:
    now = (now or datetime.now(timezone.utc)).astimezone(timezone.utc)
    return datetime(now.year, now.month, 1, tzinfo=timezone.utc)


def tenant_spend(session, tenant_id: uuid.UUID, since: datetime) -> Decimal:
    return Decimal(session.execute(TENANT_SPEND, {"since": since, "tenant": tenant_id}).scalar_one())


def global_spend(session, since: datetime) -> Decimal:
    """All tenants' spend, through the `global_spend_since` function: one number, no IDs."""
    return Decimal(session.execute(text("SELECT global_spend_since(:since)"), {"since": since}).scalar_one())


def cap_reached(repo, settings, now: Optional[datetime] = None) -> Optional[str]:
    """'tenant', 'global' or None. `repo` is a TenantRepo; both sums run in its transaction, so the check
    never takes a second pooled connection."""
    since = month_start(now)
    if repo.month_spend(since) >= settings.tenant_monthly_spend_cap_eur:
        return "tenant"
    if repo.global_month_spend(since) >= settings.global_monthly_spend_cap_eur:
        with _lock:
            first = since not in _logged_months
            _logged_months.add(since)
        if first:
            log.warning("global spend cap reached: global_spend_cap_reached")  # owner alert hook (S7)
        return "global"
    return None
