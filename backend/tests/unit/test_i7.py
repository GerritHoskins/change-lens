"""I-7 metrics (tools/i7_metrics.py) and the CI regression check: the committed held-out receipt must
carry the current prompt and model fingerprint (05, I-7)."""
import json

from tools import d17_score as sc, i7_metrics as im
from tools.i7_run import RECEIPT

OLD = "Budget: EUR 12,000\nThe client provides hosting."
NEW = "Budget: EUR 15,000\nThe client provides hosting."


def ev(side, text, quote):
    start = text.index(quote)
    return {"side": side, "quote": quote, "locator": {"page": None, "char_start": start, "char_end": start + len(quote)}}


def rec(case="value_change"):
    return {"case_types": [case], "findings": [
        {"category": "quantity", "change_type": "changed", "old_value": "EUR 12,000", "new_value": "EUR 15,000",
         "evidence_old": {"start": 0, "end": 18}, "evidence_new": {"start": 0, "end": 18}},
        {"category": "responsibility_owner", "change_type": "removed", "old_value": "client hosting",
         "evidence_old": {"start": 19, "end": 47}}]}


def budget(explanation="The budget rose from EUR 12,000 to EUR 15,000.", new_quote="Budget: EUR 15,000"):
    return {"category": "quantity", "change_type": "changed", "old_value": "EUR 12,000", "new_value": "EUR 15,000",
            "explanation": explanation, "evidence": [ev("earlier", OLD, "Budget: EUR 12,000"), ev("later", NEW, new_quote)]}


def sides():
    return sc.Side(OLD, [OLD]), sc.Side(NEW, [NEW])


def test_scores_material_recall_location_and_support():
    s = im.score_comparison(rec(), [budget()], *sides())
    assert (s["tp"], s["gold"], s["material_tp"], s["material_gold"]) == (1, 2, 1, 2)
    assert (s["located"], s["locatable"]) == (2, 2)
    assert s["unsupported"] == 0 and s["fabricated"] == 0


def test_a_locator_off_the_labelled_span_is_not_located():
    f = budget(new_quote="The client provides hosting.")  # matched on values, but cites the wrong line
    s = im.score_comparison(rec(), [f], *sides())
    assert s["tp"] == 1 and (s["located"], s["locatable"]) == (1, 2)


def test_a_number_not_in_the_quotes_is_unsupported():
    s = im.score_comparison(rec(), [budget(explanation="The budget rose by EUR 4,000.")], *sides())
    assert s["unsupported"] == 1


def test_findings_on_no_change_pairs_are_fabricated():
    s = im.score_comparison(rec("no_change") | {"findings": []}, [budget()], *sides())
    assert s["fabricated"] == 1


def test_intervals_and_gates():
    assert im.wilson(0, 0) == [None, None]
    lo, hi = im.wilson(49, 50)
    assert lo < 0.98 < hi <= 1.0
    rows = [{"id": f"P-{i}", "score": {"tp": 9, "gold": 10}} for i in range(20)]
    assert im.bootstrap(rows, "tp", "gold") == [0.9, 0.9]
    assert im.check("precision", 0.91)["pass"] and not im.check("false_removals", 1)["pass"]
    assert im.check("cost_p90_heavy_eur", None)["pass"] is None


def test_fingerprint_follows_prompts_and_model(monkeypatch):
    fp = im.fingerprint("Qwen/Qwen3.5-397B-A17B")
    assert fp != im.fingerprint("another/model")
    monkeypatch.setattr(im.compare, "SYSTEM", im.compare.SYSTEM + " changed")
    assert im.fingerprint("Qwen/Qwen3.5-397B-A17B") != fp


def test_held_out_receipt_matches_the_current_prompts_and_model():
    """Fails when a prompt, schema, model or price changes after the last held-out run: rerun
    `python -m tools.i7_run --split held_out` (backend README §12) and commit the new receipt."""
    assert RECEIPT.is_file(), "no I-7 held-out receipt: run tools.i7_run --split held_out"
    receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))
    assert receipt["split"] == "held_out"
    assert receipt["fingerprint"] == im.fingerprint(receipt["model"]), \
        "prompts or model changed since the last I-7 held-out run: rerun it"


def test_may_is_a_month_only_next_to_a_number():
    f = budget(explanation="This may or may not have been dropped.")
    assert not im.unsupported(f)
    assert im.unsupported(budget(explanation="Due 3 May."))


def test_a_counted_deliverable_is_a_quantity():
    from changelens.pipeline.extract import fact_type
    assert fact_type("deliverable", "3 short videos for social media") == "quantity"
    assert fact_type("deliverable", "24 pages") == "quantity"
    assert fact_type("deliverable", "1080p") == "deliverable"
    assert fact_type("deliverable", "delivered as svg files") == "deliverable"
    assert fact_type("date_deadline", "3 march 2027") == "date_deadline"
