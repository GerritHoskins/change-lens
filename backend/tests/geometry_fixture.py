"""I-1c fixture: one page with visible, hidden and cropped-away lines under any rotation, CropBox
and MediaBox offset. Built from raw PDF operators so every case is exact."""
from helpers import stream, text_page_pdf


def geometry_pdf(rotate=0, crop=False, offset=(0, 0), vertical_text=False) -> tuple[bytes, dict]:
    """A page with visible, hidden and (with `crop`) cropped-away lines. Returns (pdf, {line: hidden})."""
    ox, oy = offset
    lines = [  # label, font size, fill operator, y, expected hidden
        ("Visible line one", 12, b"0 g", 720, False),
        ("White on white injected text", 12, b"1 g", 690, True),
        ("Tiny injected words here", 0.5, b"0 g", 660, True),
        ("Covered injected text", 12, b"0 g", 630, True),
        ("Light grey still readable", 12, b"0.875 g", 600, False),
        ("Visible line two near crop", 12, b"0 g", 330, False),
        ("Cropped away text", 12, b"0 g", 120, crop),
    ]
    ops, expected = b"", {}
    for label, size, fill, y, hidden in lines:
        if vertical_text:  # text drawn rotated 90 degrees in user space, reading bottom to top
            tm = b"0 1 -1 0 %d %d Tm" % (ox + 40 + (720 - y) // 2, oy + 340 + (720 - y) // 8)
        else:
            tm = b"1 0 0 1 %d %d Tm" % (ox + 72, oy + y)
        ops += b"BT /F1 %s Tf %s %s (%s) Tj ET\n" % (str(size).encode(), fill, tm, label.encode())
        expected[label] = hidden
    if not vertical_text:  # opaque white panel over the covered line
        ops += b"q 1 g %d %d 400 18 re f Q\n" % (ox + 60, oy + 626)
    else:
        expected.pop("Covered injected text")
        ops = ops.replace(b"(Covered injected text)", b"()")
    media = b"[%d %d %d %d]" % (ox, oy, ox + 612, oy + 792)
    extra = b"/Rotate %d" % rotate
    if crop:
        extra += b" /CropBox [%d %d %d %d]" % (ox, oy + 300, ox + 612, oy + 792)
    return text_page_pdf(content=stream(ops), media=media, page_extra=extra), expected
