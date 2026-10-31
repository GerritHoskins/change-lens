"""Tests for the labelling kit and reconciliation, on synthetic pairs only (run: python -m unittest discover -s scripts/eval).

The page's offset logic is JavaScript; these tests run its CORE block under Node, so Node is
required: a missing Node fails the suite rather than skipping it.
"""
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import label_kit  # noqa: E402
import reconcile  # noqa: E402
import validate  # noqa: E402

OLD = ("Website brief v1\r\nBudget: €10,000 excluding VAT — fixed\r\nDelivery: 14 March 2027\r\n"
       "Owner: Zoë Ångström signs off the design\r\n\x0cPage 2\r\nAssets: 12 icons as PNG 😀\r\n")
NEW = ("Website brief v2\r\nBudget: €12,000 excluding VAT — fixed\r\nDelivery: 14 March 2027\r\n"
       "Owner: Zoë Ångström reviews the design\r\n\x0cPage 2\r\nAssets: 12 icons as SVG 😀\r\nHosting: added\r\n")
TRICKY = "a€\r\nb😀c\rd\n\x0ce f\x85g\r\n\r\n𝔘nit\tend\n"


def node():
    exe = shutil.which("node")
    if not exe:
        raise AssertionError("Node.js is required to test the labelling page's offset logic")
    return exe


def run_core(body, payload):
    """Run the template's CORE functions plus body under Node; body prints JSON from IN."""
    tpl = label_kit.TEMPLATE.read_text(encoding="utf-8")
    core = re.search(r"// CORE-BEGIN.*?// CORE-END", tpl, re.S).group(0)
    with tempfile.TemporaryDirectory() as tmp:
        src, inp = Path(tmp) / "t.js", Path(tmp) / "in.json"
        inp.write_text(json.dumps(payload), encoding="utf-8")
        src.write_text(core + "\nvar IN = JSON.parse(require('fs').readFileSync(%s, 'utf8'));\n%s" % (
            json.dumps(str(inp)), body), encoding="utf-8")
        out = subprocess.run([node(), str(src)], capture_output=True, timeout=60)
    if out.returncode:
        raise AssertionError(out.stderr.decode("utf-8", "replace"))
    return json.loads(out.stdout.decode("utf-8"))


def py_lines(text):
    """Expected (start code point, line text) using the page's rule: split on CRLF, CR or LF only."""
    starts = [0]
    for m in re.finditer(r"\r\n|\r|\n", text):
        starts.append(m.end())
    ends = [m.start() for m in re.finditer(r"\r\n|\r|\n", text)] + [len(text)]
    return [(s, text[s:e]) for s, e in zip(starts, ends)]


def make_data(root, pairs, tier="public"):
    """Synthetic private-storage layout: anon texts plus a manifest with hint fields."""
    manifest = {"pairs": []}
    for pair, (old, new) in pairs.items():
        entry = {"id": pair, "tier": tier, "licence": "test-only", "likely_case_types": "HINT-SHOULD-NOT-LEAK",
                 "note": "NOTE-SHOULD-NOT-LEAK"}
        for side, text in (("old", old), ("new", new)):
            ref = label_kit.text_ref(pair, side)
            (Path(root) / ref).parent.mkdir(parents=True, exist_ok=True)
            (Path(root) / ref).write_bytes(text.encode("utf-8"))
            entry[side] = {"url": "https://example.invalid/%s/%s" % (pair, side), "retrieved": "2026-10-30",
                           "format": "text", "storage_ref": ref, "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest()}
        manifest["pairs"].append(entry)
    (Path(root) / "manifest-draft.json").write_text(json.dumps(manifest), encoding="utf-8")


def span(text, needle):
    s = text.index(needle)
    return {"start": s, "end": s + len(needle)}


def finding(fid, category, change_type, material, old=None, new=None, note=None):
    f = {"id": fid, "category": category, "change_type": change_type, "material": material}
    if old:
        f["old_value"], f["evidence_old"] = old, span(OLD, old)
    if new:
        f["new_value"], f["evidence_new"] = new, span(NEW, new)
    if note:
        f["note"] = note
    return f


def export(root, pair, who, findings, reviewed=True):
    texts = {}
    for side in ("old", "new"):
        ref = label_kit.text_ref(pair, side)
        texts[side] = {"storage_ref": ref, "sha256": hashlib.sha256((Path(root) / ref).read_bytes()).hexdigest()}
    doc = {"format": label_kit.FORMAT, "pair": pair, "labeller": who, "texts": texts,
           "reviewed_fully": reviewed, "exported": "2026-10-31T12:00:00Z", "findings": findings}
    path = Path(root) / "labelling" / "returned" / ("labels-%s-%s.json" % (pair, who))
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path, doc


class Offsets(unittest.TestCase):
    def test_selection_offsets_round_trip_through_python_slicing(self):
        lines = py_lines(TRICKY)
        sels = []  # every pair of code-point boundaries, in UTF-16 units per line as the DOM reports them
        for i, (_, t) in enumerate(lines):
            units = [len(t[:k].encode("utf-16-le")) // 2 for k in range(len(t) + 1)]
            for j, (_, t2) in enumerate(lines[i:i + 2], i):
                units2 = [len(t2[:k].encode("utf-16-le")) // 2 for k in range(len(t2) + 1)]
                sels += [[i, a, j, b] for a in units for b in units2 if (j, b) > (i, a)]
        out = run_core("""var B = buildLines(IN.text), cps = Array.from(IN.text);
            console.log(JSON.stringify({lines: B.lines.map(function (L) { return [L.s, L.t, display(L.t).length]; }), total: B.total,
              sels: IN.sels.map(function (x) { var a = B.lines[x[0]], b = B.lines[x[2]];
                var s = a.s + cpCount(a.t, x[1]), e = b.s + cpCount(b.t, x[3]); return [s, e, cps.slice(s, e).join('')]; })}));""",
                       {"text": TRICKY, "sels": sels})
        self.assertEqual([[s, t] for s, t, _ in out["lines"]], [[s, t] for s, t in lines])
        self.assertEqual(out["total"], len(TRICKY))
        for (_, t, shown), (_, pt) in zip(out["lines"], lines):
            self.assertEqual(shown, len(pt.encode("utf-16-le")) // 2, "display() must keep UTF-16 length")
        self.assertGreater(len(sels), 100)
        for (i, a, j, b), (s, e, value) in zip(sels, out["sels"]):
            exp_s = lines[i][0] + len(lines[i][1].encode("utf-16-le")[:2 * a].decode("utf-16-le"))
            exp_e = lines[j][0] + len(lines[j][1].encode("utf-16-le")[:2 * b].decode("utf-16-le"))
            self.assertEqual((s, e), (exp_s, exp_e))
            self.assertEqual(TRICKY[s:e], value)
            self.assertEqual(validate.locator_errors({"start": s, "end": e}, value, "text", TRICKY, "t"), [])

    def test_line_lookup_and_rules_in_page_core(self):
        out = run_core("""var B = buildLines(IN.text);
            console.log(JSON.stringify({at: IN.at.map(function (v) { return lineAt(B.lines, 's', v); }),
              rules: IN.rules.map(function (f) { return checkFinding(f, IN.cats, IN.types).length; })}));""",
                       {"text": TRICKY, "at": [0, 2, 4, 8, len(TRICKY)], "cats": ["quantity", "structure"],
                        "types": ["added", "removed", "changed", "equivalent"],
                        "rules": [{"category": "quantity", "change_type": "changed", "material": True, "evidence_old": {}},
                                  {"category": "quantity", "change_type": "added", "material": True, "evidence_old": {}},
                                  {"category": "quantity", "change_type": "removed", "material": True, "evidence_new": {}},
                                  {"category": "structure", "change_type": "changed", "material": True, "evidence_old": {}},
                                  {"category": "quantity", "change_type": "equivalent", "material": True, "evidence_old": {}},
                                  {"category": "quantity", "change_type": "changed", "evidence_old": {}},
                                  {"category": "", "change_type": "changed", "material": False, "evidence_old": {}},
                                  {"category": "quantity", "change_type": "changed", "material": False}]})
        self.assertEqual(out["at"], [0, 0, 1, 2, len(py_lines(TRICKY)) - 1])
        self.assertEqual(out["rules"], [0, 1, 1, 1, 1, 1, 1, 1])

    def test_page_embeds_the_exact_stored_text_and_nothing_else(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_data(tmp, {"P-001": (OLD, TRICKY)})
            written = label_kit.write_kit(tmp)
            self.assertEqual(sorted(p.relative_to(Path(tmp).resolve()).as_posix() for p in written),
                             ["labelling/A/P-001.html", "labelling/B/P-001.html"])
            a, b = (p.read_text(encoding="utf-8") for p in written)
        for html, who in ((a, "A"), (b, "B")):
            data = json.loads(re.search(r'<script type="application/json" id="data">(.*?)</script>', html, re.S).group(1))
            self.assertEqual((data["texts"]["old"]["text"], data["texts"]["new"]["text"], data["labeller"]), (OLD, TRICKY, who))
            self.assertEqual(data["texts"]["new"]["sha256"], hashlib.sha256(TRICKY.encode("utf-8")).hexdigest())
            self.assertNotIn("SHOULD-NOT-LEAK", html)
            self.assertEqual(set(data), {"pair", "labeller", "categories", "change_types", "texts"})
        self.assertEqual(a.replace("labeller A", "labeller B").replace('"labeller": "A"', '"labeller": "B"'), b)

    def test_page_is_offline_and_script_safe(self):
        html = label_kit.page("P-001", "A", {"old": ("anon/P-001/old.txt", "x</script><img src=x>&", "0" * 64),
                                              "new": ("anon/P-001/new.txt", "y", "1" * 64)})
        self.assertIn("default-src 'none'", html)
        self.assertNotRegex(html, r"https?:|(src|href)\s*=\s*[\"']")
        self.assertEqual(html.count("</script>"), 2)
        data = re.search(r'id="data">(.*?)</script>', html, re.S).group(1)
        self.assertFalse(set("<>&") & set(data), "embedded JSON must escape <, > and &")

    def test_non_utf8_text_and_bad_ids_fail_closed(self):
        with tempfile.TemporaryDirectory() as tmp:
            make_data(tmp, {"P-001": (OLD, NEW)})
            (Path(tmp) / "anon/P-001/new.txt").write_bytes(b"caf\xe9")
            with self.assertRaisesRegex(ValueError, "not valid UTF-8"):
                label_kit.write_kit(tmp)
        for pair, who in (("P-1", "A"), ("P-001", "a"), ("../P-001", "A")):
            with self.assertRaises(ValueError):
                label_kit.page(pair, who, {})

    def test_refuses_to_write_inside_git(self):
        with self.assertRaisesRegex(SystemExit, "inside a git working tree"):
            label_kit.write_kit(Path(__file__).resolve().parent)


class LargeFile(unittest.TestCase):
    def test_large_pair_generates_and_splits_quickly(self):
        body = "".join("Q%05d. Will the deadline of 14 March move? — Answer: no, it stays; fee €%d.\r\n" % (i, i)
                       for i in range(4800))
        self.assertGreater(len(body), 374000)
        with tempfile.TemporaryDirectory() as tmp:
            make_data(tmp, {"P-015": ("short", body)})
            t0 = time.perf_counter()
            [page, _] = label_kit.write_kit(tmp)
            html = page.read_text(encoding="utf-8")
            self.assertLess(time.perf_counter() - t0, 10)
        self.assertLess(len(html), 3 * len(body))
        self.assertNotIn('class="row"', html)  # rows are created lazily, chunk by chunk
        out = run_core("""var t0 = Date.now(), B = buildLines(IN.text), ms = Date.now() - t0, k = 0;
            for (var i = 0; i < B.lines.length; i += CHUNK) k++;
            console.log(JSON.stringify({n: B.lines.length, total: B.total, ms: ms, chunks: k, chunk: CHUNK}));""", {"text": body})
        self.assertEqual((out["n"], out["total"]), (body.count("\r\n") + 1, len(body)))
        self.assertLess(out["ms"], 2000)
        self.assertLessEqual(out["chunk"], 500)
        self.assertGreater(out["chunks"], 9)


class Agreement(unittest.TestCase):
    def test_matching_needs_category_and_overlap_and_prefers_larger_overlap(self):
        a = [finding("A-1", "other_material", "changed", True, "€10,000", "€12,000"),
             finding("A-2", "deliverable", "changed", True, "PNG", "SVG"),
             finding("A-3", "approval", "changed", True, "signs off", "reviews")]
        b = [finding("B-1", "other_material", "changed", True, "10,000", None),
             finding("B-2", "other_material", "changed", True, "€10,000 excluding VAT", "€12,000"),
             finding("B-3", "quantity", "changed", True, "PNG", "SVG"),
             finding("B-4", "approval", "uncertain", False, None, "reviews the design")]
        pairs, only_a, only_b = reconcile.match(a, b)
        self.assertEqual([(x["id"], y["id"]) for x, y in pairs], [("A-1", "B-2"), ("A-3", "B-4")])
        self.assertEqual(([x["id"] for x in only_a], [y["id"] for y in only_b]), (["A-2"], ["B-1", "B-3"]))
        self.assertEqual(reconcile.overlap(a[0], b[1]), 7 + 7)

    def test_agreement_and_kappa_hand_computed(self):
        types_a, types_b = ["changed", "changed", "removed", "added"], ["changed", "not_addressed", "removed", "added"]
        mat_a, mat_b = [True, True, False, True], [True, False, False, False]
        pairs = [({"change_type": x, "material": m}, {"change_type": y, "material": n})
                 for x, y, m, n in zip(types_a, types_b, mat_a, mat_b)]
        s = reconcile.agreement(pairs, [{"change_type": "added", "material": True}], [])
        # change_type: po 3/4; pe .5*.25 + .25*.25 + .25*.25 = .25; kappa (.75-.25)/.75 = 2/3
        # material: po 2/4; pe .75*.25 + .25*.75 = .375; kappa .125/.625 = .2; items 5, of which 2 agree on both
        self.assertEqual((s["items"], s["matched"], s["only_a"], s["only_b"], s["agreed"]), (5, 4, 1, 0, 2))
        self.assertAlmostEqual(s["item_agreement"], 0.4)
        self.assertAlmostEqual(s["kappa_change_type"], 2 / 3)
        self.assertAlmostEqual(s["kappa_material"], 0.2)

    def test_same_verdict_on_different_evidence_still_needs_resolving(self):
        a = [finding("A-1", "other_material", "changed", True, "€10,000", "€12,000")]
        b = [finding("B-1", "other_material", "changed", True, "€10,000 excluding VAT", "€12,000"),
             finding("B-2", "other_material", "changed", True, "€10,000", "€12,000")]
        agreed, items = reconcile.disagreements([(a[0], b[0])], [], [], "A", "B")
        self.assertEqual((agreed, [i["disagreement"] for i in items]), ([], ["evidence or values differ"]))
        agreed, items = reconcile.disagreements([(a[0], b[1])], [], [], "A", "B")
        self.assertEqual((agreed, items), ([{"a": "A-1", "b": "B-2"}], []))

    def test_kappa_edge_cases(self):
        self.assertIsNone(reconcile.kappa([], []))
        self.assertIsNone(reconcile.kappa(["changed"] * 3, ["changed"] * 3))
        self.assertIsNone(reconcile.kappa(["a", "b"], ["a"]))
        self.assertAlmostEqual(reconcile.kappa(["a", "b"], ["b", "a"]), -1.0)
        self.assertIsNone(reconcile.agreement([], [], [])["item_agreement"])


def good_findings(who):
    return [finding(who + "-1", "other_material", "changed", True, "€10,000", "€12,000"),
            finding(who + "-2", "deliverable", "changed", True, "PNG", "SVG")]


class LabelValidation(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        make_data(self.tmp, {"P-001": (OLD, NEW), "P-002": (NEW, OLD)})

    def load(self, mutate):
        path, doc = export(self.tmp, "P-001", "A", good_findings("A"))
        mutate(doc)
        path.write_text(json.dumps(doc), encoding="utf-8")
        return reconcile.load_labels(path, "P-001", "A", self.tmp)

    def test_valid_labels_load(self):
        doc, errs = self.load(lambda d: None)
        self.assertEqual(errs, [])
        self.assertEqual(len(doc["sha256"]), 64)

    def test_every_failure_path(self):
        def f0(key, value):
            return lambda d: d["findings"][0].__setitem__(key, value)

        def drop(key):
            return lambda d: d["findings"][0].pop(key)
        cases = {
            "keys must be exactly": lambda d: d.pop("exported"),
            "format is not": lambda d: d.__setitem__("format", "other/1"),
            "expected P-001/A": lambda d: d.__setitem__("labeller", "B"),
            "not marked as fully reviewed": lambda d: d.__setitem__("reviewed_fully", "yes"),
            "findings must be a list": lambda d: d.__setitem__("findings", {}),
            "needs storage_ref and sha256": lambda d: d["texts"]["old"].pop("sha256"),
            "not this pair's stored text": lambda d: d["texts"]["new"].__setitem__("storage_ref", "anon/P-002/new.txt"),
            "sha256 mismatch": lambda d: d["texts"]["new"].__setitem__("sha256", "0" * 64),
            "not in ['deliverable'": f0("category", "budget"),
            "id must start with A-": f0("id", "B-1"),
            "duplicate finding ids": lambda d: d["findings"][1].__setitem__("id", "A-1"),
            "slices to": f0("old_value", "€10,001"),
            "outside the text": f0("evidence_new", {"start": 5, "end": 10 ** 6}),
            "evidence_old is empty": f0("evidence_old", {"start": 5, "end": 5}),
            "a text locator needs start and end": f0("evidence_old", {"start": 1, "end": 2, "page": 1}),
            "added needs evidence in the new version": lambda d: d["findings"][0].update(
                change_type="added", material=True) or d["findings"][0].pop("evidence_new") and d["findings"][0].pop("new_value"),
            "removed needs evidence in the old version": lambda d: d["findings"][0].update(change_type="removed") or (
                d["findings"][0].pop("evidence_old"), d["findings"][0].pop("old_value")),
            "never material": f0("category", "structure"),
            "old_value without evidence_old": drop("evidence_old"),
            "evidence needs a labelled value": drop("new_value"),
            "matches none of anyOf": lambda d: [d["findings"][0].pop(k) for k in EVIDENCE_KEYS],
            "unexpected property": f0("confidence", 0.9),
        }
        for expected, mutate in cases.items():
            with self.subTest(expected):
                doc, errs = self.load(mutate)
                self.assertIsNone(doc)
                self.assertTrue(any(expected in e for e in errs), errs)
        path = Path(self.tmp) / "labelling/returned/labels-P-001-A.json"
        for content, expected in ((b"{", "cannot read labels"), (b"[]", "must be a JSON object"), (b"\xff", "cannot read labels")):
            path.write_bytes(content)
            self.assertIn(expected, reconcile.load_labels(path, "P-001", "A", self.tmp)[1][0])
        self.assertIn("cannot read labels", reconcile.load_labels(path.with_name("missing.json"), "P-001", "A", self.tmp)[1][0])


EVIDENCE_KEYS = ("evidence_old", "evidence_new", "old_value", "new_value")


class Finalize(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.tmp)
        make_data(self.tmp, {"P-001": (OLD, NEW), "P-003": (OLD, OLD)})
        a = good_findings("A") + [finding("A-3", "approval", "changed", True, "signs off", "reviews")]
        b = good_findings("B")[:1] + [finding("B-2", "deliverable", "uncertain", False, "PNG", "SVG")]
        export(self.tmp, "P-001", "A", a)
        export(self.tmp, "P-001", "B", b)
        self.res = Path(self.tmp) / "labelling/reconcile/P-001-resolution.json"

    def fill(self, change):
        res = json.loads(self.res.read_text(encoding="utf-8"))
        change(res)
        self.res.write_text(json.dumps(res), encoding="utf-8")
        return reconcile.finalize(self.tmp, "P-001")

    def decide(self, res, d1="A", d2="drop", reason="agreed in call", case_types=("value_change", "partial_update")):
        res["case_types"] = list(case_types)
        for it, d in zip(res["items"], (d1, d2)):
            it["decision"], it["reason"], it["finding"] = d, reason, None

    def test_compare_writes_worksheet_and_skeleton(self):
        stats, _ = reconcile.compare(self.tmp, "P-001")
        self.assertEqual((stats["items"], stats["matched"], stats["agreed"]), (3, 2, 1))
        res = json.loads(self.res.read_text(encoding="utf-8"))
        self.assertEqual(res["agreed"], [{"a": "A-1", "b": "B-1"}])
        self.assertEqual([(i["a"], i["b"], i["decision"]) for i in res["items"]], [("A-2", "B-2", ""), ("A-3", None, "")])
        self.assertIn('change_type: A "changed" / B "uncertain"', res["items"][0]["disagreement"])
        sheet = (Path(self.tmp) / "labelling/reconcile/P-001-worksheet.md").read_text(encoding="utf-8")
        self.assertIn("## D2: only A found this", sheet)
        with self.assertRaisesRegex(SystemExit, "may hold decisions"):
            reconcile.compare(self.tmp, "P-001")

    def test_compare_refuses_invalid_labels(self):
        export(self.tmp, "P-001", "B", good_findings("B"), reviewed=False)
        with self.assertRaisesRegex(SystemExit, "draft export"):
            reconcile.compare(self.tmp, "P-001")

    def test_finalize_builds_a_valid_record(self):
        reconcile.compare(self.tmp, "P-001")
        self.assertEqual(self.fill(lambda r: self.decide(r, "B", "edit") or r["items"][1].__setitem__(
            "finding", finding("x", "approval", "changed", True, "signs off the design", "reviews the design"))), [])
        records = Path(self.tmp) / "labelling/records.jsonl"
        [rec] = [json.loads(x) for x in records.read_text(encoding="utf-8").splitlines()]
        self.assertEqual((rec["tier"], rec["split"], rec["labelled_by"]), ("public", "unsplit", ["A", "B"]))
        self.assertEqual(rec["source"], {"kind": "rfp_addendum", "url": "https://example.invalid/P-001/new",
                                         "licence": "test-only", "retrieved": "2026-10-30", "anonymised": True})
        self.assertEqual([(f["id"], f["change_type"]) for f in rec["findings"]], [("F1", "changed"), ("F2", "uncertain"), ("F3", "changed")])
        self.assertEqual(rec["reconciliation"][0]["finding"], "F2")
        self.assertEqual(rec["reconciliation"][1]["resolution"], "edit: agreed in call")
        self.assertEqual(validate.validate_file(str(records), texts_root=self.tmp), (1, []))
        self.assertEqual(self.fill(lambda r: self.decide(r, "A", "drop")), [])  # rerun replaces, never duplicates
        [rec] = [json.loads(x) for x in records.read_text(encoding="utf-8").splitlines()]
        self.assertEqual(rec["reconciliation"][1]["finding"], "none (dropped A-3)")

    def test_no_change_pair_finalizes_with_no_findings(self):
        export(self.tmp, "P-003", "A", [])
        export(self.tmp, "P-003", "B", [])
        self.assertEqual(reconcile.compare(self.tmp, "P-003")[0]["items"], 0)
        res = Path(self.tmp) / "labelling/reconcile/P-003-resolution.json"
        r = json.loads(res.read_text(encoding="utf-8"))
        r["case_types"] = ["no_change"]
        res.write_text(json.dumps(r), encoding="utf-8")
        self.assertEqual(reconcile.finalize(self.tmp, "P-003"), [])

    def test_every_resolution_failure_path(self):
        def stale(r):
            export(self.tmp, "P-001", "B", good_findings("B"))

        def manifest(r):
            m = Path(self.tmp) / "manifest-draft.json"
            m.write_text(m.read_text(encoding="utf-8").replace('"public"', '"owner"'), encoding="utf-8")
        cases = {
            "decision must be one of": lambda r: self.decide(r, "A", "B"),
            "give the reason": lambda r: self.decide(r, reason=" "),
            "required for edit and only for edit": lambda r: self.decide(r, "A", "edit"),
            "case_types must name": lambda r: self.decide(r, case_types=()),
            "not in ['value_change'": lambda r: self.decide(r, case_types=("deadline_change",)),
            "labels changed since compare": lambda r: self.decide(r) or stale(r),
            "do not match the labels": lambda r: self.decide(r) or r["items"].pop(),
            "format or labellers": lambda r: self.decide(r) or r.__setitem__("labellers", ["B", "A"]),
            "expected public": lambda r: self.decide(r) or manifest(r),
            "slices to": lambda r: self.decide(r, "A", "edit") or r["items"][1].__setitem__(
                "finding", dict(finding("x", "approval", "changed", True, "signs off"), old_value="signs of")),
            "never material": lambda r: self.decide(r, "A", "edit") or r["items"][1].__setitem__(
                "finding", finding("x", "structure", "equivalent", True, "signs off", "reviews")),
            "is not the resolution for": lambda r: r.__setitem__("pair", "P-002"),
        }
        for expected, change in cases.items():
            with self.subTest(expected):
                make_data(self.tmp, {"P-001": (OLD, NEW), "P-003": (OLD, OLD)})
                export(self.tmp, "P-001", "B", good_findings("B")[:1] + [finding("B-2", "deliverable", "uncertain", False, "PNG", "SVG")])
                reconcile.compare(self.tmp, "P-001", force=True)
                errs = self.fill(change)
                self.assertTrue(any(expected in e for e in errs), errs)
                self.assertFalse((Path(self.tmp) / "labelling/records.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
