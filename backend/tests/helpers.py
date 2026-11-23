"""Synthetic test documents only. Never read real client documents or ../change-lens-data."""
from __future__ import annotations

import io

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

TOKEN_A = "dev-token-tenant-a-0123456789"
TOKEN_B = "dev-token-tenant-b-0123456789"
# The fixed subjects the two dev tokens map to; fixtures seed a user and owner membership for each.
SUBJECT_A = "dev:tenant-a"
SUBJECT_B = "dev:tenant-b"
DEV_TOKENS = {TOKEN_A: SUBJECT_A, TOKEN_B: SUBJECT_B}
# What a deployment (logto mode) must set for the early-bird list's confirmation mail and removal links;
# synthetic values.
EARLY_BIRD_ENV = {"CHANGELENS_SMTP_HOST": "smtp.example.test", "CHANGELENS_SMTP_USER": "noreply@example.test",
                  "CHANGELENS_SMTP_PASSWORD": "smtp-password-0123456789", "CHANGELENS_MAIL_FROM": "noreply@example.test",
                  "CHANGELENS_PUBLIC_API_URL": "https://api.example.test",
                  "CHANGELENS_LANDING_URL": "https://landing.example.test",
                  "CHANGELENS_EARLY_BIRD_UNSUBSCRIBE_KEY": "unsubscribe-key-for-tests-0123456789"}

EARLIER_LINES = [
    "Project brief: website relaunch",
    "Budget: EUR 12,000",
    "Deadline: 15 March",
    "Pages: home, about, contact",
    "Hosting is provided by the client",
]
LATER_LINES = [
    "Project brief: website relaunch",
    "Budget: EUR 15,000",
    "Deadline: 15 March",
    "Pages: home, about, contact, blog",
    "Copywriting is included",
]


def make_pdf(pages: list[list[str]]) -> bytes:
    """A tiny text PDF, one line per string; an empty list makes a page with no text."""
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    for lines in pages:
        y = 800
        for line in lines:
            c.drawString(72, y, line)
            y -= 18
        c.showPage()
    c.save()
    return buf.getvalue()


def auth(token: str) -> dict:
    return {"Authorization": "Bearer " + token}


def raw_pdf(objects: list, root: int = 1) -> bytes:
    """Hand-built PDF from object bodies (object n is objects[n-1]), with a correct xref table.
    Used for hostile fixtures reportlab will not produce; nothing binary is committed."""
    out = bytearray(b"%PDF-1.7\n%\xe2\xe3\xcf\xd3\n")
    offsets = []
    for n, body in enumerate(objects, 1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % n + body + b"\nendobj\n"
    xref = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    out += b"".join(b"%010d 00000 n \n" % o for o in offsets)
    out += b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%%%EOF\n" % (len(objects) + 1, root, xref)
    return bytes(out)


def stream(data: bytes, extra: bytes = b"") -> bytes:
    return b"<< /Length %d %s >>\nstream\n" % (len(data), extra) + data + b"\nendstream"


def text_page_pdf(lines=("Hello world",), catalog_extra=b"", extra_objects=(), media=b"[0 0 612 792]",
                  page_extra=b"", content=None) -> bytes:
    """One Helvetica text page. Objects 1-5 are fixed; `extra_objects` start at 6."""
    if content is None:
        ops = b"".join(b"BT /F1 12 Tf 72 %d Td (%s) Tj ET\n" % (720 - 18 * i, l.encode("latin-1"))
                       for i, l in enumerate(lines))
        content = stream(ops)
    objs = [b"<< /Type /Catalog /Pages 2 0 R " + catalog_extra + b" >>",
            b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
            b"<< /Type /Page /Parent 2 0 R /MediaBox " + media + b" /Resources << /Font << /F1 4 0 R >> >> "
            b"/Contents 5 0 R " + page_extra + b" >>",
            b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
            content] + list(extra_objects)
    return raw_pdf(objs)
