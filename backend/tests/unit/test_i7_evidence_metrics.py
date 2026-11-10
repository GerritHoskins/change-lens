"""Sparse or failed evaluations cannot be reported as passing quality evidence."""
import pytest

from tools import i7_metrics as im, release_gate


def row():
    return {"id": "synthetic", "status": "complete", "error": None, "words": 100,
            "case_types": ["partial_update", "no_change"],
            "withheld": 0, "cost_eur": 0.01, "latency_s": 1, "signature": "synthetic",
            "score": {"tp": 1, "pred": 1, "gold": 1, "material_tp": 1, "material_gold": 1,
                      "type_agree": 1, "scope_pair": 1, "false_removals": 0, "located": 2,
                      "locatable": 2, "unsupported": 0, "shown": 1, "fabricated": 0}}


def test_empty_evaluation_has_no_measured_accuracy_and_fails():
    result = im.summarise([])
    assert result["verdict"] == "FAIL"
    for metric in ("precision", "recall", "material_recall", "evidence_location", "unsupported_rate"):
        assert result[metric] is None and result["gates"][metric]["pass"] is None
    assert not result["gates"]["evaluated_comparisons"]["pass"]


def test_negative_only_diagnostic_is_not_positive_quality_coverage():
    negative = row()
    negative["score"] = {key: 0 for key in negative["score"]}
    result = im.summarise([negative])
    assert result["fabricated_scope_changes"] == 0
    assert result["recall"] is None and result["precision_ci"] == [None, None]
    assert result["verdict"] == "FAIL"


@pytest.mark.parametrize("status,error", [("failed", None), ("failed", "timeout"), ("complete", "timeout")])
def test_failed_run_cannot_pass_even_with_perfect_scores(status, error):
    candidate = row() | {"status": status, "error": error}
    result = im.summarise([candidate])
    assert result["precision"] == 1
    assert result["verdict"] == "FAIL"
    assert result["gates"]["no_failed_comparisons"]["value"] == 1


def test_cost_holds_are_kept_distinct_from_known_usage():
    candidate = row() | {"cost_eur": 0.11, "cost_actual_eur": 0.03, "cost_reserved_eur": 0.08}
    result = im.summarise([candidate])
    assert result["cost_eur_total"] == 0.11
    assert result["cost_actual_eur_total"] == 0.03
    assert result["cost_reserved_eur_total"] == 0.08
    assert result["verdict"] == "PASS"


def test_release_gate_rejects_failed_runs_even_with_valid_total():
    result = im.summarise([row()])
    result.update(runs=1, no_change_pairs=1)
    result["status"] = {"complete": 0, "partial": 0, "failed": 1}
    assert "failed comparisons cannot establish release quality" in release_gate.quality_errors(result)


def test_untested_scope_and_negative_cases_cannot_establish_quality():
    candidate = row()
    candidate["case_types"] = ["value_change"]
    candidate["score"]["scope_pair"] = 0
    result = im.summarise([candidate])
    assert result["verdict"] == "FAIL"
    assert not result["gates"]["scope_coverage"]["pass"]
    assert not result["gates"]["no_change_coverage"]["pass"]
