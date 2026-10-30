"""Validate evaluation records against docs/eval-schema.json and their stored texts.

Standard library only, so it implements the subset of JSON Schema 2020-12 that the
schema uses (type, enum, const, pattern, format: date, required, properties,
additionalProperties, items, minItems, maxItems, minimum, anyOf, local $ref). Any other
keyword raises an error, so tightening the schema can never silently pass bad records.
On top of the schema it checks unique record and finding IDs, that each stored text
matches its SHA-256, and that every evidence span slices the text to the labelled value.

    python scripts/eval/validate.py --records <dir>/records.jsonl [--texts-root <dir>]
"""
import argparse
import datetime
import hashlib
import json
import os
import re
import sys

SCHEMA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "docs", "eval-schema.json")
TYPES = {"object": dict, "array": list, "string": str, "boolean": bool}
SUPPORTED = {"$ref", "type", "enum", "const", "pattern", "format", "minimum", "minItems", "maxItems",
             "items", "required", "properties", "additionalProperties", "anyOf"}
ANNOTATIONS = {"$schema", "$id", "$defs", "title", "description"}


def _type_ok(value, t):
    if isinstance(t, list):
        return any(_type_ok(value, x) for x in t)
    if t == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if t == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    return isinstance(value, TYPES[t])


def _date_ok(value):
    try:
        datetime.date.fromisoformat(value)
        return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", value))
    except ValueError:
        return False


def check(value, schema, root, path="$"):
    """Return a list of error strings for value against schema; raise on unsupported keywords."""
    unknown = set(schema) - SUPPORTED - ANNOTATIONS
    if unknown:
        raise ValueError("unsupported schema keyword(s) %s at %s" % (sorted(unknown), path))
    errs = []
    if "$ref" in schema:
        node = root
        for part in schema["$ref"].lstrip("#/").split("/"):
            node = node[part]
        errs += check(value, node, root, path)
    if "type" in schema and not _type_ok(value, schema["type"]):
        return errs + ["%s: expected %s" % (path, schema["type"])]
    if "enum" in schema and value not in schema["enum"]:
        errs.append("%s: %r not in %s" % (path, value, schema["enum"]))
    if "const" in schema and value != schema["const"]:
        errs.append("%s: expected %r" % (path, schema["const"]))
    if isinstance(value, str):
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errs.append("%s: %r does not match %s" % (path, value, schema["pattern"]))
        if "format" in schema:
            if schema["format"] != "date":
                raise ValueError("unsupported format %r at %s" % (schema["format"], path))
            if not _date_ok(value):
                errs.append("%s: %r is not a date (YYYY-MM-DD)" % (path, value))
    if "minimum" in schema and _type_ok(value, "number") and value < schema["minimum"]:
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
        try:
            texts[side] = data.decode("utf-8")
        except UnicodeDecodeError as e:
            errs.append("%s %s: text is not UTF-8 (%s)" % (rec["id"], side, e.reason))
    ids = [f["id"] for f in rec["findings"]]
    if len(ids) != len(set(ids)):
        errs.append("%s: duplicate finding ids" % rec["id"])
    for f in rec["findings"]:
        for side in ("old", "new"):
            span, value = f.get("evidence_" + side), f.get(side + "_value")
            if not span or side not in texts:
                continue
            where = "%s %s evidence_%s" % (rec["id"], f["id"], side)
            if "start" not in span or "end" not in span:
                errs.append(where + ": a text locator needs start and end")
            elif not span["start"] <= span["end"] <= len(texts[side]):
                errs.append(where + ": span %d-%d outside the text" % (span["start"], span["end"]))
            elif value is None or texts[side][span["start"]:span["end"]] != value:
                errs.append("%s slices to %r, labelled %r" % (where, texts[side][span["start"]:span["end"]], value))
    return errs


def validate_file(records, texts_root=None, schema_path=SCHEMA):
    with open(schema_path, encoding="utf-8") as fh:
        schema = json.load(fh)
    errs, n, seen = [], 0, set()
    with open(records, encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            if not line.strip():
                continue
            n += 1
            try:
                rec = json.loads(line)
            except ValueError as e:
                errs.append("line %d: not valid JSON (%s)" % (lineno, e))
                continue
            rid = rec.get("id") if isinstance(rec, dict) else None
            if rid in seen:
                errs.append("line %d: duplicate record id %s" % (lineno, rid))
            seen.add(rid)
            e = check(rec, schema, schema)
            errs += ["line %d %s %s" % (lineno, rid, x) for x in e]
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
