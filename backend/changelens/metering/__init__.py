"""Per-comparison cost ceiling (AC-21). Allowance, spend cap and kill switch arrive with I-8/I-14."""
from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_CEILING
from typing import Callable, Protocol
import uuid


class CeilingReached(Exception):
    """Raised before an llm call that could take the run past its ceiling."""


def money(value: Decimal) -> Decimal:
    """Keep durable accounting finite, nonnegative and rounded up to storage precision."""
    try:
        amount = Decimal(value)
        if not amount.is_finite() or amount < 0:
            raise ValueError("invalid_cost")
        return amount.quantize(Decimal("0.0000000001"), rounding=ROUND_CEILING)
    except (InvalidOperation, TypeError):
        raise ValueError("invalid_cost") from None


class Reservation:
    """One attempt's hold; settlement is idempotent in the owning budget."""

    def __init__(self, settle: Callable[[Decimal], None]):
        self._settle = settle

    def settle(self, actual_eur: Decimal) -> None:
        self._settle(money(actual_eur))


class Budget(Protocol):
    calls: int

    @property
    def total(self) -> Decimal: ...

    def reserve(self, estimate_eur: Decimal) -> Reservation: ...


class CostMeter:
    def __init__(self, ceiling_eur: Decimal):
        self.ceiling = money(ceiling_eur)
        self.actual = Decimal("0")
        self._reservations: dict[uuid.UUID, Decimal] = {}
        self.calls = 0

    @property
    def reserved(self) -> Decimal:
        return sum(self._reservations.values(), Decimal("0"))

    @property
    def total(self) -> Decimal:
        return self.actual + self.reserved

    def check(self, estimate_eur: Decimal) -> None:
        """Called before every llm call; the call is never made if it could exceed the ceiling."""
        if self.total + money(estimate_eur) > self.ceiling:
            raise CeilingReached()

    def record(self, actual_eur: Decimal) -> None:
        """Record a known standalone charge (legacy callers); requests use reserve/settle."""
        self.actual += money(actual_eur)
        self.calls += 1

    def reserve(self, estimate_eur: Decimal) -> Reservation:
        estimate = money(estimate_eur)
        self.check(estimate)
        ticket = uuid.uuid4()
        self._reservations[ticket] = estimate
        self.calls += 1

        def settle(actual: Decimal) -> None:
            if ticket in self._reservations:
                del self._reservations[ticket]
                self.actual += actual

        return Reservation(settle)
