import 'dart:async';
import 'dart:convert';

import 'package:changelens/api.dart';
import 'package:changelens/main.dart';
import 'package:changelens/screens/evidence_resolution.dart';
import 'package:changelens/screens/evidence_screen.dart';
import 'package:changelens/screens/finding_screen.dart';
import 'package:changelens/screens/review_completion.dart';
import 'package:changelens/services.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'app_test.dart' show MemoryStore, FakePicker;
import 'report_test.dart' as fixture;

class ProgressBackend extends fixture.ReportBackend {
  ProgressBackend({bool needsReview = false}) {
    findings = [
      fixture.finding('first', needsReview ? 'uncertain' : 'changed', 'budget',
        needsReview ? 'needs_review' : 'prioritised', [fixture.ev('earlier', 'First source', 0)]),
      fixture.finding('done', 'changed', 'date_deadline', 'prioritised', [fixture.ev('earlier', 'Already done', 0)],
        review: {'action': 'confirmed', 'at': '2026-11-07T00:00:00Z'}),
      fixture.finding('second', 'changed', 'deliverable', 'prioritised', [fixture.ev('later', 'Second source', 0)]),
    ];
  }

  bool rejectReview = false, failNextLoad = false, supersedeOnReject = false;
  Map<String, dynamic>? replacement;

  @override
  Future<http.Response> handle(http.Request request) async {
    if (rejectReview && request.method == 'POST' && request.url.path.endsWith('/reviews')) {
      requests.add(request);
      if (supersedeOnReject) {
        replacement = fixture.finding('first_r2', 'changed', 'budget', 'prioritised',
          [fixture.ev('later', 'Updated source', 0)], revision: 2);
        findings = [replacement!, ...findings.skip(1)];
      }
      return http.Response('{"code":"finding_superseded"}', 409);
    }
    if (request.method == 'GET' && request.url.path == '/findings/first' && replacement != null) {
      requests.add(request);
      return http.Response(jsonEncode({...replacement!, 'revisions': [replacement],
        'reviews': [], 'client_approvals': []}), 200);
    }
    if (failNextLoad && request.url.path == '/findings/second') {
      requests.add(request);
      return http.Response('{"code":"unavailable"}', 503);
    }
    final response = await super.handle(request);
    if (request.method == 'POST' && request.url.path.endsWith('/reviews') && response.statusCode < 300) {
      final current = (jsonDecode(response.body) as Map)['finding'] as Map<String, dynamic>;
      final oldId = request.url.path.split('/')[2];
      findings = [for (final finding in findings) finding['id'] == oldId ? current : finding];
    }
    return response;
  }
}

Future<void> pumpProgress(WidgetTester tester, ProgressBackend backend,
    {String findingId = 'first', EvidenceResolver resolve = resolveEvidence}) async {
  final report = await fixture.loadReport(backend);
  final store = MemoryStore()..values['api_base_url'] = 'http://dev.test'
    ..values['dev_token'] = 'dev-token-0123456789';
  final services = Services(store, FakePicker(null), apiFactory: (base, token) =>
    Api(base, token, client: MockClient(backend.handle)));
  await services.load();
  tester.view.physicalSize = const Size(800, 1800);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(ChangeLensApp(services: services, home: FindingScreen(
    comparisonId: 'c1', findingId: findingId, report: report, versions: fixture.versions, resolve: resolve)));
  await tester.pumpAndSettle();
}

List<http.Request> reviewPosts(ProgressBackend backend) => backend.requests.where((request) =>
  request.method == 'POST' && request.url.path.endsWith('/reviews')).toList();

void main() {
  testWidgets('confirmation skips reviewed findings, resets observations, and waits for next evidence', (tester) async {
    final backend = ProgressBackend();
    final next = Completer<EvidencePresentation>();
    await pumpProgress(tester, backend, resolve: (_, _, evidence) async => evidence.quote == 'Second source'
      ? next.future : const EvidencePresentation('text_only'));
    await tester.tap(find.text('First source'));
    await tester.pumpAndSettle();
    // Simulate the viewer's positive notification to verify state isolation, not native PDF rendering.
    tester.widget<EvidenceScreen>(find.byType(EvidenceScreen)).onPageOpened!();
    await tester.pageBack();
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('review-confirm')));
    await tester.pumpAndSettle();
    expect(find.text('Explanation of second.'), findsOneWidget);
    expect(backend.requests.where((r) => r.url.path == '/findings/done'), isEmpty);
    expect(tester.widget<FilledButton>(find.byKey(const Key('review-confirm'))).onPressed, isNull);
    expect(jsonDecode(reviewPosts(backend).single.body)['page_opened'], true);
    next.complete(const EvidencePresentation('text_only'));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('review-confirm')));
    await tester.pumpAndSettle();
    final posts = reviewPosts(backend);
    expect(posts.map((request) => request.url.path), ['/findings/first/reviews', '/findings/second/reviews']);
    expect(jsonDecode(posts.last.body)['evidence_mode'], {'before': null, 'after': 'text_only'});
    expect(jsonDecode(posts.last.body)['page_opened'], false);
    // Every finding now has a review on the server: the summary (P7), counted from the reloaded report.
    expect(find.byType(ReviewSummaryScreen), findsOneWidget);
    expect(backend.requests.where((r) => r.method == 'GET' && r.url.path == '/comparisons/c1/findings'),
      hasLength(greaterThanOrEqualTo(1)));
    expect(backend.requests.where((request) => request.url.path == '/comparisons/c1/opened'), hasLength(1));
  });

  testWidgets('needs-review confirmation stays even when another finding follows', (tester) async {
    final backend = ProgressBackend(needsReview: true);
    await pumpProgress(tester, backend);
    await tester.tap(find.byKey(const Key('review-confirm')));
    await tester.pumpAndSettle();
    expect(find.text('Explanation of first.'), findsOneWidget);
    expect(find.text('Confirmed by you'), findsWidgets);
    expect(backend.requests.where((r) => r.url.path == '/findings/second'), isEmpty);
  });

  testWidgets('rejected confirmation never advances or resubmits automatically', (tester) async {
    final backend = ProgressBackend()..rejectReview = true;
    await pumpProgress(tester, backend);
    await tester.tap(find.byKey(const Key('review-confirm')));
    await tester.pumpAndSettle();
    expect(find.text('First source'), findsOneWidget);
    expect(find.text('This finding changed. Review the current revision before trying again.'), findsOneWidget);
    expect(backend.requests.where((r) => r.url.path == '/findings/second'), isEmpty);
  });

  testWidgets('superseded review loads the current revision and checks new evidence without resubmitting', (tester) async {
    final backend = ProgressBackend()..rejectReview = true..supersedeOnReject = true;
    final updated = Completer<EvidencePresentation>();
    await pumpProgress(tester, backend, resolve: (_, _, evidence) async => evidence.quote == 'Updated source'
      ? updated.future : const EvidencePresentation('text_only'));
    await tester.tap(find.text('First source'));
    await tester.pumpAndSettle();
    final oldViewer = tester.widget<EvidenceScreen>(find.byType(EvidenceScreen));
    oldViewer.onPageOpened!();
    await tester.pageBack();
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('review-confirm')));
    await tester.pumpAndSettle();
    expect(find.text('Updated source'), findsOneWidget);
    expect(tester.widget<FilledButton>(find.byKey(const Key('review-confirm'))).onPressed, isNull);
    expect(reviewPosts(backend).length, 1);
    // A delayed notification from the previous revision must not contaminate the new one.
    oldViewer.onPageOpened!();
    updated.complete(const EvidencePresentation('text_only'));
    await tester.pumpAndSettle();
    expect(find.text('This finding changed. Review the current revision before trying again.'), findsOneWidget);
    backend.rejectReview = false;
    await tester.tap(find.byKey(const Key('review-confirm')));
    await tester.pumpAndSettle();
    final posts = reviewPosts(backend);
    expect(posts.map((post) => post.url.path), ['/findings/first/reviews', '/findings/first_r2/reviews']);
    expect(jsonDecode(posts.last.body)['page_opened'], false);
    expect(jsonDecode(posts.last.body)['evidence_mode'], {'before': null, 'after': 'text_only'});
  });

  testWidgets('next-detail fetch can retry without repeating the successful confirmation', (tester) async {
    final backend = ProgressBackend()..failNextLoad = true;
    await pumpProgress(tester, backend);
    await tester.tap(find.byKey(const Key('review-confirm')));
    await tester.pumpAndSettle();
    expect(find.text('First source'), findsNothing);
    expect(find.text('Retry'), findsOneWidget);
    backend.failNextLoad = false;
    await tester.tap(find.text('Retry'));
    await tester.pumpAndSettle();
    expect(find.text('Second source'), findsOneWidget);
    expect(reviewPosts(backend).length, 1);
  });

  for (final action in ['Add note']) {
    testWidgets('$action stays on the current finding', (tester) async {
      final backend = ProgressBackend();
      await pumpProgress(tester, backend);
      await tester.tap(find.text(action));
      await tester.pumpAndSettle();
      await tester.enterText(find.byKey(const Key('note-field')), 'A review note');
      await tester.tap(find.text('Save'));
      await tester.pumpAndSettle();
      expect(find.text('Explanation of first.'), findsOneWidget);
      expect(backend.requests.where((r) => r.url.path == '/findings/second'), isEmpty);
    });
  }
}
