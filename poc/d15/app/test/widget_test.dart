import 'package:changelens_poc/main.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:pdfrx/pdfrx.dart';

void main() {
  test('IoU of identical, disjoint and half-overlapping boxes', () {
    const a = PdfRect(0, 10, 10, 0);
    expect(iouOf(a, a), 1);
    expect(iouOf(a, const PdfRect(20, 10, 30, 0)), 0);
    expect(iouOf(a, const PdfRect(5, 10, 15, 0)), closeTo(1 / 3, 1e-9));
    expect(iouOf(null, a), 0);
  });

  test('union merges boxes and is null when empty', () {
    expect(union(const []), isNull);
    final u = union(const [PdfRect(0, 10, 5, 0), PdfRect(4, 12, 9, 2)])!;
    expect([u.left, u.top, u.right, u.bottom], [0, 12, 9, 0]);
  });

  testWidgets('starts with the pick prompt', (tester) async {
    await tester.pumpWidget(const PocApp());
    expect(find.text('Pick an older and a newer PDF.'), findsOneWidget);
    expect(find.byIcon(Icons.history), findsOneWidget);
  });
}
