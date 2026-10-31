"""Validate evaluation records against docs/eval-schema.json and their stored files.

Text/image validation uses the standard library; PDF validation requires pypdfium2.
It implements the subset of JSON Schema 2020-12 that the
schema uses (type, enum, const, pattern, format: date, required, properties,
additionalProperties, items, minItems, maxItems, minimum, anyOf, local $ref). Any other
keyword raises an error, so tightening the schema can never silently pass bad records.
On top of the schema it checks IDs, stored-file hashes and magic bytes, exact text/PDF
slices, full PNG decoding, image geometry and unreadable regions (image sides only, no ink,
overlapping a finding). Whether image pixels show the labelled value needs human review.
Storage checks need storage_ref; use --schema-only for records without stored files.

    python scripts/eval/validate.py --records <dir>/records.jsonl [--texts-root <dir>] [--schema-only]
"""
import argparse
from contextlib import closing
import datetime
import hashlib
import json
import os
import math
import struct
import zlib
from pathlib import Path
import re
import sys

SCHEMA = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "docs", "eval-schema.json")
TYPES = {"object": dict, "array": list, "string": str, "boolean": bool}
SUPPORTED = {"$ref", "type", "enum", "const", "pattern", "format", "minimum", "minItems", "maxItems",
             "items", "required", "properties", "additionalProperties", "anyOf"}
ANNOTATIONS = {"$schema", "$id", "$defs", "title", "description"}
SUFFIX = {"text": ".txt", "pdf": ".pdf", "image": ".png"}
CHANNELS = {0: 1, 2: 3, 4: 2, 6: 4}  # 8-bit greyscale, RGB, grey+alpha, RGBA; no palettes
UNREADABLE_INK = 128  # an unreadable region holds no pixel darker than this (07 §4)


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


def png_decode(data, pixels=False):
    """Check a non-interlaced 8-bit PNG with the standard library: (width, height, channels, rows).

    Every chunk CRC is checked, IHDR must come first and IEND last, and the inflated
    IDAT stream must hold exactly one valid filter byte plus one row of pixels per line.
    Rows are unfiltered only when pixels is true (slow in pure Python); otherwise None.
    """
    if (len(data) < 33 or data[:8] != b"\x89PNG\r\n\x1a\n" or
            data[8:16] != b"\x00\x00\x00\x0dIHDR"):
        raise ValueError("wrong PNG magic bytes or missing IHDR")
    pos, chunks = 8, []
    while pos < len(data):
        if pos + 12 > len(data):
            raise ValueError("truncated PNG chunk")
        length, kind = struct.unpack(">I", data[pos:pos + 4])[0], data[pos + 4:pos + 8]
        body, end = data[pos + 8:pos + 8 + length], pos + 12 + length
        if end > len(data) or zlib.crc32(kind + body) != struct.unpack(">I", data[end - 4:end])[0]:
            raise ValueError("invalid PNG %s chunk checksum or length" % kind.decode("latin-1"))
        chunks.append((kind, body))
        pos = end
        if kind == b"IEND":
            break
    if chunks[-1][0] != b"IEND" or pos != len(data):
        raise ValueError("PNG must end with IEND and nothing after it")
    width, height, depth, colour, _, _, interlace = struct.unpack(">IIBBBBB", chunks[0][1])
    if min(width, height) == 0 or depth != 8 or colour not in CHANNELS or interlace:
        raise ValueError("unsupported PNG: need non-empty, 8-bit, non-interlaced, no palette")
    try:
        raw = zlib.decompress(b"".join(b for k, b in chunks if k == b"IDAT"))
    except zlib.error as exc:
        raise ValueError("PNG image data does not decompress") from exc
    bpp = CHANNELS[colour]
    stride = width * bpp
    if len(raw) != height * (stride + 1):
        raise ValueError("PNG image data does not match IHDR dimensions")
    rows, prev = [], bytearray(stride)
    for y in range(height):
        kind = raw[y * (stride + 1)]
        line = bytearray(raw[y * (stride + 1) + 1:(y + 1) * (stride + 1)])
        if kind > 4:
            raise ValueError("invalid PNG filter type")
        if not pixels:
            continue
        if kind:
            for i in range(stride):
                a = line[i - bpp] if i >= bpp else 0
                b, c = prev[i], (prev[i - bpp] if i >= bpp else 0)
                if kind == 1:
                    line[i] = (line[i] + a) & 255
                elif kind == 2:
                    line[i] = (line[i] + b) & 255
                elif kind == 3:
                    line[i] = (line[i] + (a + b) // 2) & 255
                else:
                    p = a + b - c
                    pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                    line[i] = (line[i] + (a if pa <= pb and pa <= pc else b if pb <= pc else c)) & 255
        rows.append(bytes(line))
        prev = line
    return width, height, bpp, rows if pixels else None


def png_size(data):
    return png_decode(data)[:2]


def dark_pixels(data, box, threshold=UNREADABLE_INK):
    """Pixels inside box whose darkest colour channel is below threshold, i.e. ink."""
    width, height, bpp, rows = png_decode(data, pixels=True)
    x0, y0, x1, y1 = math.floor(box[0]), math.floor(box[1]), math.ceil(box[2]), math.ceil(box[3])
    colour = 1 if bpp in (1, 2) else 3
    return sum(1 for y in range(y0, y1) for x in range(x0, x1)
               if min(rows[y][x * bpp:x * bpp + colour]) < threshold)


def pdf_texts(data):
    try:
        import pypdfium2
    except ImportError as exc:
        raise ValueError("PDF validation requires pypdfium2; install requirements-render.txt") from exc
    with pypdfium2.PdfDocument(data) as doc:
        texts = []
        for page in doc:
            with closing(page), closing(page.get_textpage()) as tp:
                texts.append(tp.get_text_range())
        return texts


def read_version(ver, root):
    if "storage_ref" not in ver:
        raise ValueError("missing storage_ref")
    if not ver["storage_ref"].endswith(SUFFIX.get(ver["format"], "\0")):
        raise ValueError("storage_ref must end in %s for format %s" % (SUFFIX.get(ver["format"]), ver["format"]))
    root = Path(root).resolve()
    path = (root / ver["storage_ref"]).resolve()
    if not path.is_relative_to(root):
        raise ValueError("storage_ref escapes the private storage root")
    if not path.is_file():
        raise ValueError("missing " + str(path))
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != ver["sha256"]:
        raise ValueError("sha256 mismatch")
    if ver["format"] == "text":
        if data.startswith((b"%PDF-", b"\x89PNG\r\n\x1a\n")):
            raise ValueError("text format has PDF/PNG magic bytes")
        return data.decode("utf-8")
    if ver["format"] == "image":
        return png_decode(data)[:2] + (data,)
    if ver["format"] == "pdf":
        if not data.startswith(b"%PDF-"):
            raise ValueError("wrong PDF magic bytes")
        return pdf_texts(data)
    raise ValueError("unsupported format")


def locator_errors(span, value, fmt, content, where, check_value=True):
    if fmt == "image":
        if set(span) != {"box"}:
            return [where + ": an image locator needs only box"]
        b = span["box"]
        if not all(math.isfinite(x) for x in b) or not (0 <= b[0] < b[2] <= content[0] and 0 <= b[1] < b[3] <= content[1]):
            return [where + ": box outside the image or degenerate"]
        return []
    required = {"page", "start", "end"} if fmt == "pdf" else {"start", "end"}
    if set(span) != required:
        return [where + ": a " + fmt + " locator needs " + ("page, " if fmt == "pdf" else "") + "start and end"]
    if fmt == "pdf":
        if not 1 <= span["page"] <= len(content):
            return [where + ": page outside the PDF"]
        content = content[span["page"] - 1]
    if not 0 <= span["start"] <= span["end"] <= len(content):
        return [where + ": span %d-%d outside the text" % (span["start"], span["end"])]
    actual = content[span["start"]:span["end"]]
    if check_value and (value is None or actual != value):
        return ["%s slices to %r, labelled %r" % (where, actual, value)]
    return []


def overlaps(a, b):
    if "box" in a and "box" in b:
        a, b = a["box"], b["box"]
        return a[0] < b[2] and a[2] > b[0] and a[1] < b[3] and a[3] > b[1]
    if all("start" in x and "end" in x for x in (a, b)):
        return a.get("page") == b.get("page") and a["start"] < b["end"] and a["end"] > b["start"]
    return False


def check_texts(rec, root):
    """Validate stored bytes, format-specific evidence, and unreadable regions."""
    errs, contents = [], {}
    for side in ("old", "new"):
        try:
            contents[side] = read_version(rec[side], root)
        except Exception as exc:
            errs.append("%s %s: %s" % (rec["id"], side, exc))
    ids = [f["id"] for f in rec["findings"]]
    if len(ids) != len(set(ids)):
        errs.append("%s: duplicate finding ids" % rec["id"])
    regions = rec.get("unreadable", [])
    if regions and rec.get("expected_status") != "partial":
        errs.append(rec["id"] + ": unreadable regions require expected_status partial")
    if rec.get("expected_status") == "partial" and not regions:
        errs.append(rec["id"] + ": partial requires unreadable regions")
    for region in regions:
        side, span = region["side"], region["locator"]
        where = rec["id"] + " unreadable " + side
        if rec[side]["format"] != "image":
            errs.append(where + ": unreadable regions are only allowed on image sides")
            continue
        if side not in contents:
            continue
        bad = locator_errors(span, None, "image", contents[side], where, check_value=False)
        errs += bad
        if bad:
            continue
        if dark_pixels(contents[side][2], span["box"]):
            errs.append(where + ": region still contains ink, so it is not unreadable")
        if not any(overlaps(f.get("evidence_" + side, {}), span) for f in rec["findings"]):
            errs.append(where + ": region overlaps no finding's evidence on that side")
    for f in rec["findings"]:
        affected = False
        for side in ("old", "new"):
            span, value = f.get("evidence_" + side), f.get(side + "_value")
            if not span:
                continue
            if value is None:
                errs.append(rec["id"] + " " + f["id"] + ": evidence needs a labelled value")
            if side in contents:
                errs += locator_errors(span, value, rec[side]["format"], contents[side],
                                       "%s %s evidence_%s" % (rec["id"], f["id"], side))
            affected |= any(r["side"] == side and overlaps(span, r["locator"]) for r in regions)
        if affected and (f["change_type"] != "uncertain" or f.get("note") != "unreadable"):
            errs.append(rec["id"] + " " + f["id"] + ": unreadable evidence must be uncertain with note unreadable")
        if f.get("note") == "unreadable" and not affected:
            errs.append(rec["id"] + " " + f["id"] + ": unreadable finding has no matching region")
    return errs


def validate_file(records, texts_root=None, schema_path=SCHEMA, storage=True):
    """Schema-check every record; with storage, also check each one against its stored files."""
    with open(schema_path, encoding="utf-8") as fh:
        schema = json.load(fh)
    errs, n, seen = [], 0, set()
    texts_root = (texts_root or os.path.dirname(os.path.abspath(records))) if storage else None
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
            if isinstance(rid, str) and rid in seen:
                errs.append("line %d: duplicate record id %s" % (lineno, rid))
            if isinstance(rid, str):
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
    ap.add_argument("--schema-only", action="store_true",
                    help="check the schema only, e.g. a manifest in git without storage_ref")
    a = ap.parse_args(argv)
    n, errs = validate_file(a.records, a.texts_root, storage=not a.schema_only)
    for e in errs:
        print("FAIL " + e)
    print("%s: %d records, %d errors" % ("PASS" if not errs else "FAIL", n, len(errs)))
    return 1 if errs else 0


if __name__ == "__main__":
    sys.exit(main())
