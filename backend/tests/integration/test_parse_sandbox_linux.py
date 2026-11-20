"""The parse sandbox on Linux, as production runs it (03 §6, LR-4). It needs no database: it is in this
folder because this is the suite CI runs on Linux, and the Windows caps have their tests in tests/unit.

The kernel doesn't apply the process limit to root, so these tests need an ordinary user, as in CI and in
the backend image (uid 10001).
"""
import os
import sys
from pathlib import Path

import pytest

from changelens.config import Limits
from changelens.pipeline.sandbox import parse_sandboxed, run_sandboxed
from changelens.pipeline.types import ParseRejected
from helpers import make_pdf

pytestmark = pytest.mark.skipif(sys.platform != "linux" or os.geteuid() == 0,
                                reason="Linux as an ordinary user: setrlimit and prctl")
PROBES = [str(Path(__file__).resolve().parents[1] / "unit")]


def probe(name, limits=Limits()):
    return run_sandboxed("sandbox_probes:" + name, b"payload", {"x": 1}, limits, extra_path=PROBES)


def rejected(name, limits) -> str:
    with pytest.raises(ParseRejected) as e:
        probe(name, limits)
    return e.value.code


def test_the_child_cannot_read_its_parent(monkeypatch):
    """The worker holds the database, storage and model credentials in its environment and memory."""
    monkeypatch.setenv("CHANGELENS_S3_SECRET_KEY", "must-not-reach-the-child")
    assert probe("read_parent") == {"ok": True, "opened": []}
    assert not [k for k in probe("env_keys")["keys"] if k.startswith("CHANGELENS")]


def test_the_child_cannot_start_a_process_or_a_thread():
    assert probe("fork_process") == {"ok": True, "forked": False, "errno": 11}  # EAGAIN
    assert probe("spawn_process")["spawned"] is False
    assert probe("start_thread") == {"ok": True, "started": False}


def test_memory_and_cpu_caps_stop_the_child():
    assert rejected("hog_memory", Limits(parse_memory_mb=256)) == "parse_memory_limit"
    assert rejected("spin_cpu", Limits(parse_cpu_seconds=1, parse_wall_seconds=30)) == "parse_cpu_limit"


def test_a_pdf_still_parses_under_the_limits():
    from changelens.pipeline.parse import parse
    data = make_pdf([["Budget: 12,000 EUR", "Deadline: 14 March"], ["Second page"]])
    inside, outside = parse_sandboxed(data, "pdf", Limits()), parse(data, "pdf", Limits())
    assert inside.blocks and inside.blocks == outside.blocks and inside.warnings == outside.warnings
