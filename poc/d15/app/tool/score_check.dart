// Desktop check for D-15: score mock-API passages against pdfrx_engine's PDFium (no device needed).
//   dart run tool/score_check.dart <dir with x.pdf + x.json pairs>
import 'dart:convert';
import 'dart:io';

import 'package:pdfrx_engine/pdfrx_engine.dart';

Future<void> main(List<String> args) async {
  await pdfrxInitialize();
  var ok = 0, total = 0;
  for (final f in Directory(args.first).listSync().whereType<File>().where((f) => f.path.endsWith('.pdf'))) {
    final body = jsonDecode(File(f.path.replaceAll('.pdf', '.json')).readAsStringSync()) as Map<String, dynamic>;
    final doc = await PdfDocument.openFile(f.path);
    for (final j in (body['passages'] as List).cast<Map<String, dynamic>>()) {
      final text = await doc.pages[(j['page'] as int) - 1].loadText();
      final s = j['char_start'] as int, e = j['char_end'] as int;
      final same = text!.fullText.substring(s, e) == j['text'];
      final local = [for (final r in text.charRects.sublist(s, e)) if (r.isNotEmpty) r];
      final back = [for (final b in j['boxes'] as List) PdfRect((b[0] as num).toDouble(), (b[3] as num).toDouble(), (b[2] as num).toDouble(), (b[1] as num).toDouble())];
      final u1 = back.reduce((a, b) => a.merge(b)), u2 = local.reduce((a, b) => a.merge(b));
      final d = [u1.left - u2.left, u1.top - u2.top, u1.right - u2.right, u1.bottom - u2.bottom].map((x) => x.abs()).reduce((a, b) => a > b ? a : b);
      total++;
      if (same && d < 0.5) ok++; else print('MISMATCH ${f.uri.pathSegments.last} #${j['id']} same=$same maxdiff=$d');
    }
    await doc.dispose();
  }
  print('$ok/$total passages match (text identical, union box within 0.5 pt)');
}
