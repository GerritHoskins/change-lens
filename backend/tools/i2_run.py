"""I-2 runner: fact extraction on the constructed **development** split through the IONOS adapter.

Every distinct version of the usable development pairs (no image side, I-1b) is extracted once
with the product's `extract_cached`, then a second pass checks that the cache answers without a
model call. Held-out pairs are refused (`d17_run.dev_records` / `ensure_dev`).

Acceptance (05 I-2): schema-valid output on >= 98% of development versions; failures marked
unextracted. Also reported: first-try validity per call, unlocated facts, invented numbers or dates
in fact values, and how many gold evidence spans some extracted fact overlaps (a recall proxy for
the "extraction misses implicit deliverables" risk).

Outputs go to the private folder (refused inside Git); stdout and summary.json are content-free.

    .venv\\Scripts\\python -m tools.i2_run
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from decimal import Decimal
from pathlib import Path

from changelens.config import Limits
from changelens.llm.ionos import IonosConfig, IonosLlm, LlmAuthError, read_token
from changelens.pipeline import extract as ex
from changelens.pipeline.parse import parse
from changelens.pipeline.types import ParsedDocument
from tools import d17_score as sc
from tools.d17_run import DEFAULT_DATA, DEFAULT_SPLIT, dev_records, ensure_dev, load_split, refuse_in_git

MODEL = "Qwen/Qwen3.5-397B-A17B"


class MemoryCache:
    def __init__(self):
        self.d: dict[str, dict] = {}

    def get(self, key):
        return self.d.get(key)

    def put(self, key, value):
        self.d[key] = value


class Budget:
    """Stops the run before the call budget is exceeded; wraps the adapter like MeteredLlm."""

    def __init__(self, llm: IonosLlm, max_calls: int):
        self.llm, self.max_calls = llm, max_calls

    def structured(self, schema, system, data):
        if len(self.llm.calls) + 2 > self.max_calls:  # a call may retry once
            raise SystemExit(f"call budget {self.max_calls} reached")
        return self.llm.structured(schema, system, data)[0]


def versions(data: Path, split: dict, records) -> list[dict]:
    """Distinct versions (by content hash) of the usable development pairs, with their gold spans."""
    out: dict[str, dict] = {}
    for set_name, rec in records:
        ensure_dev(rec["id"], split)
        for side, span_key in (("old", "evidence_old"), ("new", "evidence_new")):
            ver = rec[side]
            raw = (data / set_name / ver["storage_ref"]).read_bytes()
            sha = hashlib.sha256(raw).hexdigest()
            v = out.setdefault(sha, {"sha": sha, "raw": raw, "format": ver["format"], "spans": []})
            v["spans"] += [f[span_key] for f in rec["findings"] if f.get(span_key) and "start" in f[span_key]]
    for v in out.values():  # one span per location, however many pairs cite it
        v["spans"] = [dict(t) for t in {tuple(sorted(s.items())) for s in v["spans"]}]
    return list(out.values())


def covered(span: dict, facts) -> bool:
    page = span.get("page") or 1
    return any((f.locator.page or 1) == page and f.locator.char_start < span["end"] and f.locator.char_end > span["start"]
               for f in facts)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--data", type=Path, default=Path(os.environ.get("CHANGELENS_EVAL_DATA", DEFAULT_DATA)))
    ap.add_argument("--split", type=Path, default=DEFAULT_SPLIT)
    ap.add_argument("--env-file", type=Path, default=os.environ.get("CHANGELENS_IONOS_ENV_FILE"))
    ap.add_argument("--max-calls", type=int, default=120)
    args = ap.parse_args(argv)

    split = load_split(args.split)
    records = dev_records(args.data, split)
    usable = [(n, r) for n, r in records if "image" not in (r["old"]["format"], r["new"]["format"])]
    vers = versions(args.data, split, usable)
    out_dir = args.data / "i2" / args.model.replace("/", "_")
    refuse_in_git(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    llm = IonosLlm(IonosConfig(args.model, read_token(args.env_file), reasoning_effort="none"))
    print(f"I-2 {args.model}, {ex.EXTRACT_VERSION}: {len(usable)} usable development pairs, {len(vers)} distinct versions")
    cache, budget, rows = MemoryCache(), Budget(llm, args.max_calls), []
    try:
        for v in vers:
            doc: ParsedDocument = parse(v["raw"], v["format"], Limits())
            first = len(llm.calls)
            res = ex.extract_cached(doc, v["sha"], llm.config_id, cache, budget)
            sent = "\n".join(b.text for b in doc.blocks if not b.hidden)
            side = sc.Side(sent, doc.pages)
            rows.append({"sha": v["sha"][:12], "chunks": res.chunks, "unextracted": len(res.unextracted),
                         "facts": len(res.facts), "unlocated": res.unlocated,
                         "invented": sum(bool(sc.invented(f.normalised_value, side)) for f in res.facts),
                         "gold_spans": len(v["spans"]), "covered": sum(covered(s, res.facts) for s in v["spans"]),
                         "calls": [{"attempt": c.attempt, "outcome": c.outcome, "latency_s": round(c.latency_s, 3),
                                    "in": c.prompt_tokens, "out": c.completion_tokens, "cost": str(c.cost_eur)}
                                   for c in llm.calls[first:]],
                         "result": res.to_json()})
            print(f"  {v['sha'][:12]}: {len(res.facts)} facts, {len(res.unextracted)} unextracted", flush=True)
        before = len(llm.calls)
        hits = sum(ex.extract_cached(parse(v["raw"], v["format"], Limits()), v["sha"], llm.config_id, cache, budget).cached
                   for v in vers)
        second_pass_calls = len(llm.calls) - before
    except LlmAuthError as e:
        print(f"STOP: authentication failed ({e.reason}); no retries")
        return 2
    finally:
        llm.close()
    with (out_dir / "versions.jsonl").open("w", encoding="utf-8") as fh:
        for r in rows:
            fh.write(json.dumps(r) + "\n")
    calls = [c for r in rows for c in r["calls"]]
    firsts = [c for c in calls if c["attempt"] == 1 and not c["outcome"].startswith(("http_", "timeout", "transport"))]
    lat = [c["latency_s"] for c in calls]
    tot = lambda k: sum(r[k] for r in rows)  # noqa: E731
    valid = sum(r["unextracted"] == 0 for r in rows)
    summary = {
        "model": args.model, "extract_version": ex.EXTRACT_VERSION, "versions": len(rows), "chunks": tot("chunks"),
        "calls": len(calls), "schema_valid_versions": f"{valid}/{len(rows)}",
        "schema_valid_share": round(valid / max(len(rows), 1), 3),
        "schema_valid_first_try_calls": f"{sum(c['outcome'] == 'ok' for c in firsts)}/{len(firsts)}",
        "unextracted_chunks": tot("unextracted"), "facts": tot("facts"), "unlocated_facts": tot("unlocated"),
        "facts_with_invented_numbers_or_dates": tot("invented"),
        "gold_evidence_spans_covered": f"{tot('covered')}/{tot('gold_spans')}",
        "latency_p50_s": round(sc.percentile(lat, 0.5), 2), "latency_p95_s": round(sc.percentile(lat, 0.95), 2),
        "tokens_in": sum(c["in"] for c in calls), "tokens_out": sum(c["out"] for c in calls),
        "cost_eur_total": str(round(sum(Decimal(c["cost"]) for c in calls), 4)),
        "second_pass_cache_hits": f"{hits}/{len(vers)}", "second_pass_calls": second_pass_calls,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=1) + "\n", encoding="utf-8")
    for k, val in summary.items():
        print(f"{k}: {val}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
