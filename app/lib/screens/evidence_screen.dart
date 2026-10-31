// Evidence in its document (I-10). PDFs open in pdfrx with the quote highlighted from the
// backend's character offsets, which D-15 showed pdfrx numbers the same way (23/23 on iOS and
// Android). If the text at those offsets is not the quote, the parsed text is shown instead with
// the span marked (03 §9.4, AC-9). Documents stay in memory only (AC-25).
import 'dart:typed_data';

import 'package:flutter/material.dart';
import 'package:pdfrx/pdfrx.dart';

import '../api.dart';
import '../l10n/app_localizations.dart';
import '../services.dart';

class EvidenceScreen extends StatefulWidget {
  const EvidenceScreen({super.key, required this.version, required this.evidence});

  final Version version;
  final Evidence evidence;

  @override
  State<EvidenceScreen> createState() => _EvidenceScreenState();
}

class _EvidenceScreenState extends State<EvidenceScreen> {
  final controller = PdfViewerController();
  Uint8List? pdf;
  List<PdfRect> boxes = const [];
  List<String>? pages; // parsed text fallback
  bool fellBack = false;
  String? error;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (pdf == null && pages == null && error == null) _load();
  }

  Future<void> _load() async {
    final api = ServicesScope.of(context).api;
    final e = widget.evidence;
    try {
      if (widget.version.kind == 'pdf' && e.page != null) {
        final bytes = await api.original(widget.version.id);
        final rects = await _locate(bytes, e);
        if (rects != null) {
          if (mounted) {
            setState(() {
              pdf = bytes;
              boxes = rects;
            });
          }
          return;
        }
        fellBack = true;
      }
      final text = await api.versionText(widget.version.id);
      if (mounted) setState(() => pages = text);
    } on Exception catch (err) {
      if (mounted) setState(() => error = '$err');
    }
  }

  /// The quote's character boxes, or null when pdfrx's text there is not the quote.
  static Future<List<PdfRect>?> _locate(Uint8List bytes, Evidence e) async {
    final doc = await PdfDocument.openData(bytes, sourceName: 'evidence');
    try {
      if (e.page! < 1 || e.page! > doc.pages.length) return null;
      final text = await doc.pages[e.page! - 1].loadText();
      if (text == null || e.charEnd > text.charRects.length) return null;
      if (text.fullText.substring(e.charStart, e.charEnd) != e.quote) return null;
      final rects = [for (final r in text.charRects.sublist(e.charStart, e.charEnd)) if (r.isNotEmpty) r];
      return rects.isEmpty ? null : rects;
    } finally {
      await doc.dispose();
    }
  }

  Future<void> _reveal() async {
    if (boxes.isEmpty) return;
    final area = boxes.reduce((a, b) => a.merge(b));
    final pad = PdfRect(area.left - 24, area.top + 48, area.right + 24, area.bottom - 48);
    await controller.goToRectInsidePage(pageNumber: widget.evidence.page!, rect: pad);
  }

  void _paint(Canvas canvas, Rect pageRect, PdfPage page) {
    if (page.pageNumber != widget.evidence.page) return;
    final fill = Paint()..color = Colors.amber.withValues(alpha: 0.45);
    for (final r in boxes) {
      canvas.drawRect(r.toRectInDocument(page: page, pageRect: pageRect), fill);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final e = widget.evidence;
    Widget body;
    if (pdf != null) {
      body = PdfViewer.data(pdf!, sourceName: widget.version.label, controller: controller,
          params: PdfViewerParams(pagePaintCallbacks: [_paint], onViewerReady: (_, _) => _reveal()));
    } else if (pages != null) {
      body = ParsedTextView(pages: pages!, evidence: e, note: fellBack ? l.highlightFallback : null);
    } else {
      body = Center(child: error == null ? const CircularProgressIndicator() : Text(l.loadFailed(error!)));
    }
    return Scaffold(
      appBar: AppBar(title: Text('${e.earlier ? l.sideEarlier : l.sideNewer}: ${widget.version.label}')),
      body: body,
    );
  }
}

/// The parsed page text with the evidence span marked; the fallback for every kind of version.
class ParsedTextView extends StatelessWidget {
  const ParsedTextView({super.key, required this.pages, required this.evidence, this.note});

  final List<String> pages;
  final Evidence evidence;
  final String? note;

  @override
  Widget build(BuildContext context) {
    final e = evidence;
    final index = (e.page ?? 1) - 1;
    final text = index < pages.length ? pages[index] : '';
    final ok = e.charEnd <= text.length && text.substring(e.charStart, e.charEnd) == e.quote;
    final mark = TextStyle(backgroundColor: Colors.amber.withValues(alpha: 0.6), fontWeight: FontWeight.w600);
    return ListView(padding: const EdgeInsets.all(16), children: [
      if (note != null) Padding(padding: const EdgeInsets.only(bottom: 12), child: Text(note!,
          style: Theme.of(context).textTheme.bodySmall)),
      SelectableText.rich(TextSpan(style: Theme.of(context).textTheme.bodyMedium, children: ok
          ? [
              TextSpan(text: text.substring(0, e.charStart)),
              TextSpan(text: e.quote, style: mark),
              TextSpan(text: text.substring(e.charEnd)),
            ]
          : [TextSpan(text: e.quote, style: mark)])),
    ]);
  }
}
