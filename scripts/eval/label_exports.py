"""Strict round-export validation shared by freezing and reconciliation."""
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import label_kit
import validate


def timestamp(value):
    """Require an ISO timestamp with an explicit timezone; normalise to UTC."""
    try:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if "T" not in value or dt.tzinfo is None:
            raise ValueError()
        return dt.astimezone(timezone.utc)
    except (ValueError, TypeError, AttributeError):
        raise ValueError("must be an ISO timestamp with a timezone") from None


KEYS = {"format", "pair", "round", "texts", "case_type", "reviewed_fully", "exported", "findings"}


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


def load_labels(path, pair, round_id, data):
    """(document, errors) for one round's export; any error makes the document unusable."""
    try:
        raw = Path(path).read_bytes()
        doc = json.loads(raw.decode("utf-8"))
    except (OSError, ValueError) as exc:
        return None, ["%s: cannot read labels (%s)" % (path, exc)]
    if not isinstance(doc, dict):
        return None, ["%s: labels must be a JSON object" % path]
    errs = []
    if round_id not in label_kit.ROUNDS or pair in label_kit.EXCLUDED:
        errs.append("invalid round or excluded pair")
    if set(doc) != KEYS:
        errs.append("%s: keys must be exactly %s" % (path, sorted(KEYS)))
    if doc.get("format") != label_kit.FORMAT:
        errs.append("%s: format is not %s" % (path, label_kit.FORMAT))
    if doc.get("pair") != pair or doc.get("round") != round_id:
        errs.append("%s: labels are for %r/%r, expected %s/%s" % (path, doc.get("pair"), doc.get("round"), pair, round_id))
    if doc.get("reviewed_fully") is not True:
        errs.append("%s: not marked as fully reviewed (draft export)" % path)
    if not isinstance(doc.get("findings"), list):
        errs.append("%s: findings must be a list" % path)
    if doc.get("case_type") not in label_kit.case_types():
        errs.append("%s: case_type is required and must be a schema case type" % path)
    try:
        timestamp(doc.get("exported"))
    except ValueError as exc:
        errs.append("%s: exported %s" % (path, exc))
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
    errs = check_findings(pair, versions, doc["findings"], data, prefix=round_id)
    doc["sha256"] = hashlib.sha256(raw).hexdigest()
    return (None if errs else doc), errs
