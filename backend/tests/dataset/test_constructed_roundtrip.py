"""I-1 acceptance: locators round-trip exactly on the constructed dataset (07 §4).

Reads the private data in place (never copied); SKIPPED when the folder is absent, so it is not
part of CI. Failures report record IDs, finding IDs, sides and check names only, never document
text: every comparison is reduced to a boolean before it reaches an assertion.

    CHANGELENS_EVAL_DATA=<folder> .venv\\Scripts\\python -m pytest tests/dataset -q -s
"""
import json
import os
from collections import Counter
from pathlib import Path

import pytest

from changelens.config import Limits
from changelens.pipeline.parse import parse
from changelens.pipeline.sandbox import parse_sandboxed
from changelens.pipeline.types import Locator, ParseRejected

DATA = Path(os.environ.get("CHANGELENS_EVAL_DATA", Path(__file__).resolve().parents[3].parent / "change-lens-data"))
SETS = ("constructed", "constructed-visual", "constructed-hidden")

pytestmark = pytest.mark.skipif(not all((DATA / s / "records.jsonl").is_file() for s in SETS),
                                reason="private constructed dataset not present (set CHANGELENS_EVAL_DATA)")


def _loc(span) -> Locator:
    return Locator(span["start"], span["end"], span.get("page"))


def _overlaps(loc: Locator, b) -> bool:
    return b.locator.page == loc.page and b.locator.char_start < loc.char_end and b.locator.char_end > loc.char_start


def test_constructed_dataset_round_trip():
    stats, problems = Counter(), []
    limits = Limits()
    for name in SETS:
        root = DATA / name
        for line in (root / "records.jsonl").read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            rec = json.loads(line)
            stats["records"] += 1
            for side in ("old", "new"):
                ver, where = rec[side], (rec["id"], side)
                fmt = ver["format"]
                if fmt == "image":
                    stats["image sides skipped (I-16)"] += 1
                    continue
                data = (root / ver["storage_ref"]).read_bytes()
                try:
                    doc = parse_sandboxed(data, fmt, limits) if fmt == "pdf" else parse(data, fmt, limits)
                except ParseRejected as r:
                    problems.append(where + ("rejected", r.code))
                    continue
                stats[fmt + " sides"] += 1
                stats["blocks"] += len(doc.blocks)
                if not all(doc.slice(b.locator) == b.text and b.text for b in doc.blocks):
                    problems.append(where + ("block slice",))
                hidden = [_loc(h["locator"]) for h in rec.get("hidden", []) if h["side"] == side]
                for f in rec["findings"]:
                    span = f.get("evidence_" + side)
                    if not span:
                        continue
                    loc = _loc(span)
                    stats["evidence spans"] += 1
                    if doc.slice(loc) != f[side + "_value"]:
                        problems.append(where + (f["id"], "evidence slice"))
                    if fmt == "pdf":
                        stats["pdf evidence spans"] += 1
                        if any(b.hidden for b in doc.blocks if _overlaps(loc, b)):
                            problems.append(where + (f["id"], "evidence flagged hidden"))
                for loc in hidden:
                    stats["hidden spans"] += 1
                    over = [b for b in doc.blocks if _overlaps(loc, b)]
                    covered = set()
                    for b in over:
                        covered.update(range(b.locator.char_start, b.locator.char_end))
                    text = doc.slice(loc)
                    gaps = [i for i, c in enumerate(text, loc.char_start) if not c.isspace() and i not in covered]
                    if not over or gaps or not all(b.hidden for b in over):
                        problems.append(where + ("hidden span not flagged",))
                    if not any(w.code == "hidden_text" and w.page == loc.page for w in doc.warnings):
                        problems.append(where + ("no hidden_text warning",))
                labelled = [b for b in doc.blocks if b.hidden and not any(_overlaps(h, b) for h in hidden)]
                stats["unlabelled hidden blocks"] += len(labelled)
                if labelled:
                    problems.append(where + ("unlabelled hidden blocks", len(labelled)))
    print("\nconstructed dataset round trip: " + ", ".join("%s=%d" % kv for kv in sorted(stats.items())))
    assert stats["pdf sides"] and stats["text sides"] and stats["hidden spans"]
    assert not problems, problems
