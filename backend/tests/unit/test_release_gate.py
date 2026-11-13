"""Offline release enforcement: forged PASS flags cannot replace valid held-out evidence."""
from copy import deepcopy
import json

import pytest

from tools import i7_metrics as im, release_gate as gate


@pytest.fixture
def evidence():
    # Synthetic passing aggregates based on the receipt shape, never a replacement receipt.
    receipt = json.loads(gate.RECEIPT.read_text(encoding="utf-8"))
    held_out = receipt["pairs"] + receipt["skipped_image_pairs"]
    split = {"development": ["P-900"], "held_out": [f"P-{n}" for n in range(1000, 1000 + held_out)]}
    receipt.update(no_change_pairs=8, split_fingerprint=gate.split_fingerprint(split),
                   fabricated_scope_changes=0, verdict="PASS", fingerprint=im.fingerprint(gate.MODEL))
    receipt["gates"]["fabricated_scope_changes"] = im.check("fabricated_scope_changes", 0)
    return receipt, split


def test_measured_gates_pass_with_explicitly_unmeasured_heavy_bucket(evidence):
    assert gate.release_errors(*evidence) == []


def test_current_failed_receipt_is_blocked_without_changing_it(capsys):
    original = gate.RECEIPT.read_bytes()
    fabricated = json.loads(original)["fabricated_scope_changes"]
    assert fabricated > 0, "the committed receipt is expected to fail this gate; update the test when it passes"
    assert gate.main([]) == 1
    output = capsys.readouterr().out
    assert f"fabricated_scope_changes: {fabricated} fails == 0" in output
    assert "I-7 RELEASE BLOCKED" in output
    assert gate.RECEIPT.read_bytes() == original


@pytest.mark.parametrize("metric,bad", [
    ("false_removals", 1), ("fabricated_scope_changes", 1), ("material_recall", 0.94),
    ("recall", 0.89), ("precision", 0.89), ("evidence_location", 0.97),
    ("unsupported_rate", 0.021), ("cost_p90_typical_eur", 0.21),
])
def test_all_mandatory_limits_are_recomputed_even_if_flags_claim_pass(evidence, metric, bad):
    receipt, split = evidence
    receipt[metric] = bad
    receipt["gates"][metric].update(value=bad, **{"pass": True})
    assert any(metric in e and "fails" in e for e in gate.release_errors(receipt, split))


@pytest.mark.parametrize("field", ["pairs", "comparisons", "runs", "scope_pairs", "no_change_pairs"])
@pytest.mark.parametrize("invalid", [None, 0, -1, True, "4"])
def test_empty_or_invalid_case_evidence_never_passes(evidence, field, invalid):
    receipt, split = evidence
    receipt[field] = invalid
    assert gate.release_errors(receipt, split)


@pytest.mark.parametrize("field,empty", [("tp_pred_gold", [0, 0, 0]), ("material_tp_gold", [0, 0]),
    ("located_locatable", [0, 0]), ("unsupported_shown", [0, 0])])
def test_vacuous_perfect_ratios_with_no_observations_are_rejected(evidence, field, empty):
    receipt, split = evidence
    receipt[field] = empty
    assert any(field in e for e in gate.release_errors(receipt, split))


@pytest.mark.parametrize("bad", [None, float("nan"), float("inf"), 10 ** 1000, -0.1, True, "0.01"])
def test_unmeasured_or_invalid_typical_cost_is_not_a_pass(evidence, bad):
    receipt, split = evidence
    receipt["cost_p90_typical_eur"] = bad
    assert gate.release_errors(receipt, split)


def test_heavy_cost_cannot_be_skipped_when_heavy_samples_exist(evidence):
    receipt, split = evidence
    receipt["typical_heavy_comparisons"] = [90, 2]
    assert any("cost_p90_heavy_eur" in e for e in gate.release_errors(receipt, split))
    receipt["cost_p90_heavy_eur"] = 0.61
    receipt["gates"]["cost_p90_heavy_eur"] = im.check("cost_p90_heavy_eur", 0.61)
    assert any("cost_p90_heavy_eur: 0.61 fails" in e for e in gate.release_errors(receipt, split))


@pytest.mark.parametrize("mutation", [
    lambda r: r.update(split="development"),
    lambda r: r.update(fingerprint="stale"),
    lambda r: r.update(model="another/model"),
    lambda r: r.update(commit=""),
    lambda r: r.update(split_fingerprint="another-split"),
    lambda r: r.update(real_pairs=1),
    lambda r: r.update(skipped_image_pairs=9),
    lambda r: r["status"].update(complete=91),
    lambda r: r["gates"].pop("precision"),
    lambda r: r["gates"]["precision"].update(limit=">= 0.5"),
    lambda r: r.update(tp_pred_gold=[157, 165, 156]),
])
def test_mismatched_provenance_counts_or_thresholds_block_release(evidence, mutation):
    receipt, split = evidence
    mutation(receipt)
    assert gate.release_errors(receipt, split)


def test_renamed_split_cannot_reuse_exposed_pairs(evidence):
    receipt, split = evidence
    split["held_out"][0] = "P-501"
    receipt["split_fingerprint"] = gate.split_fingerprint(split)
    assert any("exposed" in e for e in gate.release_errors(receipt, split))


def test_changed_split_is_not_covered_by_an_old_receipt(evidence):
    receipt, split = evidence
    changed = deepcopy(split)
    changed["held_out"][0] = "P-2000"
    assert any("frozen split" in e for e in gate.release_errors(receipt, changed))


@pytest.mark.parametrize("invalid", [None, [], {}, {"development": [], "held_out": []},
    {"development": ["P-1000"], "held_out": ["P-1000"]},
    {"development": [], "held_out": ["P-1000", "P-1000"]}])
def test_missing_or_invalid_split_is_rejected(invalid):
    assert gate.fresh_split_errors(invalid)


def test_invalid_receipt_file_has_nonzero_exit(tmp_path, capsys):
    receipt = tmp_path / "receipt.json"
    receipt.write_text("{", encoding="utf-8")
    assert gate.main(["--receipt", str(receipt)]) == 1
    assert "BLOCKED" in capsys.readouterr().out
