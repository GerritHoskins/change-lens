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
    doc = {"format": label_kit.FORMAT, "pair": pair, "round": who, "texts": texts,
           "reviewed_fully": reviewed, "exported": "2026-10-31T12:00:00Z" if who == "R1" else "2026-11-14T13:00:00Z", "case_type": "value_change", "findings": findings}
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
            self.assertEqual([p.relative_to(Path(tmp).resolve()).as_posix() for p in written],
                             ["labelling/R1/P-001.html"])
            html = written[0].read_text(encoding="utf-8")
        data = json.loads(re.search(r'<script type="application/json" id="data">(.*?)</script>', html, re.S).group(1))
        self.assertEqual((data["texts"]["old"]["text"], data["texts"]["new"]["text"], data["round"]), (OLD, TRICKY, "R1"))
        self.assertEqual(data["texts"]["new"]["sha256"], hashlib.sha256(TRICKY.encode("utf-8")).hexdigest())
        self.assertNotIn("SHOULD-NOT-LEAK", html)
        self.assertEqual(set(data), {"pair", "round", "categories", "change_types", "case_types", "texts"})

    def test_page_is_offline_and_script_safe(self):
        html = label_kit.page("P-001", "R1", {"old": ("anon/P-001/old.txt", "x</script><img src=x>&", "0" * 64),
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
        for pair, who in (("P-1", "R1"), ("P-001", "a"), ("../P-001", "R1")):
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
            make_data(tmp, {"P-014": ("short", body)})
            t0 = time.perf_counter()
            [page] = label_kit.write_kit(tmp)
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
        a = [finding("R1-1", "other_material", "changed", True, "€10,000", "€12,000"),
             finding("R1-2", "deliverable", "changed", True, "PNG", "SVG"),
             finding("R1-3", "approval", "changed", True, "signs off", "reviews")]
        b = [finding("R2-1", "other_material", "changed", True, "10,000", None),
             finding("R2-2", "other_material", "changed", True, "€10,000 excluding VAT", "€12,000"),
             finding("R2-3", "quantity", "changed", True, "PNG", "SVG"),
             finding("R2-4", "approval", "uncertain", False, None, "reviews the design")]
        pairs, only_a, only_b = reconcile.match(a, b)
        self.assertEqual([(x["id"], y["id"]) for x, y in pairs], [("R1-1", "R2-2"), ("R1-3", "R2-4")])
        self.assertEqual(([x["id"] for x in only_a], [y["id"] for y in only_b]), (["R1-2"], ["R2-1", "R2-3"]))
        self.assertEqual(reconcile.overlap(a[0], b[1]), 7 + 7)

    def test_agreement_and_kappa_hand_computed(self):
        types_a, types_b = ["changed", "changed", "removed", "added"], ["changed", "not_addressed", "removed", "added"]
        mat_a, mat_b = [True, True, False, True], [True, False, False, False]
        pairs = [({"change_type": x, "material": m}, {"change_type": y, "material": n})
                 for x, y, m, n in zip(types_a, types_b, mat_a, mat_b)]
        s = reconcile.agreement(pairs, [{"change_type": "added", "material": True}], [])
        # change_type: po 3/4; pe .5*.25 + .25*.25 + .25*.25 = .25; kappa (.75-.25)/.75 = 2/3
        # material: po 2/4; pe .75*.25 + .25*.75 = .375; kappa .125/.625 = .2; items 5, of which 2 agree on both
        self.assertEqual((s["items"], s["matched"], s["only_r1"], s["only_r2"], s["agreed"]), (5, 4, 1, 0, 2))
        self.assertAlmostEqual(s["item_agreement"], 0.4)
        self.assertAlmostEqual(s["kappa_change_type"], 2 / 3)
        self.assertAlmostEqual(s["kappa_material"], 0.2)

    def test_same_verdict_on_different_evidence_still_needs_resolving(self):
        a = [finding("R1-1", "other_material", "changed", True, "€10,000", "€12,000")]
        b = [finding("R2-1", "other_material", "changed", True, "€10,000 excluding VAT", "€12,000"),
             finding("R2-2", "other_material", "changed", True, "€10,000", "€12,000")]
        agreed, items = reconcile.disagreements([(a[0], b[0])], [], [], "R1", "R2")
        self.assertEqual((agreed, [i["disagreement"] for i in items]), ([], ["evidence or values differ"]))
        agreed, items = reconcile.disagreements([(a[0], b[1])], [], [], "R1", "R2")
        self.assertEqual((agreed, items), ([{"r1": "R1-1", "r2": "R2-2"}], []))

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
        path, doc = export(self.tmp, "P-001", "R1", good_findings("R1"))
        mutate(doc)
        path.write_text(json.dumps(doc), encoding="utf-8")
        return reconcile.load_labels(path, "P-001", "R1", self.tmp)

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
            "expected P-001/R1": lambda d: d.__setitem__("round", "R2"),
            "not marked as fully reviewed": lambda d: d.__setitem__("reviewed_fully", "yes"),
            "findings must be a list": lambda d: d.__setitem__("findings", {}),
            "needs storage_ref and sha256": lambda d: d["texts"]["old"].pop("sha256"),
            "not this pair's stored text": lambda d: d["texts"]["new"].__setitem__("storage_ref", "anon/P-002/new.txt"),
            "sha256 mismatch": lambda d: d["texts"]["new"].__setitem__("sha256", "0" * 64),
            "not in ['deliverable'": f0("category", "budget"),
            "id must start with R1-": f0("id", "R2-1"),
            "duplicate finding ids": lambda d: d["findings"][1].__setitem__("id", "R1-1"),
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
        path = Path(self.tmp) / "labelling/returned/labels-P-001-R1.json"
        for content, expected in ((b"{", "cannot read labels"), (b"[]", "must be a JSON object"), (b"\xff", "cannot read labels")):
            path.write_bytes(content)
            self.assertIn(expected, reconcile.load_labels(path, "P-001", "R1", self.tmp)[1][0])
        self.assertIn("cannot read labels", reconcile.load_labels(path.with_name("missing.json"), "P-001", "R1", self.tmp)[1][0])


EVIDENCE_KEYS = ("evidence_old", "evidence_new", "old_value", "new_value")


if __name__ == "__main__":
    unittest.main()
