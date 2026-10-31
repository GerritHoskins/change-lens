"""Owner R1/R2 workflow: freeze, sample, compare, build and calibrate (07 sections 5-6)."""
import argparse
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import label_kit
import label_rounds
import validate
from label_exports import check_findings, load_labels

RESOLUTION = "change-lens-resolution/2"
EVIDENCE = ("evidence_old", "evidence_new", "old_value", "new_value")


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
    """Item-level agreement: an item agrees when both rounds found it with the same change_type and material."""
    items = len(pairs) + len(only_a) + len(only_b)
    agree = sum(a["change_type"] == b["change_type"] and a["material"] == b["material"] for a, b in pairs)
    return {"items": items, "matched": len(pairs), "only_r1": len(only_a), "only_r2": len(only_b),
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
            items.append({"r1": a["id"], "r2": b["id"], "disagreement": "; ".join(diff)})
        else:
            agreed.append({"r1": a["id"], "r2": b["id"]})
    items += [{"r1": a["id"], "r2": None, "disagreement": "only %s found this" % la} for a in only_a]
    items += [{"r1": None, "r2": b["id"], "disagreement": "only %s found this" % lb} for b in only_b]
    for n, it in enumerate(items, 1):
        it["item"] = "D%d" % n
    return agreed, items


def _paths(data, pair, la, lb):
    lab = Path(data) / "labelling"
    return ([lab / "returned" / ("labels-%s-%s.json" % (pair, x)) for x in (la, lb)],
            lab / "reconcile" / ("%s-worksheet.md" % pair), lab / "reconcile" / ("%s-resolution.json" % pair))


def load_both(data, pair, la="R1", lb="R2"):
    if (la, lb) != label_kit.ROUNDS:
        raise SystemExit("rounds must be R1 and R2")
    return label_rounds.load_comparison(data, pair)


def _fmt(f):
    parts = ["%s %s %s material=%s" % (f["id"], f["category"], f["change_type"], f["material"])]
    for side in ("old", "new"):
        if "evidence_" + side in f:
            s = f["evidence_" + side]
            parts.append("%s [%d-%d] %s" % (side, s["start"], s["end"], json.dumps(f[side + "_value"], ensure_ascii=False)))
    if f.get("note"):
        parts.append("note: " + f["note"])
    return "; ".join(parts)


def compare(data, pair, la="R1", lb="R2", force=False):
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
             "Agreement: %(agreed)d of %(items)d items (matched %(matched)d, only R1 %(only_r1)d, only R2 %(only_r2)d)." % stats,
             "Kappa over matched items: change_type %s, material %s." % (_k(stats["kappa_change_type"]), _k(stats["kappa_material"])), "",
             "Agreed across rounds: %s" % (", ".join("%s=%s" % (x["r1"], x["r2"]) for x in agreed) or "none"), "",
             "For each item, set decision in %s to the version kept (%s or %s), drop, or edit (with a full" % (res.name, la, lb),
             "finding), and give the reason. Then run reconcile.py build.", ""]
    for it in items:
        lines += ["## %s: %s" % (it["item"], it["disagreement"]), ""]
        lines += ["- %s: %s" % (who, _fmt(byid[it[k]])) for who, k in ((la, "r1"), (lb, "r2")) if it[k]]
        lines.append("")
    sheet.parent.mkdir(parents=True, exist_ok=True)
    sheet.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    resolution = {"format": RESOLUTION, "pair": pair, "rounds": [la, lb],
                  "labels_sha256": {la: a["sha256"], lb: b["sha256"]}, "case_type": a["case_type"], "agreed": agreed,
                  "items": [dict(it, decision="", reason="", finding=None) for it in items]}
    res.write_text(json.dumps(resolution, indent=1, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    return stats, pairs


def _k(v):
    return "undefined" if v is None else "%.3f" % v


def resolve(a, b, resolution, la, lb):
    """(findings, reconciliation, errors) from a filled resolution file."""
    errs = []
    if resolution.get("format") != RESOLUTION or resolution.get("rounds") != [la, lb]:
        errs.append("resolution format or rounds do not match")
    if resolution.get("case_type") != a["case_type"]:
        errs.append("resolution case_type must keep the R1 sampling stratum")
    if resolution.get("labels_sha256") != {la: a["sha256"], lb: b["sha256"]}:
        errs.append("labels changed since compare: rerun compare")
    pairs, only_a, only_b = match(a["findings"], b["findings"])
    agreed, items = disagreements(pairs, only_a, only_b, la, lb)
    got = resolution.get("items") if isinstance(resolution.get("items"), list) else []
    strip = [{k: it.get(k) for k in ("item", "r1", "r2", "disagreement")} for it in got if isinstance(it, dict)]
    if resolution.get("agreed") != agreed or strip != items:
        errs.append("resolution items do not match the labels: rerun compare")
    if errs:
        return None, None, errs
    byid = {f["id"]: f for f in a["findings"] + b["findings"]}
    out, recon = [], []
    for x in agreed:
        f, g = dict(byid[x["r1"]]), byid[x["r2"]]
        if g.get("note") and g.get("note") != f.get("note"):
            f["note"] = "; ".join(n for n in ("%s: %s" % (la, f["note"]) if f.get("note") else "", "%s: %s" % (lb, g["note"])) if n)
        out.append(f)
    for it in got:
        allowed = [x for x, k in ((la, "r1"), (lb, "r2")) if it[k]] + ["drop", "edit"]
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
        f = it["finding"] if d == "edit" else None if d == "drop" else byid[it["r1" if d == la else "r2"]]
        if f is not None:
            out.append(dict(f))
        recon.append((len(out) - 1 if f is not None else None, it, d, why.strip()))
    for n, f in enumerate(out, 1):
        f["id"] = "F%d" % n
    reconciliation = [{"finding": "F%d" % (i + 1) if i is not None else "none (dropped %s)" % "/".join(filter(None, (it["r1"], it["r2"]))),
                       "disagreement": "%s %s" % (it["item"], it["disagreement"]),
                       "resolution": "%s: %s" % (d, why)} for i, it, d, why in recon]
    return out, reconciliation, errs


def build_record(data, pair):
    """R1 is authoritative; a completed, hash-bound resolution can replace its findings."""
    a, entry = label_rounds.frozen_labels(data, pair)
    m = entry["source_manifest"]
    findings = [dict(f, id="F%d" % n) for n, f in enumerate(a["findings"], 1)]
    recon, rounds, hashes = [], ["R1"], {"R1": a["sha256"]}
    _, _, res = _paths(data, pair, "R1", "R2")
    if res.exists():
        a, b = load_both(data, pair)
        resolution = label_rounds.read_json(res)
        if resolution.get("pair") != pair:
            return None, ["%s is not the resolution for %s" % (res, pair)]
        findings, recon, errs = resolve(a, b, resolution, "R1", "R2")
        if errs:
            return None, errs
        rounds.append("R2")
        hashes["R2"] = b["sha256"]
    source = {"kind": {"public": "rfp_addendum", "owner": "owner_project",
                       "donated": "interview_donation", "constructed": "generator"}[entry["tier"]],
              "anonymised": True}
    for key, value in (("url", m["new"].get("url")), ("licence", m.get("licence")),
                       ("retrieved", m["new"].get("retrieved"))):
        if value is not None:
            source[key] = value
    record = {"id": pair, "tier": entry["tier"], "source": source,
              "case_types": [a["case_type"]], "split": "unsplit",
              "old": dict(a["texts"]["old"], format="text"),
              "new": dict(a["texts"]["new"], format="text"),
              "findings": findings, "labelled_by": ["owner"], "reconciliation": recon,
              "provenance": {"rounds": rounds, "labels_sha256": hashes, "r1_frozen_at": entry["frozen_at"]}}
    if res.exists():
        record["provenance"]["resolution_sha256"] = label_rounds.digest(res)
    errs = check_findings(pair, {s: record[s] for s in label_kit.SIDES}, findings, data)
    return (None if errs else record), errs


def build(data, pairs=None):
    """Validate the entire proposed file before atomically replacing records.jsonl."""
    lab = label_kit.private_lab(data)
    pairs = sorted(set(label_rounds.read_freeze(data)["pairs"] if pairs is None else pairs) - label_kit.EXCLUDED)
    records = []
    for pair in pairs:
        record, errs = build_record(data, pair)
        if errs:
            return errs
        records.append(record)
    path = lab / "records.jsonl"
    keep = [ln for ln in (path.read_text(encoding="utf-8").splitlines() if path.exists() else [])
            if ln.strip() and json.loads(ln).get("id") not in set(pairs) | label_kit.EXCLUDED]
    payload = "".join(x + "\n" for x in keep + [json.dumps(r, ensure_ascii=False) for r in records])
    with tempfile.NamedTemporaryFile(dir=lab, suffix=".jsonl", delete=False) as fh:
        tmp = Path(fh.name)
    try:
        tmp.write_text(payload, encoding="utf-8", newline="\n")
        _, errs = validate.validate_file(str(tmp), texts_root=str(Path(data).resolve()))
        if not errs:
            os.replace(tmp, path)
        return errs
    finally:
        tmp.unlink(missing_ok=True)


def calibrate(data, pairs=None):
    """A short 07 section 6 report: intra-owner consistency, never a real-pair gate."""
    sampled = label_rounds.read_sample(data)["pairs"]
    pairs = sampled if pairs is None else pairs
    grouped = {"Real pairs (non-gating)": [], "Constructed pairs": []}
    for pair in pairs:
        a, b = load_both(data, pair)
        tier = label_rounds.read_freeze(data)["pairs"][pair]["tier"]
        grouped["Constructed pairs" if tier == "constructed" else "Real pairs (non-gating)"].append((a, b))
    lines = ["R1/R2 owner consistency (not inter-annotator agreement).",
             "Item agreement includes unmatched items; kappa uses matched items only.",
             "Constructed model-evaluation metrics alone decide gates; consistency is reported separately."]
    for title, docs in grouped.items():
        lines += ["", "%s: %d sampled pairs" % (title, len(docs)),
                  "category | agreed/items | item agreement | kappa type | kappa material"]
        for category in ["all"] + label_kit.enums()[0]:
            matched, only_r1, only_r2 = [], [], []
            for a, b in docs:
                fa = [f for f in a["findings"] if category == "all" or f["category"] == category]
                fb = [f for f in b["findings"] if category == "all" or f["category"] == category]
                ps, oa, ob = match(fa, fb)
                matched += ps
                only_r1 += oa
                only_r2 += ob
            s = agreement(matched, only_r1, only_r2)
            lines.append("%s | %d/%d | %s | %s | %s" % (category, s["agreed"], s["items"],
                         _k(s["item_agreement"]), _k(s["kappa_change_type"]), _k(s["kappa_material"])))
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    subs = ap.add_subparsers(dest="command", required=True)
    for command in ("freeze", "sample", "compare", "build", "calibrate"):
        sub = subs.add_parser(command)
        sub.add_argument("--data", default=str(label_kit.DEFAULT_DATA))
        if command == "sample":
            sub.add_argument("--seed", required=True, type=int)
        else:
            sub.add_argument("--pairs", nargs="+", help="default: whole frozen cohort or R2 sample")
        if command == "compare":
            sub.add_argument("--force", action="store_true", help="overwrite existing resolution decisions")
    a = ap.parse_args(argv)
    if a.command == "freeze":
        result = label_rounds.freeze(a.data, a.pairs)
        print("PASS: froze %d R1 exports" % len(result["pairs"]))
    elif a.command == "sample":
        result = label_rounds.sample(a.data, a.seed)
        print("PASS: R2 sample (%d): %s" % (len(result["pairs"]), " ".join(result["pairs"])))
    elif a.command == "build":
        errs = build(a.data, a.pairs)
        for e in errs:
            print("FAIL " + e)
        print("FAIL build" if errs else "PASS build: validated records, split unsplit")
        return 1 if errs else 0
    elif a.command == "calibrate":
        print(calibrate(a.data, a.pairs))
    else:
        pairs = a.pairs if a.pairs is not None else label_rounds.read_sample(a.data)["pairs"]
        # Validate the whole selection before writing a worksheet for any of it.
        for pair in pairs:
            load_both(a.data, pair)
        for pair in pairs:
            s, _ = compare(a.data, pair, force=a.force)
            tier = label_rounds.read_freeze(a.data)["pairs"][pair]["tier"]
            print("%s [%s]: %d/%d items agree; kappa type %s, material %s" % (
                pair, "constructed" if tier == "constructed" else "real, non-gating",
                s["agreed"], s["items"], _k(s["kappa_change_type"]), _k(s["kappa_material"])))
    return 0


if __name__ == "__main__":
    sys.exit(main())
