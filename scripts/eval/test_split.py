"""Split tests (07 §5.4): synthetic record headers only, no documents."""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

import split


def rec(i, case, derived=None, tier="constructed"):
    return {"id": f"P-{i:03d}", "set": "x", "tier": tier, "case_types": [case], "derived_from": derived}


def dataset():
    rs = []
    for c, case in enumerate(["value_change", "no_change", "partial_update"]):
        for k in range(10):
            rs.append(rec(100 * (c + 1) + k, case))
    # Re-renders of four value_change roots, one of them re-rendered twice (a chain).
    rs += [rec(900, "value_change", "P-100"), rec(901, "value_change", "P-101"),
           rec(902, "value_change", "P-102"), rec(903, "value_change", "P-900")]
    return rs


class Split(unittest.TestCase):
    def test_groups_stay_together(self):
        for seed in range(20):
            out = split.split(dataset(), seed)
            dev = set(out["development"])
            for root, kids in (("P-100", ["P-900", "P-903"]), ("P-101", ["P-901"]), ("P-102", ["P-902"])):
                self.assertTrue(all((k in dev) == (root in dev) for k in kids), (seed, root))

    def test_deterministic_and_seed_sensitive(self):
        a, b = split.split(dataset(), 17), split.split(dataset(), 17)
        self.assertEqual(a, b)
        self.assertNotEqual(a["development"], split.split(dataset(), 18)["development"])

    def test_partition_and_ratio_per_stratum(self):
        recs = dataset()
        out = split.split(recs, 3)
        ids = {r["id"] for r in recs}
        self.assertEqual(set(out["development"]) | set(out["held_out"]), ids)
        self.assertFalse(set(out["development"]) & set(out["held_out"]))
        for key in ("constructed/no_change", "constructed/partial_update"):
            self.assertEqual(out["strata"][key]["development"], 4)
        vc = out["strata"]["constructed/value_change"]
        self.assertEqual(vc["pairs"], 14)
        self.assertLessEqual(abs(vc["development"] - round(0.4 * 14)), 1)

    def test_stratified_by_tier_too(self):
        recs = dataset() + [rec(500 + k, "value_change", tier="real") for k in range(5)]
        out = split.split(recs, 1)
        self.assertEqual(out["strata"]["real/value_change"]["development"], 2)

    def test_unknown_parent_and_cycle_refused(self):
        with self.assertRaises(split.SplitError):
            split.split([rec(1, "no_change", "P-999")], 1)
        with self.assertRaises(split.SplitError):
            split.split([rec(1, "no_change", "P-002"), rec(2, "no_change", "P-001")], 1)
        with self.assertRaises(split.SplitError):
            split.split([rec(1, "no_change"), rec(1, "no_change")], 1)

    def test_cli_writes_ids_only(self):
        tmp = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, tmp)
        (tmp / "s").mkdir()
        lines = [{"id": r["id"], "tier": r["tier"], "case_types": r["case_types"],
                  "source": {"derived_from": r["derived_from"]} if r["derived_from"] else {},
                  "findings": [{"old_value": "SECRET-CONTENT"}]} for r in dataset()]
        (tmp / "s" / "records.jsonl").write_text("\n".join(json.dumps(x) for x in lines), encoding="utf-8")
        out = tmp / "split.json"
        import contextlib, io
        with contextlib.redirect_stdout(io.StringIO()):
            split.main(["--data", str(tmp), "--sets", "s", "--seed", "5", "--out", str(out)])
        text = out.read_text(encoding="utf-8")
        self.assertNotIn("SECRET-CONTENT", text)
        self.assertEqual(json.loads(text)["seed"], 5)


if __name__ == "__main__":
    unittest.main()
