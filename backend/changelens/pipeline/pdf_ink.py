"""Visibility rules for PDF text (SA-9, 07 §4): a backend copy of `scripts/eval/pdf_ink.py`.

KEEP IN SYNC with scripts/eval/pdf_ink.py: the constants, the page-geometry check and the
measurement below must give the same verdicts as the eval validator, so the parser flags exactly
the spans the dataset labels as hidden. `tests/unit/test_pdf_ink_sync.py` fails if they drift.

Differences, which change speed but not verdicts: the page is rendered once and reused for every
span (numpy instead of per-pixel Python), and the background colour tie-break mirrors the eval
code's first-seen order explicitly; generated characters are skipped. A page too large to render under MAX_RENDER_PIXELS is
reported as unmeasurable instead of being rendered (decompression and memory bombs).
"""
from __future__ import annotations

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


class Unmeasurable(Exception):
    """Visibility cannot be measured on this page, so its text fails closed. `code` says why."""

    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def check_page_geometry(page) -> None:
    """Only plain pages are measured: CropBox equal to a MediaBox at the origin, no rotation."""
    media, crop = tuple(page.get_mediabox()), tuple(page.get_cropbox())
    if media[:2] != (0, 0) or crop != media or page.get_rotation() != 0:
        raise Unmeasurable("page_geometry")


class PageInk:
    """One rendered page plus its text page, measured span by span."""

    def __init__(self, page, textpage, max_render_pixels: int):
        check_page_geometry(page)
        self.page, self.tp = page, textpage
        self.width, self.height = page.get_size()
        if self.width * SCALE * self.height * SCALE > max_render_pixels:
            raise Unmeasurable("page_too_large")
        self._pixels: Optional[np.ndarray] = None

    def pixels(self) -> np.ndarray:
        if self._pixels is None:
            bitmap = self.page.render(scale=SCALE, rev_byteorder=True)
            try:
                self._pixels = bitmap.to_numpy()[:, :, :3].astype(np.int16)
            finally:
                bitmap.close()
        return self._pixels

    def char_boxes(self, start: int, end: int) -> list:
        """Glyph boxes for text-range offsets. Characters PDFium generated itself (no character
        index, e.g. inserted spaces) have no glyph and are skipped; the eval validator rejects them."""
        boxes = []
        for i in range(start, end):
            ci = pdfium.raw.FPDFText_GetCharIndexFromTextIndex(self.tp, i)
            if ci >= 0:
                boxes.append(self.tp.get_charbox(ci))
        return boxes

    def measure(self, start: int, end: int) -> tuple[int, int, float]:
        """(ink rows, on-page characters, tallest on-page glyph box in points) for a text-range span."""
        width, height = self.width, self.height
        boxes = []
        for left, bottom, right, top in self.char_boxes(start, end):
            if right <= 0 or left >= width or top <= 0 or bottom >= height:
                continue  # wholly off the page
            boxes.append((max(left, 0), max(bottom, 0), min(right, width), min(top, height)))
        if not boxes:
            return 0, 0, 0.0
        px = self.pixels()
        bh, bw = px.shape[0], px.shape[1]
        x0 = max(0, math.floor(min(b[0] for b in boxes) * SCALE) - HIDDEN_PAD)
        x1 = min(bw, math.ceil(max(b[2] for b in boxes) * SCALE) + HIDDEN_PAD)
        y0 = max(0, math.floor((height - max(b[3] for b in boxes)) * SCALE) - HIDDEN_PAD)
        y1 = min(bh, math.ceil((height - min(b[1] for b in boxes)) * SCALE) + HIDDEN_PAD)
        region = px[y0:y1, x0:x1]
        glyph = max(b[3] - b[1] for b in boxes)
        if region.size == 0:
            return 0, len(boxes), glyph
        flat = region.reshape(-1, 3)
        keys = (flat[:, 0].astype(np.int64) << 16) | (flat[:, 1].astype(np.int64) << 8) | flat[:, 2]
        uniq, first, counts = np.unique(keys, return_index=True, return_counts=True)
        top = counts == counts.max()
        bg = flat[first[top].min()]  # most frequent colour; ties go to the first seen, as in the eval code
        ink_px = (np.abs(region - bg).max(axis=2) > INK_DELTA)
        return int(ink_px.any(axis=1).sum()), len(boxes), glyph

    def hidden_reason(self, start: int, end: int) -> Optional[str]:
        """None if a reader can see the span, else why not (the eval `visible_reason` inverted)."""
        ink, chars, glyph = self.measure(start, end)
        if chars == 0:
            return "off_page"
        if ink == 0:
            return "no_ink"
        if ink <= MAX_INK_ROWS and glyph <= MAX_GLYPH_PT:
            return "tiny"
        return None
