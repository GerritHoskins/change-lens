"""Synthetic test documents only. Never read real client documents or ../change-lens-data."""
from __future__ import annotations

import io

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas

TOKEN_A = "dev-token-tenant-a-0123456789"
TOKEN_B = "dev-token-tenant-b-0123456789"

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
