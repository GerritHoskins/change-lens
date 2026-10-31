"""I-3 runner: align + compare on the constructed **development** split, scored like D-17.

Facts come from the I-2 run's private output (`<data>/i2/<model>/versions.jsonl`), so only the
`FactMatches` and `SameMeaning` calls are made here; a version missing from it is extracted live.
The scope a user would confirm is taken from the pair's case type: partial_update -> partial,
unknown_scope -> unknown, otherwise complete. Held-out pairs are refused (`dev_records`).

Reports the D-17 metrics (`tools/d17_score.py`) for the fact pipeline, plus the I-3 acceptance
checks: reportable findings on reordered pairs (AC-6, must be 0) and uncertain findings kept on
ambiguous-date and contradiction pairs (AC-7). AC-8 is covered by unit tests. With `--report` the
drafts also go through verify and report (I-5), and the scores are on what the user would see; it
adds the withheld, unexplained and presentation-only counts, the groups, and how many findings kept
model wording rather than the template.

    .venv\\Scripts\\python -m tools.i3_run --runs 2 --report
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

from changelens.config import Limits
from changelens.llm.ionos import IonosConfig, IonosLlm, LlmAuthError, read_token
from changelens.pipeline import extract as ex
from changelens.pipeline.align import align
from changelens.pipeline.compare import compare
from changelens.pipeline.parse import parse
from changelens.pipeline.report import MODEL_WORDED, report, template
from changelens.pipeline.verify import verify
from tools import d17_score as sc
from tools.d17_run import DEFAULT_DATA, DEFAULT_SPLIT, dev_records, ensure_dev, load_side, load_split, refuse_in_git
from tools.i2_run import MODEL, Budget, MemoryCache


def scope_of(rec: dict) -> str:
    types = set(rec["case_types"])
    return "partial" if "partial_update" in types else "unknown" if "unknown_scope" in types else "complete"


def as_finding(d) -> dict:
    """A draft in the D-17 output shape, so `d17_score` can score it."""
    quote = {e.side: e.quote for e in d.evidence}
    return {"category": d.category, "change_type": d.change_type, "old_value": d.old_value,
            "new_value": d.new_value, "evidence_old": quote.get("earlier"), "evidence_new": quote.get("later")}


def load_facts(data: Path, model: str) -> MemoryCache:
    """I-2 results keyed by the sha prefix the I-2 runner recorded."""
    cache = MemoryCache()
    path = data / "i2" / model.replace("/", "_") / "versions.jsonl"
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            cache.put(row["sha"], row["result"])
    return cache


def facts_for(root: Path, ver: dict, saved: MemoryCache, llm, budget) -> list:
    raw = (root / ver["storage_ref"]).read_bytes()
    hit = saved.get(hashlib.sha256(raw).hexdigest()[:12])
    if hit is not None:
        return ex.ExtractionResult.from_json(hit).facts
    return ex.extract(parse(raw, ver["format"], Limits()), budget).facts


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--data", type=Path, default=Path(os.environ.get("CHANGELENS_EVAL_DATA", DEFAULT_DATA)))
    ap.add_argument("--split", type=Path, default=DEFAULT_SPLIT)
    ap.add_argument("--env-file", type=Path, default=os.environ.get("CHANGELENS_IONOS_ENV_FILE"))
    ap.add_argument("--max-calls", type=int, default=150)
    ap.add_argument("--tag", default="v1", help="output subfolder, e.g. a prompt version")
    ap.add_argument("--report", action="store_true", help="also run verify and report (I-5)")
    args = ap.parse_args(argv)

    split = load_split(args.split)
    usable = [(n, r) for n, r in dev_records(args.data, split)
              if "image" not in (r["old"]["format"], r["new"]["format"])]
    out_dir = args.data / "i3" / args.tag / args.model.replace("/", "_")
    refuse_in_git(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    saved = load_facts(args.data, args.model)
    llm = IonosLlm(IonosConfig(args.model, read_token(args.env_file), reasoning_effort="none"))
    budget = Budget(llm, args.max_calls)
    print(f"I-3 {args.model}: {len(usable)} usable development pairs x {args.runs} runs, "
          f"{len(saved.d)} versions with saved I-2 facts")
    rows = []
    try:
        for run in range(1, args.runs + 1):
            for set_name, rec in usable:
                ensure_dev(rec["id"], split)
                root = args.data / set_name
                first = len(llm.calls)
                fe = facts_for(root, rec["old"], saved, llm, budget)
                fl = facts_for(root, rec["new"], saved, llm, budget)
                drafts = compare(align(fe, fl, budget), scope_of(rec), budget)
                extra = {}
                if args.report:  # I-5: verify against the parsed text, then word and rank
                    pe = parse((root / rec["old"]["storage_ref"]).read_bytes(), rec["old"]["format"], Limits())
                    pl = parse((root / rec["new"]["storage_ref"]).read_bytes(), rec["new"]["format"], Limits())
                    checked = verify(drafts, pe, pl)
                    drafts, templated = report(checked.findings, budget)
                    extra = {"withheld": checked.withheld_count, "unexplained": len(checked.unexplained),
                             "presentation_only": len(checked.presentation_only), "templated_at_ceiling": templated,
                             "groups": [d.group for d in drafts],
                             "model_worded": sum(d.change_type in MODEL_WORDED and d.explanation != template(d)
                                                 for d in drafts),
                             "wording_eligible": sum(d.change_type in MODEL_WORDED for d in drafts)}
                findings = [as_finding(d) for d in drafts]
                old, new = load_side(root, rec["old"]), load_side(root, rec["new"])
                rows.append({"id": rec["id"], "run": run, "case_types": rec["case_types"], "scope": scope_of(rec),
                             **extra, "findings": findings, "score": sc.score_pair(rec, findings, old, new),
                             "calls": [{"schema": c.schema, "outcome": c.outcome, "latency_s": round(c.latency_s, 3),
                                        "in": c.prompt_tokens, "out": c.completion_tokens, "cost": str(c.cost_eur)}
                                       for c in llm.calls[first:]]})
                print(f"  run {run} {rec['id']}: {len(findings)} drafts, {len(rows[-1]['calls'])} calls", flush=True)
    except LlmAuthError as e:
        print(f"STOP: authentication failed ({e.reason})")
        return 2
    finally:
        llm.close()
    with (out_dir / "pairs.jsonl").open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    tot = defaultdict(int)
    by_case = defaultdict(lambda: defaultdict(int))
    for r in rows:
        for k, v in r["score"].items():
            tot[k] += int(v)
        for k in ("tp", "pred", "gold", "false_removals"):
            by_case[r["case_types"][0]][k] += r["score"][k]
    p, rc, f = sc.prf(tot["tp"], tot["pred"], tot["gold"])
    _, _, fr = sc.prf(tot["tp_relaxed"], tot["pred"], tot["gold"])
    reorder = [r for r in rows if "reordered" in r["case_types"]]
    amb = [r for r in rows if {"ambiguous_date_entity", "contradiction"} & set(r["case_types"])]
    calls = [c for r in rows for c in r["calls"]]
    lat = [c["latency_s"] for c in calls]
    sigs = defaultdict(set)
    for r in rows:
        sigs[r["id"]].add(sc.signature(r["findings"]))
    summary = {
        "model": args.model, "pairs": len(usable), "runs": args.runs, "calls": len(calls),
        "calls_by_schema": dict(sorted({s: sum(c["schema"] == s for c in calls) for s in {c["schema"] for c in calls}}.items())),
        "call_errors": sum(c["outcome"] != "ok" for c in calls),
        "precision": round(p, 3), "recall": round(rc, 3), "f1": round(f, 3), "f1_ignoring_category": round(fr, 3),
        "tp_pred_gold": [tot["tp"], tot["pred"], tot["gold"]],
        "change_type_agreement_on_matches": f"{tot['type_agree']}/{tot['tp']}",
        "false_removals": tot["false_removals"],
        "ac6_reportable_findings_on_reordered_pairs": sum(r["score"]["pred"] for r in reorder),
        "ac7_uncertain_findings_on_ambiguous_pairs": sum(sum(f["change_type"] == "uncertain" for f in r["findings"]) for r in amb),
        "ac7_gold_uncertain_on_ambiguous_pairs": None,
        "latency_p50_s": round(sc.percentile(lat, 0.5), 2), "latency_p95_s": round(sc.percentile(lat, 0.95), 2),
        "tokens_in": sum(c["in"] for c in calls), "tokens_out": sum(c["out"] for c in calls),
        "cost_eur_total": str(round(sum(Decimal(c["cost"]) for c in calls), 4)),
        "identical_runs": f"{sum(len(s) == 1 for s in sigs.values())}/{len(sigs)}" if args.runs > 1 else None,
        "by_case_type": {k: dict(v) for k, v in sorted(by_case.items())},
    }
    if args.report:
        for k in ("withheld", "unexplained", "presentation_only", "templated_at_ceiling", "model_worded",
                  "wording_eligible"):
            summary[k] = sum(r[k] for r in rows)
        summary["groups"] = {g: sum(r["groups"].count(g) for r in rows) for g in ("prioritised", "needs_review", "other")}
    gold_amb = 0
    for set_name, rec in usable:
        if {"ambiguous_date_entity", "contradiction"} & set(rec["case_types"]):
            gold_amb += sum(g["change_type"] == "uncertain" for g in rec["findings"]) * args.runs
    summary["ac7_gold_uncertain_on_ambiguous_pairs"] = gold_amb
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    for k, v in summary.items():
        print(f"{k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
