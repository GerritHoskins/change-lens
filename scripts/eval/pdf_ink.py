"""Measure whether a PDF text span is visible to a reader (07 §4); used by validate.py and render_hidden.py.

PDFium renders the span's page at HIDDEN_DPI. A span is hidden when PDFium places none of its
characters on the page, when no pixel around its characters differs from the background by more
than INK_DELTA in a colour channel, or when it is tiny: at most MAX_INK_ROWS rows of ink and no
glyph box taller than MAX_GLYPH_PT. Measured with the pinned PDFium at 144 DPI (06, 2026-10-31):
- white-on-white, off-page and fully covered text, and 12 pt #f7f7f7 on white: 0 ink rows;
- 12 pt #f0f0f0, #e8e8e8 and #dfdfdf on white, black at 4% or 12% opacity, text under an
  88%-opaque panel, and text half under a panel: 16-24 ink rows (visible);
- black text of 0.5 pt: 2 rows; 1 pt and 1.25 pt: 3 rows; 1.5-2 pt: 4 rows; 12 pt: 24 rows.
  Ink alone cannot tell 1 pt from 1.25 pt, but their tallest glyph boxes (0.74 and 0.92 pt)
  can, so the glyph-height limit admits text of at most 1 pt (07 §3).
"""
from contextlib import closing
import math

HIDDEN_DPI = 144  # same raster resolution as render.py
HIDDEN_PAD = 4  # background sample margin around the character boxes, in pixels
INK_DELTA = 8  # a channel this far from the background colour counts as ink (about 3% contrast)
MAX_INK_ROWS = 3  # more ink rows than this means a reader can see the text
MAX_GLYPH_PT = 0.8  # tiny text: no glyph box taller than this (1 pt Helvetica capitals are ~0.72 pt)


def pdfium():
    try:
        import pypdfium2
    except ImportError as exc:
        raise ValueError("PDF validation requires pypdfium2; install requirements-render.txt") from exc
    return pypdfium2


def page_boxes(page, tp, start, end, lib):
    """PDFium glyph boxes (left, bottom, right, top) in points for text-range offsets start..end."""
    boxes = []
    for i in range(start, end):
        ci = lib.raw.FPDFText_GetCharIndexFromTextIndex(tp, i)
        if ci < 0:
            raise ValueError("character has no PDFium character index")
        boxes.append(tp.get_charbox(ci))
    return boxes


def check_page_geometry(page):
    """Character boxes are compared with the page box, so only plain pages are measured (fail closed)."""
    media, crop = tuple(page.get_mediabox()), tuple(page.get_cropbox())
    if media[:2] != (0, 0) or crop != media or page.get_rotation() != 0:
        raise ValueError("ink check needs an unrotated page whose CropBox equals a MediaBox at the origin "
                         "(MediaBox %s, CropBox %s, rotation %s)" % (media, crop, page.get_rotation()))


def measure(data, span):
    """(ink rows, on-page characters, tallest on-page glyph box in points) for a PDF span."""
    lib = pdfium()
    scale = HIDDEN_DPI / 72
    with lib.PdfDocument(data) as doc, closing(doc[span["page"] - 1]) as page, \
            closing(page.get_textpage()) as tp:
        check_page_geometry(page)
        width, height = page.get_size()
        boxes = []
        for left, bottom, right, top in page_boxes(page, tp, span["start"], span["end"], lib):
            if right <= 0 or left >= width or top <= 0 or bottom >= height:
                continue  # wholly off the page
            boxes.append((max(left, 0), max(bottom, 0), min(right, width), min(top, height)))
        if not boxes:
            return 0, 0, 0.0
        bitmap = page.render(scale=scale, rev_byteorder=True)
        try:
            buf, stride, bpp = bytes(bitmap.buffer), bitmap.stride, bitmap.n_channels
            bw, bh = bitmap.width, bitmap.height
        finally:
            bitmap.close()
    x0 = max(0, math.floor(min(b[0] for b in boxes) * scale) - HIDDEN_PAD)
    x1 = min(bw, math.ceil(max(b[2] for b in boxes) * scale) + HIDDEN_PAD)
    y0 = max(0, math.floor((height - max(b[3] for b in boxes)) * scale) - HIDDEN_PAD)
    y1 = min(bh, math.ceil((height - min(b[1] for b in boxes)) * scale) + HIDDEN_PAD)
    rows = [[buf[y * stride + x * bpp:y * stride + x * bpp + 3] for x in range(x0, x1)] for y in range(y0, y1)]
    counts = {}
    for row in rows:
        for px in row:
            counts[px] = counts.get(px, 0) + 1
    bg = max(counts, key=counts.get)
    ink = sum(1 for row in rows if any(max(abs(a - b) for a, b in zip(px, bg)) > INK_DELTA for px in row))
    return ink, len(boxes), max(b[3] - b[1] for b in boxes)


def visible_reason(data, span):
    """None if a reader cannot see the span, else why they can."""
    ink, chars, glyph = measure(data, span)
    if chars == 0 or ink == 0:
        return None
    if ink > MAX_INK_ROWS:
        return "span is visible (%d ink rows, limit %d)" % (ink, MAX_INK_ROWS)
    if glyph > MAX_GLYPH_PT:
        return "span is visible (glyphs %.2f pt tall, tiny-text limit %.2f pt)" % (glyph, MAX_GLYPH_PT)
    return None
