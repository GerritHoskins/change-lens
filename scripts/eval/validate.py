"""Validate evaluation records against docs/eval-schema.json and their stored texts.

Standard library only, so it implements the subset of JSON Schema 2020-12 that the
schema uses (type, enum, const, pattern, required, properties, additionalProperties,
items, minItems, maxItems, minimum, anyOf, local $ref). On top of the schema it checks
that each stored text matches its SHA-256 and that every evidence span slices the
text to the labelled value.

    python scripts/eval/validate.py --records <dir>/records.jsonl [--texts-root <dir>]
"""
import argparse
import hashlib
import json
import os
import re
import sys

SCHEMA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "docs", "eval-schema.json")
TYPES = {"object": dict, "array": list, "string": str, "boolean": bool}


def _type_ok(value, t):
    if t == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if t == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, TYPES[t])


def check(value, schema, root, path="$"):
    """Return a list of error strings for value against schema."""
    if "$ref" in schema:
        node = root
        for part in schema["$ref"].lstrip("#/").split("/"):
            node = node[part]
        return check(value, node, root, path)
    errs = []
    if "type" in schema and not _type_ok(value, schema["type"]):
        return ["%s: expected %s" % (path, schema["type"])]
    if "enum" in schema and value not in schema["enum"]:
        errs.append("%s: %r not in %s" % (path, value, schema["enum"]))
    if "const" in schema and value != schema["const"]:
        errs.append("%s: expected %r" % (path, schema["const"]))
    if "pattern" in schema and isinstance(value, str) and not re.search(schema["pattern"], value):
        errs.append("%s: %r does not match %s" % (path, value, schema["pattern"]))
    if "minimum" in schema and isinstance(value, (int, float)) and value < schema["minimum"]:
        errs.append("%s: %r below %r" % (path, value, schema["minimum"]))
    if isinstance(value, list):
        if len(value) < schema.get("minItems", 0):
            errs.append("%s: fewer than %d items" % (path, schema["minItems"]))
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errs.append("%s: more than %d items" % (path, schema["maxItems"]))
        if "items" in schema:
            for i, v in enumerate(value):
                errs += check(v, schema["items"], root, "%s[%d]" % (path, i))
    if isinstance(value, dict):
        props = schema.get("properties", {})
        for k in schema.get("required", []):
            if k not in value:
                errs.append("%s: missing %s" % (path, k))
        for k, v in value.items():
            if k in props:
                errs += check(v, props[k], root, "%s.%s" % (path, k))
            elif schema.get("additionalProperties") is False:
                errs.append("%s: unexpected property %s" % (path, k))
    if "anyOf" in schema and not any(not check(value, s, root, path) for s in schema["anyOf"]):
        errs.append("%s: matches none of anyOf" % path)
    return errs


def check_texts(rec, root):
    """Hashes and evidence spans against the stored texts (text format only)."""
    errs, texts = [], {}
    for side in ("old", "new"):
        ver = rec[side]
        if ver.get("format") != "text" or "storage_ref" not in ver:
            continue
        p = os.path.join(root, ver["storage_ref"])
        if not os.path.isfile(p):
            errs.append("%s %s: missing %s" % (rec["id"], side, p))
            continue
        with open(p, "rb") as fh:
            data = fh.read()
        if hashlib.sha256(data).hexdigest() != ver["sha256"]:
            errs.append("%s %s: sha256 mismatch" % (rec["id"], side))
        texts[side] = data.decode("utf-8")
    ids = [f["id"] for f in rec["findings"]]
    if len(ids) != len(set(ids)):
        errs.append("%s: duplicate finding ids" % rec["id"])
    for f in rec["findings"]:
        for side in ("old", "new"):
            span, value = f.get("evidence_" + side), f.get(side + "_value")
            if not span or side not in texts or "start" not in span:
                continue
            got = texts[side][span["start"]:span["end"]]
            if value is None or got != value:
                errs.append("%s %s evidence_%s slices to %r, labelled %r" % (rec["id"], f["id"], side, got, value))
    return errs


def validate_file(records, texts_root=None, schema_path=SCHEMA):
    with open(schema_path, encoding="utf-8") as fh:
        schema = json.load(fh)
    errs, n = [], 0
    with open(records, encoding="utf-8") as fh:
        for line in fh:
            if not line.strip():
                continue
            rec = json.loads(line)
            n += 1
            e = check(rec, schema, schema)
            errs += ["%s %s" % (rec.get("id"), x) for x in e]
            if not e and texts_root:
                errs += check_texts(rec, texts_root)
    return n, errs


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--records", required=True)
    ap.add_argument("--texts-root", help="directory that storage_ref paths are relative to")
    a = ap.parse_args(argv)
    n, errs = validate_file(a.records, a.texts_root or os.path.dirname(os.path.abspath(a.records)))
    for e in errs:
        print("FAIL " + e)
    print("%s: %d records, %d errors" % ("PASS" if not errs else "FAIL", n, len(errs)))
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
