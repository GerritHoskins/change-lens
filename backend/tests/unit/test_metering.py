"""Attempt reservations retain unknown charges and never credit another request."""
from decimal import Decimal

import pytest

from changelens.llm import FakeLlm, MeteredLlm
from changelens.llm.errors import LlmUnavailable
from changelens.metering import CeilingReached, CostMeter, money


def test_pending_attempt_counts_against_ceiling_until_usage_is_known():
    meter = CostMeter(Decimal("1"))
    first = meter.reserve(Decimal("0.6"))
    with pytest.raises(CeilingReached):
        meter.reserve(Decimal("0.5"))
    assert meter.actual == 0 and meter.total == Decimal("0.6")
    first.settle(Decimal("0.2"))
    second = meter.reserve(Decimal("0.8"))
    assert meter.total == Decimal("1")
    first.settle(Decimal("0.2"))  # duplicate settlement cannot release second's hold
    assert meter.total == Decimal("1") and meter.reserved == Decimal("0.8")
    second.settle(Decimal("0.3"))
    assert meter.actual == Decimal("0.5") and meter.reserved == 0 and meter.calls == 2


def test_small_charges_and_holds_are_rounded_up_never_discarded():
    meter = CostMeter(Decimal("0.0000000002"))
    first = meter.reserve(Decimal("0.00000000001"))
    first.settle(Decimal("0.00000000001"))
    meter.reserve(Decimal("0.00000000001"))
    with pytest.raises(CeilingReached):
        meter.reserve(Decimal("0.00000000001"))
    assert meter.total == Decimal("0.0000000002")


@pytest.mark.parametrize("invalid", [Decimal("-1"), Decimal("NaN"), Decimal("Infinity"), Decimal("-Infinity")])
def test_invalid_money_is_rejected_without_modifying_budget(invalid):
    with pytest.raises(ValueError):
        money(invalid)
    meter = CostMeter(Decimal("1"))
    with pytest.raises(ValueError):
        meter.reserve(invalid)
    ticket = meter.reserve(Decimal("0.1"))
    with pytest.raises(ValueError):
        ticket.settle(invalid)
    assert meter.total == Decimal("0.1") and meter.actual == 0


@pytest.mark.parametrize("error", [LlmUnavailable("timeout"), RuntimeError("interrupted")])
def test_single_attempt_adapter_unknown_failure_keeps_reservation(error):
    class Failing:
        def estimate_cost(self, schema, data):
            return Decimal("0.6")

        def structured(self, schema, system, data):
            raise error

    meter = CostMeter(Decimal("1"))
    with pytest.raises(type(error)):
        MeteredLlm(Failing(), meter).structured("FactList", "s", ["a"])
    assert meter.actual == 0 and meter.reserved == Decimal("0.6")
    with pytest.raises(CeilingReached):
        MeteredLlm(Failing(), meter).structured("FactList", "s", ["a"])


def test_final_successful_response_with_provider_overage_is_partial():
    from changelens.config import Limits
    from changelens.pipeline.parse import parse
    from changelens.pipeline.run import run_comparison

    class Underestimated(FakeLlm):
        def estimate_cost(self, schema, data):
            return Decimal("0.6") if schema == "Explanation" else Decimal("0")

    class Cache(dict):
        put = dict.__setitem__

    sides = [(text, parse(text.encode(), "text", Limits()), Cache()) for text in ("a", "b")]
    out = run_comparison(sides, "complete", Underestimated(Decimal("2")), Decimal("1"), "fake")
    assert out.cost == Decimal("2") and out.status == "partial"
    assert any(w["code"] == "cost_ceiling" and w.get("reason") == "reported_usage_exceeded_estimate"
               for w in out.warnings)
