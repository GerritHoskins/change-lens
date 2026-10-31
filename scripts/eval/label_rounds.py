"""Immutable R1 freeze, seeded stratified R2 sample, and the 14-day consistency guard."""
import hashlib
import json
import math
import random
from datetime import datetime, timedelta, timezone
from pathlib import Path

import label_kit
from label_exports import load_labels, timestamp

FREEZE = "r1-freeze.json"
SAMPLE = "r2-sample.json"
TIERS = ("public", "owner", "donated", "constructed")


def utcnow():
    return datetime.now(timezone.utc)


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_json(path):
    try:
        obj = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(obj, dict):
            raise ValueError("expected an object")
        return obj
    except (OSError, ValueError) as exc:
        raise SystemExit("cannot read %s: %s" % (path, exc)) from exc


def write_once(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with path.open("x", encoding="utf-8", newline="\n") as fh:
            fh.write(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")
    except FileExistsError:
        raise SystemExit("%s already exists; refusing to overwrite" % path) from None


def export_path(data, pair, round_id):
    if not label_kit.PAIR_ID.fullmatch(pair) or pair in label_kit.EXCLUDED:
        raise SystemExit("invalid or excluded pair %s" % pair)
    return Path(data) / "labelling" / "returned" / ("labels-%s-%s.json" % (pair, round_id))


def labels(data, pair, round_id):
    doc, errs = load_labels(export_path(data, pair, round_id), pair, round_id, data)
    if errs:
        raise SystemExit("\n".join("FAIL " + e for e in errs))
    return doc


def manifest(data):
    rows = read_json(Path(data) / "manifest-draft.json").get("pairs")
    if not isinstance(rows, list) or any(not isinstance(x, dict) or "id" not in x for x in rows):
        raise SystemExit("manifest needs a pairs list with IDs")
    rows = [x for x in rows if x["id"] not in label_kit.EXCLUDED]
    if len({x["id"] for x in rows}) != len(rows):
        raise SystemExit("duplicate manifest IDs")
    return {x["id"]: x for x in rows}


def freeze(data, pairs=None):
    """Pin every chosen R1 file and its source metadata. No relabelling or refreeze."""
    path = label_kit.private_lab(data) / FREEZE
    if path.exists():
        raise SystemExit("%s already exists; refusing to overwrite" % path)
    source = manifest(data)
    chosen = sorted(set(source if pairs is None else pairs) - label_kit.EXCLUDED)
    if not chosen:
        raise SystemExit("no eligible pairs to freeze")
    frozen_at = utcnow().isoformat()
    entries = {}
    for pair in chosen:
        a = labels(data, pair, "R1")
        m = source.get(pair)
        if not m or m.get("tier") not in TIERS:
            raise SystemExit("%s: missing or invalid manifest tier" % pair)
        for side in label_kit.SIDES:
            if any(m.get(side, {}).get(k) != a["texts"][side][k] for k in ("sha256", "storage_ref")):
                raise SystemExit("%s: manifest %s differs from labelled text" % (pair, side))
        if timestamp(a["exported"]) > timestamp(frozen_at):
            raise SystemExit("%s: R1 export is dated after the freeze" % pair)
        entries[pair] = {"sha256": a["sha256"], "frozen_at": frozen_at,
                         "file": export_path(data, pair, "R1").relative_to(Path(data)).as_posix(),
                         "case_type": a["case_type"], "tier": m["tier"], "source_manifest": m}
    doc = {"format": "change-lens-r1-freeze/1", "excluded": sorted(label_kit.EXCLUDED), "pairs": entries}
    write_once(path, doc)
    return doc


def read_freeze(data):
    doc = read_json(label_kit.private_lab(data) / FREEZE)
    entries = doc.get("pairs")
    if doc.get("format") != "change-lens-r1-freeze/1" or not isinstance(entries, dict) or not entries:
        raise SystemExit("invalid R1 freeze manifest")
    for pair, entry in entries.items():
        path = export_path(data, pair, "R1")
        try:
            if not isinstance(entry, dict) or digest(path) != entry["sha256"]:
                raise ValueError("R1 hash differs from freeze")
            timestamp(entry["frozen_at"])
            if entry["case_type"] not in label_kit.case_types() or entry["tier"] not in TIERS:
                raise ValueError("invalid case_type or tier")
            if entry["file"] != path.relative_to(Path(data)).as_posix():
                raise ValueError("incorrect frozen file reference")
        except (OSError, ValueError, KeyError) as exc:
            raise SystemExit("%s: invalid freeze (%s)" % (pair, exc)) from exc
    return doc


def frozen_labels(data, pair):
    entry = read_freeze(data)["pairs"].get(pair)
    if entry is None:
        raise SystemExit("%s is not frozen" % pair)
    a = labels(data, pair, "R1")
    if a["case_type"] != entry["case_type"]:
        raise SystemExit("%s: R1 case_type differs from freeze" % pair)
    return a, entry


def stratified(entries, seed):
    """Ceiling(N/3); cover each case_type/tier stratum when the quota allows it."""
    rng = random.Random(seed)
    groups = {}
    for pair, entry in sorted(entries.items()):
        groups.setdefault((entry["case_type"], entry["tier"]), []).append(pair)
    strata = sorted(groups)
    rng.shuffle(strata)
    for group in groups.values():
        rng.shuffle(group)
    target = math.ceil(len(entries) / 3)
    allocated = {key: 0 for key in strata}
    # One per stratum first; if there are more strata than slots the seed breaks ties.
    for key in strata[:target]:
        allocated[key] = 1
    while sum(allocated.values()) < target:
        candidates = [k for k in strata if allocated[k] < len(groups[k])]
        key = max(candidates, key=lambda k: target * len(groups[k]) / len(entries) - allocated[k])
        allocated[key] += 1
    return sorted(pair for key in strata for pair in groups[key][:allocated[key]])


def sample(data, seed):
    path = label_kit.private_lab(data) / SAMPLE
    if path.exists():
        raise SystemExit("%s already exists; refusing a second sample" % path)
    frozen = read_freeze(data)
    chosen = stratified(frozen["pairs"], seed)
    doc = {"format": "change-lens-r2-sample/1", "seed": seed,
           "freeze_sha256": digest(path.parent / FREEZE), "pairs": chosen}
    write_once(path, doc)
    return doc


def read_sample(data):
    path = label_kit.private_lab(data) / SAMPLE
    doc = read_json(path)
    frozen = read_freeze(data)
    if (doc.get("format") != "change-lens-r2-sample/1" or type(doc.get("seed")) is not int
            or doc.get("freeze_sha256") != digest(path.parent / FREEZE)
            or doc.get("pairs") != stratified(frozen["pairs"], doc["seed"])):
        raise SystemExit("sample does not match its frozen cohort and seed")
    return doc


def load_comparison(data, pair):
    if pair not in read_sample(data)["pairs"]:
        raise SystemExit("%s is not in the R2 sample" % pair)
    a, entry = frozen_labels(data, pair)
    b = labels(data, pair, "R2")
    earliest = timestamp(entry["frozen_at"]) + timedelta(days=14)
    exported = timestamp(b["exported"])
    if exported < earliest:
        raise SystemExit("%s: R2 exported %s is less than 14 days after R1 freeze %s; earliest %s"
                         % (pair, b["exported"], entry["frozen_at"], earliest.isoformat()))
    if exported > utcnow():
        raise SystemExit("%s: R2 export is future-dated" % pair)
    return a, b
