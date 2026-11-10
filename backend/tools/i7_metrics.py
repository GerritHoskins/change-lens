"""I-7 metrics: the 04 §5 measures for one comparison, the totals with 95% intervals, and the Gate 2
thresholds (04 §6, owner decision 2026-10-30). No model calls and no document content in results.

Definitions beyond `tools/d17_score.py` (reportable, match, false removal):
- **Material recall:** gold reportable findings in a material category (deliverable, quantity,
  date_deadline, responsibility_owner, approval) matched by a reported finding / all of them.
- **Evidence location:** for every reported finding matched to a gold finding, each evidence item
  on a side where the gold finding has a span counts once; it is located when its locator (page and
  character range) overlaps that span.
- **Unsupported:** a shown finding (any group) whose old or new value, or whose explanation, names
  a number or month that its own quotes do not contain. Quotes that do not equal the document at
  their locator cannot reach the user (verify withholds them) and are counted as `withheld`.
- **Fabricated scope change:** a reportable finding on a reordered or no-change pair.
- **Fingerprint:** a hash of every prompt, output schema, the extraction prompt version, the
  pipeline version, the model configuration and its prices. The committed receipt of the last
  held-out run carries it, and a unit test fails when they differ, so a prompt or model change
  cannot ship without a new I-7 run.
"""
from __future__ import annotations

import hashlib
import json
import math
import random
import re
from collections import defaultdict

from changelens import PIPELINE_VERSION
from changelens.llm.ionos import IonosConfig
from changelens.llm.schemas import SCHEMAS
from changelens.pipeline import align, compare, extract, report
from tools import d17_score as sc

MATERIAL = report.MATERIAL
NO_CHANGE_CASES = frozenset({"reordered", "no_change"})
# Gate 2 (04 §6) plus the backlog's M1 recall floor (05, I-7).
GATES = {
    "false_removals": ("==", 0),
    "material_recall": (">=", 0.95),
    "recall": (">=", 0.90),
    "precision": (">=", 0.90),
    "evidence_location": (">=", 0.98),
    "unsupported_rate": ("<=", 0.02),
    "fabricated_scope_changes": ("==", 0),
    "cost_p90_typical_eur": ("<=", 0.20),
    "cost_p90_heavy_eur": ("<=", 0.60),
}
TYPICAL_WORDS = 5000


def fingerprint(model: str, reasoning_effort: str = "none") -> str:
    cfg = IonosConfig(model=model, api_key="-", reasoning_effort=reasoning_effort)
    parts = {
        "pipeline": PIPELINE_VERSION, "extract": extract.PROMPT_HASH, "align": align.SYSTEM,
        "compare": compare.SYSTEM, "report": report.SYSTEM, "schemas": SCHEMAS,
        "model": [cfg.model, cfg.response_mode, cfg.reasoning_effort, cfg.temperature, cfg.max_tokens,
                  [str(p) for p in cfg.prices()]],
    }
    return hashlib.sha256(json.dumps(parts, sort_keys=True, default=str).encode()).hexdigest()[:16]


def _located(ev: dict, span: dict) -> bool:
    loc = ev["locator"]
    return ((loc.get("page") or 1) == (span.get("page") or 1)
            and loc["char_start"] < span["end"] and loc["char_end"] > span["start"])


_MAY = re.compile(r"\d\s*may\b|\bmay\s*\d", re.I)


def _invented(value, side: sc.Side) -> list:
    """`d17_score.invented`, but "may" counts as a month only next to a number ("this may be")."""
    found = sc.invented(value, side)
    return [t for t in found if t.casefold() != "may" or _MAY.search(value or "")]


def unsupported(f: dict) -> bool:
    quotes = {e["side"]: e["quote"] for e in f["evidence"]}
    q_old, q_new = quotes.get("earlier", ""), quotes.get("later", "")
    both = sc.Side(f"{q_old}\n{q_new}", [])
    return bool(_invented(f.get("old_value"), sc.Side(q_old, [])) or _invented(f.get("new_value"), sc.Side(q_new, []))
                or _invented(f.get("explanation"), both))


def score_comparison(rec: dict, shown: list[dict], old: sc.Side, new: sc.Side) -> dict:
    """`shown`: findings as the user sees them, each with `evidence` [{side, quote, locator}],
    values and explanation. Returns counts only."""
    flat = [{"category": f["category"], "change_type": f["change_type"], "old_value": f.get("old_value"),
             "new_value": f.get("new_value"),
             "evidence_old": next((e["quote"] for e in f["evidence"] if e["side"] == "earlier"), None),
             "evidence_new": next((e["quote"] for e in f["evidence"] if e["side"] == "later"), None)} for f in shown]
    base = sc.score_pair(rec, flat, old, new)
    gold = [g for g in rec["findings"] if g["change_type"] in sc.REPORTABLE]
    pred_idx = [i for i, f in enumerate(flat) if f["change_type"] in sc.REPORTABLE]
    pairs = sc.assign(gold, [flat[i] for i in pred_idx], old, new)
    located = locatable = 0
    for gi, mi in pairs:
        for ev in shown[pred_idx[mi]]["evidence"]:
            span = gold[gi].get("evidence_old" if ev["side"] == "earlier" else "evidence_new")
            if span and "start" in span:
                locatable += 1
                located += _located(ev, span)
    material = [i for i, g in enumerate(gold) if g["category"] in MATERIAL]
    return base | {
        "material_gold": len(material), "material_tp": sum(gi in material for gi, _ in pairs),
        "located": located, "locatable": locatable, "shown": len(shown),
        "unsupported": sum(unsupported(f) for f in shown),
        "fabricated": base["pred"] if NO_CHANGE_CASES & set(rec["case_types"]) else 0,
    }


def score_baseline(rec: dict, findings: list[dict], old: sc.Side, new: sc.Side) -> dict:
    base = sc.score_pair(rec, findings, old, new)
    gold = [g for g in rec["findings"] if g["change_type"] in sc.REPORTABLE]
    pred = [f for f in findings if f["change_type"] in sc.REPORTABLE]
    pairs = sc.assign(gold, pred, old, new)
    material = [i for i, g in enumerate(gold) if g["category"] in MATERIAL]
    return base | {"material_gold": len(material), "material_tp": sum(gi in material for gi, _ in pairs),
                   "fabricated": base["pred"] if NO_CHANGE_CASES & set(rec["case_types"]) else 0}


def wilson(k: int, n: int, z: float = 1.96) -> list:
    if not n:
        return [None, None]
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(max(0.0, c - h), 3), round(min(1.0, c + h), 3)]


def bootstrap(rows: list[dict], num: str, den: str, n: int = 2000, seed: int = 7) -> list:
    """95% percentile interval of sum(num)/sum(den), resampling whole pairs (all runs together)."""
    by_pair = defaultdict(lambda: [0, 0])
    for r in rows:
        by_pair[r["id"]][0] += r["score"][num]
        by_pair[r["id"]][1] += r["score"][den]
    groups = list(by_pair.values())
    if not groups:
        return [None, None]
    rnd = random.Random(seed)
    stats = []
    for _ in range(n):
        pick = [groups[rnd.randrange(len(groups))] for _ in groups]
        d = sum(g[1] for g in pick)
        if d:
            stats.append(sum(g[0] for g in pick) / d)
    stats.sort()
    return [round(stats[int(0.025 * len(stats))], 3), round(stats[int(0.975 * len(stats)) - 1], 3)] if stats else [None, None]


def _ratio(k: int, n: int) -> float | None:
    # An unobserved denominator is not perfect accuracy (or a measured zero error rate).
    return round(k / n, 3) if n else None


def summarise(rows: list[dict], baseline: list[dict] | None = None) -> dict:
    t = defaultdict(int)
    for r in rows:
        for k, v in r["score"].items():
            t[k] += int(v)
    pairs = {r["id"] for r in rows}
    scope_pairs = {r["id"] for r in rows if r["score"]["scope_pair"]}
    no_change_pairs = {r["id"] for r in rows if NO_CHANGE_CASES & set(r.get("case_types", []))}
    typical = [r["cost_eur"] for r in rows if r["words"] <= TYPICAL_WORDS]
    heavy = [r["cost_eur"] for r in rows if r["words"] > TYPICAL_WORDS]
    m = {
        "pairs": len(pairs), "comparisons": len(rows), "no_change_pairs": len(no_change_pairs),
        "status": {s: sum(r["status"] == s for r in rows) for s in ("complete", "partial", "failed")},
        "precision": _ratio(t["tp"], t["pred"]), "precision_ci": bootstrap(rows, "tp", "pred"),
        "recall": _ratio(t["tp"], t["gold"]), "recall_ci": bootstrap(rows, "tp", "gold"),
        "material_recall": _ratio(t["material_tp"], t["material_gold"]),
        "material_recall_ci": bootstrap(rows, "material_tp", "material_gold"),
        "tp_pred_gold": [t["tp"], t["pred"], t["gold"]], "material_tp_gold": [t["material_tp"], t["material_gold"]],
        "change_type_agreement_on_matches": f"{t['type_agree']}/{t['tp']}",
        "false_removals": t["false_removals"], "scope_pairs": len(scope_pairs),
        # zero events in n pairs: true rate below 3/n at 95% (rule of three)
        "false_removal_rate_upper_95": round(3 / len(scope_pairs), 3) if scope_pairs and not t["false_removals"] else None,
        "evidence_location": _ratio(t["located"], t["locatable"]),
        "evidence_location_ci": wilson(t["located"], t["locatable"]), "located_locatable": [t["located"], t["locatable"]],
        "unsupported_rate": _ratio(t["unsupported"], t["shown"]),
        "unsupported_ci": wilson(t["unsupported"], t["shown"]), "unsupported_shown": [t["unsupported"], t["shown"]],
        "fabricated_scope_changes": t["fabricated"], "withheld": sum(r["withheld"] for r in rows),
        "cost_p50_eur": round(sc.percentile([r["cost_eur"] for r in rows], 0.5), 4),
        "cost_p90_typical_eur": round(sc.percentile(typical, 0.9), 4) if typical else None,
        "cost_p90_heavy_eur": round(sc.percentile(heavy, 0.9), 4) if heavy else None,
        "typical_heavy_comparisons": [len(typical), len(heavy)],
        "latency_p50_s": round(sc.percentile([r["latency_s"] for r in rows], 0.5), 1),
        "latency_p90_s": round(sc.percentile([r["latency_s"] for r in rows], 0.9), 1),
        "cost_eur_total": round(sum(r["cost_eur"] for r in rows), 4),
        "cost_actual_eur_total": round(sum(r.get("cost_actual_eur", r["cost_eur"]) for r in rows), 4),
        "cost_reserved_eur_total": round(sum(r.get("cost_reserved_eur", 0) for r in rows), 4),
    }
    sigs = defaultdict(set)
    for r in rows:
        sigs[r["id"]].add(r["signature"])
    if max((sum(x["id"] == i for x in rows) for i in pairs), default=0) > 1:
        m["identical_runs"] = f"{sum(len(s) == 1 for s in sigs.values())}/{len(sigs)}"
    m["gates"] = {k: check(k, m[k]) for k in GATES}
    failures = sum(r["status"] not in ("complete", "partial") or r.get("error") is not None for r in rows)
    m["gates"]["evaluated_comparisons"] = {"value": len(rows), "limit": "> 0", "pass": bool(rows)}
    m["gates"]["no_failed_comparisons"] = {"value": failures, "limit": "== 0", "pass": failures == 0}
    m["gates"]["scope_coverage"] = {"value": len(scope_pairs), "limit": "> 0", "pass": bool(scope_pairs)}
    m["gates"]["no_change_coverage"] = {"value": len(no_change_pairs), "limit": "> 0", "pass": bool(no_change_pairs)}
    if baseline:
        b = defaultdict(int)
        for r in baseline:
            for k, v in r["score"].items():
                b[k] += int(v)
        m["baseline"] = {"precision": _ratio(b["tp"], b["pred"]), "recall": _ratio(b["tp"], b["gold"]),
                         "material_recall": _ratio(b["material_tp"], b["material_gold"]),
                         "false_removals": b["false_removals"], "fabricated_scope_changes": b["fabricated"],
                         "missed_material": b["material_gold"] - b["material_tp"],
                         "failed": sum(r["error"] is not None for r in baseline),
                         "cost_eur_total": round(sum(r.get("cost_eur", 0) for r in baseline), 4),
                         "cost_actual_eur_total": round(sum(r.get("cost_actual_eur", r.get("cost_eur", 0)) for r in baseline), 4),
                         "cost_reserved_eur_total": round(sum(r.get("cost_reserved_eur", 0) for r in baseline), 4)}
        missed = t["material_gold"] - t["material_tp"]
        better = (t["false_removals"] <= b["false_removals"] and missed <= m["baseline"]["missed_material"]
                  and (t["false_removals"] < b["false_removals"] or missed < m["baseline"]["missed_material"]))
        m["gates"]["baseline_completed"] = {"value": m["baseline"]["failed"], "limit": "== 0",
                                             "pass": m["baseline"]["failed"] == 0}
        m["gates"]["advantage_over_baseline"] = {"value": {"false_removals": [t["false_removals"], b["false_removals"]],
                                                           "missed_material": [missed, m["baseline"]["missed_material"]]},
                                                 "pass": better, "directional": True}
    # Empty cost-size buckets stay explicitly unmeasured; quality denominators may not be waived.
    cost_buckets = {"cost_p90_typical_eur", "cost_p90_heavy_eur"}
    m["verdict"] = "PASS" if all(g["pass"] is True or (name in cost_buckets and g["pass"] is None)
                                   for name, g in m["gates"].items()) else "FAIL"
    return m


def check(name: str, value) -> dict:
    op, limit = GATES[name]
    if value is None:
        return {"value": None, "limit": f"{op} {limit}", "pass": None}
    ok = value == limit if op == "==" else value >= limit if op == ">=" else value <= limit
    return {"value": value, "limit": f"{op} {limit}", "pass": ok}
