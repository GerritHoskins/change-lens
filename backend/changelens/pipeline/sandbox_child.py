"""Child side of the parse sandbox. Reads `>I header-length, header JSON, payload` from stdin and
writes one JSON object to stdout. Exit code 3 means the child ran out of memory."""
from __future__ import annotations

import importlib
import json
import struct
import sys


def parse_entry(header: dict, payload: bytes) -> dict:
    from changelens.config import Limits
    from changelens.pipeline.parse import parse
    from changelens.pipeline.types import ParseRejected
    try:
        doc = parse(payload, header["kind"], Limits(**header["limits"]))
    except ParseRejected as r:
        return {"ok": False, "code": r.code}
    return {"ok": True, "doc": doc.to_json()}


def main(entry: str) -> None:
    raw = sys.stdin.buffer.read()
    (n,) = struct.unpack(">I", raw[:4])
    header, payload = json.loads(raw[4:4 + n]), raw[4 + n:]
    module, func = entry.split(":")
    try:
        result = getattr(importlib.import_module(module), func)(header, payload)
    except MemoryError:
        sys.exit(3)
    sys.stdout.buffer.write(json.dumps(result).encode("utf-8"))
    sys.stdout.flush()
