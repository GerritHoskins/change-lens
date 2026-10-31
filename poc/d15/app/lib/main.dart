// D-15 mobile proof of concept (docs/05-backlog.md): pick two PDF versions, get passages and
// locators from the mock API (poc/d15/mock_api.py), open the right page and highlight the
// passage with pdfrx, zoom, scroll and switch versions. Each passage is scored by comparing
// the backend's PDFium boxes with the boxes pdfrx's own PDFium build reports for the same
// characters. Documents stay in memory only; nothing is written to the device.
import 'dart:convert';
import 'dart:math' as math;
import 'dart:typed_data';

import 'package:file_picker/file_picker.dart';
import 'package:flutter/material.dart';
import 'package:http/http.dart' as http;
import 'package:pdfrx/pdfrx.dart';

const apiBase = String.fromEnvironment('API', defaultValue: 'http://127.0.0.1:8765');
const matchIoU = 0.9; // a highlight matches when the two boxes overlap this much

Future<void> main() async {
  await pdfrxFlutterInitialize();
  runApp(const PocApp());
}

class PocApp extends StatelessWidget {
  const PocApp({super.key});

  @override
  Widget build(BuildContext context) => MaterialApp(
        title: 'ChangeLens D-15',
        theme: ThemeData(colorSchemeSeed: Colors.indigo, useMaterial3: true),
        home: const HighlightPage(),
      );
}

class Passage {
  Passage(Map<String, dynamic> j)
      : id = j['id'] as int,
        page = j['page'] as int,
        text = j['text'] as String,
        charStart = j['char_start'] as int,
        charEnd = j['char_end'] as int,
        boxes = [
          for (final b in j['boxes'] as List)
            PdfRect((b[0] as num).toDouble(), (b[3] as num).toDouble(), (b[2] as num).toDouble(),
                (b[1] as num).toDouble())
        ];

  final int id, page, charStart, charEnd;
  final String text;
  final List<PdfRect> boxes;
  List<PdfRect> local = const []; // boxes pdfrx reports for the same characters
  double iou = 0;
  bool textMatches = false;

  bool get matches => textMatches && iou >= matchIoU;
}

class Version {
  Version(this.name, this.bytes, this.passages);

  final String name;
  final Uint8List bytes;
  final List<Passage> passages;
}

PdfRect? union(Iterable<PdfRect> rects) => rects.isEmpty ? null : rects.reduce((a, b) => a.merge(b));

double iouOf(PdfRect? a, PdfRect? b) {
  if (a == null || b == null) return 0;
  final w = math.min(a.right, b.right) - math.max(a.left, b.left);
  final h = math.min(a.top, b.top) - math.max(a.bottom, b.bottom);
  if (w <= 0 || h <= 0) return 0;
  final inter = w * h;
  return inter / (a.width * a.height + b.width * b.height - inter);
}

/// Score every passage against pdfrx: same text at the same character indices, same boxes.
Future<void> score(Uint8List bytes, List<Passage> passages) async {
  final doc = await PdfDocument.openData(bytes, sourceName: 'score');
  try {
    for (final p in passages) {
      final text = await doc.pages[p.page - 1].loadText();
      if (text == null || p.charEnd > text.charRects.length) continue;
      p.textMatches = text.fullText.substring(p.charStart, p.charEnd) == p.text;
      p.local = [
        for (final r in text.charRects.sublist(p.charStart, p.charEnd))
          if (r.isNotEmpty) r
      ];
      p.iou = iouOf(union(p.boxes), union(p.local));
    }
  } finally {
    await doc.dispose();
  }
}

class HighlightPage extends StatefulWidget {
  const HighlightPage({super.key});

  @override
  State<HighlightPage> createState() => _HighlightPageState();
}

class _HighlightPageState extends State<HighlightPage> {
  final controller = PdfViewerController();
  final versions = <Version?>[null, null]; // older, newer
  int current = 0;
  Passage? selected;
  String? status;

  Version? get version => versions[current];

  Future<void> pick(int slot) async {
    final file = await FilePicker.pickFile(type: FileType.custom, allowedExtensions: ['pdf']);
    if (file == null) return;
    setState(() => status = 'Locating passages…');
    try {
      final bytes = await file.xFile.readAsBytes();
      final res = await http.post(Uri.parse('$apiBase/locate'),
          headers: {'Content-Type': 'application/pdf'}, body: bytes);
      if (res.statusCode != 200) throw Exception('API ${res.statusCode}: ${res.body}');
      final body = jsonDecode(res.body) as Map<String, dynamic>;
      final passages = [for (final j in body['passages'] as List) Passage(j as Map<String, dynamic>)];
      await score(bytes, passages);
      setState(() {
        versions[slot] = Version(file.name, bytes, passages);
        current = slot;
        selected = null;
        status = null;
      });
    } catch (e) {
      setState(() => status = 'Failed: $e');
    }
  }

  Future<void> show(Passage p) async {
    setState(() => selected = p);
    final area = union(p.boxes);
    if (area == null) return;
    final pad = PdfRect(area.left - 24, area.top + 48, area.right + 24, area.bottom - 48);
    await controller.goToRectInsidePage(pageNumber: p.page, rect: pad);
  }

  void paint(Canvas canvas, Rect pageRect, PdfPage page) {
    final p = selected;
    if (p == null || p.page != page.pageNumber) return;
    final fill = Paint()..color = Colors.amber.withValues(alpha: 0.45);
    final outline = Paint()
      ..color = p.matches ? Colors.green : Colors.red
      ..style = PaintingStyle.stroke
      ..strokeWidth = 1;
    for (final r in p.boxes) {
      canvas.drawRect(r.toRectInDocument(page: page, pageRect: pageRect), fill);
    }
    for (final r in p.local) {
      canvas.drawRect(r.toRectInDocument(page: page, pageRect: pageRect), outline);
    }
  }

  @override
  Widget build(BuildContext context) {
    final v = version;
    final all = [for (final v in versions) ...?v?.passages];
    final ok = all.where((p) => p.matches).length;
    return Scaffold(
      appBar: AppBar(
        title: Text(all.isEmpty ? 'D-15 highlight test' : 'Match $ok/${all.length} '
            '(${(100 * ok / all.length).toStringAsFixed(0)}%, target ≥ 95%)'),
        actions: [
          IconButton(tooltip: 'Pick older PDF', onPressed: () => pick(0), icon: const Icon(Icons.history)),
          IconButton(tooltip: 'Pick newer PDF', onPressed: () => pick(1), icon: const Icon(Icons.upload_file)),
        ],
        bottom: PreferredSize(
          preferredSize: const Size.fromHeight(48),
          child: SegmentedButton<int>(
            segments: [
              ButtonSegment(value: 0, label: Text(versions[0]?.name ?? 'Older')),
              ButtonSegment(value: 1, label: Text(versions[1]?.name ?? 'Newer')),
            ],
            selected: {current},
            onSelectionChanged: (s) => setState(() {
              current = s.first;
              selected = null;
            }),
          ),
        ),
      ),
      body: Column(children: [
        if (status != null) Padding(padding: const EdgeInsets.all(8), child: Text(status!)),
        Expanded(
          flex: 3,
          child: v == null
              ? const Center(child: Text('Pick an older and a newer PDF.'))
              : PdfViewer.data(v.bytes,
                  key: ValueKey(v),
                  sourceName: v.name,
                  controller: controller,
                  params: PdfViewerParams(pagePaintCallbacks: [paint])),
        ),
        if (v != null)
          Expanded(
            flex: 2,
            child: ListView(children: [
              for (final p in v.passages)
                ListTile(
                  dense: true,
                  selected: identical(p, selected),
                  leading: Icon(p.matches ? Icons.check_circle : Icons.error,
                      color: p.matches ? Colors.green : Colors.red),
                  title: Text(p.text.replaceAll('\r\n', ' ⏎ '), maxLines: 1, overflow: TextOverflow.ellipsis),
                  subtitle: Text('p${p.page} · chars ${p.charStart}–${p.charEnd} · IoU ${p.iou.toStringAsFixed(3)}'
                      '${p.textMatches ? '' : ' · text differs'}'),
                  onTap: () => show(p),
                ),
            ]),
          ),
      ]),
    );
  }
}
