"""Write offline HTML labelling pages for real evaluation pairs (07 §5); standard library only.

One self-contained page per pair and labeller shows the stored normalised old and new texts
side by side. Selecting text records zero-based, end-exclusive code-point offsets into
exactly those texts, which is what validate.py slices. Pages carry no labels, hints or
manifest notes, and make no network requests (CSP default-src 'none').

    python scripts/eval/label_kit.py --data ../change-lens-data [--labellers A B] [--pairs P-001 ...]

Real pairs are read from <data>/anon/P-NNN/{old,new}.txt; invented calibration pairs from
<data>/labelling/calibration/CAL-N/{old,new}.txt. Pages go to <data>/labelling/<labeller>/.
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
LABELLER = re.compile(r"^[A-Z][A-Z0-9]{0,7}$")
FORMAT = "change-lens-labels/1"
SIDES = ("old", "new")


def enums():
    """Categories and change types, taken from the schema so the page cannot drift from it."""
    with open(validate.SCHEMA, encoding="utf-8") as fh:
        props = json.load(fh)["$defs"]["finding"]["properties"]
    return props["category"]["enum"], props["change_type"]["enum"]


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
    return [p for p in found if PAIR_ID.match(p)]


def embed(obj):
    """JSON safe inside a <script> element: no '<', '>' or '&' survives as a literal."""
    return (json.dumps(obj, ensure_ascii=True)
            .replace("<", "\\u003c").replace(">", "\\u003e").replace("&", "\\u0026"))


def page(pair, labeller, sides):
    """HTML for one pair and labeller; sides maps old/new to (storage_ref, text, sha256)."""
    if not PAIR_ID.match(pair) or not LABELLER.match(labeller):
        raise ValueError("invalid pair %r or labeller %r" % (pair, labeller))
    categories, change_types = enums()
    payload = {"pair": pair, "labeller": labeller, "categories": categories, "change_types": change_types,
               "texts": {s: {"storage_ref": sides[s][0], "text": sides[s][1], "sha256": sides[s][2]} for s in SIDES}}
    tpl = TEMPLATE.read_text(encoding="utf-8")
    for key in ("__TITLE__", "__DATA__"):
        if tpl.count(key) != 1:
            raise ValueError("template must contain %s exactly once" % key)
    title = html.escape("%s · labeller %s" % (pair, labeller))
    return tpl.replace("__TITLE__", title).replace("__DATA__", embed(payload))


def write_kit(data, labellers=("A", "B"), pairs=None):
    """Write every page; refuse a destination inside a git working tree (07 §2)."""
    out = (Path(data) / "labelling").resolve()
    if generate.inside_git(out):
        raise SystemExit("refusing to write labelling pages inside a git working tree: %s" % out)
    if len(set(labellers)) != len(labellers) or not all(LABELLER.match(x) for x in labellers):
        raise SystemExit("labellers must be distinct IDs such as A and B")
    pairs = pairs or find_pairs(data)
    if not pairs:
        raise SystemExit("no pairs found under %s" % data)
    written = []
    for pair in pairs:
        sides = {s: read_text(data, pair, s) for s in SIDES}
        for who in labellers:
            path = out / who / (pair + ".html")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(page(pair, who, sides), encoding="utf-8", newline="\n")
            written.append(path)
    for folder in ("returned", "reconcile"):
        (out / folder).mkdir(exist_ok=True)
    return written


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--data", default=str(DEFAULT_DATA), help="private storage root (outside git)")
    ap.add_argument("--labellers", nargs="+", default=["A", "B"])
    ap.add_argument("--pairs", nargs="*", help="default: every pair under anon/ and labelling/calibration/")
    a = ap.parse_args(argv)
    written = write_kit(a.data, a.labellers, a.pairs)
    print("wrote %d pages under %s" % (len(written), Path(a.data).resolve() / "labelling"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
