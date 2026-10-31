"""Compare two labellers' exports for a real pair and turn the reconciled labels into records (07 §5).

    python scripts/eval/reconcile.py compare  --data <dir> --pairs P-001 [P-002 ...] [--labellers A B]
    python scripts/eval/reconcile.py finalize --data <dir> --pair P-001

compare loads <data>/labelling/returned/labels-<pair>-<labeller>.json for both labellers,
fails closed on any invalid label (schema, rules, spans that do not slice to their value,
texts that are not the stored ones), matches findings on overlapping evidence plus category,
prints item-level agreement and Cohen's kappa, and writes reconcile/<pair>-worksheet.md and
<pair>-resolution.json. The labellers resolve every item together in the resolution file;
finalize checks it against the labels, builds the schema record and validates it with
validate.py before adding it to labelling/records.jsonl.
"""
import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import label_kit  # noqa: E402
import validate  # noqa: E402

KEYS = {"format", "pair", "labeller", "texts", "reviewed_fully", "exported", "findings"}
RESOLUTION = "change-lens-resolution/1"
SOURCE_KIND = "rfp_addendum"  # every D-3 pair is a US or Canadian RFP/RFSO revision
EVIDENCE = ("evidence_old", "evidence_new", "old_value", "new_value")


def _schema():
    with open(validate.SCHEMA, encoding="utf-8") as fh:
        return json.load(fh)


def rule_errors(f):
    """07 §4 rules beyond the schema; label_kit.html checkFinding mirrors them."""
    errs = []
    for side in ("old", "new"):
        span, value = f.get("evidence_" + side), f.get(side + "_value")
        if value is not None and span is None:
            errs.append("%s_value without evidence_%s" % (side, side))
        if span is not None and span.get("end", 0) <= span.get("start", 0):
            errs.append("evidence_%s is empty" % side)
    if f["change_type"] == "added" and "evidence_new" not in f:
        errs.append("added needs evidence in the new version")
    if f["change_type"] in ("removed", "not_addressed") and "evidence_old" not in f:
        errs.append("%s needs evidence in the old version" % f["change_type"])
    if (f["category"] == "structure" or f["change_type"] == "equivalent") and f["material"]:
        errs.append("structure and equivalent findings are never material")
    return errs


def check_findings(pair, versions, findings, data, prefix=None):
    """Schema, rule and span errors for findings against the stored texts."""
    schema, errs = _schema(), []
    for i, f in enumerate(findings):
        where = "%s finding %d" % (pair, i)
        e = validate.check(f, schema["$defs"]["finding"], schema, where)
        if not e:
            e = ["%s %s: %s" % (pair, f["id"], x) for x in rule_errors(f)]
            if prefix and not f["id"].startswith(prefix + "-"):
                e.append("%s %s: id must start with %s-" % (pair, f["id"], prefix))
        errs += e
    if not errs:
        errs += validate.check_texts({"id": pair, "old": versions["old"], "new": versions["new"],
                                      "findings": findings}, data)
    return errs


def load_labels(path, pair, labeller, data):
    """(document, errors) for one labeller's export; any error makes the document unusable."""
    try:
        raw = Path(path).read_bytes()
        doc = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError) as exc:
        return None, ["%s: cannot read labels (%s)" % (path, exc)]
    if not isinstance(doc, dict):
        return None, ["%s: labels must be a JSON object" % path]
    errs = []
    if set(doc) != KEYS:
        errs.append("%s: keys must be exactly %s" % (path, sorted(KEYS)))
    if doc.get("format") != label_kit.FORMAT:
        errs.append("%s: format is not %s" % (path, label_kit.FORMAT))
    if doc.get("pair") != pair or doc.get("labeller") != labeller:
        errs.append("%s: labels are for %r/%r, expected %s/%s" % (path, doc.get("pair"), doc.get("labeller"), pair, labeller))
    if doc.get("reviewed_fully") is not True:
        errs.append("%s: not marked as fully reviewed (draft export)" % path)
    if not isinstance(doc.get("findings"), list):
        errs.append("%s: findings must be a list" % path)
    versions = {}
    texts = doc.get("texts") if isinstance(doc.get("texts"), dict) else {}
    for side in label_kit.SIDES:
        t = texts.get(side)
        if not isinstance(t, dict) or set(t) != {"storage_ref", "sha256"}:
            errs.append("%s: texts.%s needs storage_ref and sha256" % (path, side))
            continue
        if t["storage_ref"] != label_kit.text_ref(pair, side):
            errs.append("%s: texts.%s is %r, not this pair's stored text" % (path, side, t["storage_ref"]))
            continue
        versions[side] = {"format": "text", "sha256": t["sha256"], "storage_ref": t["storage_ref"]}
        try:
            validate.read_version(versions[side], data)
        except Exception as exc:  # noqa: BLE001 - every storage failure is a label error
            errs.append("%s: texts.%s: %s" % (path, side, exc))
    if errs:
        return None, errs
    errs = check_findings(pair, versions, doc["findings"], data, prefix=labeller)
    doc["sha256"] = hashlib.sha256(raw).hexdigest()
    return (None if errs else doc), errs


def overlap(a, b):
    """Characters of evidence shared by two findings, summed over both sides."""
    n = 0
    for k in ("evidence_old", "evidence_new"):
        x, y = a.get(k), b.get(k)
        if x and y:
            n += max(0, min(x["end"], y["end"]) - max(x["start"], y["start"]))
    return n


def match(fa, fb):
    """One-to-one matches on same category and overlapping evidence, largest overlap first."""
    cands = sorted((-overlap(a, b), i, j) for i, a in enumerate(fa) for j, b in enumerate(fb)
                   if a["category"] == b["category"] and overlap(a, b) > 0)
    used_a, used_b, pairs = set(), set(), []
    for _, i, j in cands:
        if i not in used_a and j not in used_b:
            used_a.add(i)
            used_b.add(j)
            pairs.append((fa[i], fb[j]))
    pairs.sort(key=lambda p: fa.index(p[0]))
    return (pairs, [a for i, a in enumerate(fa) if i not in used_a],
            [b for j, b in enumerate(fb) if j not in used_b])


def kappa(xs, ys):
    """Cohen's kappa for two equal-length label lists; None when undefined (no items, or chance agreement is 1)."""
    n = len(xs)
    if n == 0 or n != len(ys):
        return None
    po = sum(x == y for x, y in zip(xs, ys)) / n
    pe = sum((xs.count(k) / n) * (ys.count(k) / n) for k in set(xs) | set(ys))
    return None if pe == 1 else (po - pe) / (1 - pe)


def agreement(pairs, only_a, only_b):
    """Item-level agreement: an item agrees when both labellers found it with the same change_type and material."""
    items = len(pairs) + len(only_a) + len(only_b)
    agree = sum(a["change_type"] == b["change_type"] and a["material"] == b["material"] for a, b in pairs)
    return {"items": items, "matched": len(pairs), "only_a": len(only_a), "only_b": len(only_b),
            "agreed": agree, "item_agreement": agree / items if items else None,
            "kappa_change_type": kappa([a["change_type"] for a, _ in pairs], [b["change_type"] for _, b in pairs]),
            "kappa_material": kappa([a["material"] for a, _ in pairs], [b["material"] for _, b in pairs])}


def disagreements(pairs, only_a, only_b, la, lb):
    """(agreed matches, items to resolve); a matched item with identical labels and evidence is agreed."""
    agreed, items = [], []
    for a, b in pairs:
        diff = ["%s: %s %s / %s %s" % (k, la, json.dumps(a[k]), lb, json.dumps(b[k]))
                for k in ("change_type", "material") if a[k] != b[k]]
        if any(a.get(k) != b.get(k) for k in EVIDENCE):
            diff.append("evidence or values differ")
        if diff:
            items.append({"a": a["id"], "b": b["id"], "disagreement": "; ".join(diff)})
        else:
            agreed.append({"a": a["id"], "b": b["id"]})
    items += [{"a": a["id"], "b": None, "disagreement": "only %s found this" % la} for a in only_a]
    items += [{"a": None, "b": b["id"], "disagreement": "only %s found this" % lb} for b in only_b]
    for n, it in enumerate(items, 1):
        it["item"] = "D%d" % n
    return agreed, items


def _paths(data, pair, la, lb):
    lab = Path(data) / "labelling"
    return ([lab / "returned" / ("labels-%s-%s.json" % (pair, x)) for x in (la, lb)],
            lab / "reconcile" / ("%s-worksheet.md" % pair), lab / "reconcile" / ("%s-resolution.json" % pair))


def load_both(data, pair, la, lb):
    (pa, pb), _, _ = _paths(data, pair, la, lb)
    a, ea = load_labels(pa, pair, la, data)
    b, eb = load_labels(pb, pair, lb, data)
    if ea or eb:
        raise SystemExit("\n".join("FAIL " + e for e in ea + eb))
    return a, b


def _fmt(f):
    parts = ["%s %s %s material=%s" % (f["id"], f["category"], f["change_type"], f["material"])]
    for side in ("old", "new"):
        if "evidence_" + side in f:
            s = f["evidence_" + side]
            parts.append("%s [%d-%d] %s" % (side, s["start"], s["end"], json.dumps(f[side + "_value"], ensure_ascii=False)))
    if f.get("note"):
        parts.append("note: " + f["note"])
    return "; ".join(parts)


def compare(data, pair, la="A", lb="B", force=False):
    a, b = load_both(data, pair, la, lb)
    pairs, only_a, only_b = match(a["findings"], b["findings"])
    stats = agreement(pairs, only_a, only_b)
    agreed, items = disagreements(pairs, only_a, only_b, la, lb)
    _, sheet, res = _paths(data, pair, la, lb)
    if res.exists() and not force:
        raise SystemExit("%s exists and may hold decisions; use --force to overwrite" % res)
    byid = {f["id"]: f for f in a["findings"] + b["findings"]}
    lines = ["# Reconciliation worksheet %s (%s and %s)" % (pair, la, lb), "",
             "Labels: %s %s, %s %s" % (la, a["sha256"], lb, b["sha256"]), "",
             "Agreement: %(agreed)d of %(items)d items (matched %(matched)d, only A %(only_a)d, only B %(only_b)d)." % stats,
             "Kappa over matched items: change_type %s, material %s." % (_k(stats["kappa_change_type"]), _k(stats["kappa_material"])), "",
             "Agreed without discussion: %s" % (", ".join("%s=%s" % (x["a"], x["b"]) for x in agreed) or "none"), "",
             "For each item, set decision in %s to the version kept (%s or %s), drop, or edit (with a full" % (res.name, la, lb),
             "finding), and give the reason. Then run reconcile.py finalize.", ""]
    for it in items:
        lines += ["## %s: %s" % (it["item"], it["disagreement"]), ""]
        lines += ["- %s: %s" % (who, _fmt(byid[it[k]])) for who, k in ((la, "a"), (lb, "b")) if it[k]]
        lines.append("")
    sheet.parent.mkdir(parents=True, exist_ok=True)
    sheet.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    resolution = {"format": RESOLUTION, "pair": pair, "labellers": [la, lb],
                  "labels_sha256": {la: a["sha256"], lb: b["sha256"]}, "case_types": [], "agreed": agreed,
                  "items": [dict(it, decision="", reason="", finding=None) for it in items]}
    res.write_text(json.dumps(resolution, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return stats, pairs


def _k(v):
    return "undefined" if v is None else "%.3f" % v


def resolve(a, b, resolution, la, lb):
    """(findings, reconciliation, errors) from a filled resolution file."""
    errs = []
    if resolution.get("format") != RESOLUTION or resolution.get("labellers") != [la, lb]:
        errs.append("resolution format or labellers do not match")
    if resolution.get("labels_sha256") != {la: a["sha256"], lb: b["sha256"]}:
        errs.append("labels changed since compare: rerun compare")
    pairs, only_a, only_b = match(a["findings"], b["findings"])
    agreed, items = disagreements(pairs, only_a, only_b, la, lb)
    got = resolution.get("items") if isinstance(resolution.get("items"), list) else []
    strip = [{k: it.get(k) for k in ("item", "a", "b", "disagreement")} for it in got if isinstance(it, dict)]
    if resolution.get("agreed") != agreed or strip != items:
        errs.append("resolution items do not match the labels: rerun compare")
    if errs:
        return None, None, errs
    byid = {f["id"]: f for f in a["findings"] + b["findings"]}
    out, recon = [], []
    for x in agreed:
        f, g = dict(byid[x["a"]]), byid[x["b"]]
        if g.get("note") and g.get("note") != f.get("note"):
            f["note"] = "; ".join(n for n in ("%s: %s" % (la, f["note"]) if f.get("note") else "", "%s: %s" % (lb, g["note"])) if n)
        out.append(f)
    for it in got:
        allowed = [x for x, k in ((la, "a"), (lb, "b")) if it[k]] + ["drop", "edit"]
        d, why = it.get("decision"), it.get("reason")
        if d not in allowed:
            errs.append("%s: decision must be one of %s" % (it["item"], allowed))
            continue
        if not isinstance(why, str) or not why.strip():
            errs.append("%s: give the reason for the decision" % it["item"])
            continue
        if (d == "edit") != isinstance(it.get("finding"), dict):
            errs.append("%s: a finding object is required for edit and only for edit" % it["item"])
            continue
        f = it["finding"] if d == "edit" else None if d == "drop" else byid[it["a" if d == la else "b"]]
        if f is not None:
            out.append(dict(f))
        recon.append((len(out) - 1 if f is not None else None, it, d, why.strip()))
    for n, f in enumerate(out, 1):
        f["id"] = "F%d" % n
    reconciliation = [{"finding": "F%d" % (i + 1) if i is not None else "none (dropped %s)" % "/".join(filter(None, (it["a"], it["b"]))),
                       "disagreement": "%s %s" % (it["item"], it["disagreement"]),
                       "resolution": "%s: %s" % (d, why)} for i, it, d, why in recon]
    return out, reconciliation, errs


def build_record(data, pair, la="A", lb="B"):
    """(record, errors) for a pair whose resolution file is complete."""
    a, b = load_both(data, pair, la, lb)
    _, _, res = _paths(data, pair, la, lb)
    try:
        resolution = json.loads(res.read_text(encoding="utf-8"))
        manifest = {p["id"]: p for p in json.loads((Path(data) / "manifest-draft.json").read_text(encoding="utf-8"))["pairs"]}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return None, ["cannot read the resolution or manifest: %s" % exc]
    if not isinstance(resolution, dict) or resolution.get("pair") != pair:
        return None, ["%s is not the resolution for %s" % (res, pair)]
    findings, recon, errs = resolve(a, b, resolution, la, lb)
    m = manifest.get(pair)
    if m is None:
        return None, errs + ["%s is not in manifest-draft.json" % pair]
    if m.get("tier") != "public":
        errs.append("%s: manifest tier is %r, expected public" % (pair, m.get("tier")))
    for side in label_kit.SIDES:
        if m[side].get("sha256") != a["texts"][side]["sha256"] or m[side].get("storage_ref") != a["texts"][side]["storage_ref"]:
            errs.append("%s: manifest %s text differs from the labelled text" % (pair, side))
    if not resolution.get("case_types"):
        errs.append("%s: case_types must name at least one 04 §4 case type" % pair)
    if errs:
        return None, errs
    record = {"id": pair, "tier": "public",
              "source": {"kind": SOURCE_KIND, "url": m["new"]["url"], "licence": m["licence"],
                         "retrieved": m["new"]["retrieved"], "anonymised": True},
              "case_types": resolution["case_types"], "split": "unsplit",
              "old": {"format": "text", "sha256": m["old"]["sha256"], "storage_ref": m["old"]["storage_ref"]},
              "new": {"format": "text", "sha256": m["new"]["sha256"], "storage_ref": m["new"]["storage_ref"]},
              "findings": findings, "labelled_by": [la, lb], "reconciliation": recon}
    errs = check_findings(pair, {s: record[s] for s in label_kit.SIDES}, findings, data)
    return (None if errs else record), errs


def finalize(data, pair, la="A", lb="B"):
    """Validate the record on its own with validate.py, then add or replace it in records.jsonl."""
    record, errs = build_record(data, pair, la, lb)
    if errs:
        return errs
    lab = Path(data).resolve() / "labelling"
    with tempfile.TemporaryDirectory() as tmp:
        one = Path(tmp) / "records.jsonl"
        one.write_text(json.dumps(record, ensure_ascii=False) + "\n", encoding="utf-8")
        _, errs = validate.validate_file(str(one), texts_root=str(Path(data).resolve()))
    if errs:
        return errs
    path = lab / "records.jsonl"
    keep = [ln for ln in (path.read_text(encoding="utf-8").splitlines() if path.exists() else [])
            if ln.strip() and json.loads(ln).get("id") != pair]
    tmp = path.with_suffix(".tmp")
    tmp.write_text("".join(x + "\n" for x in keep + [json.dumps(record, ensure_ascii=False)]), encoding="utf-8", newline="\n")
    os.replace(tmp, path)
    return validate.validate_file(str(path), texts_root=str(Path(data).resolve()))[1]


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("command", choices=["compare", "finalize"])
    ap.add_argument("--data", default=str(label_kit.DEFAULT_DATA))
    ap.add_argument("--pairs", nargs="+", help="compare: one or more pairs (pooled statistics at the end)")
    ap.add_argument("--pair", help="finalize: the pair")
    ap.add_argument("--labellers", nargs=2, default=["A", "B"])
    ap.add_argument("--force", action="store_true", help="compare: overwrite an existing resolution file")
    a = ap.parse_args(argv)
    la, lb = a.labellers
    if a.command == "finalize":
        errs = finalize(a.data, a.pair, la, lb)
        for e in errs:
            print("FAIL " + e)
        print("%s: %s" % ("FAIL" if errs else "PASS", a.pair))
        return 1 if errs else 0
    pooled = []
    for pair in a.pairs:
        stats, pairs = compare(a.data, pair, la, lb, a.force)
        pooled += pairs
        print("%s: %d/%d items agree, kappa change_type %s, material %s" % (
            pair, stats["agreed"], stats["items"], _k(stats["kappa_change_type"]), _k(stats["kappa_material"])))
    if len(a.pairs) > 1:
        print("pooled kappa over %d matched items: change_type %s, material %s" % (
            len(pooled), _k(kappa([x["change_type"] for x, _ in pooled], [y["change_type"] for _, y in pooled])),
            _k(kappa([x["material"] for x, _ in pooled], [y["material"] for _, y in pooled]))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
