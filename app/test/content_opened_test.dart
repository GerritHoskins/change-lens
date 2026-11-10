import 'dart:async';

import 'package:changelens/api.dart';
import 'package:changelens/main.dart';
import 'package:changelens/screens/evidence_resolution.dart';
import 'package:changelens/screens/evidence_screen.dart';
import 'package:changelens/screens/finding_screen.dart';
import 'package:changelens/screens/report_screen.dart';
import 'package:changelens/services.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'app_test.dart' show MemoryStore, FakePicker;
import 'report_test.dart' as fixture;

class OpenedBackend extends fixture.ReportBackend {
  bool failOpened = false, failText = false;
  Completer<http.Response>? pendingOpened;

  @override
  Future<http.Response> handle(http.Request request) async {
    if (request.url.path.endsWith('/opened') && (failOpened || pendingOpened != null)) {
      requests.add(request);
      return pendingOpened?.future ?? http.Response(
        '{"code":"unavailable","detail":"PRIVATE_CONTENT"}', 503);
    }
    if (failText && request.url.path.endsWith('/text')) {
      requests.add(request);
      return http.Response('{"code":"unavailable"}', 503);
    }
    return super.handle(request);
  }

  List<String> get calls => requests.map((request) => '${request.method} ${request.url.path}').toList();
}

Future<Services> pumpContent(WidgetTester tester, OpenedBackend backend, Widget screen) async {
  final store = MemoryStore()..values['api_base_url'] = 'http://dev.test'
    ..values['dev_token'] = 'dev-token-0123456789';
  final services = Services(store, FakePicker(null), apiFactory: (base, token) =>
    Api(base, token, client: MockClient(backend.handle)));
  await services.load();
  tester.view.physicalSize = const Size(800, 1800);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(ChangeLensApp(services: services, home: screen));
  await tester.pump();
  return services;
}

void main() {
  test('explicit opened methods send only authenticated content-free POSTs and accept 204', () async {
    final requests = <http.Request>[];
    final api = Api('http://dev.test', 'test-token', client: MockClient((request) async {
      requests.add(request);
      return http.Response('', 204);
    }));
    await api.comparisonOpened('c1');
    await api.versionOpened('v1');
    expect(requests.map((request) => request.url.path), ['/comparisons/c1/opened', '/versions/v1/opened']);
    for (final request in requests) {
      expect(request.method, 'POST');
      expect(request.headers['Authorization'], 'Bearer test-token');
      expect(request.body, isEmpty);
    }
  });

  testWidgets('report waits for opened acknowledgement; refresh and return reload do not repeat it', (tester) async {
    final backend = OpenedBackend()..pendingOpened = Completer<http.Response>();
    await pumpContent(tester, backend, ReportScreen(comparisonId: 'c1', versions: fixture.versions));
    expect(backend.calls, ['POST /comparisons/c1/opened']);
    expect(find.text('Changes'), findsNothing);
    backend.pendingOpened!.complete(http.Response('', 204));
    backend.pendingOpened = null;
    await tester.pumpAndSettle();
    expect(backend.calls, ['POST /comparisons/c1/opened', 'GET /comparisons/c1/findings']);
    await tester.widget<RefreshIndicator>(find.byType(RefreshIndicator)).onRefresh();
    await tester.pumpAndSettle();
    expect(backend.posts(), ['/comparisons/c1/opened']);
    await tester.tap(find.text('Explanation of f1.'));
    await tester.pumpAndSettle();
    expect(backend.posts(), ['/comparisons/c1/opened', '/comparisons/c1/opened']);
    expect(backend.requests.where((request) => request.url.path == '/versions/v1/opened'), isEmpty);
    await tester.pageBack();
    await tester.pumpAndSettle();
    expect(backend.posts(), ['/comparisons/c1/opened', '/comparisons/c1/opened']);
  });

  for (final surface in ['report', 'finding', 'cached source']) {
    testWidgets('$surface blocks content on failed opened event and recovers only on explicit Retry', (tester) async {
      final report = await fixture.loadReport(fixture.ReportBackend());
      final backend = OpenedBackend()..failOpened = true;
      var pageOpened = false;
      final screen = switch (surface) {
        'report' => ReportScreen(comparisonId: 'c1', versions: fixture.versions),
        'finding' => FindingScreen(comparisonId: 'c1', findingId: 'f1', report: report,
          versions: fixture.versions),
        _ => EvidenceScreen(version: fixture.versions[0], evidence: Evidence(fixture.ev('earlier', 'Budget', 0)),
          presentation: const EvidencePresentation('text_fallback', pages: [fixture.earlierText]),
          onPageOpened: () => pageOpened = true),
      };
      await pumpContent(tester, backend, screen);
      await tester.pumpAndSettle();
      expect(find.text('This content could not be opened. Check your connection and retry.'), findsOneWidget);
      expect(find.textContaining('PRIVATE_CONTENT'), findsNothing);
      expect(find.byType(ParsedTextView), findsNothing);
      expect(find.text('Explanation of f1.'), findsNothing);
      expect(find.text('Confirm'), findsNothing);
      tester.view.physicalSize = const Size(320, 568);
      tester.binding.platformDispatcher.textScaleFactorTestValue = 2;
      addTearDown(tester.binding.platformDispatcher.clearAllTestValues);
      await tester.pumpAndSettle();
      expect(tester.takeException(), isNull);
      expect(find.text('Retry').hitTestable(), findsOneWidget);
      tester.view.physicalSize = const Size(800, 1800);
      tester.binding.platformDispatcher.textScaleFactorTestValue = 1;
      await tester.pumpAndSettle();
      final endpoint = surface == 'cached source' ? '/versions/v1/opened' : '/comparisons/c1/opened';
      expect(backend.calls, ['POST $endpoint']);
      await tester.pump(const Duration(seconds: 30));
      expect(backend.calls, ['POST $endpoint']); // no retry heartbeat
      backend.failOpened = false;
      await tester.tap(find.text('Retry'));
      await tester.pumpAndSettle();
      expect(backend.posts(), [endpoint, endpoint]);
      if (surface == 'cached source') {
        expect(find.byType(ParsedTextView), findsOneWidget);
        expect(backend.calls, ['POST $endpoint', 'POST $endpoint']); // cached content still registers use
        expect(pageOpened, false); // retention use is distinct from physical PDF-page telemetry
      } else {
        expect(find.text('Explanation of f1.'), findsOneWidget);
      }
    });
  }

  testWidgets('source fetch retry does not repeat successful opened event', (tester) async {
    final backend = OpenedBackend()..failText = true;
    await pumpContent(tester, backend, EvidenceScreen(version: fixture.versions[0],
      evidence: Evidence(fixture.ev('earlier', 'Budget', 0))));
    await tester.pumpAndSettle();
    expect(backend.calls, ['POST /versions/v1/opened', 'GET /versions/v1/text']);
    backend.failText = false;
    await tester.tap(find.text('Retry'));
    await tester.pumpAndSettle();
    expect(find.byType(ParsedTextView), findsOneWidget);
    expect(backend.calls, ['POST /versions/v1/opened', 'GET /versions/v1/text', 'GET /versions/v1/text']);
  });

  testWidgets('iOS-themed German error remains scrollable at small phone size and 200% text', (tester) async {
    tester.binding.platformDispatcher.localesTestValue = const [Locale('de')];
    tester.binding.platformDispatcher.textScaleFactorTestValue = 2;
    addTearDown(tester.binding.platformDispatcher.clearAllTestValues);
    final backend = OpenedBackend()..failOpened = true;
    await pumpContent(tester, backend, const ReportScreen(comparisonId: 'c1'));
    tester.view.physicalSize = const Size(320, 568);
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    await tester.ensureVisible(find.text('Erneut versuchen'));
    await tester.pumpAndSettle();
    expect(find.text('Erneut versuchen').hitTestable(), findsOneWidget);
    expect(backend.calls, ['POST /comparisons/c1/opened']);
  }, variant: TargetPlatformVariant.only(TargetPlatform.iOS));

  testWidgets('cached source rebuild never repeats use but a new screen opening does', (tester) async {
    final backend = OpenedBackend();
    Widget source(String key) => EvidenceScreen(key: ValueKey(key), version: fixture.versions[0],
      evidence: Evidence(fixture.ev('earlier', 'Budget', 0)),
      presentation: const EvidencePresentation('text_only', pages: [fixture.earlierText]));
    final services = await pumpContent(tester, backend, source('first'));
    await tester.pumpAndSettle();
    await tester.pumpWidget(ChangeLensApp(services: services, home: source('first')));
    await tester.pumpAndSettle();
    expect(backend.posts(), ['/versions/v1/opened']);
    await tester.pumpWidget(ChangeLensApp(services: services, home: source('second')));
    await tester.pumpAndSettle();
    expect(backend.posts(), ['/versions/v1/opened', '/versions/v1/opened']);
  });
}
