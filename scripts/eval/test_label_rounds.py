"""Option A workflow tests: all documents, labels and timestamps are synthetic."""
import contextlib
import io
import json
import re
import shutil
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

import label_kit
import label_rounds
import reconcile
import validate
from test_label_kit import OLD, NEW, export, finding, good_findings, make_data, run_core

FROZEN = datetime(2026, 10, 31, 13, tzinfo=timezone.utc)
LATER = datetime(2026, 11, 15, 13, tzinfo=timezone.utc)


def freeze_at(data, pairs=None):
    with mock.patch.object(label_rounds, "utcnow", return_value=FROZEN):
        return label_rounds.freeze(data, pairs)


class Build(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        make_data(self.tmp, {"P-001": (OLD, NEW), "P-003": (OLD, OLD)})
        a = good_findings("R1") + [finding("R1-3", "approval", "changed", True, "signs off", "reviews")]
        b = good_findings("R2")[:1] + [finding("R2-2", "deliverable", "uncertain", False, "PNG", "SVG")]
        export(self.tmp, "P-001", "R1", a)
        export(self.tmp, "P-001", "R2", b)
        freeze_at(self.tmp, ["P-001"])
        label_rounds.sample(self.tmp, 7)
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(label_rounds, "utcnow", return_value=LATER).start()
        self.res = Path(self.tmp) / "labelling/reconcile/P-001-resolution.json"

    def fill(self, change):
        res = json.loads(self.res.read_text(encoding="utf-8"))
        change(res)
        self.res.write_text(json.dumps(res), encoding="utf-8")
        return reconcile.build(self.tmp, ["P-001"])

    def decide(self, res, d1="R1", d2="drop", reason="owner resolution", case_types=("value_change", "partial_update")):
        res["case_type"] = case_types[0] if case_types else ""
        for it, d in zip(res["items"], (d1, d2)):
            it["decision"], it["reason"], it["finding"] = d, reason, None

    def test_compare_writes_worksheet_and_skeleton(self):
        stats, _ = reconcile.compare(self.tmp, "P-001")
        self.assertEqual((stats["items"], stats["matched"], stats["agreed"]), (3, 2, 1))
        res = json.loads(self.res.read_text(encoding="utf-8"))
        self.assertEqual(res["agreed"], [{"r1": "R1-1", "r2": "R2-1"}])
        self.assertEqual([(i["r1"], i["r2"], i["decision"]) for i in res["items"]], [("R1-2", "R2-2", ""), ("R1-3", None, "")])
        self.assertIn('change_type: R1 "changed" / R2 "uncertain"', res["items"][0]["disagreement"])
        sheet = (Path(self.tmp) / "labelling/reconcile/P-001-worksheet.md").read_text(encoding="utf-8")
        self.assertIn("## D2: only R1 found this", sheet)
        with self.assertRaisesRegex(SystemExit, "may hold decisions"):
            reconcile.compare(self.tmp, "P-001")

    def test_compare_refuses_invalid_labels(self):
        export(self.tmp, "P-001", "R2", good_findings("R2"), reviewed=False)
        with self.assertRaisesRegex(SystemExit, "draft export"):
            reconcile.compare(self.tmp, "P-001")

    def test_build_prefers_resolved_labels_and_validates_record(self):
        reconcile.compare(self.tmp, "P-001")
        self.assertEqual(self.fill(lambda r: self.decide(r, "R2", "edit") or r["items"][1].__setitem__(
            "finding", finding("x", "approval", "changed", True, "signs off the design", "reviews the design"))), [])
        records = Path(self.tmp) / "labelling/records.jsonl"
        [rec] = [json.loads(x) for x in records.read_text(encoding="utf-8").splitlines()]
        self.assertEqual((rec["tier"], rec["split"], rec["labelled_by"]), ("public", "unsplit", ["owner"]))
        self.assertEqual(rec["source"], {"kind": "rfp_addendum", "url": "https://example.invalid/P-001/new",
                                         "licence": "test-only", "retrieved": "2026-10-30", "anonymised": True})
        self.assertEqual([(f["id"], f["change_type"]) for f in rec["findings"]], [("F1", "changed"), ("F2", "uncertain"), ("F3", "changed")])
        self.assertEqual(rec["reconciliation"][0]["finding"], "F2")
        self.assertEqual(rec["reconciliation"][1]["resolution"], "edit: owner resolution")
        self.assertEqual(validate.validate_file(str(records), texts_root=self.tmp), (1, []))
        self.assertEqual(self.fill(lambda r: self.decide(r, "R1", "drop")), [])  # rerun replaces, never duplicates
        [rec] = [json.loads(x) for x in records.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(rec["reconciliation"][1]["finding"], "none (dropped R1-3)")

    def test_no_change_pair_builds_from_r1_without_r2(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_data(tmp, {"P-003": (OLD, OLD)})
            path, doc = export(tmp, "P-003", "R1", [])
            doc["case_type"] = "no_change"
            path.write_text(json.dumps(doc), encoding="utf-8")
            freeze_at(tmp)
            self.assertEqual(reconcile.build(tmp), [])
            rec = json.loads((Path(tmp) / "labelling/records.jsonl").read_text(encoding="utf-8"))
            self.assertEqual(rec["findings"], [])
            self.assertEqual(rec["case_types"], ["no_change"])
            self.assertEqual(rec["provenance"]["rounds"], ["R1"])

    def test_every_resolution_failure_path(self):
        def stale(r):
            export(self.tmp, "P-001", "R2", good_findings("R2"))

        cases = {
            "decision must be one of": lambda r: self.decide(r, "R1", "R2"),
            "give the reason": lambda r: self.decide(r, reason=" "),
            "required for edit and only for edit": lambda r: self.decide(r, "R1", "edit"),
            "case_type must keep": lambda r: self.decide(r, case_types=()),
            "case_type must keep the R1": lambda r: self.decide(r, case_types=("deadline_change",)),
            "labels changed since compare": lambda r: self.decide(r) or stale(r),
            "do not match the labels": lambda r: self.decide(r) or r["items"].pop(),
            "format or rounds": lambda r: self.decide(r) or r.__setitem__("rounds", ["R2", "R1"]),
            "slices to": lambda r: self.decide(r, "R1", "edit") or r["items"][1].__setitem__(
                "finding", dict(finding("x", "approval", "changed", True, "signs off"), old_value="signs of")),
            "never material": lambda r: self.decide(r, "R1", "edit") or r["items"][1].__setitem__(
                "finding", finding("x", "structure", "equivalent", True, "signs off", "reviews")),
            "is not the resolution for": lambda r: r.__setitem__("pair", "P-002"),
        }
        for expected, change in cases.items():
            with self.subTest(expected):
                make_data(self.tmp, {"P-001": (OLD, NEW), "P-003": (OLD, OLD)})
                export(self.tmp, "P-001", "R2", good_findings("R2")[:1] + [finding("R2-2", "deliverable", "uncertain", False, "PNG", "SVG")])
                reconcile.compare(self.tmp, "P-001", force=True)
                errs = self.fill(change)
                self.assertTrue(any(expected in e for e in errs), errs)
                self.assertFalse((Path(self.tmp) / "labelling/records.jsonl").exists())


class Rounds(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        make_data(self.tmp, {"P-001": (OLD, NEW)})
        export(self.tmp, "P-001", "R1", good_findings("R1"))
        self.addCleanup(mock.patch.stopall)
        mock.patch.object(label_rounds, "utcnow", return_value=LATER).start()

    def ready(self):
        freeze_at(self.tmp)
        label_rounds.sample(self.tmp, 7)
        return export(self.tmp, "P-001", "R2", good_findings("R2"))

    def test_freeze_is_immutable_and_records_file_hash_and_date(self):
        frozen = freeze_at(self.tmp)
        entry = frozen["pairs"]["P-001"]
        self.assertEqual(entry["frozen_at"], FROZEN.isoformat())
        self.assertEqual(entry["sha256"], label_rounds.digest(label_rounds.export_path(self.tmp, "P-001", "R1")))
        path = Path(self.tmp) / "labelling" / label_rounds.FREEZE
        original = path.read_bytes()
        with self.assertRaisesRegex(SystemExit, "refusing to overwrite"):
            freeze_at(self.tmp)
        self.assertEqual(path.read_bytes(), original)

    def test_freeze_detects_modified_r1_export_on_all_consumers(self):
        self.ready()
        path = label_rounds.export_path(self.tmp, "P-001", "R1")
        doc = json.loads(path.read_text(encoding="utf-8"))
        doc["findings"][0]["note"] = "changed after freezing"
        path.write_text(json.dumps(doc), encoding="utf-8")
        for operation in (lambda: label_rounds.read_freeze(self.tmp), lambda: reconcile.compare(self.tmp, "P-001"),
                          lambda: reconcile.build(self.tmp), lambda: reconcile.calibrate(self.tmp)):
            with self.subTest(operation=operation), self.assertRaisesRegex(SystemExit, "R1 hash differs"):
                operation()

    def cohort(self, data):
        ids = ["P-%03d" % i for i in range(101, 110)]
        make_data(data, {pair: (OLD, NEW) for pair in ids})
        path = Path(data) / "manifest-draft.json"
        manifest = json.loads(path.read_text(encoding="utf-8"))
        for n, row in enumerate(manifest["pairs"]):
            row["tier"] = "constructed" if n >= 6 else "public"
            ep, doc = export(data, row["id"], "R1", good_findings("R1"))
            doc["case_type"] = "partial_update" if 3 <= n < 6 else "value_change"
            ep.write_text(json.dumps(doc), encoding="utf-8")
        path.write_text(json.dumps(manifest), encoding="utf-8")
        return freeze_at(data)

    def test_sample_is_seeded_stratified_and_cannot_run_twice(self):
        with tempfile.TemporaryDirectory() as one, tempfile.TemporaryDirectory() as two:
            frozen = self.cohort(one)
            self.cohort(two)
            a, b = label_rounds.sample(one, 42), label_rounds.sample(two, 42)
            self.assertEqual(a, b)
            self.assertEqual(len(a["pairs"]), 3)
            self.assertEqual(len({(frozen["pairs"][p]["case_type"], frozen["pairs"][p]["tier"]) for p in a["pairs"]}), 3)
            for seed in range(12):
                pairs = label_rounds.stratified(frozen["pairs"], seed)
                self.assertEqual(len({(frozen["pairs"][p]["case_type"], frozen["pairs"][p]["tier"]) for p in pairs}), 3)
            self.assertGreater(len({tuple(label_rounds.stratified(frozen["pairs"], seed)) for seed in range(12)}), 1)
            path = Path(one) / "labelling" / label_rounds.SAMPLE
            original = path.read_bytes()
            with self.assertRaisesRegex(SystemExit, "refusing a second sample"):
                label_rounds.sample(one, 99)
            self.assertEqual(path.read_bytes(), original)
            doc = json.loads(original)
            doc["pairs"] = []
            path.write_text(json.dumps(doc), encoding="utf-8")
            with self.assertRaisesRegex(SystemExit, "sample does not match"):
                label_rounds.read_sample(one)

    def test_third_rounds_up_and_handles_more_strata_than_slots(self):
        entries = {"P-%03d" % i: {"case_type": "value_change", "tier": "public"} for i in range(25)}
        self.assertEqual(len(label_rounds.stratified(entries, 7)), 9)
        entries = {str(i): {"case_type": ct, "tier": "public"} for i, ct in enumerate(label_kit.case_types())}
        chosen = label_rounds.stratified(entries, 7)
        self.assertEqual(len(chosen), 5)
        self.assertEqual(len(set(chosen)), 5)

    def test_compare_rejects_early_r2_but_accepts_exact_fourteen_days(self):
        path, doc = self.ready()
        doc["exported"] = "2026-11-14T12:59:59Z"
        path.write_text(json.dumps(doc), encoding="utf-8")
        for operation in (lambda: reconcile.compare(self.tmp, "P-001"), lambda: reconcile.calibrate(self.tmp)):
            with self.assertRaisesRegex(SystemExit, "less than 14 days after R1 freeze"):
                operation()
        self.assertFalse((Path(self.tmp) / "labelling/reconcile/P-001-resolution.json").exists())
        doc["exported"] = "2026-11-14T15:00:00+02:00"
        path.write_text(json.dumps(doc), encoding="utf-8")
        self.assertEqual(reconcile.compare(self.tmp, "P-001")[0]["agreed"], 2)

    def test_bad_and_future_dates_fail_closed(self):
        path, doc = self.ready()
        for date in ("2026-11-14", "2026-11-14T13:00:00", "never", None):
            doc["exported"] = date
            path.write_text(json.dumps(doc), encoding="utf-8")
            with self.subTest(date=date), self.assertRaisesRegex(SystemExit, "ISO timestamp"):
                reconcile.compare(self.tmp, "P-001")
        doc["exported"] = "2026-12-01T13:00:00Z"
        path.write_text(json.dumps(doc), encoding="utf-8")
        with self.assertRaisesRegex(SystemExit, "future-dated"):
            reconcile.compare(self.tmp, "P-001")

    def test_r2_pages_are_blind_and_round_storage_and_imports_are_isolated(self):
        ep, doc = export(self.tmp, "P-001", "R1", good_findings("R1"))
        doc["findings"][0]["note"] = "SECRET-R1-LABEL"
        ep.write_text(json.dumps(doc), encoding="utf-8")
        self.ready()
        [page] = label_kit.write_kit(self.tmp, "R2")
        html = page.read_text(encoding="utf-8")
        self.assertNotIn("SECRET-R1-LABEL", html)
        self.assertNotIn("R1-1", html)
        self.assertNotIn("SHOULD-NOT-LEAK", html)
        data = json.loads(re.search(r'id="data">(.*?)</script>', html, re.S).group(1))
        self.assertEqual(set(data), {"pair", "round", "categories", "change_types", "case_types", "texts"})
        self.assertNotIn("case_type", data)
        self.assertEqual(data["round"], "R2")
        out = run_core('''var a = Object.assign({}, IN, {round: 'R1'});
            var e = makeExport(a, 'value_change', true, [], '2026-10-31T12:00:00Z');
            var b = makeExport(IN, 'value_change', true, [], '2026-11-14T13:00:00Z');
            console.log(JSON.stringify([storageKey(a) !== storageKey(IN), canImport(IN, e), canImport(IN, b)]));''', data)
        self.assertEqual(out, [True, False, True])
        self.assertIn('var KEY = storageKey(D);', html)
        self.assertIn('if (!canImport(D, d))', html)

    def test_export_requires_owner_case_type_in_page_and_loader(self):
        path, doc = export(self.tmp, "P-001", "R1", [])
        for value in (None, "", "deadline_change", []):
            doc["case_type"] = value
            path.write_text(json.dumps(doc), encoding="utf-8")
            self.assertIsNone(reconcile.load_labels(path, "P-001", "R1", self.tmp)[0])
        doc.pop("case_type")
        path.write_text(json.dumps(doc), encoding="utf-8")
        self.assertIsNone(reconcile.load_labels(path, "P-001", "R1", self.tmp)[0])
        data = {"pair": "P-001", "round": "R1", "case_types": label_kit.case_types(), "texts": doc["texts"]}
        out = run_core('''var rejected = false; try { makeExport(IN, '', true, [], 'now'); } catch(e) { rejected = true; }
            console.log(JSON.stringify([rejected, makeExport(IN, 'partial_update', true, [], 'now').case_type]));''', data)
        self.assertEqual(out, [True, "partial_update"])

    def test_p015_is_skipped_by_discovery_kit_manifest_and_freeze(self):
        make_data(self.tmp, {"P-001": (OLD, NEW), "P-015": (OLD, NEW)})
        self.assertEqual(label_kit.find_pairs(self.tmp), ["P-001"])
        self.assertEqual(set(label_rounds.manifest(self.tmp)), {"P-001"})
        written = label_kit.write_kit(self.tmp, pairs=["P-001", "P-015"])
        self.assertEqual([p.name for p in written], ["P-001.html"])
        frozen = freeze_at(self.tmp, ["P-001", "P-015"])
        self.assertEqual(list(frozen["pairs"]), ["P-001"])
        self.assertEqual(label_rounds.sample(self.tmp, 7)["pairs"], ["P-001"])
        self.assertEqual(reconcile.build(self.tmp, ["P-001", "P-015"]), [])
        with self.assertRaisesRegex(SystemExit, "excluded"):
            label_rounds.export_path(self.tmp, "P-015", "R1")

    def test_r2_pages_and_compare_require_sample_membership(self):
        freeze_at(self.tmp)
        with self.assertRaisesRegex(SystemExit, "cannot read"):
            label_kit.write_kit(self.tmp, "R2")
        label_rounds.sample(self.tmp, 7)
        for operation in (lambda: label_kit.write_kit(self.tmp, "R2", ["P-002"]),
                          lambda: reconcile.compare(self.tmp, "P-002")):
            with self.assertRaisesRegex(SystemExit, "sample"):
                operation()

    def test_build_uses_r1_without_resolution_and_keeps_frozen_sources(self):
        self.ready()
        export(self.tmp, "P-001", "R2", [])
        m = Path(self.tmp) / "manifest-draft.json"
        m.write_text(m.read_text(encoding="utf-8").replace('"public"', '"owner"'), encoding="utf-8")
        self.assertEqual(reconcile.build(self.tmp), [])
        rec = json.loads((Path(self.tmp) / "labelling/records.jsonl").read_text(encoding="utf-8"))
        self.assertEqual(len(rec["findings"]), 2)
        self.assertEqual(rec["labelled_by"], ["owner"])
        self.assertEqual(rec["split"], "unsplit")
        self.assertEqual(rec["tier"], "public")
        self.assertEqual(rec["provenance"]["rounds"], ["R1"])

    def test_build_rejects_incomplete_resolution_without_changing_output(self):
        path, doc = self.ready()
        self.assertEqual(reconcile.build(self.tmp), [])
        records = Path(self.tmp) / "labelling/records.jsonl"
        original = records.read_bytes()
        doc["findings"][0]["material"] = False
        path.write_text(json.dumps(doc), encoding="utf-8")
        reconcile.compare(self.tmp, "P-001")
        self.assertTrue(reconcile.build(self.tmp))
        self.assertEqual(records.read_bytes(), original)

    def test_calibrate_keeps_real_and_constructed_metrics_separate(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.cohort(tmp)
            chosen = label_rounds.sample(tmp, 7)["pairs"]
            frozen = label_rounds.read_freeze(tmp)["pairs"]
            for pair in chosen:
                fs = good_findings("R2") if frozen[pair]["tier"] == "constructed" else []
                export(tmp, pair, "R2", fs)
            report = reconcile.calibrate(tmp)
            real, constructed = report.split('Constructed pairs:')
            self.assertIn('Real pairs (non-gating): 2 sampled pairs', real)
            self.assertIn('all | 0/4 | 0.000', real)
            self.assertIn('1 sampled pairs', constructed)
            self.assertIn('all | 2/2 | 1.000', constructed)
            self.assertIn('other_material | 1/1 | 1.000', constructed)
            self.assertIn('kappa type | kappa material', report)

    def test_cli_accepts_every_new_subcommand(self):
        with contextlib.redirect_stdout(io.StringIO()) as output:
            with mock.patch.object(label_rounds, "utcnow", return_value=FROZEN):
                self.assertEqual(reconcile.main(["freeze", "--data", self.tmp, "--pairs", "P-001"]), 0)
            self.assertEqual(reconcile.main(["sample", "--data", self.tmp, "--seed", "7"]), 0)
            export(self.tmp, "P-001", "R2", good_findings("R2"))
            for cmd in ("compare", "build", "calibrate"):
                self.assertEqual(reconcile.main([cmd, "--data", self.tmp]), 0)
        self.assertIn('PASS build', output.getvalue())


if __name__ == "__main__":
    unittest.main()
