"""Offline fresh-cohort regressions; every review below is a disposable test fixture.

No test calls a model, reads a private dataset, or records real owner approval.
Run with: .venv/Scripts/python -m unittest discover -s scripts/eval -p test_fresh_cohort.py
"""
from collections import Counter, defaultdict
import copy
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

import fresh_cohort as fc
import generate
import validate
import bases as prior_bases


def approved_fixture(manifest, records):
    """Synthetic review data for tests only; never use this helper on a real cohort."""
    return {
        "version": fc.VERSION,
        "cohort_sha256": manifest["cohort_sha256"],
        "reviewer": "Disposable unit-test owner fixture, not a real approval",
        "reviewed_at": datetime.now(timezone.utc).isoformat(),
        "attestation": fc.ATTESTATION,
        "pairs": {record["id"]: {"decision": "approved", "note": "Test fixture only"}
                  for record in records},
    }


class Construction(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.draft = list(fc.constructed())
        cls.records = [record for record, *_ in cls.draft]
        cls.schema = json.loads(Path(validate.SCHEMA).read_text(encoding="utf-8"))

    def test_all_120_constructed_records_have_exact_schema_and_evidence(self):
        self.assertEqual(len(self.draft), 120)
        for draft, old, new, formats in self.draft:
            with self.subTest(pair=draft["id"]):
                record = copy.deepcopy(draft)
                for side, text in (("old", old), ("new", new)):
                    record[side] = {"format": "text", "sha256": generate.sha(text)}
                self.assertEqual(validate.check(record, self.schema, self.schema), [])
                for finding in record["findings"]:
                    self.assertTrue(any("evidence_" + side in finding for side in ("old", "new")))
                    for side, text in (("old", old), ("new", new)):
                        span = finding.get("evidence_" + side)
                        if span:
                            self.assertLess(span["start"], span["end"])
                            self.assertEqual(text[span["start"]:span["end"]], finding[side + "_value"])
                self.assertIn(formats, fc.FORMATS)

    def test_every_family_has_each_operator_and_two_distinct_partial_updates(self):
        families = defaultdict(list)
        for record, old, new, formats in self.draft:
            families[record["source"]["base_pair"]].append((record, old, new))
        expected = Counter(generate.OPERATORS.keys())
        expected["partial_update"] += 1
        self.assertEqual(len(families), 10)
        for family, pairs in families.items():
            with self.subTest(family=family):
                self.assertEqual(Counter(r["source"]["operators"][0] for r, *_ in pairs), expected)
                self.assertEqual(len({(old, new) for _, old, new in pairs}), 12)
                partial = [(old, new) for r, old, new in pairs
                           if r["source"]["operators"] == ["partial_update"]]
                self.assertEqual(len(partial), 2)
                self.assertNotEqual(partial[0], partial[1])

    def test_contradictions_use_only_mutually_exclusive_exact_quantities(self):
        bases = {base["id"]: base for base in fc.BASES}
        for base in fc.BASES:
            eligible = [item for item in generate.items(base) if item.get("contradiction_eligible")]
            self.assertGreaterEqual(len(eligible), 1)
            for item in eligible:
                self.assertEqual(item["cat"], "quantity")
                self.assertIn("exactly {v}", item["tpl"])
                self.assertIn("exactly {v}", item["para"])
                self.assertNotIn(item["v"], item["alts"])
        for record, old, new, _ in self.draft:
            if record["case_types"] != ["contradiction"]:
                continue
            base = bases[record["source"]["base_pair"]]
            _, spans, _ = generate.render(base, generate.base_vals(base))
            eligible = [item for item in generate.items(base) if item.get("contradiction_eligible")]
            eligible_spans = {tuple(spans[item["id"]]["val"]) for item in eligible}
            self.assertEqual(len(record["findings"]), 2)
            for finding in record["findings"]:
                span = finding["evidence_old"]
                self.assertIn((span["start"], span["end"]), eligible_spans)
                self.assertEqual(finding["change_type"], "uncertain")
                self.assertEqual(finding["category"], "quantity")

    def test_fresh_ids_and_bases_do_not_recycle_exposed_ancestry(self):
        self.assertEqual([r["id"] for r in self.records], [f"P-{n}" for n in range(800, 920)])
        exposed_ids = {f"P-{n}" for n in (*range(500, 566), *range(600, 617), *range(700, 720))}
        self.assertFalse(exposed_ids & {r["id"] for r in self.records})
        old_ids = {b["id"] for b in (*prior_bases.BASES, *getattr(prior_bases, "DEV2_BASES", []))}
        self.assertFalse(old_ids & {r["source"]["base_pair"] for r in self.records})
        self.assertTrue(all("derived_from" not in r["source"] for r in self.records))
        self.assertTrue(all(r["tier"] == "constructed" and r["split"] == "unsplit"
                            and r["labelled_by"] == ["generator"] for r in self.records))

    def test_construction_and_split_are_deterministic(self):
        self.assertEqual(self.draft, list(fc.constructed()))
        self.assertEqual(fc.family_split(self.records, fc.SEED), fc.family_split(self.records, fc.SEED))
        self.assertNotEqual(self.draft, list(fc.constructed(fc.SEED + 1)))

    def test_family_split_preserves_48_72_coverage_without_leakage(self):
        split = fc.family_split(self.records, fc.SEED)
        dev, held = set(split["development"]), set(split["held_out"])
        self.assertEqual((len(dev), len(held)), (48, 72))
        self.assertFalse(dev & held)
        self.assertEqual(dev | held, {r["id"] for r in self.records})
        families = {side: {r["source"]["base_pair"] for r in self.records if r["id"] in ids}
                    for side, ids in (("dev", dev), ("held", held))}
        self.assertEqual((len(families["dev"]), len(families["held"])), (4, 6))
        self.assertFalse(families["dev"] & families["held"])
        held_records = [r for r in self.records if r["id"] in held]
        self.assertEqual(sum(bool({"partial_update", "unknown_scope"} & set(r["case_types"]))
                             for r in held_records), 18)
        self.assertEqual(sum(bool({"no_change", "reordered"} & set(r["case_types"]))
                             for r in held_records), 12)
        for counts in split["strata"].values():
            self.assertEqual(counts["development"] * 5, counts["pairs"] * 2)
            self.assertEqual(counts["held_out"] * 5, counts["pairs"] * 3)

    def test_split_rejects_missing_duplicate_or_contaminated_families(self):
        bad_sets = [self.records[:-1], self.records + [self.records[0]]]
        for field, value in (("tier", "public"), ("case_types", ["no_change"])):
            bad = copy.deepcopy(self.records)
            bad[0][field] = value
            bad_sets.append(bad)
        for field, value in (("base_pair", ""), ("derived_from", "P-500")):
            bad = copy.deepcopy(self.records)
            bad[0]["source"][field] = value
            bad_sets.append(bad)
        for bad in bad_sets:
            with self.subTest(first=bad[0], count=len(bad)):
                with self.assertRaises(fc.CohortError):
                    fc.family_split(bad, fc.SEED)


class ReviewValidation(unittest.TestCase):
    def setUp(self):
        self.records = [{"id": "P-800"}, {"id": "P-801"}]
        self.manifest = {
            "cohort_sha256": "a" * 64,
            "created_at": (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat(),
        }
        self.review = approved_fixture(self.manifest, self.records)

    def test_complete_synthetic_review_is_accepted(self):
        self.assertIsNone(fc.validate_review(self.review, self.manifest, self.records))

    def test_pending_changes_requested_missing_extra_and_malformed_pairs_are_rejected(self):
        variants = []
        for decision in ("pending", "changes_requested", None):
            review = copy.deepcopy(self.review)
            review["pairs"]["P-800"]["decision"] = decision
            variants.append(review)
        for remove in (True, False):
            review = copy.deepcopy(self.review)
            if remove:
                del review["pairs"]["P-800"]
            else:
                review["pairs"]["P-999"] = {"decision": "approved", "note": ""}
            variants.append(review)
        for pair in (None, "approved", {"decision": "approved", "note": None}):
            review = copy.deepcopy(self.review)
            review["pairs"]["P-800"] = pair
            variants.append(review)
        for review in variants:
            with self.subTest(pairs=review["pairs"]):
                with self.assertRaises(fc.CohortError):
                    fc.validate_review(review, self.manifest, self.records)

    def test_foreign_cohort_wrong_version_and_absent_attestation_are_rejected(self):
        for field, value in (("cohort_sha256", "b" * 64), ("version", "other"),
                             ("attestation", ""), ("attestation", None)):
            review = copy.deepcopy(self.review)
            review[field] = value
            with self.subTest(field=field, value=value):
                with self.assertRaises(fc.CohortError):
                    fc.validate_review(review, self.manifest, self.records)

    def test_missing_blank_or_automated_reviewer_is_rejected(self):
        for reviewer in (None, "", "   ", "agent", "AI", " generator ", "Codex", "assistant"):
            review = copy.deepcopy(self.review)
            review["reviewer"] = reviewer
            with self.subTest(reviewer=reviewer):
                with self.assertRaises(fc.CohortError):
                    fc.validate_review(review, self.manifest, self.records)

    def test_review_time_must_be_aware_after_preparation_and_not_future(self):
        now = datetime.now(timezone.utc)
        for timestamp in (None, "not-a-time", now.replace(tzinfo=None).isoformat(),
                          (now - timedelta(days=1)).isoformat(), (now + timedelta(days=1)).isoformat()):
            review = copy.deepcopy(self.review)
            review["reviewed_at"] = timestamp
            with self.subTest(timestamp=timestamp):
                with self.assertRaises(fc.CohortError):
                    fc.validate_review(review, self.manifest, self.records)
        review = copy.deepcopy(self.review)
        del review["reviewed_at"]
        with self.assertRaises(fc.CohortError):
            fc.validate_review(review, self.manifest, self.records)


class StorageBoundaries(unittest.TestCase):
    def test_output_inside_git_is_rejected_before_any_files_are_created(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            target = root / "cohort"
            with self.assertRaisesRegex(fc.CohortError, "outside Git"):
                fc.prepare(target)
            self.assertFalse(target.exists())

    def test_output_through_link_into_git_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repository = root / "repository"
            repository.mkdir()
            (repository / ".git").mkdir()
            link = root / "linked"
            if os.name == "nt":
                result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(repository)],
                                        capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
            else:
                link.symlink_to(repository, target_is_directory=True)
            with self.assertRaisesRegex(fc.CohortError, "outside Git"):
                fc.prepare(link / "cohort")
            self.assertFalse((repository / "cohort").exists())

    def test_existing_directory_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "cohort"
            root.mkdir()
            sentinel = root / "existing.txt"
            sentinel.write_text("keep the original", encoding="utf-8")
            with self.assertRaisesRegex(fc.CohortError, "overwrite"):
                fc.prepare(root)
            self.assertEqual(sentinel.read_text(encoding="utf-8"), "keep the original")
            self.assertEqual(list(root.iterdir()), [sentinel])

    def test_confined_paths_reject_absolute_and_parent_escapes(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "cohort"
            root.mkdir()
            for path in ("../outside.txt", str(Path(tmp) / "outside.txt")):
                with self.subTest(path=path):
                    with self.assertRaises(fc.CohortError):
                        fc.confined(root, path)


class PreparedCohort(unittest.TestCase):
    """Prepare one real text/PDF cohort in disposable storage, then exercise tamper checks."""
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name) / "synthetic-test-cohort"
        cls.legacy = {}
        for name in ("split.json", "i7_receipt.json"):
            path = Path(fc.__file__).parent / name
            cls.legacy[name] = path.read_bytes() if path.exists() else None
        cls.manifest = fc.prepare(cls.root)
        cls.records = [json.loads(line) for line in (cls.root / "records.jsonl").read_text(encoding="utf-8").splitlines()]

    def test_preparation_validates_all_stored_text_and_pdf_inputs(self):
        self.assertEqual(validate.validate_file(self.root / "records.jsonl"), (120, []))
        self.assertEqual(self.manifest["pairs"], 120)
        self.assertEqual(self.manifest["families"], 10)
        self.assertEqual(self.manifest["state"], "owner_review_pending")
        self.assertEqual(set(self.manifest["format_counts"]), {"text/text", "text/pdf", "pdf/text", "pdf/pdf"})
        self.assertEqual(sum(self.manifest["format_counts"].values()), 120)
        self.assertGreater(len(list((self.root / "review").glob("*.png"))), 0)
        self.assertEqual(len(list((self.root / "review").glob("*.html"))), 120)
        template = json.loads((self.root / "owner-review.template.json").read_text(encoding="utf-8"))
        self.assertEqual(template["reviewer"], "")
        self.assertEqual(template["attestation"], "")
        self.assertTrue(all(p["decision"] == "pending" for p in template["pairs"].values()))

    def test_verification_checks_original_sources_records_and_review_assets(self):
        manifest, records = fc.verify(self.root)
        self.assertEqual(manifest, self.manifest)
        self.assertEqual(records, self.records)

    def test_tampered_source_record_review_page_and_preview_are_rejected(self):
        source = self.root / next(iter(self.manifest["files"]))
        preview = next((self.root / "review").glob("*.png"))
        for path in (source, self.root / "records.jsonl", self.root / "review.html",
                     self.root / "review" / "P-800.html", preview):
            original = path.read_bytes()
            with self.subTest(file=path.name):
                try:
                    path.write_bytes(original + b"\nchanged after preparation")
                    with self.assertRaises(fc.CohortError):
                        fc.verify(self.root)
                finally:
                    path.write_bytes(original)

    def test_manifest_identity_tampering_is_rejected(self):
        path = self.root / "manifest.json"
        original = path.read_bytes()
        manifest = copy.deepcopy(self.manifest)
        manifest["seed"] += 1
        try:
            path.write_text(json.dumps(manifest), encoding="utf-8")
            with self.assertRaisesRegex(fc.CohortError, "identity"):
                fc.verify(self.root)
        finally:
            path.write_bytes(original)

    def test_freeze_requires_review_is_immutable_and_does_not_change_legacy_evidence(self):
        # This entire directory and all approvals are synthetic fixtures deleted after the suite.
        self.assertFalse((self.root / "frozen").exists())
        review_path = self.root / "unit-test-review.json"
        pending = json.loads((self.root / "owner-review.template.json").read_text(encoding="utf-8"))
        review_path.write_text(json.dumps(pending), encoding="utf-8")
        with self.assertRaises(fc.CohortError):
            fc.freeze(self.root, review_path)
        self.assertFalse((self.root / "frozen").exists())
        review = approved_fixture(self.manifest, self.records)
        review_path.write_text(json.dumps(review), encoding="utf-8")
        split = fc.freeze(self.root, review_path)
        self.assertEqual((len(split["development"]), len(split["held_out"])), (48, 72))
        frozen = self.root / "frozen"
        self.assertEqual(json.loads((frozen / "split.json").read_text(encoding="utf-8")), split)
        receipt = json.loads((frozen / "freeze.json").read_text(encoding="utf-8"))
        self.assertEqual(receipt["model_calls"], 0)
        self.assertIs(receipt["paid_evaluation_authorized"], False)
        self.assertEqual(receipt["owner_review_sha256"], fc.digest(fc.canonical(review)))
        self.assertEqual(receipt["split_sha256"], fc.digest(fc.canonical(split)))
        frozen_bytes = {path.name: path.read_bytes() for path in frozen.iterdir()}
        with self.assertRaisesRegex(fc.CohortError, "already frozen"):
            fc.freeze(self.root, review_path)
        self.assertEqual({path.name: path.read_bytes() for path in frozen.iterdir()}, frozen_bytes)
        self.assertIsNone(fc.verify_frozen(self.root, self.manifest, self.records))
        changed_split = copy.deepcopy(split)
        changed_split["development"][0], changed_split["held_out"][0] = (
            changed_split["held_out"][0], changed_split["development"][0])
        changed_review = copy.deepcopy(review)
        changed_review["pairs"]["P-800"]["decision"] = "pending"
        variants = [("split.json", changed_split), ("owner-review.json", changed_review)]
        for key, value in (("paid_evaluation_authorized", True), ("model_calls", 1),
                           ("frozen_at", (datetime.now(timezone.utc) + timedelta(days=1)).isoformat())):
            changed_receipt = copy.deepcopy(receipt)
            changed_receipt[key] = value
            variants.append(("freeze.json", changed_receipt))
        for name, changed in variants:
            with self.subTest(tampered=name, changed=changed):
                try:
                    (frozen / name).write_text(json.dumps(changed), encoding="utf-8")
                    with self.assertRaises(fc.CohortError):
                        fc.verify_frozen(self.root, self.manifest, self.records)
                finally:
                    (frozen / name).write_bytes(frozen_bytes[name])
        marker = frozen / "freeze.json"
        temporary_marker = self.root / "unit-test-held-completion-marker.json"
        try:
            marker.rename(temporary_marker)
            with self.assertRaisesRegex(fc.CohortError, "incomplete"):
                fc.verify_frozen(self.root, self.manifest, self.records)
        finally:
            temporary_marker.rename(marker)
        for name, original in self.legacy.items():
            path = Path(fc.__file__).parent / name
            if original is None:
                self.assertFalse(path.exists())
            else:
                self.assertEqual(path.read_bytes(), original)


if __name__ == "__main__":
    unittest.main()
