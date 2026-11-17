"""Hidden-text fixtures: labels, hiding measured by PDFium, determinism and fail-closed validation."""
import base64
import builtins
from contextlib import closing
import copy
import hashlib
import json
from pathlib import Path
import re
import shutil
import tempfile
import unittest
from unittest import mock
import zlib

import pdf_ink
import pypdfium2
import render
import render_hidden
import validate
from test_render import semantic_digest

GOLDEN = '0ea05fd624ea488c836b876bcd3de25a024e5ed7a3f69524406f48fb70680d03'
PDF = re.compile(rb'(?P<head>.*?)/Length \d+(?P<dict>[^>]*>>\s*)stream\r?\n(?P<body>.*?)endstream(?P<tail>.*?)\nxref\n.*', re.S)


def canonical(data: bytes) -> bytes:
    """One fixture PDF with its content stream decoded and its size bookkeeping removed.

    The compressed bytes, their /Length, the xref offsets and the trailer ID depend on the zlib build
    (Python 3.14 on Windows ships a different one), although the page is the same. Everything else,
    and the decoded page content, is compared byte for byte.
    """
    match = PDF.fullmatch(data)
    if not match or data.count(b'endstream') != 1 or not match['head'].rstrip().endswith(b'[ /ASCII85Decode /FlateDecode ]'):
        raise AssertionError('fixture PDF is no longer one ASCII85 and Flate content stream')
    body = match['body'].strip()
    content = zlib.decompress(base64.a85decode(body[:-2] if body.endswith(b'~>') else body))
    return match['head'] + match['dict'] + content + match['tail']


def source_texts():
    return {r['id']: (r, o, n) for r, o, n in render.generate.generate(per_op=6, seed=7)}


class HiddenFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        cls.records = render_hidden.write(cls.root)
        cls.schema = json.loads(Path(validate.SCHEMA).read_text(encoding='utf-8'))

    def hidden_bytes(self, rec):
        entry = rec['hidden'][0]
        return (self.root / rec[entry['side']]['storage_ref']).read_bytes(), entry['locator']

    def test_schema_and_storage(self):
        for rec in self.records:
            self.assertEqual(validate.check(rec, self.schema, self.schema), [])
        self.assertEqual(validate.validate_file(self.root / 'records.jsonl'), (4, []))

    def test_ids_formats_status_and_case_types(self):
        self.assertEqual([r['id'] for r in self.records], ['P-613', 'P-614', 'P-615', 'P-616'])
        for rec in self.records:
            self.assertEqual((rec['old']['format'], rec['new']['format']), ('pdf', 'pdf'))
            self.assertEqual(rec['expected_status'], 'complete')
            self.assertIn('prompt_injection', rec['case_types'])
        self.assertEqual([r['source']['operators'][-1] for r in self.records],
                         ['white_on_white_text', 'tiny_text', 'off_page_text', 'covered_text'])

    def test_three_new_side_and_one_old_side(self):
        sides = [e['side'] for r in self.records for e in r['hidden']]
        self.assertEqual((sides.count('new'), sides.count('old'), len(sides)), (3, 1, 4))

    def test_distinct_unused_text_sources_and_labels_kept(self):
        texts = source_texts()
        derived = [r['source']['derived_from'] for r in self.records]
        self.assertEqual(len(set(derived)), 4)
        self.assertFalse(set(derived) & {s[0]['id'] for s in render.select(7)})
        for rec in self.records:
            source = texts[rec['source']['derived_from']][0]
            self.assertEqual(rec['source']['base_pair'], source['source']['base_pair'])
            self.assertEqual(rec['source']['operators'][:-1], source['source']['operators'])
            self.assertIn(source['source']['operators'][0], ('value_change', 'qualifier_flip'))
            self.assertTrue(any(f['change_type'] == 'changed' and f['material'] and
                                {'evidence_old', 'evidence_new'} <= set(f) for f in rec['findings']))
            for before, after in zip(source['findings'], rec['findings']):
                strip = lambda f: {k: v for k, v in f.items() if not k.startswith('evidence_')}
                self.assertEqual(strip(after), strip(before))
            self.assertEqual(len(rec['findings']), len(source['findings']))

    def test_real_change_spans_slice_to_values(self):
        for rec in self.records:
            for f in rec['findings']:
                for side in ('old', 'new'):
                    span = f['evidence_' + side]
                    with pypdfium2.PdfDocument(self.root / rec[side]['storage_ref']) as doc, \
                            closing(doc[span['page'] - 1]) as page, closing(page.get_textpage()) as tp:
                        self.assertEqual(tp.get_text_range()[span['start']:span['end']], f[side + '_value'])

    def test_hidden_span_is_the_injection_and_really_hidden(self):
        for rec, (technique, side, _, injection) in zip(self.records, render_hidden.PAIRS):
            data, span = self.hidden_bytes(rec)
            self.assertEqual(rec['hidden'][0]['side'], side)
            self.assertEqual(validate.pdf_texts(data)[span['page'] - 1][span['start']:span['end']], injection)
            ink, on_page, glyph = pdf_ink.measure(data, span)
            self.assertIsNone(pdf_ink.visible_reason(data, span), technique)
            self.assertLessEqual(ink, pdf_ink.MAX_INK_ROWS, technique)
            if technique == 'tiny_text':
                self.assertLess(glyph, pdf_ink.MAX_GLYPH_PT / 2)  # 0.5 pt text, well inside the limit
            if technique == 'off_page_text':
                self.assertEqual(on_page, 0)
            else:
                self.assertEqual(on_page, len(injection))
            if technique in ('white_on_white_text', 'covered_text'):
                self.assertEqual(ink, 0, technique)
        self.assertEqual(len({p[3] for p in render_hidden.PAIRS}), 4)

    def test_hidden_text_produces_no_finding(self):
        for rec, pair in zip(self.records, render_hidden.PAIRS):
            entry, injection = rec['hidden'][0], pair[3]
            for f in rec['findings']:
                self.assertFalse(validate.overlaps(f.get('evidence_' + entry['side'], {}), entry['locator']))
                self.assertNotIn(f.get('old_value', ''), ('', injection))
                self.assertNotIn(f.get('new_value', ''), ('', injection))

    def test_deterministic_bytes_and_semantic_golden(self):
        # The records hold only locators, so the golden also covers each extracted hidden text.
        hidden = [validate.pdf_texts(data)[span['page'] - 1][span['start']:span['end']]
                  for data, span in map(self.hidden_bytes, self.records)]
        # The PDF bytes pin how the text is hidden (colour, size, opacity, panel), not just what it says.
        # They are compared in canonical form, so the golden holds on every zlib build.
        pdfs = sorted(hashlib.sha256(canonical((self.root / r[s]['storage_ref']).read_bytes())).hexdigest()
                      for r in self.records for s in ('old', 'new'))
        digest = hashlib.sha256(json.dumps([semantic_digest(self.records), hidden, pdfs]).encode()).hexdigest()
        self.assertEqual(digest, GOLDEN)
        with tempfile.TemporaryDirectory() as tmp:
            other = Path(tmp)
            render_hidden.write(other)
            digest = lambda root: {p.relative_to(root): hashlib.sha256(p.read_bytes()).hexdigest()
                                   for p in root.rglob('*') if p.is_file()}
            self.assertEqual(digest(self.root), digest(other))

    def test_review_sheet_shows_hidden_text_and_evidence(self):
        sheet = (self.root / 'review.html').read_text(encoding='utf-8')
        for rec, pair in zip(self.records, render_hidden.PAIRS):
            self.assertIn('id="' + rec['id'] + '"', sheet)
            self.assertIn(pair[3].replace("'", '&#x27;'), sheet)
        self.assertEqual(sheet.count('PDF page with hidden span outlined'), 4)
        self.assertEqual(sheet.count('<h3>'), sum(len(r['findings']) for r in self.records))
        self.assertIn('PDF page with evidence highlighted', sheet)
        self.assertIn('outside the', sheet)
        self.assertIn('Human review is pending', sheet)

    def test_refuses_id_collisions_reused_sources_and_git(self):
        for start in (600, 610, 560, 503):
            with self.assertRaisesRegex(ValueError, 'collide'):
                render_hidden.write(self.root / 'x', start=start)
        reused = (render_hidden.PAIRS[0][:2] + ('P-500',) + render_hidden.PAIRS[0][3:],) + render_hidden.PAIRS[1:]
        with mock.patch.object(render_hidden, 'PAIRS', reused):
            with self.assertRaisesRegex(ValueError, 'no visual pair uses'):
                render_hidden.write(self.root / 'x')
        out = Path(__file__).parent / 'out'
        with self.assertRaises(SystemExit):
            render_hidden.write(out)
        self.assertFalse(out.exists())
        self.assertFalse((self.root / 'x').exists())

    def changed(self, change, needle, index=0):
        """Copy one record and its files, apply change(rec, side, root), expect an error containing needle."""
        rec = copy.deepcopy(self.records[index])
        side = rec['hidden'][0]['side']
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for s in ('old', 'new'):
                path = root / rec[s]['storage_ref']
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(self.root / rec[s]['storage_ref'], path)
            change(rec, side, root)
            errors = validate.check(rec, self.schema, self.schema) or validate.check_texts(rec, root)
            self.assertTrue(any(needle in e for e in errors), errors)

    def test_visible_hidden_text_rejected(self):
        texts = source_texts()

        def visible(index):
            injection = render_hidden.PAIRS[index][3]

            def change(rec, side, root):
                def draw(pdf):
                    pdf.setFont('Helvetica', 12)
                    pdf.drawString(48, render_hidden.HIDDEN_Y, injection)
                source = texts[rec['source']['derived_from']]
                data, _ = render.make_pdf(source[1 if side == 'old' else 2], draw)
                rec[side] = render.store(root, data, 'pdf')
                start = validate.pdf_texts(data)[0].index(injection)
                rec['hidden'][0]['locator'].update(start=start, end=start + len(injection))
            return change
        for i in range(4):
            self.changed(visible(i), 'span is visible', i)

    def test_barely_hidden_variants_rejected(self):
        # Each variant is readable or larger than tiny text; the validator must call it visible.
        texts = source_texts()
        variants = {
            'light grey #dfdfdf': dict(rgb=(0xdf / 255,) * 3),
            'light grey #f0f0f0': dict(rgb=(0xf0 / 255,) * 3),
            'black at 12% opacity': dict(alpha=0.12),
            '1.25 pt black': dict(size=1.25),
            '1.5 pt black': dict(size=1.5),
            '2 pt black': dict(size=2),
            'under an 88%-opaque panel': dict(panel=(0.88, render_hidden.PANEL)),
            'half under a panel': dict(panel=(1, render_hidden.PANEL[:3] + (render_hidden.HIDDEN_Y + 3,))),
        }

        def variant(size=12, rgb=(0, 0, 0), alpha=1, panel=None):
            def change(rec, side, root):
                injection = render_hidden.PAIRS[0][3]

                def draw(pdf):
                    pdf.saveState()
                    pdf.setFillColorRGB(*rgb)
                    pdf.setFillAlpha(alpha)
                    pdf.setFont('Helvetica', size)
                    pdf.drawString(48, render_hidden.HIDDEN_Y, injection)
                    if panel:
                        opacity, box = panel
                        pdf.setFillAlpha(opacity)
                        pdf.setFillColorRGB(0.85, 0.88, 0.92)
                        pdf.rect(box[0], box[1], box[2] - box[0], box[3] - box[1], stroke=0, fill=1)
                    pdf.restoreState()
                data, _ = render.make_pdf(texts['P-504'][2], draw)
                rec[side] = render.store(root, data, 'pdf')
                start = validate.pdf_texts(data)[0].index(injection)
                rec['hidden'][0]['locator'].update(start=start, end=start + len(injection))
            return change
        for name, kwargs in variants.items():
            with self.subTest(name):
                self.changed(variant(**kwargs), 'span is visible')

    def test_cropped_or_rotated_page_fails_closed(self):
        def reshape(how):
            def change(rec, side, root):
                path = root / rec[side]['storage_ref']
                with pypdfium2.PdfDocument(path) as doc:
                    page = doc[rec['hidden'][0]['locator']['page'] - 1]
                    if how == 'crop':
                        page.set_cropbox(0, 421, 842, 842)
                    else:
                        page.set_rotation(90)
                    page.close()
                    data = tempfile.SpooledTemporaryFile()
                    doc.save(data)
                    data.seek(0)
                    rec[side] = render.store(root, data.read(), 'pdf')
            return change
        for how in ('crop', 'rotate'):
            with self.subTest(how):
                self.changed(reshape(how), 'unrotated page whose CropBox equals')

    def test_invisible_evidence_rejected(self):
        # Evidence for a real change hidden under a panel: the inverse of the hidden check.
        texts = source_texts()

        def cover(rec, side, root):
            f = next(f for f in rec['findings'] if 'evidence_' + side in f)
            span = f['evidence_' + side]
            with pypdfium2.PdfDocument(root / rec[side]['storage_ref']) as doc,                     closing(doc[span['page'] - 1]) as page, closing(page.get_textpage()) as tp:
                boxes = pdf_ink.page_boxes(page, tp, span['start'], span['end'], pypdfium2)
            box = (min(b[0] for b in boxes) - 2, min(b[1] for b in boxes) - 2,
                   max(b[2] for b in boxes) + 2, max(b[3] for b in boxes) + 2)

            def draw(pdf):
                pdf.setFillColorRGB(1, 1, 1)
                pdf.rect(box[0], box[1], box[2] - box[0], box[3] - box[1], stroke=0, fill=1)
            source = texts[rec['source']['derived_from']]
            data, _ = render.make_pdf(source[1 if side == 'old' else 2], draw)
            rec[side] = render.store(root, data, 'pdf')
            del rec['hidden']
        self.changed(cover, 'evidence is not visible', 3)

    def test_hidden_text_over_visible_lines_refused(self):
        y = 533  # a visible line of P-616's new side
        with mock.patch.object(render_hidden, 'HIDDEN_Y', y),                 mock.patch.object(render_hidden, 'PANEL', (36, y - 16, 806, y + 24)):
            with self.assertRaisesRegex(ValueError, 'overlaps visible text'):
                render_hidden.write(self.root / 'y')

    def test_extraction_count_guard(self):
        injection = render_hidden.PAIRS[0][3]
        original = validate.pdf_texts
        twice = lambda data: [t + injection for t in original(data)]
        with mock.patch.object(render_hidden.validate, 'pdf_texts', side_effect=twice):
            with self.assertRaisesRegex(ValueError, 'exactly once'):
                render_hidden.write(self.root / 'z')

    def test_hidden_span_on_text_side_rejected(self):
        def to_text(rec, side, root):
            rec[side] = render.store(root, b'plain text side', 'text')
        self.changed(to_text, 'only allowed on PDF sides')

    def test_finding_overlapping_hidden_text_rejected(self):
        def overlap(rec, side, root):
            f = rec['findings'][0]
            span = dict(rec['hidden'][0]['locator'])
            span['end'] = span['start'] + 4
            f['evidence_' + side] = span
            f[side + '_value'] = render_hidden.PAIRS[int(rec['id'][2:]) - 613][3][:4]
        for i in range(4):
            self.changed(overlap, 'must produce no finding', i)

    def test_empty_hidden_span_rejected(self):
        def empty(rec, side, root):
            loc = rec['hidden'][0]['locator']
            loc['end'] = loc['start']
        self.changed(empty, 'empty or blank')

    def test_hidden_span_outside_page_text_rejected(self):
        self.changed(lambda r, s, p: r['hidden'][0]['locator'].update(end=99999), 'outside the text')
        self.changed(lambda r, s, p: r['hidden'][0]['locator'].update(page=9), 'page outside')

    def test_pdfium_missing_fails_closed(self):
        original = builtins.__import__

        def missing(name, *args, **kwargs):
            if name == 'pypdfium2':
                raise ImportError('simulated missing PDFium')
            return original(name, *args, **kwargs)
        rec = self.records[0]
        side = rec['hidden'][0]['side']
        contents = {s: validate.read_version(rec[s], self.root) for s in ('old', 'new')}
        with mock.patch('builtins.__import__', side_effect=missing):
            self.assertTrue(any('requires pypdfium2' in e for e in validate.check_texts(rec, self.root)))
            errors = validate.hidden_errors(rec, contents, self.root)
            self.assertTrue(any('requires pypdfium2' in e and side in e for e in errors), errors)


if __name__ == '__main__':
    unittest.main()
