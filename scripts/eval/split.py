"""Seeded development / held-out split of the constructed pairs (07 §5.4, D-17).

Rules:
- 40% development, 60% held-out, stratified jointly by tier and case type;
- group rule: a pair and every pair whose `source.derived_from` names it (transitively) land on
  the same side, so a re-rendered pair never tests what its text source tuned;
- a group's stratum is its root pair's tier and case types; within a stratum, groups are
  shuffled with a seed derived from the run seed and the stratum, then added to development while
  that brings the development pair count closer to round(40% of the stratum's pairs).

The output lists record IDs only (no content), so it is kept in git: `scripts/eval/split.json`.
Held-out pairs are frozen: never used for prompt tuning, D-17 or debugging (07 §5.4).
A development-only set (I-7 owner decision Q2 = A, 2026-11-01) is built after the split for tuning
only: all its pairs go to development, and the seeded split of the other sets is unchanged by it.
Standard library only.

    python scripts/eval/split.py --data ../change-lens-data --seed 17 --dev-only-sets constructed-dev2
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

DEV_FRACTION = 0.4
DEFAULT_SETS = ("constructed", "constructed-visual", "constructed-hidden")
DEFAULT_OUT = Path(__file__).resolve().parent / "split.json"


class SplitError(ValueError):
    pass


def load(data: Path, sets=DEFAULT_SETS) -> list[dict]:
    records = []
    for name in sets:
        path = Path(data) / name / "records.jsonl"
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                records.append({"id": r["id"], "set": name, "tier": r["tier"],
                                "case_types": list(r["case_types"]),
                                "derived_from": r.get("source", {}).get("derived_from")})
    return records


def groups(records: list[dict]) -> list[list[dict]]:
    """Each group is a root pair plus all its transitive `derived_from` descendants."""
    by_id = {}
    for r in records:
        if r["id"] in by_id:
            raise SplitError(f"duplicate id {r['id']}")
        by_id[r["id"]] = r

    def root(r, seen=()):
        parent = r["derived_from"]
        if parent is None:
            return r["id"]
        if parent not in by_id:
            raise SplitError(f"{r['id']} derives from unknown {parent}")
        if parent in seen:
            raise SplitError(f"derived_from cycle at {r['id']}")
        return root(by_id[parent], seen + (r["id"],))

    out = defaultdict(list)
    for r in records:
        out[root(r)].append(r)
    return [sorted(g, key=lambda r: r["id"]) for _, g in sorted(out.items())]


def stratum(group: list[dict]) -> str:
    root = next(r for r in group if r["derived_from"] is None)
    return root["tier"] + "/" + "+".join(root["case_types"])


def split(records: list[dict], seed: int, fraction: float = DEV_FRACTION) -> dict:
    by_stratum = defaultdict(list)
    for g in groups(records):
        by_stratum[stratum(g)].append(g)
    dev, held, strata = [], [], {}
    for key in sorted(by_stratum):
        gs = list(by_stratum[key])
        random.Random(f"{seed}:{key}").shuffle(gs)
        total = sum(len(g) for g in gs)
        target = round(fraction * total)
        n_dev = 0
        for g in gs:
            if abs(n_dev + len(g) - target) < abs(n_dev - target):
                dev.extend(r["id"] for r in g)
                n_dev += len(g)
            else:
                held.extend(r["id"] for r in g)
        strata[key] = {"pairs": total, "groups": len(gs), "development": n_dev, "held_out": total - n_dev}
    return {"seed": seed, "dev_fraction": fraction, "unit": "root pair plus derived_from descendants",
            "strata": strata, "development": sorted(dev), "held_out": sorted(held)}


def add_dev_only(result: dict, records: list[dict]) -> dict:
    """Append a development-only set to a finished split; its pairs never touch the seeded split."""
    ids = [r["id"] for r in records]
    clash = set(ids) & (set(result["development"]) | set(result["held_out"]))
    if clash or len(set(ids)) != len(ids):
        raise SplitError(f"development-only ids already in the split or repeated: {sorted(clash) or ids}")
    known = set(ids) | set(result["development"]) | set(result["held_out"])
    if any(r["derived_from"] and r["derived_from"] not in known for r in records):
        raise SplitError("a development-only pair derives from an unknown pair")
    if any(r["derived_from"] in set(result["held_out"]) for r in records):
        raise SplitError("a development-only pair derives from a held-out pair")
    by = Counter(r["tier"] + "/" + "+".join(r["case_types"]) for r in records)
    return result | {"development": sorted(result["development"] + ids),
                     "development_only": {"pairs": len(ids), "strata": dict(sorted(by.items()))}}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", type=Path, required=True, help="private data folder (change-lens-data)")
    ap.add_argument("--sets", nargs="+", default=list(DEFAULT_SETS))
    ap.add_argument("--dev-only-sets", nargs="*", default=[], help="sets whose pairs all go to development")
    ap.add_argument("--seed", type=int, default=17)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args(argv)
    result = split(load(args.data, args.sets), args.seed)
    if args.dev_only_sets:
        result = add_dev_only(result, load(args.data, args.dev_only_sets))
    result["sets"] = list(args.sets) + list(args.dev_only_sets)
    args.out.write_text(json.dumps(result, indent=1) + "\n", encoding="utf-8", newline="\n")
    counts = Counter(s.split("/")[0] for s in result["strata"])
    print(f"split seed={args.seed}: development {len(result['development'])}, held-out "
          f"{len(result['held_out'])}, strata {len(result['strata'])} ({dict(counts)}) -> {args.out.name}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
