"""Unit tests for the constructed-pair generator and validator (run: python -m unittest discover -s scripts/eval)."""
import hashlib
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate  # noqa: E402
import validate  # noqa: E402
from bases import BASES  # noqa: E402

with open(validate.SCHEMA, encoding="utf-8") as _fh:
    SCHEMA = json.load(_fh)
BASE = {b["id"]: b for b in BASES}

# Digest of all records for seed 7, 6 per operator. A change to an operator or a base
# changes every hash the manifest records, so it must be deliberate: update this value.
GOLDEN = "4852dad289bfb579bcef8bfb1548ec0ec3c65a94450d2f7c35e3f108457574d9"


def pairs(per_op=6, seed=7):
    return list(generate.generate(per_op=per_op, seed=seed))


def copy(rec):
    return json.loads(json.dumps(rec))


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
        self.assertEqual(ids, ["P-%03d" % i for i in range(500, 500 + len(ids))])

    def test_deterministic_for_a_seed(self):
        self.assertEqual([r for r, _, _ in pairs(seed=3)], [r for r, _, _ in pairs(seed=3)])

    def test_golden_digest(self):
        h = hashlib.sha256()
        for rec, _, _ in pairs():
            h.update(json.dumps(rec, sort_keys=True).encode("utf-8"))
        self.assertEqual(h.hexdigest(), GOLDEN)


class LabelRules(unittest.TestCase):
    """Gold labels follow docs/07-eval-dataset.md §3-4."""

    def by_op(self, name):
        found = [(r, o, n) for r, o, n in pairs() if r["source"]["operators"] == [name]]
        self.assertTrue(found, name)
        return found

    def n_items(self, rec):
        return sum(len(s["items"]) for s in BASE[rec["source"]["base_pair"]]["sections"])

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

    def test_moved_sections_use_the_structure_category(self):
        for rec, _, _ in self.by_op("reorder"):
            self.assertEqual({f["category"] for f in rec["findings"]}, {"structure"})

    def test_partial_update_labels_every_item(self):
        changed_counts = set()
        for rec, _, _ in self.by_op("partial_update"):
            fs = rec["findings"]
            self.assertEqual(len(fs), self.n_items(rec))
            changed = [f for f in fs if f["change_type"] == "changed"]
            changed_counts.add(len(changed))
            self.assertTrue(1 <= len(changed) <= 3)
            for f in fs:
                expected = ("changed", True) if f in changed else ("not_addressed", False)
                self.assertEqual((f["change_type"], f["material"]), expected)
        self.assertGreater(len(changed_counts), 1, "emails should vary in how many items they change")

    def test_unknown_scope_is_uncertain_never_removed(self):
        for rec, _, _ in self.by_op("unknown_scope"):
            fs = rec["findings"]
            self.assertEqual(len(fs), self.n_items(rec))
            self.assertEqual({f["change_type"] for f in fs}, {"changed", "uncertain"})
            self.assertTrue(all(f["material"] for f in fs))

    def test_contradiction_labels_both_new_spans(self):
        for rec, _, new in self.by_op("contradiction"):
            fs = rec["findings"]
            self.assertEqual([f["change_type"] for f in fs], ["uncertain", "uncertain"])
            self.assertTrue(all(f["material"] for f in fs))
            spans = {(f["evidence_new"]["start"], f["evidence_new"]["end"]) for f in fs}
            self.assertEqual(len(spans), 2)
            self.assertNotEqual(fs[0]["new_value"], fs[1]["new_value"])

    def test_ambiguous_replacement_is_uncertain_and_material(self):
        for rec, _, _ in self.by_op("ambiguous"):
            (f,) = rec["findings"]
            self.assertEqual((f["change_type"], f["material"]), ("uncertain", True))
            self.assertIn(f["category"], ("date_deadline", "responsibility_owner"))

    def test_removed_only_in_full_replacements(self):
        for rec, _, new in pairs():
            if any(f["change_type"] == "removed" for f in rec["findings"]):
                self.assertEqual(rec["source"]["operators"], ["replacement"])
                self.assertIn("replaces all previous versions", new)

    def test_removed_items_are_absent_from_new_text(self):
        for rec, _, new in self.by_op("replacement"):
            for f in rec["findings"]:
                self.assertEqual((f["change_type"], f["material"]), ("removed", True))
                self.assertNotIn(f["old_value"], new)

    def test_injection_text_produces_no_finding(self):
        variants = set()
        for rec, _, new in self.by_op("injection"):
            hits = [i for i in generate.INJECTIONS if i in new]
            self.assertEqual(len(hits), 1)
            variants.add(hits[0])
            cut = new.index(hits[0])
            self.assertIn("prompt_injection", rec["case_types"])
            for f in rec["findings"]:
                self.assertLess(f["evidence_new"]["end"], cut)
        self.assertGreater(len(variants), 1)

    def test_qualifier_flip_is_material(self):
        flips = set()
        for rec, _, _ in self.by_op("qualifier_flip"):
            (f,) = rec["findings"]
            self.assertEqual((f["change_type"], f["material"]), ("changed", True))
            flips.add((f["old_value"], f["new_value"]))
        self.assertGreater(len(flips), 3)

    def test_all_case_types_except_formats_covered(self):
        cases = {c for r, _, _ in pairs() for c in r["case_types"]}
        missing = set(SCHEMA["properties"]["case_types"]["items"]["enum"]) - cases
        self.assertEqual(missing, {"poor_quality", "cross_format"})

    def test_paraphrases_keep_binding_words(self):
        binding = ("must", "only", "capped", "including", "excluding")
        for base in BASES:
            for sec in base["sections"]:
                for it in sec["items"]:
                    for w in binding:
                        if (" %s " % w) in (" " + it["tpl"].lower()):
                            self.assertIn(w, it["para"].lower(), (base["id"], it["id"], w))


class Validator(unittest.TestCase):
    def setUp(self):
        self.rec = pairs(per_op=1)[0][0]

    def errs(self, rec):
        return validate.check(rec, SCHEMA, SCHEMA)

    def test_round_trip_through_storage(self):
        with tempfile.TemporaryDirectory() as d:
            n = generate.write(d, per_op=2, seed=1, start=100)
            count, errs = validate.validate_file(os.path.join(d, "records.jsonl"), d)
            self.assertEqual((count, errs), (n, []))

    def test_schema_violations(self):
        cases = [("tier", "synthetic"), ("id", "X-1"), ("labelled_by", []), ("extra", 1)]
        for key, val in cases:
            bad = copy(self.rec)
            bad[key] = val
            self.assertTrue(self.errs(bad), key)
        bad = copy(self.rec)
        bad["findings"][0]["material"] = "yes"
        self.assertTrue(self.errs(bad))

    def test_finding_and_locator_need_evidence(self):
        bad = copy(self.rec)
        for k in ("evidence_old", "evidence_new"):
            bad["findings"][0].pop(k)
        self.assertTrue(self.errs(bad))
        bad = copy(self.rec)
        bad["findings"][0]["evidence_old"] = {}
        self.assertTrue(self.errs(bad))

    def test_unsupported_keyword_fails_closed(self):
        schema = copy(SCHEMA)
        schema["properties"]["id"]["minLength"] = 3
        with self.assertRaises(ValueError):
            validate.check(self.rec, schema, schema)

    def test_date_format(self):
        bad = copy(self.rec)
        bad["source"]["retrieved"] = "30.10.2026"
        self.assertTrue(self.errs(bad))
        bad["source"]["retrieved"] = "2026-10-30"
        self.assertEqual(self.errs(bad), [])

    def stored(self, d, mutate):
        generate.write(d, per_op=1, seed=7, start=500)
        path = os.path.join(d, "records.jsonl")
        with open(path, encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        lines = mutate(lines, d)
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        return validate.validate_file(path, d)[1]

    def test_storage_errors(self):
        def shift_span(lines, d):
            r = json.loads(lines[0])
            r["findings"][0]["evidence_old"]["start"] += 1
            return [json.dumps(r)] + lines[1:]

        def page_only(lines, d):
            r = json.loads(lines[0])
            r["findings"][0]["evidence_old"] = {"page": 1}
            return [json.dumps(r)] + lines[1:]

        def reversed_span(lines, d):
            r = json.loads(lines[0])
            r["findings"][0]["evidence_old"] = {"start": 5, "end": 2}
            return [json.dumps(r)] + lines[1:]

        def tamper_text(lines, d):
            r = json.loads(lines[0])
            p = os.path.join(d, r["old"]["storage_ref"])
            with open(p, "ab") as fh:
                fh.write(b"x")
            return lines

        def delete_text(lines, d):
            os.remove(os.path.join(d, json.loads(lines[0])["new"]["storage_ref"]))
            return lines

        def dup_finding(lines, d):
            r = json.loads(lines[0])
            r["findings"].append(copy(r["findings"][0]))
            return [json.dumps(r)] + lines[1:]

        def dup_record(lines, d):
            return lines + [lines[0]]

        def bad_json(lines, d):
            return lines + ["{not json"]

        expect = {shift_span: "slices to", page_only: "needs start and end", reversed_span: "outside the text",
                  tamper_text: "sha256 mismatch", delete_text: "missing", dup_finding: "duplicate finding ids",
                  dup_record: "duplicate record id", bad_json: "not valid JSON"}
        for mutate, needle in expect.items():
            with tempfile.TemporaryDirectory() as d:
                errs = self.stored(d, mutate)
                self.assertTrue(any(needle in e for e in errs), (mutate.__name__, errs))

    def test_refuses_output_inside_git(self):
        here = os.path.dirname(os.path.abspath(__file__))
        self.assertTrue(generate.inside_git(os.path.join(here, "out")))
        with self.assertRaises(SystemExit):
            generate.write(os.path.join(here, "out"), per_op=1, seed=1, start=1)
        self.assertFalse(os.path.exists(os.path.join(here, "out")))


if __name__ == "__main__":
    unittest.main()
