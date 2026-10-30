"""Unit tests for the constructed-pair generator and validator (run: python -m unittest discover -s scripts/eval)."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate  # noqa: E402
import validate  # noqa: E402

with open(validate.SCHEMA, encoding="utf-8") as _fh:
    SCHEMA = json.load(_fh)


def pairs(per_op=6, seed=7):
    return list(generate.generate(per_op=per_op, seed=seed))


class SchemaAndSpans(unittest.TestCase):
    def test_every_record_is_schema_valid(self):
        for rec, _, _ in pairs():
            self.assertEqual(validate.check(rec, SCHEMA, SCHEMA), [], rec["id"])

    def test_every_span_slices_to_its_labelled_value(self):
        for rec, old, new in pairs():
            texts = {"old": old, "new": new}
            for f in rec["findings"]:
                for side in ("old", "new"):
                    span = f.get("evidence_" + side)
                    if span:
                        self.assertEqual(texts[side][span["start"]:span["end"]], f[side + "_value"],
                                         (rec["id"], f["id"], side))

    def test_every_finding_has_evidence(self):
        for rec, _, _ in pairs():
            for f in rec["findings"]:
                self.assertTrue("evidence_old" in f or "evidence_new" in f, (rec["id"], f["id"]))

    def test_ids_unique_and_sequential(self):
        ids = [rec["id"] for rec, _, _ in pairs()]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(ids[0], "P-500")

    def test_deterministic_for_a_seed(self):
        self.assertEqual([r for r, _, _ in pairs(seed=3)], [r for r, _, _ in pairs(seed=3)])


class LabelRules(unittest.TestCase):
    """Gold labels follow docs/07-eval-dataset.md §3-4."""

    def by_op(self, name):
        return [(r, o, n) for r, o, n in pairs() if r["source"]["operators"] == [name]]

    def test_no_change_has_no_findings_but_different_text(self):
        for rec, old, new in self.by_op("no_change"):
            self.assertEqual(rec["findings"], [])
            self.assertNotEqual(old, new)

    def test_value_changes_are_material(self):
        for rec, _, _ in self.by_op("value_change"):
            self.assertTrue(rec["findings"])
            for f in rec["findings"]:
                self.assertEqual((f["change_type"], f["material"]), ("changed", True))
                self.assertNotEqual(f["old_value"], f["new_value"])

    def test_rewording_and_reorder_are_equivalent_not_material(self):
        for op in ("rewording", "reorder"):
            for rec, _, _ in self.by_op(op):
                self.assertTrue(rec["findings"])
                for f in rec["findings"]:
                    self.assertEqual((f["change_type"], f["material"]), ("equivalent", False))

    def test_partial_update_marks_untouched_items_not_addressed(self):
        for rec, _, _ in self.by_op("partial_update"):
            types = [f["change_type"] for f in rec["findings"]]
            self.assertEqual(types.count("changed"), 1)
            self.assertNotIn("removed", types)
            self.assertEqual(set(types), {"changed", "not_addressed"})

    def test_unknown_scope_is_uncertain_never_removed(self):
        for rec, _, _ in self.by_op("unknown_scope"):
            types = {f["change_type"] for f in rec["findings"]}
            self.assertEqual(types, {"changed", "uncertain"})

    def test_removed_only_in_full_replacements(self):
        for rec, _, new in pairs():
            if any(f["change_type"] == "removed" for f in rec["findings"]):
                self.assertEqual(rec["source"]["operators"], ["replacement"])
                self.assertIn("replaces all previous versions", new)

    def test_removed_items_are_absent_from_new_text(self):
        for rec, _, new in self.by_op("replacement"):
            for f in rec["findings"]:
                self.assertNotIn(f["old_value"], new)

    def test_injection_text_produces_no_finding(self):
        for rec, _, new in self.by_op("injection"):
            self.assertIn(generate.INJECTION.strip(), new)
            self.assertIn("prompt_injection", rec["case_types"])
            for f in rec["findings"]:
                self.assertNotIn("ignore your earlier instructions", f.get("new_value", ""))

    def test_qualifier_flip_is_material(self):
        for rec, _, _ in self.by_op("qualifier_flip"):
            (f,) = rec["findings"]
            self.assertEqual((f["change_type"], f["material"]), ("changed", True))
            self.assertEqual(f["old_value"], "must")

    def test_all_case_types_except_formats_covered(self):
        cases = {c for r, _, _ in pairs() for c in r["case_types"]}
        missing = set(SCHEMA["properties"]["case_types"]["items"]["enum"]) - cases
        self.assertEqual(missing, {"poor_quality", "cross_format"})


class Validator(unittest.TestCase):
    def test_round_trip_through_storage(self):
        with tempfile.TemporaryDirectory() as d:
            n = generate.write(d, per_op=2, seed=1, start=100)
            count, errs = validate.validate_file(os.path.join(d, "records.jsonl"), d)
            self.assertEqual((count, errs), (n, []))

    def test_detects_bad_record_and_bad_span(self):
        rec, old, new = pairs(per_op=1)[0]
        bad = json.loads(json.dumps(rec))
        bad["tier"] = "synthetic"
        bad["findings"][0]["material"] = "yes"
        self.assertEqual(len(validate.check(bad, SCHEMA, SCHEMA)), 2)
        no_evidence = json.loads(json.dumps(rec))
        for k in ("evidence_old", "evidence_new"):
            no_evidence["findings"][0].pop(k)
        self.assertTrue(validate.check(no_evidence, SCHEMA, SCHEMA))
        with tempfile.TemporaryDirectory() as d:
            generate.write(d, per_op=1, seed=7, start=500)
            path = os.path.join(d, "records.jsonl")
            with open(path, encoding="utf-8") as fh:
                lines = fh.read().splitlines()
            first = json.loads(lines[0])
            first["findings"][0]["evidence_old"]["start"] += 1
            lines[0] = json.dumps(first)
            with open(path, "w", encoding="utf-8") as fh:
                fh.write("\n".join(lines) + "\n")
            _, errs = validate.validate_file(path, d)
            self.assertTrue(any("slices to" in e for e in errs), errs)


if __name__ == "__main__":
    unittest.main()
