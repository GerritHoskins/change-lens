"""Parse sandbox caps (kill on breach) and hostile-file fixtures, all generated in the tests."""
import os
import sys
import zlib
from pathlib import Path

import pytest

from changelens.config import Limits
from changelens.pipeline.sandbox import parse_sandboxed, run_sandboxed
from changelens.pipeline.types import ParseRejected
from helpers import make_pdf, raw_pdf, stream, text_page_pdf

PROBES = [str(Path(__file__).resolve().parent)]
LIMITS = Limits()
windows_only = pytest.mark.skipif(sys.platform != "win32", reason="Job Object caps; Linux uses setrlimit")


def probe(name, limits=LIMITS):
    return run_sandboxed("sandbox_probes:" + name, b"payload", {"x": 1}, limits, extra_path=PROBES)


def rejected(fn, *args) -> str:
    with pytest.raises(ParseRejected) as e:
        fn(*args)
    return e.value.code


# Sandbox mechanics ---------------------------------------------------------------------------
def test_child_round_trip_and_clean_environment(monkeypatch):
    monkeypatch.setenv("CHANGELENS_S3_SECRET_KEY", "must-not-reach-the-child")
    monkeypatch.setenv("CHANGELENS_DATABASE_URL", "postgresql://user:pw@host/db")
    assert probe("echo") == {"ok": True, "n": 7, "header": {"x": 1}}
    keys = probe("env_keys")["keys"]
    assert not [k for k in keys if k.startswith("CHANGELENS") or k.startswith("AWS")]
    assert set(keys) <= {"PYTHONDONTWRITEBYTECODE", "PYTHONIOENCODING", "OPENBLAS_NUM_THREADS",
                         "SYSTEMROOT", "WINDIR", "TEMP", "TMP"}


@windows_only
def test_memory_cap_kills_the_child():
    assert rejected(probe, "hog_memory", Limits(parse_memory_mb=256)) == "parse_memory_limit"


@windows_only
def test_cpu_cap_kills_the_child():
    assert rejected(probe, "spin_cpu", Limits(parse_cpu_seconds=1, parse_wall_seconds=30)) == "parse_cpu_limit"


def test_wall_clock_timeout_kills_the_child():
    assert rejected(probe, "sleep_forever", Limits(parse_wall_seconds=2)) == "parse_timeout"


@windows_only
def test_child_cannot_start_processes():
    assert probe("spawn_process") == {"ok": True, "spawned": False, "winerror": 1816}  # ERROR_NOT_ENOUGH_QUOTA


def test_crash_is_reported_without_details():
    assert rejected(probe, "crash") == "parse_crashed"


def test_sandboxed_parse_matches_in_process_parse():
    from changelens.pipeline.parse import parse
    data = make_pdf([["Alpha one", "Alpha two"], ["Beta"]])
    a, b = parse_sandboxed(data, "pdf", LIMITS), parse(data, "pdf", LIMITS)
    assert a.pages == b.pages and a.blocks == b.blocks and a.warnings == b.warnings


# Hostile files -------------------------------------------------------------------------------
def codes(doc):
    return [w.code for w in doc.warnings]


def test_oversized_pdf_is_rejected_in_the_sandbox_too():
    assert rejected(parse_sandboxed, make_pdf([["x"]]), "pdf", Limits(max_pdf_bytes=100)) == "limit_exceeded_bytes"


@pytest.mark.parametrize("data", [
    text_page_pdf()[:300],  # truncated mid-file
    b"%PDF-1.7\n" + bytes(range(256)) * 20,  # garbage after the header
    b"%PDF-1.7\n1 0 obj << /Type /Catalog /Pages 9 0 R >> endobj\ntrailer << /Root 1 0 R >>\n%%EOF",
])
def test_malformed_pdfs_are_rejected(data):
    assert rejected(parse_sandboxed, data, "pdf", LIMITS) == "malformed_pdf"


def test_javascript_and_open_action_are_warned_never_run():
    js = b"<< /S /JavaScript /JS (app.launchURL('https://example.invalid/x'); this.exportDataObject({cName:'a'})) >>"
    data = text_page_pdf(catalog_extra=b"/OpenAction 6 0 R /Names << /JavaScript << /Names [(a) 6 0 R] >> >>",
                         extra_objects=[js], page_extra=b"/AA << /O 6 0 R >>")
    doc = parse_sandboxed(data, "pdf", LIMITS)
    assert codes(doc) == ["active_content", "auto_action"]
    assert [b.text for b in doc.blocks] == ["Hello world"]
    import pypdfium2.version
    assert "V8" not in pypdfium2.version.PDFIUM_INFO.flags  # no JavaScript engine in this PDFium build


def test_embedded_file_is_warned_never_extracted(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    data = text_page_pdf(catalog_extra=b"/Names << /EmbeddedFiles << /Names [(evil.exe) 6 0 R] >> >>",
                         extra_objects=[b"<< /Type /Filespec /F (evil.exe) /EF << /F 7 0 R >> >>",
                                        stream(b"MZ not a real program", b"/Type /EmbeddedFile")])
    doc = parse_sandboxed(data, "pdf", LIMITS)
    assert codes(doc) == ["embedded_files"]
    assert "MZ not a real program" not in "".join(doc.pages)
    assert os.listdir(tmp_path) == []


@windows_only
def test_decompression_bomb_hits_the_memory_cap():
    bomb = zlib.compress(b" " * (400 * 1024 * 1024) + b"BT /F1 12 Tf 72 720 Td (Bomb) Tj ET", 9)
    data = text_page_pdf(content=stream(bomb, b"/Filter /FlateDecode"))
    assert len(data) < 1024 * 1024
    assert rejected(parse_sandboxed, data, "pdf", LIMITS) == "parse_memory_limit"


def test_page_count_bombs_are_rejected_before_parsing():
    many = text_page_pdf().replace(b"/Kids [3 0 R] /Count 1", b"/Kids [" + b" ".join([b"3 0 R"] * 5000) + b"] /Count 5000")
    lying = text_page_pdf().replace(b"/Count 1", b"/Count 999999")
    real = make_pdf([["page"]] * 21)
    for data in (many, lying, real):
        assert rejected(parse_sandboxed, data, "pdf", LIMITS) == "limit_exceeded_pages"


def test_giant_page_is_not_rendered():
    doc = parse_sandboxed(text_page_pdf(media=b"[0 0 14400 14400]"), "pdf", LIMITS)
    assert codes(doc) == ["visibility_unchecked"] and doc.blocks[0].hidden_reason == "page_too_large"


def test_image_regions_are_warned():
    img = stream(b"\x00" * 3, b"/Type /XObject /Subtype /Image /Width 1 /Height 1 /ColorSpace /DeviceRGB /BitsPerComponent 8")
    big = text_page_pdf(content=stream(b"q 500 0 0 500 50 50 cm /Im1 Do Q BT /F1 12 Tf 72 720 Td (Hi) Tj ET"),
                        extra_objects=[img])
    big = big.replace(b"/Font << /F1 4 0 R >>", b"/Font << /F1 4 0 R >> /XObject << /Im1 6 0 R >>")
    small = big.replace(b"500 0 0 500", b"40 0 0 40")
    assert "unextracted_region" in codes(parse_sandboxed(big, "pdf", LIMITS))
    assert codes(parse_sandboxed(small, "pdf", LIMITS)) == ["image_region"]


def test_raw_pdf_helper_builds_valid_files():
    lines = ["Alpha line one", "Beta line two"]
    assert [b.text for b in parse_sandboxed(text_page_pdf(lines), "pdf", LIMITS).blocks] == lines
    assert raw_pdf([b"<< /Type /Catalog >>"]).startswith(b"%PDF-1.7")
