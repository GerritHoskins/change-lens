"""Per-comparison cost ceiling (AC-21). Allowance, spend cap and kill switch arrive with I-8/I-14."""
from __future__ import annotations

from decimal import Decimal


class CeilingReached(Exception):
    """Raised before an llm call that could take the run past its ceiling."""


class CostMeter:
    def __init__(self, ceiling_eur: Decimal):
        self.ceiling = Decimal(ceiling_eur)
        self.total = Decimal("0")
        self.calls = 0

    def check(self, estimate_eur: Decimal) -> None:
        """Called before every llm call; the call is never made if it could exceed the ceiling."""
        if self.total + Decimal(estimate_eur) > self.ceiling:
            raise CeilingReached()

    def record(self, actual_eur: Decimal) -> None:
        self.total += Decimal(actual_eur)
        self.calls += 1
