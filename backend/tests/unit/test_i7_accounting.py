"""I-7 uses the same reservations as the worker, including unsuccessful model attempts."""
from decimal import Decimal

import pytest

from changelens.llm import MeteredLlm
from changelens.llm.errors import LlmUnavailable
from tools import i7_run as runner


@pytest.fixture
def pair(tmp_path, monkeypatch):
    (tmp_path / "old.txt").write_text("Earlier source", encoding="utf-8")
    (tmp_path / "new.txt").write_text("Newer source", encoding="utf-8")
    monkeypatch.setattr(runner, "CEILING", Decimal("0.20"))
    monkeypatch.setattr(runner.im, "score_comparison", lambda *_: {})
    monkeypatch.setattr(runner.im, "score_baseline", lambda *_: {})
    return tmp_path, {"id": "P-offline", "case_types": ["no_change"],
                      "old": {"format": "text", "storage_ref": "old.txt"},
                      "new": {"format": "text", "storage_ref": "new.txt"}}


@pytest.mark.parametrize("failed_cost,expected_actual,expected_reserved", [
    (None, 0.04, 0.05), (Decimal("0.02"), 0.06, 0),
])
def test_failure_keeps_prior_spend_and_unknown_hold(pair, monkeypatch, failed_cost, expected_actual, expected_reserved):
    class TwoAttempts:
        config_id = "offline-test"
        calls = 0

        def estimate_cost(self, *_):
            return Decimal("0.05")

        def structured(self, *_):
            self.calls += 1
            if self.calls == 1:
                return {}, Decimal("0.04")
            raise LlmUnavailable("timeout", failed_cost)

    def partial_pipeline(_sides, _scope, llm, ceiling, _config, *, meter):
        assert meter.ceiling == ceiling == Decimal("0.20")
        port = MeteredLlm(llm, meter)
        port.structured("first", "", ["synthetic"])
        port.structured("second", "", ["synthetic"])

    monkeypatch.setattr(runner, "run_comparison", partial_pipeline)
    row = runner.compare_pair(TwoAttempts(), *pair)
    assert row["status"] == "failed" and row["error"] == "timeout"
    assert row["cost_actual_eur"] == expected_actual
    assert row["cost_reserved_eur"] == expected_reserved
    assert row["cost_eur"] == pytest.approx(expected_actual + expected_reserved)


@pytest.mark.parametrize("estimate,timeout,expected_cost,expected_reserved,expected_calls", [
    ("0.21", False, 0, 0, 0),
    ("0.05", True, 0.05, 0.05, 1),
    ("0.05", False, 0.03, 0, 1),
])
def test_optional_baseline_is_metered_and_preserves_unknown_usage(pair, estimate, timeout,
                                                                expected_cost, expected_reserved, expected_calls):
    class Baseline:
        calls = 0

        def estimate_cost(self, *_):
            return Decimal(estimate)

        def structured(self, *_):
            self.calls += 1
            if timeout:
                raise LlmUnavailable("timeout")
            return {"findings": []}, Decimal("0.03")

    llm = Baseline()
    row = runner.baseline_pair(llm, *pair)
    assert row["cost_eur"] == expected_cost
    assert row["cost_reserved_eur"] == expected_reserved
    assert row["cost_actual_eur"] == pytest.approx(expected_cost - expected_reserved)
    assert llm.calls == expected_calls
    assert row["error"] == ("cost_ceiling" if expected_calls == 0 else "timeout" if timeout else None)
