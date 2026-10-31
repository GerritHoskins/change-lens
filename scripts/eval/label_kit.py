"""Write offline HTML labelling pages for real evaluation pairs (07 §5); standard library only.

One self-contained page per pair and round shows the stored normalised old and new texts
side by side. Selecting text records zero-based, end-exclusive code-point offsets into
exactly those texts, which is what validate.py slices. Pages carry no labels, hints or
manifest notes, and make no network requests (CSP default-src 'none').

    python scripts/eval/label_kit.py --data ../change-lens-data [--round R1|R2] [--pairs P-001 ...]

Real pairs are read from <data>/anon/P-NNN/{old,new}.txt; invented calibration pairs from
<data>/labelling/calibration/CAL-N/{old,new}.txt. Pages go to <data>/labelling/<round>/.
"""
import argparse
import hashlib
import html
import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate  # noqa: E402
import validate  # noqa: E402

TEMPLATE = Path(__file__).resolve().parent / "label_kit.html"
DEFAULT_DATA = Path(__file__).resolve().parents[2].parent / "change-lens-data"
PAIR_ID = re.compile(r"^(P-[0-9]{3,}|CAL-[0-9]+)$")
ROUNDS = ("R1", "R2")
EXCLUDED = {"P-015"}
FORMAT = "change-lens-labels/2"
SIDES = ("old", "new")


def enums():
    """Categories and change types, taken from the schema so the page cannot drift from it."""
    with open(validate.SCHEMA, encoding="utf-8") as fh:
        props = json.load(fh)["$defs"]["finding"]["properties"]
    return props["category"]["enum"], props["change_type"]["enum"]


def case_types():
    with open(validate.SCHEMA, encoding="utf-8") as fh:
        return json.load(fh)["properties"]["case_types"]["items"]["enum"]


def private_lab(data):
    out = (Path(data) / "labelling").resolve()
    if generate.inside_git(out):
        raise SystemExit("refusing to write labels inside a git working tree: %s" % out)
    return out


def text_ref(pair, side):
    """storage_ref of a pair's stored text, relative to the data root."""
    if not PAIR_ID.match(pair) or side not in SIDES:
        raise ValueError("invalid pair %r or side %r" % (pair, side))
    folder = "anon" if pair.startswith("P-") else "labelling/calibration"
    return "%s/%s/%s.txt" % (folder, pair, side)


def read_text(data, pair, side):
    """(storage_ref, text, sha256); the bytes must be strict UTF-8, as validate.py reads them."""
    ref = text_ref(pair, side)
    raw = (Path(data) / ref).read_bytes()
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("%s is not valid UTF-8: %s" % (ref, exc)) from exc
    return ref, text, hashlib.sha256(raw).hexdigest()


def find_pairs(data):
    data = Path(data)
    found = [p.name for p in sorted((data / "anon").glob("P-*")) if p.is_dir()]
    found += [p.name for p in sorted((data / "labelling" / "calibration").glob("CAL-*")) if p.is_dir()]
    return [p for p in found if PAIR_ID.match(p) and p not in EXCLUDED]


def embed(obj):
    """JSON safe inside a <script> element: no '<', '>' or '&' survives as a literal."""
    return (json.dumps(obj, ensure_ascii=True)
            .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))


def page(pair, round_id, sides):
    """HTML for one pair and round; sides maps old/new to (storage_ref, text, sha256)."""
    if not PAIR_ID.match(pair) or round_id not in ROUNDS or pair in EXCLUDED:
        raise ValueError("invalid pair %r or round_id %r" % (pair, round_id))
    categories, change_types = enums()
    payload = {"pair": pair, "round": round_id, "categories": categories, "change_types": change_types, "case_types": case_types(),
               "texts": {s: {"storage_ref": sides[s][0], "text": sides[s][1], "sha256": sides[s][2]} for s in SIDES}}
    tpl = TEMPLATE.read_text(encoding="utf-8")
    for key in ("__TITLE__", "__DATA__"):
        if tpl.count(key) != 1:
            raise ValueError("template must contain %s exactly once" % key)
    title = html.escape("%s · round %s" % (pair, round_id))
    return tpl.replace("__TITLE__", title).replace("__DATA__", embed(payload))


def write_kit(data, round_id="R1", pairs=None):
    """R2 reads only sampled IDs and source texts, never R1 labels or case types."""
    out = private_lab(data)
    if round_id not in ROUNDS:
        raise SystemExit("round must be R1 or R2")
    if round_id == "R2":
        import label_rounds
        sampled = label_rounds.read_sample(data)["pairs"]
        pairs = sampled if pairs is None else pairs
        if set(pairs) - set(sampled):
            raise SystemExit("R2 pages are limited to the frozen sample")
    else:
        pairs = find_pairs(data) if pairs is None else pairs
    pairs = sorted(set(pairs) - EXCLUDED)
    if not pairs:
        raise SystemExit("no eligible pairs found under %s" % data)
    written = []
    for pair in pairs:
        sides = {s: read_text(data, pair, s) for s in SIDES}
        path = out / round_id / (pair + ".html")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(page(pair, round_id, sides), encoding="utf-8", newline="\n")
        written.append(path)
    for folder in ("returned", "reconcile"):
        (out / folder).mkdir(exist_ok=True)
    (out / "GUIDE.md").write_bytes((TEMPLATE.parent / "GUIDE.md").read_bytes())
    return written


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", default=str(DEFAULT_DATA), help="private storage root (outside git)")
    ap.add_argument("--round", choices=ROUNDS, default="R1")
    ap.add_argument("--pairs", nargs="*", help="default: every pair under anon/ and labelling/calibration/")
    a = ap.parse_args(argv)
    written = write_kit(a.data, a.round, a.pairs)
    print("wrote %d pages under %s" % (len(written), Path(a.data).resolve() / "labelling"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
