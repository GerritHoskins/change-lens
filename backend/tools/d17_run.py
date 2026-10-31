"""D-17 runner: change detection on the constructed **development** split through the IONOS adapter.

Reads the private dataset in place and never runs on held-out pairs (`dev_records`, checked again
before every call). Text sides are sent exactly; PDF sides through the I-1 parser, visible blocks
only (hidden text is left out, as in the product). Pairs with an image side are skipped (I-1b).

Model outputs and per-pair scores go to the private output folder (refused inside a Git
worktree); stdout and `summary.json` hold aggregate, content-free metrics only. The token is read
from `IONOS_API_TOKEN` or from the env file named by `--env-file` / `CHANGELENS_IONOS_ENV_FILE`,
never printed. A 401/403 stops the run.

    .venv\\Scripts\\python -m tools.d17_run --model Qwen/Qwen3.5-397B-A17B --runs 2
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from decimal import Decimal
from pathlib import Path

from changelens.config import Limits
from changelens.llm.ionos import IonosConfig, IonosLlm, LlmAuthError, LlmError, LlmOutputInvalid, read_token
from changelens.pipeline.parse import parse
from tools import d17_score as sc

BACKEND = Path(__file__).resolve().parents[1]
DEFAULT_DATA = BACKEND.parents[1] / "change-lens-data"
DEFAULT_SPLIT = BACKEND.parent / "scripts" / "eval" / "split.json"
SCHEMA = "ChangeFindings"
PROMPT_VERSION = "v3"  # v1: no scope step or contradiction rule; v2: scope in the prompt only

SYSTEM = """You compare two versions of a brief for creative or project work. Data block 1 is the EARLIER version; data block 2 is the NEWER version (a revised brief, or an email or note about the brief).

Return every difference that matters as a finding with these fields:
- category: deliverable (what is produced, its format, style or tone); quantity (counts and amounts of work; an item whose main point is a number of pages, templates, videos or other units is quantity); date_deadline; responsibility_owner (who does or owns a task); approval (who approves and how binding it is); other_material (budget, fees, VAT, other material terms); structure (sections moved, nothing else changed).
- change_type:
  - changed: in both versions with a different value or meaning. Wording that changes binding force or scope counts ("must" -> "should", "including VAT" -> "excluding VAT", "capped" -> "estimated", "signs off" -> "reviews").
  - added: only in the newer version.
  - removed: only if the newer version explicitly deletes the item, or states or clearly is a full replacement of the whole earlier document and the item is gone.
  - not_addressed: the newer version is a partial update (for example an email that changes a few items and says the rest stands) and does not mention this earlier item. List every such earlier item.
  - uncertain: the evidence cannot settle it: unknown scope, a contradiction, or a vague date or person ("early next month", "the usual contact").
  - equivalent: reworded or moved with the same meaning, or the same value in a different format.
- First decide newer_scope. complete: a full brief, or it says it replaces earlier versions. partial: it changes some items and explicitly says the rest of the brief stands. unknown: it changes some items and says nothing about the rest; an update that only lists changes is unknown, not partial.
  - Complete: an earlier item that is gone is removed.
  - Partial: every earlier item it does not mention is not_addressed.
  - Unknown: every earlier item it does not mention is uncertain, never not_addressed or removed.
- Contradiction: if the newer version gives two different values for the same item (for example in the main text and again in a note), report two uncertain findings, one per value, each with that value as new_value and its own evidence_new, even when one value equals the earlier one.
- If in doubt between removed and not_addressed or uncertain, choose not_addressed or uncertain.
- old_value / new_value: the specific value on each side, copied exactly (for example "EUR 9,500", "14 March 2027", "Contact A", "warm and playful"); for whole items without a single value, the item sentence. null when that side has none.
- evidence_old / evidence_new: an exact quote of the sentence or line that shows it in that version; null when that side has none.
- Copy numbers and dates exactly as written. Never compute, convert or guess them.
- Formatting-only differences are not findings. If nothing changed, return an empty findings list."""


class HeldOutError(RuntimeError):
    """A held-out or unassigned pair reached the D-17 runner (07 §5.4)."""


def load_split(path: Path) -> dict:
    split = json.loads(Path(path).read_text(encoding="utf-8"))
    if set(split["development"]) & set(split["held_out"]):
        raise HeldOutError("split lists a pair on both sides")
    return split


def ensure_dev(pair_id: str, split: dict) -> None:
    if pair_id in set(split["held_out"]) or pair_id not in set(split["development"]):
        raise HeldOutError(f"{pair_id} is not in the development split")


def dev_records(data: Path, split: dict) -> list[tuple[str, dict]]:
    out = []
    for name in split["sets"]:
        for line in (Path(data) / name / "records.jsonl").read_text(encoding="utf-8").splitlines():
            if line.strip():
                rec = json.loads(line)
                if rec["id"] in set(split["development"]):
                    ensure_dev(rec["id"], split)
                    out.append((name, rec))
    return sorted(out, key=lambda t: t[1]["id"])


def refuse_in_git(path: Path) -> None:
    p = Path(path).resolve()
    for d in (p, *p.parents):
        if (d / ".git").exists():
            raise SystemExit(f"refusing to write model outputs inside a Git worktree: {d}")


def load_side(root: Path, ver: dict) -> sc.Side:
    data = (root / ver["storage_ref"]).read_bytes()
    if ver["format"] == "text":
        text = data.decode("utf-8")
        return sc.Side(text, [text])
    doc = parse(data, "pdf", Limits())
    parts = []
    for n in range(1, len(doc.pages) + 1):
        lines = [b.text for b in doc.blocks if b.locator.page == n and not b.hidden]
        parts.append((f"[page {n}]\n" if len(doc.pages) > 1 else "") + "\n".join(lines))
    return sc.Side("\n\n".join(parts), doc.pages)


def run_model(llm: IonosLlm, records, data: Path, split: dict, runs: int, out_dir: Path, max_calls: int) -> list[dict]:
    rows = []
    for run in range(1, runs + 1):
        with (out_dir / f"run{run}.jsonl").open("w", encoding="utf-8") as fh:
            for set_name, rec in records:
                ensure_dev(rec["id"], split)
                if len(llm.calls) >= max_calls:
                    raise SystemExit(f"call budget {max_calls} reached")
                old, new = (load_side(Path(data) / set_name, rec[s]) for s in ("old", "new"))
                first = len(llm.calls)
                row = {"id": rec["id"], "run": run, "output": None, "error": None}
                try:
                    row["output"], _ = llm.structured(SCHEMA, SYSTEM, [old.sent, new.sent])
                except LlmAuthError:
                    raise
                except LlmOutputInvalid as e:
                    row["error"] = e.reason
                except LlmError as e:
                    row["error"] = e.reason
                calls = llm.calls[first:]
                row["calls"] = [{"attempt": c.attempt, "outcome": c.outcome, "latency_s": round(c.latency_s, 3),
                                 "in": c.prompt_tokens, "out": c.completion_tokens, "cost": str(c.cost_eur)}
                                for c in calls]
                if row["output"] is not None:
                    row["score"] = sc.score_pair(rec, row["output"]["findings"], old, new)
                row["case_types"] = rec["case_types"]
                fh.write(json.dumps(row) + "\n")
                fh.flush()
                rows.append(row)
                print(f"  run {run} {rec['id']}: {row['error'] or 'ok'} "
                      f"({', '.join(c['outcome'] for c in row['calls'])})", flush=True)
    return rows


def summarise(rows: list[dict], runs: int) -> dict:
    calls = [c for r in rows for c in r["calls"]]
    answered = [r for r in rows if r["calls"] and not r["calls"][0]["outcome"].startswith(("http_", "timeout", "transport"))]
    first_ok = sum(r["calls"][0]["outcome"] == "ok" for r in answered)
    after = sum(r["output"] is not None for r in answered)
    scored = [r["score"] for r in rows if "score" in r]
    tot = defaultdict(int)
    for s in scored:
        for k, v in s.items():
            tot[k] += int(v)
    p, rc, f = sc.prf(tot["tp"], tot["pred"], tot["gold"])
    pr, rr, fr = sc.prf(tot["tp_relaxed"], tot["pred"], tot["gold"])
    by_case = defaultdict(lambda: defaultdict(int))
    for r in rows:
        if "score" in r:
            for k in ("tp", "pred", "gold", "false_removals"):
                by_case[r["case_types"][0]][k] += r["score"][k]
    cost = sum(Decimal(c["cost"]) for c in calls)
    lat = [c["latency_s"] for c in calls if c["latency_s"] > 0]
    out = {
        "pair_runs": len(rows), "calls": len(calls),
        "schema_valid_first_try": f"{first_ok}/{len(answered)}", "schema_valid_after_retry": f"{after}/{len(answered)}",
        "error_rate": f"{len(rows) - len(answered)}/{len(rows)}",
        "precision": round(p, 3), "recall": round(rc, 3), "f1": round(f, 3),
        "f1_ignoring_category": round(fr, 3), "tp_pred_gold": [tot["tp"], tot["pred"], tot["gold"]],
        "change_type_agreement_on_matches": f"{tot['type_agree']}/{tot['tp']}",
        "findings_with_invented_numbers_or_dates": tot["invented"],
        "evidence_quotes_verbatim": f"{tot['quotes_verbatim']}/{tot['quotes']}",
        "false_removals": tot["false_removals"],
        "latency_p50_s": round(sc.percentile(lat, 0.5), 2), "latency_p95_s": round(sc.percentile(lat, 0.95), 2),
        "tokens_in": sum(c["in"] for c in calls), "tokens_out": sum(c["out"] for c in calls),
        "cost_eur_total": str(round(cost, 4)), "cost_eur_per_comparison": str(round(cost / max(len(rows), 1), 5)),
        "by_case_type": {k: dict(v) for k, v in sorted(by_case.items())},
    }
    if runs > 1:
        sigs = defaultdict(dict)
        for r in rows:
            sigs[r["id"]][r["run"]] = sc.signature(r["output"]["findings"] if r["output"] else None)
        same = [len(set(v.values())) == 1 and None not in v.values() for v in sigs.values() if len(v) == runs]
        out["determinism_identical_pairs"] = f"{sum(same)}/{len(same)}"
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--model", required=True)
    ap.add_argument("--runs", type=int, default=1)
    ap.add_argument("--data", type=Path, default=Path(os.environ.get("CHANGELENS_EVAL_DATA", DEFAULT_DATA)))
    ap.add_argument("--split", type=Path, default=DEFAULT_SPLIT)
    ap.add_argument("--out", type=Path, help="default: <data>/d17/<prompt version>/<model>")
    ap.add_argument("--env-file", type=Path, default=os.environ.get("CHANGELENS_IONOS_ENV_FILE"))
    ap.add_argument("--mode", choices=["json_schema", "json_object"], default="json_schema")
    ap.add_argument("--reasoning-effort", default="none", help="'' to omit the parameter")
    ap.add_argument("--max-tokens", type=int, default=4096)
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--price-in", type=Decimal, help="EUR per million input tokens")
    ap.add_argument("--price-out", type=Decimal, help="EUR per million output tokens")
    ap.add_argument("--max-calls", type=int, default=300)
    args = ap.parse_args(argv)

    split = load_split(args.split)
    records = dev_records(args.data, split)
    usable = [(n, r) for n, r in records if "image" not in (r["old"]["format"], r["new"]["format"])]
    out_dir = args.out or args.data / "d17" / PROMPT_VERSION / args.model.replace("/", "_")
    refuse_in_git(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    cfg = IonosConfig(model=args.model, api_key=read_token(args.env_file), timeout_s=args.timeout,
                      max_tokens=args.max_tokens, response_mode=args.mode,
                      reasoning_effort=args.reasoning_effort or None,
                      price_in_eur=args.price_in, price_out_eur=args.price_out)
    print(f"D-17 {args.model}, prompt {PROMPT_VERSION}: {len(records)} development pairs, {len(records) - len(usable)} skipped "
          f"(image side, I-1b), {len(usable)} x {args.runs} runs, mode {args.mode}, "
          f"reasoning_effort {cfg.reasoning_effort}, prices EUR {cfg.prices()[0]}/{cfg.prices()[1]} per M")
    llm = IonosLlm(cfg)
    try:
        rows = run_model(llm, usable, args.data, split, args.runs, out_dir, args.max_calls)
    except LlmAuthError as e:
        print(f"STOP: authentication failed ({e.reason}); no retries")
        return 2
    finally:
        llm.close()
    summary = summarise(rows, args.runs) | {"model": args.model, "prompt": PROMPT_VERSION, "mode": args.mode,
                                            "reasoning_effort": cfg.reasoning_effort,
                                            "dev_pairs": len(records), "skipped_image": len(records) - len(usable)}
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    for k, v in summary.items():
        print(f"{k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
