"""Run PDF parsing in a capped child process (03 §6 Upload validation, 03a P3, AC-20).

The child gets the document on stdin and returns JSON on stdout. Its environment holds no
credentials, it is started with `-I` (no PYTHON* variables, user site or script directory), and on breach it is
killed and the version rejected with a content-free reason:

- wall clock: `parse_wall_seconds`, enforced by the parent on every platform -> `parse_timeout`;
- Windows: a Job Object caps the child's committed memory (`parse_memory_mb`) and user CPU time
  (`parse_cpu_seconds`), allows one active process, and kills the child when the job closes;
- Linux (production): `setrlimit` for address space, CPU seconds, file size 0 and no core dumps.
  Not exercised by the tests on this machine.
- page count: checked inside the child, after PDFium opens the file and before any page is parsed.

Limitation: neither platform removes network access from the child here. The child runs only our
parse code, which makes no network calls; production should also run the worker with outbound
traffic restricted to the model API and storage (03 §6).
"""
from __future__ import annotations

import json
import os
import struct
import subprocess
import sys
import sysconfig
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from changelens.config import Limits
from changelens.pipeline.types import Kind, ParsedDocument, ParseRejected

BACKEND_ROOT = str(Path(__file__).resolve().parents[2])
CHILD_ENTRY = "changelens.pipeline.sandbox_child:parse_entry"
MAX_OUTPUT_FACTOR = 8  # JSON output may be this many times the text cap before it is refused


def _interpreter() -> str:
    """The real interpreter: a Windows venv's python.exe is a launcher that would start the actual
    interpreter as a second process outside the Job Object, so the base executable is used and the
    venv's site-packages are put on its path explicitly."""
    return getattr(sys, "_base_executable", None) or sys.executable


def _child_env() -> dict:
    # One BLAS thread: OpenBLAS otherwise commits ~0.5 GB of per-thread buffers when numpy loads.
    env = {"PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8", "OPENBLAS_NUM_THREADS": "1"}
    for key in ("SYSTEMROOT", "WINDIR", "TEMP", "TMP"):  # Windows needs these for Python to start
        if key in os.environ:
            env[key] = os.environ[key]
    return env


def run_sandboxed(entry: str, payload: bytes, header: dict, limits: Limits,
                  extra_path: Optional[list] = None) -> dict:
    """Run `module:function(header, payload) -> dict` in a capped child; returns its dict or raises."""
    paths = [BACKEND_ROOT] + list(dict.fromkeys(sysconfig.get_paths()[k] for k in ("purelib", "platlib")))
    boot = ("import sys; sys.path[:0] = %r; from changelens.pipeline.sandbox_child import main; main(%r)"
            % (paths + list(extra_path or []), entry))
    kwargs = {}
    if sys.platform != "win32":
        kwargs["preexec_fn"] = _posix_limits(limits)
    proc = subprocess.Popen([_interpreter(), "-I", "-c", boot], stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, env=_child_env(),
                            cwd=BACKEND_ROOT, **kwargs)
    job = None
    try:
        if sys.platform == "win32":
            from changelens.pipeline import winjob
            job = winjob.confine(proc, limits.parse_memory_mb * 1024 * 1024, limits.parse_cpu_seconds)
        head = json.dumps(header).encode()
        try:
            out, _ = proc.communicate(struct.pack(">I", len(head)) + head + payload,
                                      timeout=limits.parse_wall_seconds)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.communicate()
            raise ParseRejected("parse_timeout") from None
        except (BrokenPipeError, OSError):
            proc.kill()
            out, _ = proc.communicate()
        code = proc.returncode
        if code != 0:
            raise ParseRejected(_breach(code, job, limits))
        if len(out) > MAX_OUTPUT_FACTOR * limits.max_extracted_chars:
            raise ParseRejected("limit_exceeded_text")
        try:
            return json.loads(out)
        except ValueError:
            raise ParseRejected("parse_crashed") from None
    finally:
        if proc.poll() is None:
            proc.kill()
        if job is not None:
            winjob.close(job)


def _breach(code: int, job, limits: Limits) -> str:
    """Name the cap a failed child hit. A refused allocation does not raise the recorded peak, so a
    failure after using half the memory cap counts as a memory breach (e.g. a decompression bomb)."""
    if job is not None:
        from changelens.pipeline import winjob
        peak, cpu = winjob.usage(job)
        if cpu >= limits.parse_cpu_seconds:
            return "parse_cpu_limit"
        if peak >= 0.5 * limits.parse_memory_mb * 1024 * 1024:
            return "parse_memory_limit"
    if code == 3:
        return "parse_memory_limit"  # MemoryError in the child (RLIMIT_AS on Linux)
    if sys.platform != "win32" and code in (-24, -9):
        return "parse_cpu_limit"  # SIGXCPU, then SIGKILL, at RLIMIT_CPU
    return "parse_crashed"


def _posix_limits(limits: Limits):
    def apply():
        import resource
        mem = limits.parse_memory_mb * 1024 * 1024
        resource.setrlimit(resource.RLIMIT_AS, (mem, mem))
        resource.setrlimit(resource.RLIMIT_CPU, (limits.parse_cpu_seconds, limits.parse_cpu_seconds))
        resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    return apply


def parse_sandboxed(data: bytes, kind: Kind, limits: Limits) -> ParsedDocument:
    """The worker's entry point: PDFs are parsed in the sandbox; text is decoded in-process."""
    if kind != "pdf":
        from changelens.pipeline.parse import parse
        return parse(data, kind, limits)
    result = run_sandboxed(CHILD_ENTRY, data, {"kind": kind, "limits": asdict(limits)}, limits)
    if not result.get("ok"):
        raise ParseRejected(str(result.get("code", "parse_crashed"))[:50])
    return ParsedDocument.from_json(result["doc"])
