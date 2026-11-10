// Device-side passage placement, shared by finding review and the page viewer (O-17).
// All document bytes/text stay in memory. A failed fetch is not a placement result.
import 'dart:typed_data';

import 'package:pdfrx/pdfrx.dart';

import '../api.dart';

class EvidencePresentation {
  const EvidencePresentation(this.mode, {this.pdf, this.originalPdf, this.boxes = const [], this.pages});

  final String mode;
  final Uint8List? pdf;
  /// Original bytes remain in memory for an explicitly requested unhighlighted PDF view.
  final Uint8List? originalPdf;
  final List<PdfRect> boxes;
  final List<String>? pages;
}

typedef PassageLocator = Future<List<PdfRect>?> Function(Uint8List bytes, Evidence evidence);
typedef EvidenceResolver = Future<EvidencePresentation> Function(Api api, Version version, Evidence evidence);

Future<EvidencePresentation> resolveEvidence(Api api, Version version, Evidence evidence,
    {PassageLocator locate = locatePdfPassage}) async {
  if (version.kind == 'text') return const EvidencePresentation('text_only');
  if (version.kind != 'pdf') throw const FormatException('unsupported source kind');
  final bytes = await api.original(version.id);
  List<PdfRect>? boxes;
  try {
    boxes = await locate(bytes, evidence);
  } on Exception {
    // A readable parsed source remains useful if the device cannot render this PDF.
    boxes = null;
  }
  if (boxes != null && boxes.isNotEmpty) {
    return EvidencePresentation('pdf_highlight', pdf: bytes, boxes: boxes);
  }
  return EvidencePresentation('text_fallback', originalPdf: bytes, pages: await api.versionText(version.id));
}

/// Null means that the exact quote cannot be placed, including malformed/out-of-range locators.
Future<List<PdfRect>?> locatePdfPassage(Uint8List bytes, Evidence evidence) async {
  final pageNumber = evidence.page;
  if (pageNumber == null || pageNumber < 1 || evidence.charStart < 0 || evidence.charEnd <= evidence.charStart) {
    return null;
  }
  final doc = await PdfDocument.openData(bytes, sourceName: 'evidence');
  try {
    if (pageNumber > doc.pages.length) return null;
    final text = await doc.pages[pageNumber - 1].loadText();
    if (text == null || evidence.charEnd > text.charRects.length || evidence.charEnd > text.fullText.length) {
      return null;
    }
    if (text.fullText.substring(evidence.charStart, evidence.charEnd) != evidence.quote) return null;
    final boxes = [for (final box in text.charRects.sublist(evidence.charStart, evidence.charEnd))
      if (box.isNotEmpty) box];
    return boxes.isEmpty ? null : boxes;
  } finally {
    await doc.dispose();
  }
}

/// Every passage must resolve. A side is fallback if any of its passages needs parsed text.
Map<String, String?> evidenceModes(Map<Evidence, EvidencePresentation> presentations) {
  final modes = <String, String?>{'before': null, 'after': null};
  for (final entry in presentations.entries) {
    final side = entry.key.earlier ? 'before' : 'after';
    if (modes[side] != 'text_fallback') modes[side] = entry.value.mode;
  }
  return modes;
}
