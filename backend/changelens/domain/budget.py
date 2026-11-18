"""Durable comparison budgets. A committed reservation always precedes a model request.

Unknown outcomes keep their reservation: retries and another worker share the remaining
budget instead of treating an interrupted request as free. Only its ticket can settle a hold.
"""
from __future__ import annotations

import uuid
from decimal import Decimal

from changelens.domain import Database
from changelens.metering import CeilingReached, Reservation, money


class DbCostMeter:
    def __init__(self, db: Database, tenant_id: uuid.UUID, comparison_id: uuid.UUID, settings=None):
        self.db, self.tenant_id, self.comparison_id = db, tenant_id, comparison_id
        self.calls = 0
        self.settings = settings  # with settings, the monthly spend caps are checked before each reservation
        self.spend_cap: str | None = None  # 'tenant' or 'global' once a cap stopped the run (I-8 S6)

    @staticmethod
    def _amounts(comparison) -> tuple[Decimal, Decimal]:
        actual = money(comparison.cost_actual if comparison.cost_actual is not None else 0)
        reserved = sum((money(value) for value in comparison.cost_reservations.values()), Decimal("0"))
        return actual, reserved

    def _read(self) -> tuple[Decimal, Decimal]:
        with self.db.tenant_scope(self.tenant_id) as repo:
            comparison = repo.comparison_ledger(self.comparison_id)
            if comparison is None:
                comparison = repo.comparison_cost_tombstone(self.comparison_id)
            if comparison is None:
                raise CeilingReached()
            return self._amounts(comparison)

    @property
    def actual(self) -> Decimal:
        return self._read()[0]

    @property
    def reserved(self) -> Decimal:
        return self._read()[1]

    @property
    def total(self) -> Decimal:
        actual, reserved = self._read()
        return actual + reserved

    def reserve(self, estimate_eur: Decimal) -> Reservation:
        estimate = money(estimate_eur)
        ticket = str(uuid.uuid4())
        with self.db.tenant_scope(self.tenant_id) as repo:
            comparison = repo.comparison(self.comparison_id, lock=True)
            if comparison is None or comparison.status not in ("queued", "running"):
                raise CeilingReached()
            if self.settings is not None:
                from changelens.domain.spend import cap_reached
                # Spend is booked to the month the comparison was created in. A run that starts after
                # the month has turned is also held to that month's caps, or its cost would count
                # against no cap at all (review ledger LR-2).
                self.spend_cap = (cap_reached(repo, self.settings)
                                  or cap_reached(repo, self.settings, now=comparison.created_at))
                if self.spend_cap is not None:
                    raise CeilingReached()  # stops like the ceiling; the worker marks the run failed
            actual, reserved = self._amounts(comparison)
            if actual + reserved + estimate > money(comparison.cost_ceiling):
                raise CeilingReached()
            comparison.cost_actual = actual
            comparison.cost_reservations = {**comparison.cost_reservations, ticket: str(estimate)}
        # The transaction has committed before the caller can send a request.
        self.calls += 1
        return Reservation(lambda actual_eur: self._settle(ticket, actual_eur))

    def _settle(self, ticket: str, actual_eur: Decimal) -> None:
        actual = money(actual_eur)
        with self.db.tenant_scope(self.tenant_id) as repo:
            comparison = repo.comparison_ledger(self.comparison_id, lock=True)
            if comparison is None:
                comparison = repo.comparison_cost_tombstone(self.comparison_id, lock=True)
            if comparison is None or ticket not in comparison.cost_reservations:
                return  # already settled (including an uncertain commit), or deleted
            holds = dict(comparison.cost_reservations)
            del holds[ticket]
            known, _ = self._amounts(comparison)
            comparison.cost_actual = known + actual
            comparison.cost_reservations = holds
            # A late response can settle after completion. Never clamp real usage to the
            # reservation: if a provider exceeds its estimate, subsequent calls must stop.
