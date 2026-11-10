"""The `llm` port (AD-9) and a fake adapter for I-22.

The port is one structured-output call: a schema name, a system prompt and delimited data blocks.
No tools, no URL fetching, and prompts or responses are never logged (AC-18, AC-23). The IONOS
AI Model Hub adapter is `changelens.llm.ionos` (D-17); the worker uses it when
`CHANGELENS_LLM=ionos` (I-2) and the fake otherwise.
"""
from __future__ import annotations

import re
from decimal import Decimal
from typing import Protocol, Sequence

from changelens.llm.errors import LlmError
from changelens.metering import Budget


class LlmPort(Protocol):
    """Single-attempt port; adapters with retries also implement structured_metered."""
    def estimate_cost(self, schema: str, data: Sequence[str]) -> Decimal: ...

    def structured(self, schema: str, system: str, data: Sequence[str]) -> tuple[dict, Decimal]:
        """Return (validated output, actual cost in EUR)."""
        ...


_LINE = re.compile(r"^\[(\d+)\] (.+)$", re.M)


def _fake_fact(n: int, line: str) -> dict:
    """One fact per numbered line: "Budget: EUR 12,000" -> subject "Budget", value "EUR 12,000"."""
    subject, sep, value = line.partition(":")
    return {"type": "deliverable", "subject": subject.strip(), "value": (value if sep else line).strip(),
            "block": n, "quote": line.strip(), "ambiguity": None, "confidence": "high"}


class FakeLlm:
    """Deterministic stand-in: costs a configurable fixed amount per Explanation call, answers the
    other schemas for free (so the I-22 ceiling arithmetic only counts explanations): one fact per
    line, no alignment proposals and no same-meaning verdicts (each such pair is then a change).
"""

    config_id = "fake-llm-0"

    def __init__(self, cost_per_call_eur: Decimal):
        self.cost = Decimal(cost_per_call_eur)
        self.calls = 0

    def estimate_cost(self, schema: str, data: Sequence[str]) -> Decimal:
        return self.cost if schema == "Explanation" else Decimal("0")

    def structured(self, schema: str, system: str, data: Sequence[str]) -> tuple[dict, Decimal]:
        self.calls += 1
        if schema == "Explanation":
            return {"explanation": "Placeholder explanation (fake llm); no model was called."}, self.cost
        if schema == "FactList":
            return {"facts": [_fake_fact(int(n), s) for n, s in _LINE.findall(data[0]) if s.strip()]}, Decimal("0")
        if schema == "FactMatches":
            return {"matches": []}, Decimal("0")
        if schema == "SameMeaning":
            return {"verdicts": []}, Decimal("0")
        raise ValueError("unknown schema")


class MeteredLlm:
    """Wraps a port so every call is checked against the meter first (03 §9.1 `worker` must-not)."""

    def __init__(self, port: LlmPort, meter: Budget):
        self.port = port
        self.meter = meter

    def structured(self, schema: str, system: str, data: Sequence[str]) -> dict:
        metered = getattr(self.port, "structured_metered", None)
        if metered is not None:
            # The adapter owns its retry loop and reserves each HTTP attempt separately.
            return metered(schema, system, data, self.meter)[0]
        reservation = self.meter.reserve(self.port.estimate_cost(schema, data))
        try:
            out, cost = self.port.structured(schema, system, data)
        except LlmError as e:  # failed calls still cost money and count (SA-4)
            if e.cost_known:
                reservation.settle(e.cost)
            raise
        reservation.settle(cost)
        return out
