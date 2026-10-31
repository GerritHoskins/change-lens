"""I-1c: rotated pages, CropBox and offset MediaBox are measured instead of failing closed."""
import ctypes
import importlib.util
import itertools
from pathlib import Path

import pypdfium2 as pdfium
import pytest

from changelens.config import Limits
from changelens.pipeline.parse import parse
from changelens.pipeline.pdf_ink import SCALE, PageGeometry
from geometry_fixture import geometry_pdf
from helpers import text_page_pdf

EVAL_INK = Path(__file__).resolve().parents[3] / "scripts" / "eval" / "pdf_ink.py"
OFFSETS = ((0, 0), (100, 200))
ROTATIONS = (0, 90, 180, 270)


def flags(data):
    doc = parse(data, "pdf", Limits())
    return doc, {b.text: b.hidden for b in doc.blocks}


@pytest.mark.parametrize("rotate,crop,offset", list(itertools.product(ROTATIONS, (False, True), OFFSETS)))
def test_rotated_cropped_and_offset_pages_are_measured(rotate, crop, offset):
    data, expected = geometry_pdf(rotate, crop, offset)
    doc, got = flags(data)
    assert got == expected
    assert "visibility_unchecked" not in [w.code for w in doc.warnings]
    for b in doc.blocks:
        assert doc.slice(b.locator) == b.text  # locators are text offsets: unaffected by geometry
    reasons = {b.text: b.hidden_reason for b in doc.blocks if b.hidden}
    assert reasons["White on white injected text"] == "no_ink" and reasons["Tiny injected words here"] == "tiny"
    if crop:
        assert reasons["Cropped away text"] == "off_page"


@pytest.mark.parametrize("rotate", ROTATIONS)
def test_vertical_text_is_measured_across_its_direction(rotate):
    data, expected = geometry_pdf(rotate, vertical_text=True)
    assert flags(data)[1] == expected


@pytest.mark.parametrize("rotate,offset", list(itertools.product(ROTATIONS, OFFSETS)))
def test_mapping_matches_pdfium_page_to_device(rotate, offset):
    data, _ = geometry_pdf(rotate, True, offset)
    with pdfium.PdfDocument(data) as pdf:
        page = pdf[0]
        geo = PageGeometry(page)
        geo.cross_check(page)  # raises if any probe point disagrees
        bw, bh = round(geo.width * SCALE), round(geo.height * SCALE)
        dx, dy = ctypes.c_int(), ctypes.c_int()
        for x, y in ((offset[0] + 73, offset[1] + 720), (offset[0] + 500, offset[1] + 310)):
            pdfium.raw.FPDF_PageToDevice(page.raw, 0, 0, bw, bh, 0, x, y, dx, dy)
            px, py = geo.point(x, y)
            assert abs(px * SCALE - dx.value) <= 1 and abs(py * SCALE - dy.value) <= 1


def test_unmappable_pages_still_fail_closed():
    data, _ = geometry_pdf(0, crop=True)
    empty = data.replace(b"/CropBox [0 300 612 792]", b"/CropBox [0 300 0 792]")
    huge = text_page_pdf(media=b"[0 0 14400 14400]", page_extra=b"/Rotate 90")
    for pdf, reason in ((huge, "page_too_large"),):
        doc, _ = flags(pdf)
        assert [(b.hidden, b.hidden_reason) for b in doc.blocks] == [(True, reason)]
        assert [w.code for w in doc.warnings] == ["visibility_unchecked"]
    doc, _ = flags(empty)  # PDFium falls back to the MediaBox for an empty CropBox; never measured blind
    assert all(b.hidden for b in doc.blocks if b.text == "White on white injected text")


def test_eval_validator_keeps_failing_closed_on_these_pages():
    """Decision (06): scripts/eval/pdf_ink.py is unchanged and still refuses rotated or cropped pages;
    the dataset has none. The backend measures them; on plain pages both agree (test_visibility)."""
    spec = importlib.util.spec_from_file_location("eval_pdf_ink", EVAL_INK)
    eval_ink = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(eval_ink)
    data, _ = geometry_pdf(90, True, (100, 200))
    doc, _ = flags(data)
    b = doc.blocks[0]
    with pytest.raises(ValueError):
        eval_ink.visible_reason(data, {"page": 1, "start": b.locator.char_start, "end": b.locator.char_end})


def test_mapping_that_disagrees_with_pdfium_fails_closed(monkeypatch):
    """Stand-in for any transform we do not model: the cross-check refuses the page."""
    data, _ = geometry_pdf(90, True, (100, 200))
    real = PageGeometry.point
    monkeypatch.setattr(PageGeometry, "point", lambda self, x, y: real(self, x + 5, y))
    doc, _ = flags(data)
    assert all(b.hidden and b.hidden_reason == "page_geometry" for b in doc.blocks)
    assert [w.code for w in doc.warnings] == ["visibility_unchecked"]
