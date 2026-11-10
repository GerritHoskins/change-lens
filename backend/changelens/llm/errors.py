"""Errors raised by `llm` adapters. Messages are content-free: a reason code only (AC-23)."""
from __future__ import annotations

from decimal import Decimal


class LlmError(Exception):
    """Base class. Messages are content-free: a reason code only."""

    def __init__(self, reason: str, cost: Decimal | None = None):
        super().__init__(reason)
        self.reason = reason
        # An absent usage report is not evidence that a failed request was free.
        self.cost_known = cost is not None
        self.cost = cost if cost is not None else Decimal("0")


class LlmAuthError(LlmError):
    """401/403: the token is wrong or lacks access. Never retried."""


class LlmUnavailable(LlmError):
    """Timeout, transport failure, rate limit or a 5xx."""


class LlmOutputInvalid(LlmError):
    """Output was not valid JSON for the schema after the one retry."""
