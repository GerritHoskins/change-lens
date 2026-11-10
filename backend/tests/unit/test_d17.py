"""D-17 runner guard and scoring, with synthetic records and a fake model (no network, no dataset)."""
import json
from decimal import Decimal

import pytest

from changelens.llm.ionos import CallStats
from tools import d17_run
from tools import d17_score as sc

OLD = "Deliver 4 posters by 3 May 2027.\nBudget is EUR 9,500.\nContact E licenses music.\n"
NEW = "Deliver 5 posters by 3 May 2027.\nBudget is EUR 9,500.\n"


def record(pid, findings, case="value_change"):
    return {"id": pid, "tier": "constructed", "case_types": [case], "source": {}, "findings": findings,
            "old": {"format": "text", "storage_ref": "texts/old.txt"},
            "new": {"format": "text", "storage_ref": "texts/new.txt"}}


GOLD_QTY = {"category": "quantity", "change_type": "changed", "old_value": "4", "new_value": "5",
            "evidence_old": {"start": 8, "end": 9}, "evidence_new": {"start": 8, "end": 9}}
GOLD_NA = {"category": "responsibility_owner", "change_type": "not_addressed",
           "old_value": "Contact E licenses music.", "evidence_old": {"start": 54, "end": 79}}


def model_f(cat, ct, ov=None, nv=None, eo=None, en=None):
    return {"category": cat, "change_type": ct, "old_value": ov, "new_value": nv, "evidence_old": eo, "evidence_new": en}


def sides():
    return sc.Side(OLD, [OLD]), sc.Side(NEW, [NEW])


@pytest.fixture
def data(tmp_path):
    d = tmp_path / "data"
    (d / "constructed" / "texts").mkdir(parents=True)
    (d / "constructed" / "texts" / "old.txt").write_text(OLD, encoding="utf-8", newline="")
    (d / "constructed" / "texts" / "new.txt").write_text(NEW, encoding="utf-8", newline="")
    recs = [record("P-001", [GOLD_QTY]), record("P-002", [GOLD_QTY]), record("P-003", [GOLD_NA], "partial_update")]
    (d / "constructed" / "records.jsonl").write_text("\n".join(json.dumps(r) for r in recs), encoding="utf-8")
    split = {"sets": ["constructed"], "development": ["P-001", "P-003"], "held_out": ["P-002"]}
    (tmp_path / "split.json").write_text(json.dumps(split), encoding="utf-8")
    return d, tmp_path / "split.json"


def test_only_development_pairs_are_loaded(data):
    d, split_path = data
    split = d17_run.load_split(split_path)
    assert [r["id"] for _, r in d17_run.dev_records(d, split)] == ["P-001", "P-003"]


def test_held_out_or_unassigned_pair_is_refused(data):
    d, split_path = data
    split = d17_run.load_split(split_path)
    with pytest.raises(d17_run.HeldOutError):
        d17_run.ensure_dev("P-002", split)
    with pytest.raises(d17_run.HeldOutError):
        d17_run.ensure_dev("P-999", split)
    bad = dict(split, development=["P-001", "P-002"])
    with pytest.raises(d17_run.HeldOutError):
        d17_run.dev_records(d, bad)  # listed as development but also held out
    split_path.write_text(json.dumps(dict(split, held_out=["P-001"])), encoding="utf-8")
    with pytest.raises(d17_run.HeldOutError):
        d17_run.load_split(split_path)


class FakeIonos:
    def __init__(self, outputs):
        self.outputs, self.calls, self.sent_ids = outputs, [], []

    def structured(self, schema, system, data):
        self.calls.append(CallStats("m", schema, 1, "ok", 0.5, 100, 20, Decimal("0.001")))
        return self.outputs.pop(0), Decimal("0.001")


def test_runner_never_sends_held_out_and_scores(data, tmp_path):
    d, split_path = data
    split = d17_run.load_split(split_path)
    recs = d17_run.dev_records(d, split)
    good = {"newer_scope": "complete", "findings": [model_f("quantity", "changed", "4", "5", "Deliver 4 posters", "Deliver 5 posters")]}
    removal = {"newer_scope": "complete", "findings": [model_f("responsibility_owner", "removed", "Contact E", None, "Contact E licenses music.")]}
    llm = FakeIonos([good, removal, good, removal])
    out = tmp_path / "out"
    out.mkdir()
    rows = d17_run.run_model(llm, recs, d, split, 2, out, 10)
    assert [r["id"] for r in rows] == ["P-001", "P-003", "P-001", "P-003"]
    s = d17_run.summarise(rows, 2)
    assert s["tp_pred_gold"] == [2, 4, 2] and s["false_removals"] == 2
    assert s["determinism_identical_pairs"] == "2/2" and s["schema_valid_first_try"] == "4/4"
    assert s["findings_with_invented_numbers_or_dates"] == 0
    # A held-out pair smuggled into the record list is refused before any call.
    smuggled = recs + [("constructed", record("P-002", [GOLD_QTY]))]
    llm = FakeIonos([good, removal, good])
    with pytest.raises(d17_run.HeldOutError):
        d17_run.run_model(llm, smuggled, d, split, 1, out, 10)
    assert len(llm.calls) == 2


def test_outputs_refused_inside_git(tmp_path):
    (tmp_path / ".git").mkdir()
    with pytest.raises(SystemExit):
        d17_run.refuse_in_git(tmp_path / "d17" / "x")


def test_match_by_value_or_evidence_and_category():
    old, new = sides()
    rec = record("P-1", [GOLD_QTY])
    by_value = model_f("quantity", "changed", "4 posters", "5 posters")
    by_evidence = model_f("quantity", "changed", None, None, "Deliver 4 posters by 3 May 2027.")
    wrong_cat = model_f("deliverable", "changed", "4", "5")
    wrong_value = model_f("quantity", "changed", "4", "6")
    assert sc.score_pair(rec, [by_value], old, new)["tp"] == 1
    assert sc.score_pair(rec, [by_evidence], old, new)["tp"] == 1
    s = sc.score_pair(rec, [wrong_cat], old, new)
    assert s["tp"] == 0 and s["tp_relaxed"] == 1
    assert sc.score_pair(rec, [wrong_value], old, new)["tp"] == 0
    # O-14: a budget finding matches gold labelled other_material (labels predate the split).
    budget_gold = dict(GOLD_QTY, category="other_material")
    assert sc.score_pair(record("P-2", [budget_gold]), [model_f("budget", "changed", "4 posters", "5 posters")],
                         old, new)["tp"] == 1
    # Non-reportable model findings are not predictions; extra reportable ones are false positives.
    s = sc.score_pair(rec, [by_value, model_f("deliverable", "equivalent"), model_f("approval", "added", None, "x")], old, new)
    assert (s["tp"], s["pred"], s["gold"]) == (1, 2, 1)


def test_invented_numbers_and_dates():
    old, new = sides()
    assert sc.invented("EUR 9500", old) == []  # separators ignored
    assert sc.invented("3 May 2027", old) == [] and sc.invented("2028", old) == ["2028"]
    assert sc.invented("Deliver 6 posters", new) == ["6"]
    assert sc.invented("by 3 June 2027", new) == ["June"]
    assert sc.invented("EUR 9,50", new) == ["9,50"]
    rec = record("P-1", [GOLD_QTY])
    s = sc.score_pair(rec, [model_f("quantity", "changed", "4", "7")], old, new)
    assert s["invented"] == 1


def test_false_removal_rules():
    old, new = sides()
    na = record("P-1", [GOLD_NA], "value_change")
    removed = model_f("responsibility_owner", "removed", "Contact E licenses music.")
    assert sc.score_pair(na, [removed], old, new)["false_removals"] == 1  # matches a not_addressed label
    scope = record("P-2", [], "partial_update")
    assert sc.score_pair(scope, [model_f("deliverable", "removed", "x")], old, new)["false_removals"] == 1
    replaced = record("P-3", [dict(GOLD_NA, change_type="removed")], "replacement_with_omissions")
    s = sc.score_pair(replaced, [removed], old, new)
    assert s["false_removals"] == 0 and s["tp"] == 1


def test_prf_and_percentile_edges():
    assert sc.prf(0, 0, 0) == (1.0, 1.0, 1.0)
    assert sc.prf(0, 2, 0)[0] == 0.0
    assert sc.percentile([1, 2, 3, 4], 0.5) == 2.5 and sc.percentile([], 0.95) == 0.0
