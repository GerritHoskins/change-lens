"""The `llm` port (AD-9) and a fake adapter for I-22.

The port is one structured-output call: a schema name, a system prompt and delimited data blocks.
No tools, no URL fetching, and prompts or responses are never logged (AC-18, AC-23). The real
provider adapter arrives with D-17/I-2.
"""
from __future__ import annotations

from decimal import Decimal
from typing import Protocol, Sequence

from changelens.metering import CostMeter


class LlmPort(Protocol):
    def estimate_cost(self, schema: str, data: Sequence[str]) -> Decimal: ...

    def structured(self, schema: str, system: str, data: Sequence[str]) -> tuple[dict, Decimal]:
        """Return (validated output, actual cost in EUR)."""
        ...


class FakeLlm:
    """Deterministic stand-in: costs a configurable fixed amount per call and returns template output."""

    def __init__(self, cost_per_call_eur: Decimal):
        self.cost = Decimal(cost_per_call_eur)
        self.calls = 0

    def estimate_cost(self, schema: str, data: Sequence[str]) -> Decimal:
        return self.cost

    def structured(self, schema: str, system: str, data: Sequence[str]) -> tuple[dict, Decimal]:
        self.calls += 1
        if schema == "Explanation":
            return {"explanation": "Placeholder explanation (fake llm); no model was called."}, self.cost
        raise ValueError("unknown schema")


class MeteredLlm:
    """Wraps a port so every call is checked against the meter first (03 §9.1 `worker` must-not)."""

    def __init__(self, port: LlmPort, meter: CostMeter):
        self.port = port
        self.meter = meter

    def structured(self, schema: str, system: str, data: Sequence[str]) -> dict:
        self.meter.check(self.port.estimate_cost(schema, data))
        out, cost = self.port.structured(schema, system, data)
        self.meter.record(cost)
        return out
