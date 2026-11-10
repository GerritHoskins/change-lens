"""Prepare, review and freeze a fresh constructed text/PDF cohort without model calls.

The legacy generator, split and receipt are never changed. Gold labels come from
the established edit operators. Owner review is required before a split exists.
All generated documents, labels and review artifacts must remain outside Git.
See FRESH_COHORT.md for the human review and subsequent paid-evaluation boundary.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from contextlib import closing
import copy
from datetime import datetime, timezone
import hashlib
import html
import json
from pathlib import Path
import random
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import generate
import validate
from fresh_bases import BASES

VERSION = "fresh-text-pdf-v1"
SEED = 20261107
START = 800
OPERATORS = tuple(generate.OPERATORS) + ("partial_update",)
FORMATS = (("text", "text"), ("text", "pdf"), ("pdf", "text"), ("pdf", "pdf"))
ATTESTATION = (
    "I personally reviewed both complete inputs and all construction labels for every pair; "
    "I have not used model predictions to choose or change these labels."
)
STYLE = """body{font:16px/1.5 system-ui;max-width:1150px;margin:32px auto;padding:0 20px;color:#18232c}
a{color:#174e86}h1{line-height:1.2}table{border-collapse:collapse;width:100%;margin:16px 0}
td,th{text-align:left;vertical-align:top;padding:10px;border-bottom:1px solid #c7d1da}
pre{white-space:pre-wrap;overflow-wrap:anywhere;background:#f1f4f7;padding:16px}
img{max-width:100%;height:auto}mark{background:#ffeb9a}code{overflow-wrap:anywhere}
input,select,button{font:inherit;padding:7px;max-width:100%}button{cursor:pointer;margin:6px}
label{display:block;margin:12px 0}details{margin:20px 0}summary{cursor:pointer;font-weight:bold}
.notice{padding:16px;border-left:4px solid #b16a12;background:#fff8e9}
.sides{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:24px}
@media(max-width:750px){.sides{display:block}td,th{padding:6px}table{font-size:14px}}
"""


class CohortError(ValueError):
    pass


def canonical(value):
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":")).encode()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def outside_git(path):
    path = Path(path).resolve()
    if any((parent / ".git").exists() for parent in (path, *path.parents)):
        raise CohortError("generated cohort files must be outside Git, including through links")
    return path


def confined(root, relative):
    path = (root / relative).resolve()
    if not path.is_relative_to(root.resolve()) or Path(relative).is_absolute():
        raise CohortError("a cohort path escapes its directory")
    return path


def tooling_hashes():
    folder = Path(__file__).resolve().parent
    names = ("fresh_cohort.py", "fresh_bases.py", "generate.py", "render.py", "pdf_ink.py", "validate.py")
    result = {name: digest((folder / name).read_bytes()) for name in names}
    result["eval-schema.json"] = digest(Path(validate.SCHEMA).read_bytes())
    return result


def constructed(seed=SEED):
    """Use scripted edits, never model-written labels; keep every base's variants together."""
    if len(BASES) != 10 or len({b["id"] for b in BASES}) != 10:
        raise CohortError("this cohort requires ten distinct fresh base families")
    number = START
    for family_index, base in enumerate(BASES):
        seen = set()
        for op_index, name in enumerate(OPERATORS):
            op = generate.OPERATORS[name]
            operator_base = base
            if name == 'contradiction':
                # Two maxima or prerequisites can both hold. Only explicitly exclusive
                # exact-count requirements may generate a contradiction in this cohort.
                operator_base = copy.deepcopy(base)
                for item in generate.items(operator_base):
                    if not item.get('contradiction_eligible'):
                        item.pop('alts', None)
                if not any(it.get('alts') for it in generate.items(operator_base)):
                    raise CohortError('each base needs an explicitly exclusive contradiction item')
            for attempt in range(100):
                rng = random.Random(f"{seed}:{base['id']}:{op_index}:{attempt}")
                args = (operator_base, rng, family_index) if name == "qualifier_flip" else (operator_base, rng)
                old, new, findings, cases = op(*args)
                # Avoid a duplicate second partial update by construction, never by model score.
                if (old, new) not in seen:
                    break
            else:
                raise CohortError("edit operators could not produce a distinct pair")
            seen.add((old, new))
            for index, finding in enumerate(findings, 1):
                finding["id"] = f"F-{index}"
            record = {
                "id": f"P-{number}", "tier": "constructed", "split": "unsplit",
                "source": {"kind": "generator", "base_pair": base["id"],
                           "operators": [name], "anonymised": True},
                "case_types": cases, "findings": findings, "labelled_by": ["generator"],
                "expected_status": "complete",
            }
            formats = FORMATS[(family_index + op_index) % len(FORMATS)]
            # Existing long injection lines are deliberately kept intact as plain text.
            if name == "injection":
                formats = ("text", "text")
            number += 1
            yield record, old, new, formats


def family_split(records, seed):
    """Equal case profiles make the 4/6 family split jointly stratified by tier/case."""
    families = defaultdict(list)
    ids = set()
    for record in records:
        if record["id"] in ids or record["tier"] != "constructed":
            raise CohortError("duplicate or nonconstructed pair")
        ids.add(record["id"])
        family = record["source"].get("base_pair")
        if not family or record["source"].get("derived_from"):
            raise CohortError("fresh roots require a family and no prior-pair ancestry")
        families[family].append(record)
    profiles = [Counter(tuple(r["case_types"]) for r in group) for group in families.values()]
    if len(families) != 10 or len(ids) != 120 or any(p != profiles[0] for p in profiles):
        raise CohortError("expected ten equal twelve-case family profiles")
    names = sorted(families)
    random.Random(seed).shuffle(names)
    dev_families = set(names[:4])
    dev, held, strata = [], [], defaultdict(lambda: {"pairs": 0, "development": 0, "held_out": 0})
    for family, group in sorted(families.items()):
        which = "development" if family in dev_families else "held_out"
        (dev if which == "development" else held).extend(r["id"] for r in group)
        for record in group:
            key = "constructed/" + "+".join(record["case_types"])
            strata[key]["pairs"] += 1
            strata[key][which] += 1
    return {"seed": seed, "dev_fraction": 0.4,
            "unit": "whole fresh base family, all edits and formats",
            "strata": dict(sorted(strata.items())), "development": sorted(dev), "held_out": sorted(held)}


def write_json(path, value):
    with path.open("x", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(value, ensure_ascii=True, indent=2) + "\n")


def page(title, body, script=""):
    import base64
    def csp_hash(text):
        return "'sha256-" + base64.b64encode(hashlib.sha256(text.encode()).digest()).decode() + "'"
    policy = ("default-src 'none'; img-src 'self' data:; style-src " + csp_hash(STYLE)
              + "; script-src " + (csp_hash(script) if script else "'none'")
              + "; connect-src 'none'; base-uri 'none'; form-action 'none'")
    return ('<!doctype html><html lang="en"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta http-equiv="Content-Security-Policy" content="{html.escape(policy, quote=True)}">'
            f'<title>{html.escape(title)}</title><style>{STYLE}</style><body>{body}'
            + (f'<script>{script}</script>' if script else '') + '</body></html>')


def marked(text, findings, side):
    spans = [f['evidence_' + side] for f in findings if 'evidence_' + side in f]
    bounds = sorted({0, len(text), *(s[k] for s in spans for k in ('start', 'end'))})
    parts = []
    for start, end in zip(bounds, bounds[1:]):
        value = html.escape(text[start:end])
        covered = any(s['start'] <= start and end <= s['end'] for s in spans)
        parts.append('<mark>' + value + '</mark>' if covered else value)
    return ''.join(parts)


def pair_page(root, rec):
    import render
    from PIL import ImageDraw
    body = [f'<a href="../review.html">Back to review checklist</a><h1>{rec["id"]}</h1>',
            '<p>' + html.escape(', '.join(rec['case_types'])) + '</p>',
            '<p>Read both complete inputs, then check each construction label and highlighted span. '
            'Highlighting is a review aid, not a model prediction.</p><div class="sides">']
    for side in ('old', 'new'):
        version = rec[side]
        path = root / version['storage_ref']
        body.append(f'<section><h2>{side.title()} ({version["format"]})</h2>'
                    f'<a href="../{version["storage_ref"]}">Open full original</a>')
        if version['format'] == 'text':
            text = path.read_text(encoding='utf-8')
            body.append('<pre>' + marked(text, rec['findings'], side) + '</pre>')
        else:
            with render.pdfium.PdfDocument(path) as doc:
                for index in range(len(doc)):
                    with closing(doc[index]) as pdf_page, closing(pdf_page.get_textpage()) as tp:
                        preview = render.raster(pdf_page)
                        for finding in rec['findings']:
                            loc = finding.get('evidence_' + side)
                            if loc and loc['page'] == index + 1:
                                box = render.character_box(pdf_page, tp, loc['start'], loc['end'])
                                ImageDraw.Draw(preview).rectangle(box, outline='#b54111', width=3)
                        name = f'{rec["id"]}-{side}-{index + 1}.png'
                        (root / 'review' / name).write_bytes(render.png(preview))
                        body.append(f'<p>Page {index + 1}</p><img src="{name}" alt="{side} page {index + 1} with gold evidence outlined">')
        body.append('</section>')
    body.append('</div><h2>Construction labels</h2>')
    if not rec['findings']:
        body.append('<p>No findings expected. Check the entire documents for any semantic change.</p>')
    else:
        body.append('<table><thead><tr><th>Finding</th><th>Old</th><th>New</th><th>Rule / note</th></tr></thead><tbody>')
        for finding in rec['findings']:
            body.append('<tr><td>' + html.escape(f"{finding['id']} / {finding['category']} / {finding['change_type']}")
                        + f'<br>Material: {finding["material"]}</td>')
            for side in ('old', 'new'):
                body.append('<td>' + html.escape(finding.get(side + '_value', '(no evidence on this side)'))
                            + '<br><code>' + html.escape(json.dumps(finding.get('evidence_' + side))) + '</code></td>')
            body.append('<td>' + html.escape(finding.get('note', 'scripted edit; check the category and meaning')) + '</td></tr>')
        body.append('</tbody></table>')
    (root / 'review' / (rec['id'] + '.html')).write_text(page(rec['id'], ''.join(body)), encoding='utf-8')


def review_index(root, records, manifest):
    entries = {r['id']: {'decision': 'pending', 'note': ''} for r in records}
    template = {'version': VERSION, 'cohort_sha256': manifest['cohort_sha256'],
                'reviewer': '', 'reviewed_at': None, 'attestation': '', 'pairs': entries}
    write_json(root / 'owner-review.template.json', template)
    body = ['<h1>Fresh ChangeLens evaluation: owner review</h1>',
            '<p class="notice">120 pairs from 10 new synthetic brief families. All reviews are pending. '
            'No split is frozen and no model has evaluated this cohort. Review every pair before exporting approval.</p>',
            '<p>The planned family-isolated split is 48 development / 72 held-out. Text and PDF only; '
            'screenshots, hidden-text techniques, German and long-document cost performance are not established by this pack. '
            'After freezing, held-out content must not be used for tuning or debugging.</p>',
            '<p>Each link shows both complete originals, gold evidence and labels. Record any problem as '
            '&ldquo;Changes requested&rdquo;; do not approve a label just because the generator produced it.</p>',
            '<label>Your name or owner identifier <input id="reviewer" autocomplete="off"></label>',
            '<label>Import a saved review <input id="import" type="file" accept=".json"></label>',
            '<p id="status" role="status">0 / 120 approved. Decisions stay in this page until exported.</p>']
    grouped = defaultdict(list)
    for record in records:
        grouped[record['source']['base_pair']].append(record)
    for family, group in sorted(grouped.items()):
        body.append(f'<details><summary>{html.escape(family)} — 12 pairs</summary><table>'
                    '<thead><tr><th>Open and review</th><th>Decision</th><th>Note</th></tr></thead><tbody>')
        for rec in group:
            rid = rec['id']
            body.append(f'<tr><td><a href="review/{rid}.html" target="_blank" rel="noopener">{rid}</a><br>'
                        + html.escape(', '.join(rec['case_types'])) + f'<br>{rec["old"]["format"]} / {rec["new"]["format"]}</td>'
                        f'<td><select aria-label="Decision for {rid}" data-id="{rid}">'
                        '<option value="pending">Pending</option><option value="approved">Approved</option>'
                        '<option value="changes_requested">Changes requested</option></select></td>'
                        f'<td><input aria-label="Note for {rid}" data-note="{rid}"></td></tr>')
        body.append('</tbody></table></details>')
    body.append('<label><input id="attest" type="checkbox"> ' + html.escape(ATTESTATION) + '</label>'
                '<button id="save">Save review progress</button><button id="approve">Export completed owner review</button>'
                '<p>No network requests, credentials or model calls are used. Save the JSON export; refreshing loses unsaved changes.</p>')
    script = 'const review = ' + json.dumps(template).replace('<', '\\u003c') + ';\n'
    script += 'const attestation = ' + json.dumps(ATTESTATION) + ';\n' + r'''
const byId = id => document.getElementById(id);
const collect = () => {
  for (const el of document.querySelectorAll('[data-id]')) review.pairs[el.dataset.id].decision = el.value;
  for (const el of document.querySelectorAll('[data-note]')) review.pairs[el.dataset.note].note = el.value;
  review.reviewer = byId('reviewer').value.trim();
  const approved = Object.values(review.pairs).filter(p => p.decision === 'approved').length;
  byId('status').textContent = `${approved} / ${Object.keys(review.pairs).length} approved. Export to save.`;
  return approved;
};
document.addEventListener('change', collect);
function download(complete) {
  const approved = collect();
  if (complete && (approved !== Object.keys(review.pairs).length || !review.reviewer || !byId('attest').checked)) {
    byId('status').textContent = 'Review and approve every pair, enter your name and confirm the attestation first.';
    return;
  }
  review.reviewed_at = complete ? new Date().toISOString() : null;
  review.attestation = complete ? attestation : '';
  const url = URL.createObjectURL(new Blob([JSON.stringify(review, null, 2) + '\n'], {type:'application/json'}));
  const a = document.createElement('a'); a.href = url;
  a.download = complete ? 'owner-review.json' : 'owner-review-progress.json'; a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
byId('save').addEventListener('click', () => download(false));
byId('approve').addEventListener('click', () => download(true));
byId('import').addEventListener('change', async event => {
  try {
    const incoming = JSON.parse(await event.target.files[0].text());
    if (incoming.cohort_sha256 !== review.cohort_sha256 || incoming.version !== review.version ||
        JSON.stringify(Object.keys(incoming.pairs).sort()) !== JSON.stringify(Object.keys(review.pairs).sort()) ||
        Object.values(incoming.pairs).some(p => !['pending','approved','changes_requested'].includes(p.decision) || typeof p.note !== 'string'))
      throw Error('wrong cohort or invalid decisions');
    for (const el of document.querySelectorAll('[data-id]')) el.value = incoming.pairs[el.dataset.id].decision;
    for (const el of document.querySelectorAll('[data-note]')) el.value = incoming.pairs[el.dataset.note].note;
    byId('reviewer').value = typeof incoming.reviewer === 'string' ? incoming.reviewer : '';
    byId('attest').checked = false; collect();
  } catch { byId('status').textContent = 'Cannot import this review: wrong cohort or invalid JSON.'; }
});
'''
    (root / 'review.html').write_text(page('Fresh ChangeLens owner review', ''.join(body), script), encoding='utf-8')


def prepare(destination, seed=SEED):
    import render
    root = outside_git(destination)
    if not root.name or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-_' for c in root.name):
        raise CohortError("cohort directory name must contain only letters, numbers, hyphens or underscores")
    if root.exists():
        raise CohortError("refusing to overwrite an existing cohort; preserve its review history")
    # Validate construction before writing. No pipeline/model is imported or invoked.
    draft = list(constructed(seed))
    family_split([r for r, *_ in draft], seed)
    root.mkdir(parents=True)
    (root / 'review').mkdir()
    records = []
    for rec, old, new, formats in draft:
        for side, text, fmt in zip(('old', 'new'), (old, new), formats):
            render.visual_side(root, rec, side, text, fmt)
        records.append(rec)
    with (root / 'records.jsonl').open('x', encoding='utf-8', newline='\n') as fh:
        for record in records:
            fh.write(json.dumps(record, ensure_ascii=True) + '\n')
    count, errors = validate.validate_file(root / 'records.jsonl')
    if errors:
        raise CohortError('generated records failed validation: ' + '; '.join(errors[:5]))
    for record in records:
        pair_page(root, record)
    source_files = sorted({r[side]['storage_ref'] for r in records for side in ('old', 'new')})
    identity = {'version': VERSION, 'seed': seed, 'set': root.name,
                'records_sha256': digest((root / 'records.jsonl').read_bytes()),
                'files': {name: digest((root / name).read_bytes()) for name in source_files},
                'review_assets': {p.relative_to(root).as_posix(): digest(p.read_bytes())
                                  for p in sorted((root / 'review').iterdir())},
                'tooling_sha256': tooling_hashes()}
    manifest = {**identity, 'cohort_sha256': digest(canonical(identity)), 'created_at': utc_now(),
                'state': 'owner_review_pending', 'pairs': count, 'families': 10,
                'case_counts': dict(sorted(Counter(c for r in records for c in r['case_types']).items())),
                'format_counts': dict(sorted(Counter(r['old']['format'] + '/' + r['new']['format'] for r in records).items())),
                'coverage': 'English constructed short text/PDF only; no real, image, hidden-text or heavy-document claim'}
    review_index(root, records, manifest)
    # The checklist embeds cohort_sha256, so its own hash cannot be in that identity.
    # All documents, pair pages and previews being approved are already bound above.
    manifest['checklist_sha256'] = digest((root / 'review.html').read_bytes())
    write_json(root / 'manifest.json', manifest)
    return manifest


def verify(destination):
    root = outside_git(destination)
    manifest = json.loads((root / 'manifest.json').read_text(encoding='utf-8'))
    keys = ('version', 'seed', 'set', 'records_sha256', 'files', 'review_assets', 'tooling_sha256')
    identity = {key: manifest[key] for key in keys}
    if manifest['version'] != VERSION or manifest['set'] != root.name or digest(canonical(identity)) != manifest['cohort_sha256']:
        raise CohortError('cohort identity changed')
    if digest((root / 'records.jsonl').read_bytes()) != manifest['records_sha256']:
        raise CohortError('records changed since preparation')
    for relative, expected in {**manifest['files'], **manifest['review_assets'],
                               'review.html': manifest['checklist_sha256']}.items():
        if digest(confined(root, relative).read_bytes()) != expected:
            raise CohortError('source or review file changed since preparation: ' + relative)
    records = [json.loads(line) for line in (root / 'records.jsonl').read_text(encoding='utf-8').splitlines()]
    expected_files = {r[side]['storage_ref'] for r in records for side in ('old', 'new')}
    if expected_files != set(manifest['files']):
        raise CohortError('source inventory differs from records')
    expected_assets = {f'review/{r["id"]}.html' for r in records}
    for rec in records:
        for side in ('old', 'new'):
            source = confined(root, rec[side]['storage_ref'])
            if rec[side]['format'] == 'pdf':
                expected_assets.update(f'review/{rec["id"]}-{side}-{page + 1}.png'
                                       for page in range(len(validate.pdf_texts(source.read_bytes()))))
    if expected_assets != set(manifest['review_assets']):
        raise CohortError('review asset inventory differs from records')
    family_split(records, manifest['seed'])
    count, errors = validate.validate_file(root / 'records.jsonl')
    if errors or count != 120 or manifest['pairs'] != count:
        raise CohortError('cohort validation failed: ' + '; '.join(errors[:5]))
    if (root / 'frozen').exists():
        verify_frozen(root, manifest, records)
    return manifest, records


def validate_review(review, manifest, records):
    expected = {r['id'] for r in records}
    if review.get('version') != VERSION or review.get('cohort_sha256') != manifest['cohort_sha256']:
        raise CohortError('owner review belongs to a different cohort')
    if (not isinstance(review.get('reviewer'), str) or not review['reviewer'].strip()
            or review['reviewer'].strip().lower() in {'ai', 'agent', 'generator', 'codex', 'assistant'}
            or review.get('attestation') != ATTESTATION):
        raise CohortError('actual owner review and explicit attestation required')
    pairs = review.get('pairs')
    if not isinstance(pairs, dict) or set(pairs) != expected or any(
            not isinstance(v, dict) or v.get('decision') != 'approved' or not isinstance(v.get('note'), str)
            for v in pairs.values()):
        raise CohortError('every pair must be explicitly approved by the owner')
    try:
        reviewed = datetime.fromisoformat(review['reviewed_at'].replace('Z', '+00:00'))
        created = datetime.fromisoformat(manifest['created_at'])
        if reviewed.tzinfo is None or not created <= reviewed <= datetime.now(timezone.utc):
            raise ValueError()
    except (KeyError, TypeError, AttributeError, ValueError):
        raise CohortError('owner review timestamp must be after preparation and not in the future') from None


def freeze(destination, review_file):
    root = outside_git(destination)
    if (root / 'frozen').exists():
        raise CohortError('cohort already frozen; never overwrite or reroll it')
    manifest, records = verify(root)
    review = json.loads(Path(review_file).read_text(encoding='utf-8'))
    validate_review(review, manifest, records)
    split = family_split(records, manifest['seed'])
    split.update(sets=[root.name], cohort_sha256=manifest['cohort_sha256'],
                 records_sha256=manifest['records_sha256'], owner_review_sha256=digest(canonical(review)))
    receipt = {'version': VERSION, 'state': 'frozen_for_evaluation', 'frozen_at': utc_now(),
               'cohort_sha256': manifest['cohort_sha256'], 'manifest_sha256': digest((root / 'manifest.json').read_bytes()),
               'owner_review_sha256': digest(canonical(review)), 'split_sha256': digest(canonical(split)),
               'model_calls': 0, 'paid_evaluation_authorized': False}
    frozen = root / 'frozen'
    frozen.mkdir()
    write_json(frozen / 'split.json', split)
    write_json(frozen / 'owner-review.json', review)
    write_json(frozen / 'freeze.json', receipt)  # Completion marker; never a model-quality receipt.
    return split


def verify_frozen(root, manifest, records):
    """A partial or tampered freeze is never mistaken for a verified draft."""
    frozen = root / 'frozen'
    if {p.name for p in frozen.iterdir()} != {'split.json', 'owner-review.json', 'freeze.json'}:
        raise CohortError('frozen cohort is incomplete or has unexpected files')
    review = json.loads(confined(root, 'frozen/owner-review.json').read_text(encoding='utf-8'))
    validate_review(review, manifest, records)
    split = json.loads(confined(root, 'frozen/split.json').read_text(encoding='utf-8'))
    expected = family_split(records, manifest['seed'])
    expected.update(sets=[root.name], cohort_sha256=manifest['cohort_sha256'],
                    records_sha256=manifest['records_sha256'], owner_review_sha256=digest(canonical(review)))
    if split != expected:
        raise CohortError('frozen split differs from the reviewed family-isolated assignment')
    receipt = json.loads(confined(root, 'frozen/freeze.json').read_text(encoding='utf-8'))
    checks = {'version': VERSION, 'state': 'frozen_for_evaluation',
              'cohort_sha256': manifest['cohort_sha256'],
              'manifest_sha256': digest((root / 'manifest.json').read_bytes()),
              'owner_review_sha256': digest(canonical(review)), 'split_sha256': digest(canonical(split)),
              'model_calls': 0, 'paid_evaluation_authorized': False}
    if any(receipt.get(key) != value for key, value in checks.items()):
        raise CohortError('frozen receipt does not match its manifest, review and split')
    try:
        frozen_at = datetime.fromisoformat(receipt['frozen_at'])
        reviewed_at = datetime.fromisoformat(review['reviewed_at'].replace('Z', '+00:00'))
        if frozen_at.tzinfo is None or not reviewed_at <= frozen_at <= datetime.now(timezone.utc):
            raise ValueError()
    except (KeyError, TypeError, ValueError):
        raise CohortError('invalid freeze timestamp') from None


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest='command', required=True)
    prep = commands.add_parser('prepare')
    prep.add_argument('--out', type=Path, required=True)
    prep.add_argument('--seed', type=int, default=SEED)
    check = commands.add_parser('verify')
    check.add_argument('--cohort', type=Path, required=True)
    lock = commands.add_parser('freeze')
    lock.add_argument('--cohort', type=Path, required=True)
    lock.add_argument('--owner-review', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == 'prepare':
            manifest = prepare(args.out, args.seed)
            print(f"Prepared {manifest['pairs']} pairs; owner review pending; no split frozen; no model calls.")
            print(args.out.resolve() / 'review.html')
        elif args.command == 'verify':
            manifest, _ = verify(args.cohort)
            print(f"PASS: {manifest['pairs']} records, source hashes, evidence and review assets; no model calls.")
        else:
            split = freeze(args.cohort, args.owner_review)
            print(f"Frozen {len(split['development'])} development / {len(split['held_out'])} held-out pairs.")
            print('Paid evaluation still requires separate owner approval and a clean evaluated code commit.')
    except (CohortError, OSError, ValueError, KeyError, TypeError) as error:
        print('BLOCK: ' + str(error), file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
