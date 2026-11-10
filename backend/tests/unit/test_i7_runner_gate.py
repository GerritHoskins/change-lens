"""I-7 runner preflights and exit codes, with no credentials or model requests."""
import json

import pytest

from tools import i7_run as runner


def refuse_credentials(*args, **kwargs):
    raise AssertionError("preflight must not request credentials")


@pytest.mark.parametrize("extra", [[], ["--rerun-reason", "one more look"]])
def test_exhausted_held_out_split_cannot_receive_third_look(monkeypatch, extra):
    monkeypatch.setattr(runner, "read_token", refuse_credentials)
    with pytest.raises(SystemExit, match="exhausted"):
        runner.main(["--split", "held_out", *extra])


@pytest.mark.parametrize("argument", [["--runs", "0"], ["--runs", "-1"], ["--max-calls", "0"]])
def test_nonpositive_run_or_call_limits_are_rejected_before_credentials(monkeypatch, argument):
    monkeypatch.setattr(runner, "read_token", refuse_credentials)
    with pytest.raises(SystemExit) as exc:
        runner.main(argument)
    assert exc.value.code == 2


def test_empty_supported_dataset_is_rejected_before_credentials(tmp_path, monkeypatch):
    monkeypatch.setattr(runner, "read_token", refuse_credentials)
    monkeypatch.setattr(runner, "git", lambda *a: "a" * 40)
    monkeypatch.setattr(runner, "split_records", lambda *a: [])
    with pytest.raises(SystemExit, match="no supported pairs"):
        runner.main(["--data", str(tmp_path)])


@pytest.mark.parametrize("record", [
    {"id": "P-1000", "tier": "public"},
    {"id": "P-1000", "tier": "constructed", "source": {"derived_from": "P-501"}},
    {"id": "P-1000", "tier": "constructed", "source": {"derived_from": "P-1000"}},
])
def test_nonconstructed_or_contaminated_held_out_records_are_rejected(record):
    with pytest.raises(SystemExit):
        runner.validate_held_out_records([("synthetic", record)])


def test_fresh_parent_and_descendant_are_allowed_together():
    runner.validate_held_out_records([
        ("synthetic", {"id": "P-1000", "tier": "constructed"}),
        ("synthetic", {"id": "P-1001", "tier": "constructed", "source": {"derived_from": "P-1000"}}),
    ])


@pytest.mark.parametrize("fabricated,expected_exit", [(0, 0), (1, 1)])
def test_runner_returns_real_quality_verdict_without_touching_receipt(tmp_path, monkeypatch, fabricated, expected_exit):
    original = runner.RECEIPT.read_bytes()
    record = {"id": "P-700", "old": {"format": "text"}, "new": {"format": "text"},
              "case_types": ["partial_update", "no_change"]}
    score = dict(tp=1, pred=1, gold=1, material_tp=1, material_gold=1, type_agree=1,
                 false_removals=0, scope_pair=1, located=2, locatable=2, unsupported=0, shown=1,
                 fabricated=fabricated)
    row = dict(status="complete", error=None, warnings=[], words=100, withheld=0, latency_s=1,
               cost_eur=0.01, findings=[], score=score, signature="synthetic")

    class OfflineLlm:
        calls = []

        def __init__(self, *args):
            pass

        def close(self):
            pass

    monkeypatch.setattr(runner, "git", lambda *a: "a" * 40)
    monkeypatch.setattr(runner, "read_token", lambda *a: "offline-test-only")
    monkeypatch.setattr(runner, "IonosLlm", OfflineLlm)
    monkeypatch.setattr(runner, "split_records", lambda *a: [("synthetic", record)])
    monkeypatch.setattr(runner, "compare_pair", lambda *a: row)
    assert runner.main(["--data", str(tmp_path)]) == expected_exit
    summary = json.loads(next(tmp_path.rglob("summary.json")).read_text(encoding="utf-8"))
    assert summary["verdict"] == ("PASS" if expected_exit == 0 else "FAIL")
    assert summary["no_change_pairs"] == 1 and summary["split_fingerprint"]
    assert runner.RECEIPT.read_bytes() == original
