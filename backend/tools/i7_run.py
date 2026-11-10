"""I-7 evaluation harness: the worker's comparison pipeline on a constructed split, scored with the
04 §5 metrics against the Gate 2 thresholds (definitions in `tools/i7_metrics.py`).

Every comparison runs `changelens.pipeline.run.run_comparison`, the code the worker runs, from a
fresh fact cache, so its cost includes extracting both versions. The scope is the one a user would
confirm for the pair's case type (as in I-3). Pairs with an image side are skipped until I-1b.

The held-out split (07 §5.4) is frozen: it is never used for tuning or debugging. `--split
held_out` therefore refuses to run on a working tree with uncommitted changes (the result is bound
to a commit), refuses a second run for the same fingerprint unless `--rerun-reason` says why, and
writes `scripts/eval/i7_receipt.json`: aggregates only, which CI checks against the current
fingerprint. `--baseline` also runs the D-17 single-prompt detector (the general-purpose baseline)
on the same pairs. Per-comparison output with quotes stays in `<data>/i7/` outside Git by default.
`--output-root PATH` writes to `PATH/i7/<split>/<split fingerprint>/<pipeline fingerprint>/`
instead, while reading the input dataset in place. Neither output location may be inside Git.
`--pair-ids ID ...` selects a development-only diagnostic subset from the existing split;
it cannot select held-out or unassigned pairs and never edits the source split.
The original cohort is exhausted: held-out runs require a fresh split for I-7b, even with a
rerun reason. A failed evaluation exits 1; development may continue under its recorded deviation.

    .venv\\Scripts\\python -m tools.i7_run --split development --runs 1
    .venv\\Scripts\\python -m tools.i7_run --split held_out --runs 2 --baseline
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path

from changelens.config import Limits
from changelens.llm import MeteredLlm
from changelens.llm.ionos import IonosConfig, IonosLlm, LlmAuthError, LlmError, read_token
from changelens.metering import CeilingReached, CostMeter
from changelens.pipeline.parse import parse
from changelens.pipeline.run import run_comparison
from tools import d17_run, d17_score as sc, i7_metrics as im
from tools.d17_run import DEFAULT_DATA, DEFAULT_SPLIT, load_side, load_split, refuse_in_git
from tools.i2_run import MODEL, MemoryCache
from tools.i3_run import scope_of
from tools.release_gate import EXPOSED_PAIR_IDS, fresh_split_errors, split_fingerprint

REPO = Path(__file__).resolve().parents[2]
RECEIPT = REPO / "scripts" / "eval" / "i7_receipt.json"
CEILING = Decimal(os.environ.get("CHANGELENS_COST_CEILING_EUR", "1.50"))  # as the worker (config.py)


def split_records(data: Path, split: dict, which: str) -> list[tuple[str, dict]]:
    ids = set(split[which])
    out = []
    for name in split["sets"]:
        for f in sorted((data / name).glob("*.jsonl")):
            for line in f.read_text(encoding="utf-8").splitlines():
                rec = json.loads(line)
                if rec["id"] in ids:
                    out.append((name, rec))
    missing = ids - {r["id"] for _, r in out}
    if missing:
        raise SystemExit(f"{len(missing)} {which} pairs not found in the dataset")
    if len(out) != len(ids):
        raise SystemExit("duplicate evaluation pair IDs")
    return out


def validate_held_out_records(records: list[tuple[str, dict]]) -> None:
    """Reject known exposure and cross-split/missing ancestry before any model request."""
    by_id = {rec["id"]: rec for _, rec in records}
    for _, rec in records:
        if rec.get("tier") != "constructed":
            raise SystemExit("held-out gates require constructed pairs; real pairs are descriptive only")
        seen = set()
        current = rec
        while current is not None:
            if current["id"] in EXPOSED_PAIR_IDS or current["id"] in seen:
                raise SystemExit("held-out ancestry is exposed or cyclic; I-7b requires fresh bases")
            seen.add(current["id"])
            parent = current.get("source", {}).get("derived_from")
            if parent is not None and parent not in by_id:
                raise SystemExit("held-out descendants must keep their base in the same fresh split")
            current = by_id.get(parent)


def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, check=True).stdout.strip()


def output_directory(root: Path, split: str, split_fp: str, fingerprint: str) -> Path:
    """Resolve once and reject path traversal or an existing link escaping the selected root."""
    root = root.resolve()
    destination = (root / "i7" / split / split_fp / fingerprint).resolve()
    if not destination.is_relative_to(root):
        raise SystemExit("evaluation output escapes its selected root")
    refuse_in_git(destination)
    return destination


def shown(f) -> dict:
    return {"category": f.category, "change_type": f.change_type, "old_value": f.old_value, "new_value": f.new_value,
            "explanation": f.explanation, "group": f.group,
            "evidence": [{"side": e.side, "quote": e.quote, "locator": {"page": e.locator.page,
                          "char_start": e.locator.char_start, "char_end": e.locator.char_end}} for e in f.evidence]}


def compare_pair(llm: IonosLlm, root: Path, rec: dict) -> dict:
    sides, words = [], 0
    for key in ("old", "new"):
        raw = (root / rec[key]["storage_ref"]).read_bytes()
        doc = parse(raw, rec[key]["format"], Limits())
        words = max(words, sum(len(p.split()) for p in doc.pages))
        sides.append((hashlib.sha256(raw).hexdigest(), doc, MemoryCache()))
    t0, error = time.perf_counter(), None
    meter = CostMeter(CEILING)
    try:
        out = run_comparison(sides, scope_of(rec), llm, CEILING, llm.config_id, meter=meter)
        findings, status, withheld = [shown(f) for f in out.checked.findings], out.status, out.checked.withheld_count
        warnings = [w["code"] for w in out.warnings]
    except LlmAuthError:
        raise
    except LlmError as e:  # the worker would retry the job; here it counts as a failed comparison
        findings, status, withheld, warnings, error = [], "failed", 0, [], e.reason
    old, new = load_side(root, rec["old"]), load_side(root, rec["new"])
    return {"status": status, "error": error, "warnings": warnings, "words": words, "withheld": withheld,
            "latency_s": round(time.perf_counter() - t0, 2), "cost_eur": float(meter.total),
            "cost_actual_eur": float(meter.actual), "cost_reserved_eur": float(meter.reserved), "findings": findings,
            "score": im.score_comparison(rec, findings, old, new),
            "signature": repr(sorted(sc.signature(findings) or []))}


def baseline_pair(llm: IonosLlm, root: Path, rec: dict) -> dict:
    old, new = load_side(root, rec["old"]), load_side(root, rec["new"])
    meter = CostMeter(CEILING)  # An optional baseline has its own explicit per-comparison allowance.
    try:
        out = MeteredLlm(llm, meter).structured(d17_run.SCHEMA, d17_run.SYSTEM, [old.sent, new.sent])
        findings, error = out["findings"], None
    except LlmAuthError:
        raise
    except LlmError as e:
        findings, error = [], e.reason
    except CeilingReached:
        findings, error = [], "cost_ceiling"
    return {"error": error, "findings": findings, "cost_eur": float(meter.total),
            "cost_actual_eur": float(meter.actual), "cost_reserved_eur": float(meter.reserved),
            "score": im.score_baseline(rec, findings, old, new)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--split", choices=["development", "held_out"], default="development")
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--baseline", action="store_true", help="also run the D-17 single-prompt baseline")
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--data", type=Path, default=Path(os.environ.get("CHANGELENS_EVAL_DATA", DEFAULT_DATA)))
    ap.add_argument("--output-root", type=Path, help="artifact root; defaults to --data, always outside Git")
    ap.add_argument("--split-file", type=Path, default=DEFAULT_SPLIT)
    ap.add_argument("--pair-ids", nargs="+", help="development-only subset of IDs already assigned by --split-file")
    ap.add_argument("--env-file", type=Path, default=os.environ.get("CHANGELENS_IONOS_ENV_FILE"))
    ap.add_argument("--max-calls", type=int, default=2000)
    ap.add_argument("--rerun-reason", help="required to run the held-out split again for the same fingerprint")
    args = ap.parse_args(argv)
    if args.runs <= 0 or args.max_calls <= 0:
        ap.error("--runs and --max-calls must be positive")

    fp = im.fingerprint(args.model)
    held_out = args.split == "held_out"
    if held_out and args.pair_ids is not None:
        ap.error("--pair-ids is only allowed for development diagnostics")
    split = load_split(args.split_file)
    if args.pair_ids is not None:
        if len(args.pair_ids) != len(set(args.pair_ids)):
            ap.error("--pair-ids contains duplicate IDs")
        if set(args.pair_ids) - set(split["development"]):
            ap.error("--pair-ids must belong to the existing development split")
        split = {**split, "development": sorted(args.pair_ids)}
    if held_out:
        errors = fresh_split_errors(split)
        if errors:
            raise SystemExit("; ".join(errors))
    split_fp = split_fingerprint(split)
    commit = git("rev-parse", "HEAD")
    if held_out and git("status", "--porcelain", "--untracked-files=no"):
        raise SystemExit("held-out runs are bound to a commit: commit or stash the changes first")
    out_dir = output_directory(args.output_root if args.output_root is not None else args.data,
                               args.split, split_fp, fp)
    if held_out and (out_dir / "summary.json").exists() and not args.rerun_reason:
        raise SystemExit(f"the held-out split already ran for fingerprint {fp}; pass --rerun-reason to run it again")
    records = split_records(args.data, split, args.split)
    if held_out:
        validate_held_out_records(records)
    usable = [(n, r) for n, r in records if "image" not in (r["old"]["format"], r["new"]["format"])]
    if not usable:
        raise SystemExit("evaluation has no supported pairs")
    out_dir.mkdir(parents=True, exist_ok=True)
    llm = IonosLlm(IonosConfig(args.model, read_token(args.env_file), reasoning_effort="none"))
    print(f"I-7 {args.split}: {len(usable)} pairs x {args.runs} runs ({len(records) - len(usable)} with an image "
          f"side skipped), {args.model}, fingerprint {fp}, commit {commit[:7]}", flush=True)
    rows, base = [], []
    try:
        for run in range(1, args.runs + 1):
            for set_name, rec in usable:
                if len(llm.calls) >= args.max_calls:
                    raise SystemExit(f"call budget {args.max_calls} reached")
                row = {"id": rec["id"], "run": run, "case_types": rec["case_types"], "scope": scope_of(rec),
                       **compare_pair(llm, args.data / set_name, rec)}
                rows.append(row)
                msg = f"  run {run} {rec['id']}: {row['status']}, {len(row['findings'])} findings"
                if args.baseline:
                    b = {"id": rec["id"], "run": run, **baseline_pair(llm, args.data / set_name, rec)}
                    base.append(b)
                    msg += f"; baseline {b['error'] or 'ok'}"
                print(msg, flush=True)
    except LlmAuthError as e:
        print(f"STOP: authentication failed ({e.reason})")
        return 2
    finally:
        llm.close()
    with (out_dir / "pairs.jsonl").open("w", encoding="utf-8") as fh:
        for r in rows + [{"baseline": True, **b} for b in base]:
            fh.write(json.dumps(r) + "\n")
    summary = {"split": args.split, "model": args.model, "fingerprint": fp, "commit": commit,
               "split_fingerprint": split_fp,
               "date": datetime.now(timezone.utc).strftime("%Y-%m-%d"), "runs": args.runs,
               "skipped_image_pairs": len(records) - len(usable), "real_pairs": 0,
               "rerun_reason": args.rerun_reason, "calls": len(llm.calls),
               "no_change_pairs": len({r["id"] for r in rows if im.NO_CHANGE_CASES & set(r["case_types"])}),
               **im.summarise(rows, base or None)}
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    if held_out:
        RECEIPT.write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    for k, v in summary.items():
        if k != "gates":
            print(f"{k}: {v}")
    for k, g in summary["gates"].items():
        print(f"gate {k}: {g['value']} ({g.get('limit', 'directional')}) {'PASS' if g['pass'] else 'n/a' if g['pass'] is None else 'FAIL'}")
    print(f"I-7 {args.split} {summary['verdict']}")
    return 0 if summary["verdict"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
