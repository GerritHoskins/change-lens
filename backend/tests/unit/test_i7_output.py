"""Offline artifact routing; no actual credentials, evaluation inputs, or held-out outputs."""
import json
import pytest

from tools import i7_run as runner


@pytest.fixture
def offline_run(tmp_path, monkeypatch):
    source = tmp_path / "private inputs"
    source.mkdir()
    marker = source / "unchanged.txt"
    marker.write_bytes(b"input must not be modified")
    receipt = tmp_path / "existing-receipt.json"
    receipt.write_bytes(b"existing receipt sentinel")
    split = {"sets": ["synthetic"], "development": ["P-9000"], "held_out": []}
    record = {"id": "P-9000", "old": {"format": "text"}, "new": {"format": "text"},
              "case_types": ["no_change"], "tier": "constructed"}
    roots = []

    class OfflineLlm:
        calls = []

        def __init__(self, *_):
            pass

        def close(self):
            pass

    def compare_pair(_llm, root, _record):
        roots.append(root)
        return dict(status="complete", error=None, warnings=[], words=100, withheld=0,
                    latency_s=1, cost_eur=0.01, findings=[], signature="synthetic",
                    score=dict(tp=1, pred=1, gold=1, material_tp=1, material_gold=1, type_agree=1,
                               false_removals=0, scope_pair=1, located=1, locatable=1,
                               unsupported=0, shown=1, fabricated=0))

    monkeypatch.setattr(runner, "RECEIPT", receipt)
    monkeypatch.setattr(runner, "git", lambda *args: "a" * 40 if args[0] == "rev-parse" else "")
    monkeypatch.setattr(runner, "load_split", lambda *_: split)
    monkeypatch.setattr(runner, "split_records", lambda *_: [("synthetic", record)])
    monkeypatch.setattr(runner, "read_token", lambda *_: "offline-fixture")
    monkeypatch.setattr(runner, "IonosLlm", OfflineLlm)
    monkeypatch.setattr(runner, "compare_pair", compare_pair)
    return source, receipt, split, record, roots


@pytest.mark.parametrize("explicit", [False, True])
def test_output_root_routes_artifacts_without_mutating_inputs_or_development_receipt(tmp_path, offline_run, explicit):
    source, receipt, split, _, roots = offline_run
    destination = tmp_path / "review output with spaces" if explicit else source
    args = ["--data", str(source)]
    if explicit:
        args += ["--output-root", str(destination)]
    assert runner.main(args) == 0
    path = destination / "i7" / "development" / runner.split_fingerprint(split) / runner.im.fingerprint(runner.MODEL)
    assert json.loads((path / "summary.json").read_text())["split"] == "development"
    assert (path / "pairs.jsonl").is_file()
    assert roots == [source / "synthetic"]
    assert (source / "unchanged.txt").read_bytes() == b"input must not be modified"
    assert receipt.read_bytes() == b"existing receipt sentinel"
    if explicit:
        assert sorted(item.name for item in source.iterdir()) == ["unchanged.txt"]


@pytest.mark.parametrize("git_file", [False, True])
def test_output_inside_git_is_refused_before_credentials_or_writes(tmp_path, monkeypatch, offline_run, git_file):
    source, *_ = offline_run
    worktree = tmp_path / "worktree"
    worktree.mkdir()
    if git_file:
        (worktree / ".git").write_text("gitdir: elsewhere")
    else:
        (worktree / ".git").mkdir()
    destination = worktree / "new-output"
    monkeypatch.setattr(runner, "read_token", lambda *_: pytest.fail("credentials read during preflight"))
    with pytest.raises(SystemExit, match="inside a Git worktree"):
        runner.main(["--data", str(source), "--output-root", str(destination)])
    assert not destination.exists()


def test_output_components_cannot_escape_selected_root(tmp_path):
    with pytest.raises(SystemExit, match="escapes"):
        runner.output_directory(tmp_path / "chosen", "development", "../../../escape", "fingerprint")
    assert not (tmp_path / "chosen").exists()


def test_existing_output_link_cannot_escape_selected_root(tmp_path):
    selected, outside = tmp_path / "selected", tmp_path / "outside"
    selected.mkdir()
    outside.mkdir()
    try:
        (selected / "i7").symlink_to(outside, target_is_directory=True)
    except OSError:
        pytest.skip("OS does not permit local symlink creation")
    with pytest.raises(SystemExit, match="escapes"):
        runner.output_directory(selected, "development", "split", "pipeline")
    assert not list(outside.iterdir())


@pytest.mark.parametrize("exposed_split", [False, True])
def test_held_out_exposure_preflight_precedes_new_output_and_credentials(tmp_path, monkeypatch, offline_run, exposed_split):
    source, _, split, record, _ = offline_run
    split.update(development=[], held_out=["P-501" if exposed_split else "P-9000"])
    record["source"] = {"derived_from": "P-501"}
    destination = tmp_path / "must-stay-absent"
    monkeypatch.setattr(runner, "read_token", lambda *_: pytest.fail("credentials read during preflight"))
    with pytest.raises(SystemExit, match="exhausted|fresh split"):
        runner.main(["--split", "held_out", "--data", str(source), "--output-root", str(destination)])
    assert not destination.exists()


def test_empty_development_subset_creates_no_output_and_requests_no_credentials(tmp_path, monkeypatch, offline_run):
    source, *_ = offline_run
    destination = tmp_path / "empty-output"
    monkeypatch.setattr(runner, "split_records", lambda *_: [])
    monkeypatch.setattr(runner, "read_token", lambda *_: pytest.fail("credentials read during preflight"))
    with pytest.raises(SystemExit, match="no supported pairs"):
        runner.main(["--data", str(source), "--output-root", str(destination)])
    assert not destination.exists()


@pytest.mark.parametrize("args", [
    ["--split", "held_out", "--pair-ids", "P-9000"],
    ["--pair-ids", "P-9000", "P-9000"],
    ["--pair-ids", "P-unknown"],
    ["--pair-ids", "P-9001"],
])
def test_pair_selection_rejects_held_out_unassigned_or_duplicate_ids_before_credentials(tmp_path, monkeypatch, offline_run, args):
    source, _, split, _, _ = offline_run
    split["held_out"] = ["P-9001"]
    destination = tmp_path / "no-selection-output"
    monkeypatch.setattr(runner, "read_token", lambda *_: pytest.fail("credentials read during preflight"))
    with pytest.raises(SystemExit) as error:
        runner.main(["--data", str(source), "--output-root", str(destination), *args])
    assert error.value.code == 2
    assert not destination.exists()


def test_pair_selection_is_fingerprinted_without_mutating_original_split(tmp_path, monkeypatch, offline_run):
    source, _, split, record, roots = offline_run
    split["development"] = ["P-9000", "P-9002"]
    original = json.dumps(split, sort_keys=True)
    destination = tmp_path / "selected-output"

    def selected_records(data, selected_split, which):
        assert data == source and which == "development"
        assert selected_split["development"] == ["P-9000"]
        return [("synthetic", record)]

    monkeypatch.setattr(runner, "split_records", selected_records)
    assert runner.main(["--data", str(source), "--output-root", str(destination),
                        "--pair-ids", "P-9000"]) == 0
    summary = json.loads(next(destination.rglob("summary.json")).read_text())
    assert summary["pairs"] == 1 and roots == [source / "synthetic"]
    assert summary["split_fingerprint"] == runner.split_fingerprint({**split, "development": ["P-9000"]})
    assert summary["split_fingerprint"] != runner.split_fingerprint(split)
    assert json.dumps(split, sort_keys=True) == original
