"""Offline I-7 release-quality gate; development's accepted deviation is not release approval.

Check aggregate evidence only: no model requests, private documents, or receipt writes. A
passing result covers the evaluated formats and word-size buckets, not overall launch readiness.
The exhausted 2026-11-01 cohort must not receive a third look (06; I-7b requires fresh bases).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from pathlib import Path

from tools import i7_metrics as im
from tools.d17_run import DEFAULT_SPLIT
from tools.i2_run import MODEL

RECEIPT = Path(__file__).resolve().parents[2] / "scripts" / "eval" / "i7_receipt.json"
# Existing constructed bases, their visual/hidden descendants, and development-only pairs.
# Fresh identifiers alone cannot prove fresh content; construction/review remains required.
EXPOSED_PAIR_IDS = frozenset(f"P-{n}" for n in (*range(500, 566), *range(600, 617), *range(700, 720)))


def split_fingerprint(split: dict) -> str:
    return hashlib.sha256(json.dumps(split, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def fresh_split_errors(split) -> list[str]:
    if not isinstance(split, dict):
        return ["split must be an object"]
    groups = [split.get(name) for name in ("development", "held_out")]
    if any(not isinstance(ids, list) or any(not isinstance(i, str) or not i for i in ids) for ids in groups):
        return ["split must contain development and held_out ID lists"]
    dev, held = groups
    errors = []
    if not held:
        errors.append("held-out split is empty")
    if len(set(dev)) != len(dev) or len(set(held)) != len(held) or set(dev) & set(held):
        errors.append("split IDs must be unique and disjoint")
    if set(held) & EXPOSED_PAIR_IDS:
        errors.append("exhausted or development-exposed pairs cannot be held out again; I-7b requires fresh bases")
    return errors


def _number(value) -> bool:
    try:
        return type(value) in (int, float) and math.isfinite(value) and value >= 0
    except OverflowError:
        return False


def _counts(value, size: int, positive_last: bool = False) -> bool:
    return (isinstance(value, list) and len(value) == size
            and all(type(n) is int and n >= 0 for n in value)
            and (not positive_last or value[-1] > 0))


def quality_errors(receipt) -> list[str]:
    """Validate sufficient nonempty observations and recompute gates; never trust PASS alone."""
    if not isinstance(receipt, dict):
        return ["receipt must be an object"]
    errors = []
    for key in ("pairs", "comparisons", "runs", "scope_pairs", "no_change_pairs"):
        if type(receipt.get(key)) is not int or receipt[key] <= 0:
            errors.append(f"{key}: positive evidence count required")
    if not errors:
        if receipt["comparisons"] != receipt["pairs"] * receipt["runs"]:
            errors.append("comparisons must equal pairs times runs")
        if receipt["scope_pairs"] > receipt["pairs"] or receipt["no_change_pairs"] > receipt["pairs"]:
            errors.append("case coverage exceeds pair count")
    status = receipt.get("status")
    if (not isinstance(status, dict) or set(status) != {"complete", "partial", "failed"}
            or any(type(n) is not int or n < 0 for n in status.values())):
        errors.append("status: complete/partial/failed counts required")
    elif sum(status.values()) != receipt.get("comparisons"):
        errors.append("status counts must total comparisons")
    elif status["failed"]:
        errors.append("failed comparisons cannot establish release quality")

    ratios = {
        "tp_pred_gold": (3, (("precision", 0, 1), ("recall", 0, 2))),
        "material_tp_gold": (2, (("material_recall", 0, 1),)),
        "located_locatable": (2, (("evidence_location", 0, 1),)),
        "unsupported_shown": (2, (("unsupported_rate", 0, 1),)),
    }
    for key, (size, checks) in ratios.items():
        counts = receipt.get(key)
        if not _counts(counts, size, positive_last=True):
            errors.append(f"{key}: nonempty evidence denominator required")
            continue
        for metric, numerator, denominator in checks:
            if counts[denominator] <= 0 or counts[numerator] > counts[denominator]:
                errors.append(f"{key}: invalid evidence counts")
            elif receipt.get(metric) != round(counts[numerator] / counts[denominator], 3):
                errors.append(f"{metric}: inconsistent with evidence counts")

    buckets = receipt.get("typical_heavy_comparisons")
    valid_buckets = _counts(buckets, 2) and sum(buckets) == receipt.get("comparisons") and sum(buckets) > 0
    if not valid_buckets:
        errors.append("typical_heavy_comparisons: nonempty cost evidence required")
    gates = receipt.get("gates")
    if not isinstance(gates, dict):
        gates = {}
        errors.append("gates: mandatory gate records required")
    for metric in im.GATES:
        value = receipt.get(metric)
        empty_bucket = (valid_buckets and metric in ("cost_p90_typical_eur", "cost_p90_heavy_eur")
                        and buckets[metric == "cost_p90_heavy_eur"] == 0)
        if empty_bucket:
            if metric not in receipt or value is not None:
                errors.append(f"{metric}: empty bucket must be explicitly unmeasured")
            expected = im.check(metric, None)
        elif not _number(value) or (metric in ("false_removals", "fabricated_scope_changes") and type(value) is not int):
            errors.append(f"{metric}: finite measured value required")
            continue
        else:
            expected = im.check(metric, value)
            if expected["pass"] is not True:
                errors.append(f"{metric}: {value} fails {expected['limit']}")
        recorded = gates.get(metric)
        if (not isinstance(recorded, dict) or recorded.get("value") != expected["value"]
                or recorded.get("limit") != expected["limit"] or recorded.get("pass") is not expected["pass"]):
            errors.append(f"{metric}: missing or inconsistent gate record")
    if receipt.get("verdict") != "PASS":
        errors.append("receipt verdict is not PASS; development deviations do not authorise release")
    return errors


def release_errors(receipt, split, model: str = MODEL) -> list[str]:
    errors = quality_errors(receipt) + fresh_split_errors(split)
    if not isinstance(receipt, dict):
        return errors
    if receipt.get("split") != "held_out":
        errors.append("release evidence must be held_out")
    if receipt.get("model") != model or receipt.get("fingerprint") != im.fingerprint(model):
        errors.append("receipt does not match the current model/prompt/schema fingerprint")
    if not isinstance(receipt.get("commit"), str) or not re.fullmatch(r"[0-9a-f]{40}", receipt["commit"]):
        errors.append("receipt must identify its evaluated commit")
    if not isinstance(split, dict) or receipt.get("split_fingerprint") != split_fingerprint(split):
        errors.append("receipt does not match the supplied frozen split")
    if isinstance(split, dict) and isinstance(split.get("held_out"), list):
        skipped = receipt.get("skipped_image_pairs")
        if type(skipped) is not int or skipped < 0 or receipt.get("pairs", -1) != len(split["held_out"]) - skipped:
            errors.append("evaluated and skipped pair counts do not match the frozen split")
    if receipt.get("real_pairs") != 0 or type(receipt.get("real_pairs")) is not int:
        errors.append("release gates must use constructed pairs only")
    return errors


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--receipt", type=Path, default=RECEIPT)
    parser.add_argument("--split-file", type=Path, default=DEFAULT_SPLIT)
    parser.add_argument("--model", default=MODEL)
    args = parser.parse_args(argv)
    try:
        receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
        split = json.loads(args.split_file.read_text(encoding="utf-8"))
        errors = release_errors(receipt, split, args.model)
    except (OSError, UnicodeError, ValueError, TypeError):
        print("I-7 RELEASE BLOCKED: unreadable or invalid receipt, split, or model configuration")
        return 1
    for error in errors:
        print(f"BLOCK: {error}")
    print("I-7 RELEASE BLOCKED" if errors else "I-7 QUALITY PASS (evaluated formats and size buckets only)")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
