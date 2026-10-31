"""Deterministic visual fixtures; install requirements-render.txt in .venv first.

The text operators own labels. PDFium owns reference text and character geometry.
All outputs (including the human review sheet) must stay outside git.
"""
import argparse
from contextlib import closing
import base64
import copy
import hashlib
import html
import io
import json
import math
from pathlib import Path

import pypdfium2 as pdfium
from PIL import Image, ImageDraw, ImageFilter
from reportlab.pdfgen import canvas
from reportlab.pdfbase.pdfmetrics import stringWidth

import generate

DPI = 144
SCALE = DPI / 72
PAGE = (842, 842)
OPS = ('value_change', 'qualifier_flip', 'partial_update', 'no_change', 'replacement')


def make_pdf(text):
    """Keep each source line intact; return bytes and source-line/page mapping."""
    stream = io.BytesIO()
    pdf = canvas.Canvas(stream, pagesize=PAGE, invariant=1, pageCompression=1)
    pdf.setTitle('ChangeLens constructed brief')
    pdf.setAuthor('ChangeLens')
    lines, offset, page, y = [], 0, 1, PAGE[1] - 48
    for raw in text.splitlines(keepends=True):
        line = raw.rstrip('\r\n')
        if y < 48:
            pdf.showPage()
            page, y = page + 1, PAGE[1] - 48
        if line:
            if not line.isascii() or stringWidth(line, 'Helvetica', 12) > PAGE[0] - 96:
                raise ValueError('source line cannot be rendered exactly without wrapping')
            pdf.setFont('Helvetica', 12)
            pdf.drawString(48, y, line)
            lines.append((offset, line, page))
        y -= 22
        offset += len(raw)
    pdf.save()
    return stream.getvalue(), lines


def character_box(page, textpage, start, end):
    """Union PDFium glyph boxes, translated to pixels with a top-left origin."""
    boxes = []
    for i in range(start, end):
        ci = pdfium.raw.FPDFText_GetCharIndexFromTextIndex(textpage, i)
        if ci < 0:
            raise ValueError('reference character has no PDFium character index')
        left, bottom, right, top = textpage.get_charbox(ci)
        if right > left and top > bottom:
            boxes.append((left * SCALE, (page.get_height() - top) * SCALE,
                          right * SCALE, (page.get_height() - bottom) * SCALE))
    if not boxes:
        raise ValueError('reference span has no visible character boxes')
    return [math.floor(min(b[0] for b in boxes)), math.floor(min(b[1] for b in boxes)),
            math.ceil(max(b[2] for b in boxes)), math.ceil(max(b[3] for b in boxes))]


def raster(page):
    bitmap = page.render(scale=SCALE)
    try:
        return bitmap.to_pil().convert('RGB').copy()
    finally:
        bitmap.close()


def reference(data, lines, evidence):
    """Resolve a source offset via its exact line, never via the first equal value."""
    locators, boxes = {}, {}
    with pdfium.PdfDocument(data) as doc:
        cursors, mappings = {}, []
        for source_start, line, pno in lines:
            with closing(doc[pno - 1]) as page, closing(page.get_textpage()) as tp:
                text = tp.get_text_range()
                start = text.find(line, cursors.get(pno, 0))
                if start < 0:
                    raise ValueError('PDFium extraction changed a source line')
                cursors[pno] = start + len(line)
                mappings.append((source_start, line, pno, start))
        for key, (span, value) in evidence.items():
            matches = [m for m in mappings if m[0] <= span['start'] < span['end'] <= m[0] + len(m[1])]
            if len(matches) != 1:
                raise ValueError('evidence must be wholly inside one rendered source line')
            source_start, line, pno, line_start = matches[0]
            start, end = (line_start + span[k] - source_start for k in ('start', 'end'))
            with closing(doc[pno - 1]) as page, closing(page.get_textpage()) as tp:
                if tp.get_text_range()[start:end] != value:
                    raise ValueError('PDFium reference slice does not equal the labelled value')
                locators[key] = {'page': pno, 'start': start, 'end': end}
                boxes[key] = character_box(page, tp, start, end)
    return locators, boxes


def transform(image, boxes, scale=1.0, crop=(0, 0, 0, 0)):
    """Downsample and/or crop margins; refuse any crop that loses evidence."""
    width, height = image.size
    size = (round(width * scale), round(height * scale))
    if min(size) <= 0:
        raise ValueError('invalid image scale')
    sx, sy = size[0] / width, size[1] / height
    left, top, right, bottom = crop
    result = image.resize(size, Image.Resampling.LANCZOS)
    result = result.crop((left, top, size[0] - right, size[1] - bottom))
    mapped = {k: [round(b[0] * sx - left, 4), round(b[1] * sy - top, 4),
                  round(b[2] * sx - left, 4), round(b[3] * sy - top, 4)] for k, b in boxes.items()}
    for box in mapped.values():
        if not (0 <= box[0] < box[2] <= result.width and 0 <= box[1] < box[3] <= result.height):
            raise ValueError('crop would lose evidence; refusing to label it as removed')
    return result, mapped


def png(image):
    stream = io.BytesIO()
    image.save(stream, format='PNG', optimize=False, compress_level=9)
    return stream.getvalue()


def store(out, data, fmt):
    digest = hashlib.sha256(data).hexdigest()
    rel = ('texts/' if fmt == 'text' else 'files/') + digest + {'text': '.txt', 'pdf': '.pdf', 'image': '.png'}[fmt]
    path = out / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return {'format': fmt, 'sha256': digest, 'storage_ref': rel}


def visual_side(out, rec, side, text, fmt, degradation=None):
    if fmt == 'text':
        rec[side] = store(out, text.encode('utf-8'), fmt)
        return
    evidence = {f['id']: (f['evidence_' + side], f[side + '_value'])
                for f in rec['findings'] if 'evidence_' + side in f}
    data, lines = make_pdf(text)
    locators, boxes = reference(data, lines, evidence)
    if fmt == 'image':
        with pdfium.PdfDocument(data) as doc:
            if len(doc) != 1:
                raise ValueError('image fixtures require exactly one page')
            with closing(doc[0]) as page:
                image = raster(page)
        if degradation == 'blur':
            image = image.filter(ImageFilter.GaussianBlur(0.65))
        elif degradation == 'low_resolution_jpeg_crop':
            image, boxes = transform(image, boxes, 0.6, (12, 12, 12, 12))
            stream = io.BytesIO()
            image.save(stream, format='JPEG', quality=55, subsampling=0, optimize=False)
            with Image.open(io.BytesIO(stream.getvalue())) as jpeg:
                image = jpeg.convert('RGB')
        elif degradation == 'unreadable':
            if not boxes:
                raise ValueError('unreadable fixture needs evidence')
            target = next(iter(boxes.values()))
            region = [max(0, target[0] - 3), max(0, target[1] - 3),
                      min(image.width, target[2] + 3), min(image.height, target[3] + 3)]
            patch = image.crop(tuple(region)).filter(ImageFilter.GaussianBlur(40))
            image.paste(patch, tuple(region))
            rec['expected_status'] = 'partial'
            rec['unreadable'] = [{'side': side, 'locator': {'box': region}}]
            for f in rec['findings']:
                b = boxes.get(f['id'])
                if b and b[0] < region[2] and b[2] > region[0] and b[1] < region[3] and b[3] > region[1]:
                    f.update(change_type='uncertain', material=True, note='unreadable')
        elif degradation is not None:
            raise ValueError('unknown degradation: ' + degradation)
        data = png(image)
        locators = {k: {'box': b} for k, b in boxes.items()}
    for f in rec['findings']:
        if f['id'] in locators:
            f['evidence_' + side] = locators[f['id']]
    rec[side] = store(out, data, fmt)


def image_tag(image, alt):
    encoded = base64.b64encode(png(image)).decode('ascii')
    return '<img alt="' + html.escape(alt, quote=True) + '" src="data:image/png;base64,' + encoded + '">'


def review(out, records):
    """Self-contained evidence previews, escaped labels and links to both originals."""
    parts = ['<!doctype html><html lang="en"><meta charset="utf-8"><title>ChangeLens visual review</title>',
             '<style>body{font:16px system-ui;max-width:1100px;margin:40px auto;padding:0 24px;color:#172333}',
             'article{border-top:2px solid #ccd5df;margin-top:36px;padding-top:12px}figure{margin:12px 0;padding:12px;background:#f1f5f9}',
             'img{display:block;max-width:100%;height:auto;margin-top:8px}pre{white-space:pre-wrap}code{overflow-wrap:anywhere}',
             '.partial{color:#9b3215}details{margin:12px 0}a{color:#145ca3}</style>',
             '<h1>Visual fixture review</h1><p>13 constructed pairs. Human review is pending for every pair.</p>',
             '<p>Check every evidence crop against its label and both original documents. For partial results,',
             ' confirm the blurred region is unreadable and affected findings are uncertain. Its value is a construction reference,',
             ' not a claim that a reader can recover it. Review complete documents for no-change and omitted-item cases.</p>']
    for rec in records:
        parts.append(f'<article id="{rec["id"]}"><h2>{rec["id"]}</h2><p>{html.escape(", ".join(rec["case_types"]))}</p>')
        parts.append(f'<p class="{rec["expected_status"]}">Expected: <b>{rec["expected_status"]}</b> | '
                     f'{html.escape(", ".join(rec["source"]["operators"]))}</p>')
        for side in ('old', 'new'):
            ver = rec[side]
            path = out / ver['storage_ref']
            parts.append(f'<details><summary>{side}: full {ver["format"]} document</summary>'
                         f'<a href="{ver["storage_ref"]}">Open original</a>')
            if ver['format'] == 'text':
                parts.append('<pre>' + html.escape(path.read_text(encoding='utf-8')) + '</pre>')
            elif ver['format'] == 'image':
                parts.append(f'<img alt="{side} full document" src="{ver["storage_ref"]}">')
            else:
                with pdfium.PdfDocument(path) as doc:
                    for page in doc:
                        with closing(page):
                            parts.append(image_tag(raster(page), side + ' full PDF page'))
            parts.append('</details>')
        if not rec['findings']:
            parts.append('<p>No findings expected. Compare both full documents above.</p>')
        for f in rec['findings']:
            parts.append(f'<h3>{f["id"]}: {f["change_type"]}</h3><p>{html.escape(f.get("note", ""))}</p>')
            for side in ('old', 'new'):
                span = f.get('evidence_' + side)
                if span is None:
                    continue
                value = f[side + '_value']
                parts.append(f'<figure><figcaption>{side}: <code>{html.escape(value)}</code></figcaption>')
                ver = rec[side]
                if ver['format'] == 'image':
                    with Image.open(out / ver['storage_ref']) as im:
                        box = span['box']
                        crop = (math.floor(box[0]), math.floor(box[1]), math.ceil(box[2]), math.ceil(box[3]))
                        parts.append(image_tag(im.crop(crop), side + ' evidence crop'))
                elif ver['format'] == 'pdf':
                    with pdfium.PdfDocument(out / ver['storage_ref']) as doc:
                        with closing(doc[span['page'] - 1]) as page, closing(page.get_textpage()) as tp:
                            im = raster(page)
                            box = character_box(page, tp, span['start'], span['end'])
                            ImageDraw.Draw(im).rectangle(box, outline='#c53030', width=3)
                            parts.append(image_tag(im, side + ' PDF page with evidence highlighted'))
                else:
                    text = (out / ver['storage_ref']).read_text(encoding='utf-8')
                    parts.append('<pre>' + html.escape(text[span['start']:span['end']]) + '</pre>')
                parts.append('</figure>')
        for region in rec.get('unreadable', []):
            with Image.open(out / rec[region['side']]['storage_ref']) as im:
                parts.append('<figure><figcaption>Unreadable region: ' + region['side'] + '</figcaption>')
                parts.append(image_tag(im.crop(tuple(region['locator']['box'])), 'unreadable region'))
                parts.append('</figure>')
        parts.append('</article>')
    parts.append('</html>')
    (out / 'review.html').write_text('\n'.join(parts), encoding='utf-8')


def write(out, seed=7, start=600):
    out = Path(out).resolve()
    if generate.inside_git(out):
        raise SystemExit('refusing to write visual fixtures inside a git working tree: ' + str(out))
    if start < 600:
        raise ValueError('visual record IDs must start at 600 or later')
    out.mkdir(parents=True, exist_ok=True)
    sources = {op: [] for op in OPS}
    for rec, old, new in generate.generate(per_op=6, seed=seed):
        op = rec['source']['operators'][0]
        if op in sources:
            sources[op].append((rec, old, new))
    records = []
    for i in range(13):
        op = OPS[i % 5] if i < 10 else 'value_change'
        source, old, new = sources[op][i % 6]
        rec = copy.deepcopy(source)
        rec['id'], rec['expected_status'] = 'P-%03d' % (start + i), 'complete'
        degradation = None
        if i < 10:
            other = 'text' if i < 5 else 'pdf'
            formats = ('image', other) if i in (1, 6, 9) else (other, 'image')
            rec['case_types'].append('cross_format')
            rec['source']['operators'].append('cross_format')
        else:
            formats = ('image', 'image')
            degradation = ('blur', 'low_resolution_jpeg_crop', 'unreadable')[i - 10]
            rec['case_types'].append('poor_quality')
            rec['source']['operators'].append(degradation)
        for side, text, fmt in zip(('old', 'new'), (old, new), formats):
            visual_side(out, rec, side, text, fmt, degradation if side == 'new' else None)
        records.append(rec)
    (out / 'records.jsonl').write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in records), encoding='utf-8')
    review(out, records)
    return records


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--out', required=True)
    parser.add_argument('--seed', type=int, default=7)
    parser.add_argument('--start', type=int, default=600)
    args = parser.parse_args()
    records = write(args.out, args.seed, args.start)
    print(f'wrote {len(records)} visual pairs and review.html to {args.out}')


if __name__ == '__main__':
    main()
