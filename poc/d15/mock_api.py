"""D-15 mock locator API: the backend half of the mobile highlight test (05 D-15).

POST /locate with a PDF body. The reply holds 20 test passages chosen deterministically from the
PDF's text, each with the locator the real pipeline will use (page, PDFium text-range start/end)
plus PDFium character indices and glyph boxes in PDF points (origin bottom-left of the MediaBox).
The app highlights the backend boxes and checks them against the boxes its own PDFium build
(pdfrx) reports for the same characters. Dev tool only: no auth, binds to localhost.

    .venv/Scripts/python poc/d15/mock_api.py [--port 8765]
    adb reverse tcp:8765 tcp:8765   # lets an Android phone on USB reach it as 127.0.0.1
"""
import argparse
from contextlib import closing
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import re

import pypdfium2 as pdfium

PASSAGES = 20
MAX_BYTES = 20 * 1024 * 1024


def char_index(tp, text_index):
    ci = pdfium.raw.FPDFText_GetCharIndexFromTextIndex(tp, text_index)
    if ci < 0:
        raise ValueError('text index %d has no PDFium character' % text_index)
    return ci


def candidates(page_no, text):
    """(page, start, end) phrases: the middle words of each line, plus a few spans across a line break."""
    spans, offset = [], 0
    lines = text.split('\r\n')
    for i, line in enumerate(lines):
        words = [(m.group(), m.start()) for m in re.finditer(r'\S+', line)]
        if len(words) >= 3:
            a, b = len(words) // 3, min(len(words), len(words) // 3 + 3)
            s, e = words[a][1], words[b - 1][1] + len(words[b - 1][0])
            spans.append((page_no, offset + s, offset + e))
        if i + 1 < len(lines) and line.split() and lines[i + 1].split() and i % 7 == 3:
            last = line.rsplit(None, 1)[-1]
            nxt = lines[i + 1].split()[0]
            s = offset + line.rindex(last)
            e = offset + len(line) + 2 + lines[i + 1].index(nxt) + len(nxt)
            spans.append((page_no, s, e))
        offset += len(line) + 2
    return spans


def locate(data):
    with pdfium.PdfDocument(data) as doc:
        pages, spans = [], []
        for n, page in enumerate(doc, 1):
            with closing(page), closing(page.get_textpage()) as tp:
                left, bottom, right, top = page.get_mediabox()
                pages.append({'width': right - left, 'height': top - bottom, 'rotation': page.get_rotation()})
                spans += candidates(n, tp.get_text_range())
        if not spans:
            return {'pages': pages, 'passages': []}
        step = max(1, len(spans) / PASSAGES)
        chosen = [spans[int(i * step)] for i in range(min(PASSAGES, len(spans)))]
        passages = []
        for k, (n, start, end) in enumerate(chosen):
            page = doc[n - 1]
            with closing(page), closing(page.get_textpage()) as tp:
                left, bottom = page.get_mediabox()[:2]
                text = tp.get_text_range()[start:end]
                c0, c1 = char_index(tp, start), char_index(tp, end - 1) + 1
                boxes = []
                for ci in range(c0, c1):
                    l, b, r, t = tp.get_charbox(ci)
                    if r > l and t > b:  # spaces and generated line breaks have no box
                        boxes.append([l - left, b - bottom, r - left, t - bottom])
            passages.append({'id': k + 1, 'page': n, 'start': start, 'end': end, 'text': text,
                             'char_start': c0, 'char_end': c1, 'boxes': boxes})
        return {'pages': pages, 'passages': passages}


class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        if self.path != '/locate':
            return self.reply(404, {'error': 'not_found'})
        length = int(self.headers.get('Content-Length') or 0)
        if not 0 < length <= MAX_BYTES:
            return self.reply(413, {'error': 'limit_exceeded'})
        data = self.rfile.read(length)
        if not data.startswith(b'%PDF-'):
            return self.reply(415, {'error': 'unsupported_type'})
        try:
            self.reply(200, locate(data))
        except Exception as exc:  # a dev tool: report, don't crash the server
            self.reply(422, {'error': 'unreadable_pdf', 'detail': str(exc)})

    def reply(self, status, body):
        raw = json.dumps(body).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Content-Length', str(len(raw)))
        self.end_headers()
        self.wfile.write(raw)

    def log_message(self, fmt, *args):  # status lines only, never document content
        print('%s %s' % (self.command, args[1] if len(args) > 1 else ''))


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('--port', type=int, default=8765)
    ap.add_argument('--host', default='127.0.0.1', help='use 0.0.0.0 only on a trusted LAN (iPhone over Wi-Fi)')
    a = ap.parse_args()
    print('D-15 mock locator API on http://%s:%d/locate' % (a.host, a.port))
    ThreadingHTTPServer((a.host, a.port), Handler).serve_forever()


if __name__ == '__main__':
    main()
