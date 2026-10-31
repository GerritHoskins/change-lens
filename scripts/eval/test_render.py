"""Visual fixture coverage, geometry, determinism and fail-closed validation."""
import builtins
from collections import Counter
from contextlib import closing
import copy
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest import mock

import pypdfium2
from PIL import Image
import render
import validate

GOLDEN = '1346c8d4583d4cbd2a2f58e020c83b2726f1855d1ed600699275ef09973d3099'


def semantic_digest(records):
    stripped = copy.deepcopy(records)
    for rec in stripped:
        for side in ('old', 'new'):
            rec[side].pop('sha256')
            rec[side].pop('storage_ref')
    return hashlib.sha256(json.dumps(stripped, sort_keys=True).encode()).hexdigest()


class VisualFixtures(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.addClassCleanup(cls.temp.cleanup)
        cls.root = Path(cls.temp.name)
        cls.records = render.write(cls.root)
        cls.schema = json.loads(Path(validate.SCHEMA).read_text(encoding='utf-8'))

    def test_schema_and_storage(self):
        for rec in self.records:
            self.assertEqual(validate.check(rec, self.schema, self.schema), [])
        self.assertEqual(validate.validate_file(self.root / 'records.jsonl'), (13, []))

    def test_case_and_direction_mix(self):
        cross = [r for r in self.records if 'cross_format' in r['case_types']]
        poor = [r for r in self.records if 'poor_quality' in r['case_types']]
        self.assertEqual((len(cross), len(poor)), (10, 3))
        mix = Counter(tuple(sorted((r['old']['format'], r['new']['format']))) for r in cross)
        self.assertEqual(mix, {('image', 'text'): 5, ('image', 'pdf'): 5})
        self.assertEqual(sum(r['new']['format'] == 'image' for r in cross), 7)
        for group in (cross[:5], cross[5:]):
            self.assertEqual({r['source']['operators'][0] for r in group}, set(render.OPS))
        self.assertEqual([r['id'] for r in self.records], ['P-%d' % n for n in range(600, 613)])

    def test_pdf_spans_and_image_bounds(self):
        for rec in self.records:
            for side in ('old', 'new'):
                ver = rec[side]
                path = self.root / ver['storage_ref']
                spans = [(f['evidence_' + side], f[side + '_value']) for f in rec['findings'] if 'evidence_' + side in f]
                if ver['format'] == 'pdf':
                    with pypdfium2.PdfDocument(path) as doc:
                        for span, value in spans:
                            with closing(doc[span['page'] - 1]) as page, closing(page.get_textpage()) as tp:
                                self.assertEqual(tp.get_text_range()[span['start']:span['end']], value)
                elif ver['format'] == 'image':
                    with Image.open(path) as im:
                        self.assertEqual(validate.png_size(path.read_bytes()), im.size)
                        for span, _ in spans:
                            x0, y0, x1, y1 = span['box']
                            self.assertTrue(0 <= x0 < x1 <= im.width and 0 <= y0 < y1 <= im.height)

    def test_downsample_and_crop_transform_pdfium_boxes(self):
        data, lines = render.make_pdf('Hello 123 world.\n')
        _, boxes = render.reference(data, lines, {'F-1': ({'start': 6, 'end': 9}, '123')})
        with pypdfium2.PdfDocument(data) as doc, closing(doc[0]) as page:
            im = render.raster(page)
        reduced, mapped = render.transform(im, boxes, 0.5)
        self.assertEqual(reduced.size, (im.width // 2, im.height // 2))
        for original, scaled in zip(boxes['F-1'], mapped['F-1']):
            self.assertAlmostEqual(scaled, original * 0.5, delta=1)
        _, shifted = render.transform(im, boxes, 0.5, (10, 11, 0, 0))
        for i, (a, b) in enumerate(zip(mapped['F-1'], shifted['F-1'])):
            self.assertEqual(b, a - (10 if i % 2 == 0 else 11))
        with self.assertRaisesRegex(ValueError, 'crop would lose evidence'):
            render.transform(im, boxes, crop=(200, 0, 0, 0))

    def test_exact_source_occurrence_and_extraction_failure(self):
        text = 'Same 123 first.\nSame 123 second.\n'
        start = text.rindex('123')
        evidence = {'F-1': ({'start': start, 'end': start + 3}, '123')}
        data, lines = render.make_pdf(text)
        locs, _ = render.reference(data, lines, evidence)
        page = validate.pdf_texts(data)[0]
        self.assertEqual(locs['F-1']['start'], page.rindex('123'))
        with self.assertRaisesRegex(ValueError, 'does not equal'):
            render.reference(data, lines, {'F-1': ({'start': start, 'end': start + 3}, '999')})
        with mock.patch.object(pypdfium2.PdfTextPage, 'get_text_range', return_value='different text'):
            with self.assertRaisesRegex(ValueError, 'changed a source line'):
                render.reference(data, lines, evidence)
        with self.assertRaisesRegex(ValueError, 'without wrapping'):
            render.make_pdf('a' * 1000)

    def test_page_numbers_are_one_based(self):
        text = ''.join('Line %02d unique.\n' % n for n in range(50))
        value = 'Line 49 unique.'
        start = text.index(value)
        data, lines = render.make_pdf(text)
        locs, _ = render.reference(data, lines, {'F-1': ({'start': start, 'end': start + len(value)}, value)})
        self.assertEqual(locs['F-1']['page'], 2)
        self.assertEqual(validate.pdf_texts(data)[1][locs['F-1']['start']:locs['F-1']['end']], value)

    def test_degradation_preserves_labels_except_unreadable_region(self):
        sources = [t for t in render.generate.generate(per_op=6, seed=7) if t[0]['source']['operators'] == ['value_change']]
        for i, rec in enumerate(self.records[10:], 10):
            original = sources[i % 6][0]
            self.assertEqual(rec['expected_status'], 'partial' if i == 12 else 'complete')
            for before, after in zip(original['findings'], rec['findings']):
                expected = {k: v for k, v in before.items() if not k.startswith('evidence_')}
                actual = {k: v for k, v in after.items() if not k.startswith('evidence_')}
                if after.get('note') == 'unreadable':
                    expected.update(change_type='uncertain', material=True, note='unreadable')
                self.assertEqual(actual, expected)
        partial = self.records[12]
        self.assertTrue(partial['unreadable'])
        self.assertTrue(any(f.get('note') == 'unreadable' for f in partial['findings']))
        self.assertNotIn('removed', [f['change_type'] for f in partial['findings']])

    def test_deterministic_bytes_and_semantic_golden(self):
        self.assertEqual(semantic_digest(self.records), GOLDEN)
        with tempfile.TemporaryDirectory() as tmp:
            other = Path(tmp)
            render.write(other)
            first = {p.relative_to(self.root): hashlib.sha256(p.read_bytes()).hexdigest() for p in self.root.rglob('*') if p.is_file()}
            second = {p.relative_to(other): hashlib.sha256(p.read_bytes()).hexdigest() for p in other.rglob('*') if p.is_file()}
            self.assertEqual(first, second)

    def test_review_sheet_covers_findings_and_partial_regions(self):
        sheet = (self.root / 'review.html').read_text(encoding='utf-8')
        for rec in self.records:
            self.assertIn('id="' + rec['id'] + '"', sheet)
        self.assertEqual(sheet.count('<h3>'), sum(len(r['findings']) for r in self.records))
        self.assertIn('PDF page with evidence highlighted', sheet)
        self.assertIn('evidence crop', sheet)
        self.assertIn('Unreadable region: new', sheet)
        self.assertIn('No findings expected', sheet)
        self.assertIn('Human review is pending', sheet)

    def changed(self, fmt, change, needle, partial=False):
        rec = copy.deepcopy(self.records[12] if partial else next(r for r in self.records
                            if any(r[s]['format'] == fmt and any('evidence_' + s in f for f in r['findings']) for s in ('old', 'new'))))
        side = next(s for s in ('new', 'old') if rec[s]['format'] == fmt and any('evidence_' + s in f for f in rec['findings']))
        f = next(f for f in rec['findings'] if 'evidence_' + side in f)
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for s in ('old', 'new'):
                path = root / rec[s]['storage_ref']
                path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(self.root / rec[s]['storage_ref'], path)
            change(rec, side, f, root)
            errors = validate.check(rec, self.schema, self.schema)
            if not errors:
                errors = validate.check_texts(rec, root)
            self.assertTrue(any(needle in e for e in errors), errors)

    def test_shifted_pdf_span_rejected(self):
        self.changed('pdf', lambda r, s, f, p: f['evidence_' + s].update(start=f['evidence_' + s]['start'] + 1), 'slices to')

    def test_pdf_page_out_of_range_rejected(self):
        self.changed('pdf', lambda r, s, f, p: f['evidence_' + s].update(page=999), 'page outside')

    def test_pdf_missing_offsets_rejected(self):
        self.changed('pdf', lambda r, s, f, p: f['evidence_' + s].pop('start'), 'needs page')

    def test_image_boxes_rejected(self):
        for box in ([-1, 0, 20, 20], [0, 0, 99999, 20], [2, 2, 1, 4], [1, 1, 2, 1], [0, 0, float('nan'), 2]):
            self.changed('image', lambda r, s, f, p: f['evidence_' + s].update(box=box), 'box outside')

    def test_tampered_files_rejected(self):
        for fmt in ('pdf', 'image', 'text'):
            self.changed(fmt, lambda r, s, f, p: (p / r[s]['storage_ref']).write_bytes(b'tampered'), 'sha256 mismatch')

    def test_wrong_magic_rejected_even_with_updated_hash(self):
        def wrong(rec, side, finding, root):
            data = b'wrong magic bytes' + b'\x00' * 100
            (root / rec[side]['storage_ref']).write_bytes(data)
            rec[side]['sha256'] = hashlib.sha256(data).hexdigest()
        for fmt in ('pdf', 'image'):
            self.changed(fmt, wrong, 'magic')

    def test_missing_files_and_storage_refs_rejected(self):
        for fmt in ('pdf', 'image', 'text'):
            self.changed(fmt, lambda r, s, f, p: (p / r[s]['storage_ref']).unlink(), 'missing')
            self.changed(fmt, lambda r, s, f, p: r[s].pop('storage_ref'), 'missing storage_ref')

    def test_pdfium_missing_fails_closed(self):
        original = builtins.__import__
        def missing(name, *args, **kwargs):
            if name == 'pypdfium2':
                raise ImportError('simulated missing PDFium')
            return original(name, *args, **kwargs)
        rec = next(r for r in self.records if 'pdf' in (r['old']['format'], r['new']['format']))
        with mock.patch('builtins.__import__', side_effect=missing):
            errors = validate.check_texts(rec, self.root)
        self.assertTrue(any('requires pypdfium2' in e for e in errors), errors)

    def test_unreadable_status_regions_and_labels_are_enforced(self):
        self.changed('image', lambda r, s, f, p: r.update(expected_status='complete'), 'require expected_status partial', True)
        self.changed('image', lambda r, s, f, p: r.pop('unreadable'), 'partial requires', True)
        self.changed('image', lambda r, s, f, p: r['unreadable'][0]['locator'].update(box=[0, 0, 99999, 20]), 'box outside', True)
        def removed(r, s, f, p):
            next(f for f in r['findings'] if f.get('note') == 'unreadable')['change_type'] = 'removed'
        self.changed('image', removed, 'must be uncertain', True)

    def test_storage_escape_and_corrupt_png_header_rejected(self):
        self.changed('image', lambda r, s, f, p: r[s].update(storage_ref='../outside.png'), 'escapes')
        with self.assertRaisesRegex(ValueError, 'IHDR'):
            validate.png_size(b'\x89PNG\r\n\x1a\n')

    def test_refuses_output_inside_git_and_text_id_range(self):
        for out in (Path(__file__).parent / 'out', Path(__file__).parent / 'sub' / '..' / 'out'):
            with self.assertRaises(SystemExit):
                render.write(out)
            self.assertFalse(out.exists())
        with self.assertRaises(ValueError):
            render.write(self.root, start=500)


if __name__ == '__main__':
    unittest.main()
