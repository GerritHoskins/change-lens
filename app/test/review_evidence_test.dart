import 'dart:async';
import 'dart:convert';
import 'dart:typed_data';

import 'package:changelens/api.dart';
import 'package:changelens/screens/evidence_resolution.dart';
import 'package:changelens/screens/evidence_screen.dart';
import 'package:changelens/screens/finding_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:pdfrx/pdfrx.dart';

import 'report_test.dart' as fixture;

final pdfVersion = Version({'id': 'v1', 'label': 'Brief v1', 'kind': 'pdf', 'status': 'parsed'});

void main() {
  test('historical review observations stay unknown', () {
    final review = Review({'action': 'confirmed', 'at': '2026-11-07T00:00:00Z'});
    expect(review.evidenceModeBefore, isNull);
    expect(review.evidenceModeAfter, isNull);
    expect(review.pageOpened, isNull);
    final observed = Review({'action': 'note', 'at': '2026-11-07T00:00:00Z',
      'evidence_mode': {'before': 'text_fallback', 'after': null}, 'page_opened': false});
    expect(observed.evidenceModeBefore, 'text_fallback');
    expect(observed.evidenceModeAfter, isNull);
    expect(observed.pageOpened, false);
  });

  for (final mode in ['pdf_highlight', 'text_fallback']) {
    testWidgets('$mode is resolved before all review controls and sent without opening a page', (tester) async {
      final report = await fixture.loadReport(fixture.ReportBackend());
      final resolved = Completer<EvidencePresentation>();
      final backend = await fixture.pump(tester, FindingScreen(comparisonId: 'c1', findingId: 'f1', report: report,
        versions: [pdfVersion, fixture.versions[1]], resolve: (api, version, evidence) async =>
          version.kind == 'pdf' ? resolved.future : const EvidencePresentation('text_only')));
      for (final label in ['Confirm', 'Correct', 'Dismiss', 'Add note']) {
        final button = tester.widget<ButtonStyleButton>(label == 'Confirm'
          ? find.byKey(const Key('review-confirm'))
          : find.ancestor(of: find.text(label),
              matching: find.byWidgetPredicate((widget) => widget is ButtonStyleButton)));
        expect(button.onPressed, isNull);
      }
      expect(backend.posts(), ['/comparisons/c1/opened']);
      resolved.complete(EvidencePresentation(mode, pages: [fixture.earlierText]));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('review-fallback')), mode == 'text_fallback' ? findsOneWidget : findsNothing);
      if (mode == 'text_fallback') {
        expect(tester.getBottomLeft(find.byKey(const Key('review-fallback'))).dy,
            lessThan(tester.getTopLeft(find.byKey(const Key('review-confirm'))).dy));
      }
      await tester.tap(find.byKey(const Key('review-confirm')));
      await tester.pumpAndSettle();
      final body = jsonDecode(backend.requests.lastWhere((r) => r.method == 'POST').body);
      expect(body['evidence_mode'], {'before': mode, 'after': 'text_only'});
      expect(body['page_opened'], false);
      expect(backend.posts(), ['/comparisons/c1/opened', '/findings/f1/reviews']);
    });
  }

  testWidgets('failed source check blocks review and retry recovers', (tester) async {
    final report = await fixture.loadReport(fixture.ReportBackend());
    var failing = true;
    final backend = await fixture.pump(tester, FindingScreen(comparisonId: 'c1', findingId: 'f2', report: report,
      versions: fixture.versions, resolve: (api, version, evidence) async {
        if (failing) throw ApiException(503, 'unavailable');
        return const EvidencePresentation('text_only');
      }));
    expect(tester.widget<FilledButton>(find.byKey(const Key('review-confirm'))).onPressed, isNull);
    failing = false;
    await tester.tap(find.text('Retry'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('review-confirm')));
    await tester.pumpAndSettle();
    final body = jsonDecode(backend.requests.lastWhere((r) => r.method == 'POST').body);
    expect(body['evidence_mode'], {'before': 'text_only', 'after': null});
    expect(find.textContaining('Hosting is provided'), findsOneWidget); // needs-review never advances
  });

  testWidgets('opening parsed PDF fallback does not claim the physical page opened', (tester) async {
    final report = await fixture.loadReport(fixture.ReportBackend());
    final backend = await fixture.pump(tester, FindingScreen(comparisonId: 'c1', findingId: 'f2', report: report,
      versions: [pdfVersion], resolve: (api, version, evidence) async =>
        const EvidencePresentation('text_fallback', pages: [fixture.earlierText])));
    await tester.tap(find.text('Hosting is provided by the client'));
    await tester.pumpAndSettle();
    expect(find.byType(ParsedTextView), findsOneWidget);
    await tester.pageBack();
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('review-confirm')));
    await tester.pumpAndSettle();
    final body = jsonDecode(backend.requests.lastWhere((r) => r.method == 'POST').body);
    expect(body['page_opened'], false);
    expect(body['evidence_mode'], {'before': 'text_fallback', 'after': null});
  });

  testWidgets('German fallback at 200% keeps source evidence scrollable above pinned Confirm', (tester) async {
    tester.binding.platformDispatcher.localesTestValue = const [Locale('de')];
    tester.binding.platformDispatcher.textScaleFactorTestValue = 2;
    addTearDown(tester.binding.platformDispatcher.clearAllTestValues);
    final report = await fixture.loadReport(fixture.ReportBackend());
    await fixture.pump(tester, FindingScreen(comparisonId: 'c1', findingId: 'f1', report: report,
      versions: fixture.versions, resolve: (_, _, _) async =>
        const EvidencePresentation('text_fallback', pages: [fixture.earlierText])));
    tester.view.physicalSize = const Size(320, 568);
    await tester.pumpAndSettle();
    await tester.scrollUntilVisible(find.text('Budget: EUR 12,000'), 120,
      scrollable: find.byType(Scrollable).first);
    await tester.pumpAndSettle();
    expect(tester.getBottomLeft(find.text('Budget: EUR 12,000')).dy,
      lessThan(tester.getTopLeft(find.byKey(const Key('review-fallback'))).dy));
    expect(find.byKey(const Key('review-confirm')), findsOneWidget);
    expect(tester.takeException(), isNull);
  });

  test('resolver distinguishes exact placement, parsed fallback, and failed fetch', () async {
    final requests = <String>[];
    var unavailable = false;
    final api = Api('http://dev.test', 'token', client: MockClient((request) async {
      requests.add(request.url.path);
      if (unavailable) return http.Response('', 503);
      return request.url.path.endsWith('/original') ? http.Response.bytes([1, 2], 200) :
        http.Response(jsonEncode({'pages': [fixture.earlierText]}), 200);
    }));
    final evidence = Evidence(fixture.ev('earlier', 'Budget', 0));
    expect((await resolveEvidence(api, fixture.versions[0], evidence)).mode, 'text_only');
    expect(requests, isEmpty);
    final highlighted = await resolveEvidence(api, pdfVersion, evidence,
      locate: (_, _) async => [const PdfRect(0, 10, 20, 0)]);
    expect(highlighted.mode, 'pdf_highlight');
    expect(highlighted.pdf, [1, 2]);
    expect(requests, ['/versions/v1/original']);
    for (final throws in [false, true]) {
      final fallback = await resolveEvidence(api, pdfVersion, evidence, locate: (_, _) async {
        if (throws) throw const FormatException('unreadable');
        return null;
      });
      expect(fallback.mode, 'text_fallback');
      expect(fallback.pages, [fixture.earlierText]);
    }
    unavailable = true;
    await expectLater(resolveEvidence(api, pdfVersion, evidence), throwsA(isA<ApiException>()));
    expect(await locatePdfPassage(Uint8List(0), evidence), isNull); // page missing: no native load
  });

  test('one fallback controls a side with several passages; absent side stays null', () {
    final a = Evidence(fixture.ev('earlier', 'One', 0));
    final b = Evidence(fixture.ev('earlier', 'Two', 4));
    expect(evidenceModes({a: const EvidencePresentation('text_fallback'),
      b: const EvidencePresentation('pdf_highlight')}), {'before': 'text_fallback', 'after': null});
    expect(evidenceModes({a: const EvidencePresentation('pdf_highlight'),
      b: const EvidencePresentation('text_fallback')}), {'before': 'text_fallback', 'after': null});
  });
}
