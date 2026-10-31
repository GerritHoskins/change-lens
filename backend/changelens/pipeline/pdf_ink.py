"""Visibility rules for PDF text (SA-9, 07 §4): a backend copy of `scripts/eval/pdf_ink.py`.

KEEP IN SYNC with scripts/eval/pdf_ink.py: the constants and the measurement must give the same
verdicts as the eval validator on the pages it measures (unrotated, CropBox equal to a MediaBox at
the origin), so the parser flags exactly the spans the dataset labels as hidden.
`tests/unit/test_visibility.py` fails if they drift.

Deliberate differences:
- Covered text (I-6). A span the ink rule calls visible is still `covered` when the page rendered
  from a second copy of the document with all text objects removed shows no difference there:
  the "ink" is an image or shape drawn over the text. The eval validator has no such rule.
- Geometry (I-1c). The eval validator fails closed on rotated pages, a CropBox or an offset
  MediaBox; the backend maps glyph boxes from user space into the rendered page (CropBox origin,
  then /Rotate) and measures them. On plain pages the mapping is the identity the eval code uses.
  Each page's mapping is cross-checked against PDFium's own FPDF_PageToDevice; a page where they
  disagree, an empty visible box or a render over MAX_RENDER_PIXELS still fails closed.
- Reading direction. Ink rows and glyph height are measured across the text's displayed
  direction: for text that runs vertically on screen (rotated pages, or vertical text) that is
  columns and box width. For horizontal text this is exactly the eval rule.
- Speed: one render per page, numpy instead of per-pixel Python; the background colour tie-break
  mirrors the eval code's first-seen order explicitly. Characters PDFium generated itself (no
  character index) are skipped; the eval validator rejects them.
"""
from __future__ import annotations

import ctypes
import math
from typing import Optional

import numpy as np
import pypdfium2 as pdfium

HIDDEN_DPI = 144  # same raster resolution as render.py
HIDDEN_PAD = 4  # background sample margin around the character boxes, in pixels
INK_DELTA = 8  # a channel this far from the background colour counts as ink (about 3% contrast)
MAX_INK_ROWS = 3  # more ink rows than this means a reader can see the text
MAX_GLYPH_PT = 0.8  # tiny text: no glyph box taller than this (1 pt Helvetica capitals are ~0.72 pt)
SCALE = HIDDEN_DPI / 72
MAPPING_TOLERANCE_PX = 1.5  # our mapping vs FPDF_PageToDevice, which rounds to whole pixels


class Unmeasurable(Exception):
    """Visibility cannot be measured on this page, so its text fails closed. `code` says why."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


class PageGeometry:
    """Maps PDF user space to the displayed page: points, origin top-left, y down, after /Rotate."""

    def __init__(self, page):
        self.rotation = page.get_rotation()
        if self.rotation not in (0, 90, 180, 270):
            raise Unmeasurable("page_geometry")
        # Visible box (CropBox clipped to MediaBox), in user space.
        self.x0, self.y0, self.x1, self.y1 = page.get_bbox()
        w, h = self.x1 - self.x0, self.y1 - self.y0
        if not (w > 0 and h > 0 and math.isfinite(w * h)):
            raise Unmeasurable("page_geometry")
        self.w, self.h = w, h
        self.width, self.height = (w, h) if self.rotation in (0, 180) else (h, w)
        size = page.get_size()
        if abs(size[0] - self.width) > 0.5 or abs(size[1] - self.height) > 0.5:
            raise Unmeasurable("page_geometry")

    def point(self, x: float, y: float) -> tuple[float, float]:
        u, v = x - self.x0, self.y1 - y  # unrotated, top-left origin
        if self.rotation == 0:
            return u, v
        if self.rotation == 90:
            return self.h - v, u
        if self.rotation == 180:
            return self.w - u, self.h - v
        return v, self.w - u

    def box(self, left, bottom, right, top) -> tuple[float, float, float, float]:
        """User-space box -> displayed (left, top, right, bottom)."""
        (ax, ay), (bx, by) = self.point(left, bottom), self.point(right, top)
        return min(ax, bx), min(ay, by), max(ax, bx), max(ay, by)

    def cross_check(self, page) -> None:
        """Compare with PDFium's own page-to-device mapping at the visible box's corners and centre."""
        bw, bh = round(self.width * SCALE), round(self.height * SCALE)
        dx, dy = ctypes.c_int(), ctypes.c_int()
        xs, ys = (self.x0, (self.x0 + self.x1) / 2, self.x1), (self.y0, (self.y0 + self.y1) / 2, self.y1)
        for x in xs:
            for y in ys:
                if not pdfium.raw.FPDF_PageToDevice(page.raw, 0, 0, bw, bh, 0, x, y, dx, dy):
                    raise Unmeasurable("page_geometry")
                px, py = self.point(x, y)
                if abs(px * SCALE - dx.value) > MAPPING_TOLERANCE_PX or abs(py * SCALE - dy.value) > MAPPING_TOLERANCE_PX:
                    raise Unmeasurable("page_geometry")


class PageInk:
    """One rendered page plus its text page, measured span by span."""

    def __init__(self, page, textpage, max_render_pixels: int, spare_page=None):
        self.geo = PageGeometry(page)
        if self.geo.width * SCALE * self.geo.height * SCALE > max_render_pixels:
            raise Unmeasurable("page_too_large")
        self.geo.cross_check(page)
        self.page, self.tp = page, textpage
        self.spare = spare_page  # the same page from a second copy of the document, for `textless`
        self.width, self.height = self.geo.width, self.geo.height
        self._pixels: Optional[np.ndarray] = None
        self._textless: Optional[np.ndarray] = None

    @staticmethod
    def _render(page) -> np.ndarray:
        bitmap = page.render(scale=SCALE, rev_byteorder=True)
        try:
            return bitmap.to_numpy()[:, :, :3].astype(np.int16)
        finally:
            bitmap.close()

    def pixels(self) -> np.ndarray:
        if self._pixels is None:
            self._pixels = self._render(self.page)
        return self._pixels

    def textless(self) -> Optional[np.ndarray]:
        """The page rendered with every text object removed (I-6), or None without a spare page.
        Where it equals `pixels()`, the text there changes nothing a reader sees: something is
        drawn over it (an image or a shape), whatever the colours or texture of the cover."""
        if self._textless is None and self.spare is not None:
            _strip_text(self.spare.raw, pdfium.raw.FPDFPage_CountObjects, pdfium.raw.FPDFPage_GetObject,
                        pdfium.raw.FPDFPage_RemoveObject)
            self._textless = self._render(self.spare)
        return self._textless

    def char_boxes(self, start: int, end: int) -> list:
        """(user-space box, char index) for text-range offsets; generated characters are skipped."""
        out = []
        for i in range(start, end):
            ci = pdfium.raw.FPDFText_GetCharIndexFromTextIndex(self.tp, i)
            if ci >= 0:
                out.append((self.tp.get_charbox(ci), ci))
        return out

    def vertical(self, ci: int) -> bool:
        """Does this character's text run vertically on the displayed page?"""
        angle = pdfium.raw.FPDFText_GetCharAngle(self.tp, ci)
        if angle < 0:
            return self.geo.rotation in (90, 270)
        turns = (math.degrees(angle) - self.geo.rotation) / 90
        nearest = round(turns)
        return abs(turns - nearest) < 0.1 and nearest % 2 == 1

    def measure(self, start: int, end: int) -> tuple[int, int, float]:
        """(ink rows, on-page characters, tallest on-page glyph box in points) for a text-range span,
        rows and height taken across the text's displayed direction."""
        ink, chars, glyph, _ = self._measure(start, end)
        return ink, chars, glyph

    def _measure(self, start: int, end: int) -> tuple[int, int, float, Optional[int]]:
        """`measure` plus the rows where removing the text changes the render (None: not checked)."""
        width, height = self.width, self.height
        boxes, vertical = [], None
        for user_box, ci in self.char_boxes(start, end):
            left, top, right, bottom = self.geo.box(*user_box)
            if right <= 0 or left >= width or bottom <= 0 or top >= height:
                continue  # wholly outside the visible page: cropped away or off the page
            boxes.append((max(left, 0), max(top, 0), min(right, width), min(bottom, height)))
            if vertical is None:
                vertical = self.vertical(ci)
        if not boxes:
            return 0, 0, 0.0, None
        px = self.pixels()
        bh, bw = px.shape[0], px.shape[1]
        x0 = max(0, math.floor(min(b[0] for b in boxes) * SCALE) - HIDDEN_PAD)
        x1 = min(bw, math.ceil(max(b[2] for b in boxes) * SCALE) + HIDDEN_PAD)
        y0 = max(0, math.floor(min(b[1] for b in boxes) * SCALE) - HIDDEN_PAD)
        y1 = min(bh, math.ceil(max(b[3] for b in boxes) * SCALE) + HIDDEN_PAD)
        region = px[y0:y1, x0:x1]
        bare = self.textless()
        bare = None if bare is None or bare.shape != px.shape else bare[y0:y1, x0:x1]
        if vertical:
            region = region.transpose(1, 0, 2)
            bare = None if bare is None else bare.transpose(1, 0, 2)
            glyph = max(b[2] - b[0] for b in boxes)
        else:
            glyph = max(b[3] - b[1] for b in boxes)
        if region.size == 0:
            return 0, len(boxes), glyph, None
        flat = region.reshape(-1, 3)
        keys = (flat[:, 0].astype(np.int64) << 16) | (flat[:, 1].astype(np.int64) << 8) | flat[:, 2]
        uniq, first, counts = np.unique(keys, return_index=True, return_counts=True)
        top = counts == counts.max()
        bg = flat[first[top].min()]  # most frequent colour; ties go to the first seen, as in the eval code
        ink_px = (np.abs(region - bg).max(axis=2) > INK_DELTA)
        shown = None if bare is None else int((np.abs(region - bare).max(axis=2) > INK_DELTA).any(axis=1).sum())
        return int(ink_px.any(axis=1).sum()), len(boxes), glyph, shown

    def hidden_reason(self, start: int, end: int) -> Optional[str]:
        """None if a reader can see the span, else why not (the eval `visible_reason` inverted).
        `covered` is backend-only (I-6): the span has ink, but removing the text changes no pixel,
        so what looks like ink is whatever was drawn over it."""
        ink, chars, glyph, shown = self._measure(start, end)
        if chars == 0:
            return "off_page"
        if ink == 0:
            return "no_ink"
        if ink <= MAX_INK_ROWS and glyph <= MAX_GLYPH_PT:
            return "tiny"
        if shown == 0:
            return "covered"
        return None


def _strip_text(holder, count, get, remove) -> None:
    """Remove every text object from a page or form XObject, nested forms included."""
    for i in reversed(range(count(holder))):
        obj = get(holder, i)
        kind = pdfium.raw.FPDFPageObj_GetType(obj)
        if kind == pdfium.raw.FPDF_PAGEOBJ_TEXT:
            if remove(holder, obj):
                pdfium.raw.FPDFPageObj_Destroy(obj)
        elif kind == pdfium.raw.FPDF_PAGEOBJ_FORM:
            _strip_text(obj, pdfium.raw.FPDFFormObj_CountObjects, pdfium.raw.FPDFFormObj_GetObject,
                        pdfium.raw.FPDFFormObj_RemoveObject)
