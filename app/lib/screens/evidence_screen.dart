// Evidence in its document (I-10). PDFs open in pdfrx with the quote highlighted from the
// backend's character offsets, which D-15 showed pdfrx numbers the same way (23/23 on iOS and
// Android). If the text at those offsets is not the quote, the parsed text is shown instead with
// the span marked (03 §9.4, AC-9). Documents stay in memory only (AC-25).
import 'package:flutter/material.dart';
import 'package:pdfrx/pdfrx.dart';

import '../api.dart';
import '../design/calm_theme.dart';
import '../design/calm_widgets.dart';
import '../l10n/app_localizations.dart';
import '../services.dart';
import 'evidence_resolution.dart';

class EvidenceScreen extends StatefulWidget {
  const EvidenceScreen({super.key, required this.version, required this.evidence,
    this.presentation, this.onPageOpened});

  final Version version;
  final Evidence evidence;
  final EvidencePresentation? presentation;
  final VoidCallback? onPageOpened;

  @override
  State<EvidenceScreen> createState() => _EvidenceScreenState();
}

class _EvidenceScreenState extends State<EvidenceScreen> {
  final controller = PdfViewerController();
  EvidencePresentation? presentation;
  List<String>? pages;
  bool loading = false, opened = false, sourceOpened = false, textView = false;
  String? error;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!loading && presentation == null && error == null) _load();
  }

  Future<void> _load() async {
    if (loading) return;
    final api = ServicesScope.of(context).api;
    setState(() { loading = true; error = null; });
    try {
      // Counts an explicit source view even when its presentation was prefetched in memory.
      // Separate from pageOpened, which deliberately excludes parsed-text fallback.
      if (!sourceOpened) {
        await api.versionOpened(widget.version.id);
        sourceOpened = true;
      }
      if (!mounted) return;
      final resolved = widget.presentation ?? await resolveEvidence(api, widget.version, widget.evidence);
      final text = resolved.pdf == null ? resolved.pages ?? await api.versionText(widget.version.id) : null;
      if (!mounted) return;
      setState(() { presentation = resolved; pages = text; textView = resolved.pdf == null; });
    } on Exception catch (err) {
      if (mounted) setState(() => error = '$err');
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  void _pageOpened() {
    // This observation means the physical PDF page viewer, never parsed-text fallback.
    if (!mounted || opened || !(ModalRoute.of(context)?.isCurrent ?? true)) return;
    opened = true;
    widget.onPageOpened?.call();
  }

  Future<void> _reveal() async {
    final boxes = presentation!.boxes;
    final duration = calmReduceMotion(context) ? Duration.zero : const Duration(milliseconds: 180);
    final page = widget.evidence.page;
    if (boxes.isEmpty) {
      if (page != null && page > 0 && page <= controller.pageCount) {
        await controller.goToPage(pageNumber: page, duration: duration);
      }
      _pageOpened();
      return;
    }
    final area = boxes.reduce((a, b) => a.merge(b));
    final pad = PdfRect(area.left - 24, area.top + 48, area.right + 24, area.bottom - 48);
    await controller.goToRectInsidePage(pageNumber: page!, rect: pad, duration: duration);
    _pageOpened();
  }

  void _paint(Canvas canvas, Rect pageRect, PdfPage page) {
    if (page.pageNumber != widget.evidence.page) return;
    final fill = Paint()..color = CalmColors.markerFill;
    for (final r in presentation!.boxes) {
      canvas.drawRect(r.toRectInDocument(page: page, pageRect: pageRect), fill);
    }
  }

  Future<void> _showText() async {
    if (loading) return;
    if (pages != null) { setState(() => textView = true); return; }
    setState(() => loading = true);
    try {
      final text = await ServicesScope.of(context).api.versionText(widget.version.id);
      if (mounted) setState(() { pages = text; textView = true; });
    } on Exception {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text(AppLocalizations.of(context).contentLoadFailed)));
      }
    } finally { if (mounted) setState(() => loading = false); }
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final e = widget.evidence;
    final pdf = presentation?.pdf ?? presentation?.originalPdf;
    Widget body;
    if (pdf != null && !textView) {
      // The page and its highlight are painted, so a screen reader gets them as one described image.
      body = Semantics(container: true, image: true,
        label: evidencePdfDescription(l, e, marked: presentation!.boxes.isNotEmpty),
        // The viewer identifies a document by this name; labels can repeat, IDs can't (LR-6).
        child: PdfViewer.data(pdf, sourceName: widget.version.id, controller: controller,
          params: PdfViewerParams(pagePaintCallbacks: [_paint], onViewerReady: (_, _) => _reveal())));
    } else if (pages != null) {
      body = ParsedTextView(pages: pages!, evidence: e,
          note: presentation!.mode == 'text_fallback' ? l.highlightFallback : null);
    } else {
      body = error == null ? Center(child: CircularProgressIndicator(semanticsLabel: l.loading)) :
        CalmLoadError(onRetry: loading ? null : _load);
    }
    return Scaffold(
      appBar: AppBar(title: Text('${e.earlier ? l.sideEarlier : l.sideNewer}: ${widget.version.label}')),
      body: SafeArea(top: false, child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        if (pdf != null) Padding(padding: const EdgeInsets.fromLTRB(20, 0, 20, 8),
          child: Wrap(spacing: 8, children: [
            ChoiceChip(label: Text(l.pdfPage), selected: !textView,
              onSelected: (_) => setState(() => textView = false)),
            ChoiceChip(label: Text(l.readableText), selected: textView,
              onSelected: loading ? null : (_) => _showText()),
          ])),
        if (pdf != null && !textView && presentation?.mode == 'text_fallback')
          Padding(padding: const EdgeInsets.symmetric(horizontal: 20),
            child: CalmWarning(text: l.evidenceFallbackReview)),
        if (loading && presentation != null) LinearProgressIndicator(semanticsLabel: l.loading),
        Expanded(child: body),
      ])),
    );
  }
}

/// What a screen reader says for the PDF page view: the page, and the passage that is marked on it
/// (or, when the highlight could not be placed, that it is not marked).
String evidencePdfDescription(AppLocalizations l, Evidence e, {required bool marked}) => marked
    ? l.evidencePdfMarkedA11y(e.page ?? 1, e.quote) : l.evidencePdfUnmarkedA11y(e.page ?? 1, e.quote);

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
    final text = index >= 0 && index < pages.length ? pages[index] : '';
    final ok = e.charStart >= 0 && e.charEnd >= e.charStart && e.charEnd <= text.length &&
        text.substring(e.charStart, e.charEnd) == e.quote;
    final colors = CalmColors.of(context);
    // Translucent `marker-fill` on light, so a text selection shows through; on dark the mark stays
    // solid, because its ink text needs the lime behind it.
    final mark = TextStyle(backgroundColor: colors.dark ? colors.marker : CalmColors.markerFill,
      color: colors.onMarker, fontWeight: FontWeight.w600);
    return ListView(padding: const EdgeInsets.all(20), children: [
      if (note != null) Padding(padding: const EdgeInsets.only(bottom: 16), child: CalmWarning(text: note!)),
      // The mark is colour and weight only, so the passage is also named before the page text is read.
      Semantics(container: true, label: AppLocalizations.of(context).evidenceMarkedA11y(e.quote),
        // Selection here is `link`, not the marker: lime under a lime mark would not show.
        child: TextSelectionTheme(
          data: TextSelectionTheme.of(context).copyWith(selectionColor: colors.link.withValues(alpha: .35)),
          child: SelectableText.rich(TextSpan(style: Theme.of(context).textTheme.bodyLarge, children: ok
          ? [
              TextSpan(text: text.substring(0, e.charStart)),
              TextSpan(text: e.quote, style: mark),
              TextSpan(text: text.substring(e.charEnd)),
            ]
          : [TextSpan(text: e.quote, style: mark)])))),
    ]);
  }
}
