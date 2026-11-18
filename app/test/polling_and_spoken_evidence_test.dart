// L28 (audit A6, A8): polling pauses while the app is in the background, every request has a time
// limit with a plain message, and the marked evidence passage has a spoken label. Widget tests with a
// fake API; not device or screen-reader evidence.
import 'dart:async';

import 'package:changelens/api.dart';
import 'package:changelens/design/calm_widgets.dart';
import 'package:changelens/l10n/app_localizations.dart';
import 'package:changelens/main.dart';
import 'package:changelens/screens/comparison_screen.dart';
import 'package:changelens/screens/evidence_screen.dart';
import 'package:changelens/screens/project_screen.dart';
import 'package:changelens/screens/projects_screen.dart';
import 'package:changelens/services.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'app_test.dart' show Backend, FakePicker, MemoryStore, project;
import 'report_test.dart' as fixture;

final en = lookupAppLocalizations(const Locale('en'));

int gets(Backend backend) => backend.requests.where((r) => r.method == 'GET').length;

/// Sends the app to the background and brings it back at the end of the test.
void background(WidgetTester tester) {
  addTearDown(() => tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed));
  for (final state in [AppLifecycleState.inactive, AppLifecycleState.hidden, AppLifecycleState.paused]) {
    tester.binding.handleAppLifecycleStateChanged(state);
  }
}

/// Shows [screen] against [handler] without waiting for it to settle: a status screen never does.
Future<void> pumpScreen(WidgetTester tester, Widget screen, MockClientHandler handler) async {
  final store = MemoryStore()
    ..values['api_base_url'] = 'http://dev.test'
    ..values['dev_token'] = 'dev-token-0123456789';
  final services = Services(store, FakePicker(null),
      apiFactory: (base, token) => Api(base, token, client: MockClient(handler)));
  await services.load();
  await tester.pumpWidget(ChangeLensApp(services: services, home: screen));
  await tester.pump();
}

void main() {
  for (final (name, screen) in <(String, Widget Function())>[
    ('project list', () => const ProjectsScreen()),
    ('project', () => ProjectScreen(project: project)),
    ('comparison status', () => const ComparisonScreen(comparisonId: 'c1')),
  ]) {
    testWidgets('A6: the $name stops polling in the background and resumes after it', (tester) async {
      final backend = Backend();
      await pumpScreen(tester, screen(), backend.handle);
      await tester.pump(const Duration(seconds: 3));
      await tester.pump();
      final before = gets(backend);
      expect(before, greaterThan(1)); // it polls while the app is in front

      background(tester);
      await tester.pump(const Duration(seconds: 12));
      await tester.pump();
      expect(gets(backend), before);

      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      await tester.pump(const Duration(seconds: 3));
      await tester.pump();
      expect(gets(backend), greaterThan(before));
      await tester.pumpWidget(const SizedBox());
    });
  }

  test('A6: a request that gets no answer ends at the time limit', () async {
    final api = Api('http://dev.test', 't', client: MockClient((_) => Completer<http.Response>().future),
        limit: const Duration(milliseconds: 20));
    await expectLater(api.projects(), throwsA(isA<TimeoutException>()));
    expect(userErrorMessage(en, TimeoutException('no answer')), en.errorConnection);
  });

  testWidgets('A6: a stalled status request shows a plain message and Retry', (tester) async {
    await pumpScreen(tester, const ComparisonScreen(comparisonId: 'c1'),
        (_) => Completer<http.Response>().future);
    await tester.pump(const Duration(seconds: 29));
    expect(find.text(en.comparisonLoadFailed), findsNothing);
    await tester.pump(const Duration(seconds: 2));
    await tester.pump();
    expect(find.text(en.comparisonLoadFailed), findsOneWidget);
    expect(find.text(en.retry), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
    await tester.pump(const Duration(seconds: 31)); // the last request's own limit runs out
  });

  testWidgets('A8: the marked passage in the text view has a spoken label', (tester) async {
    final semantics = tester.ensureSemantics();
    final e = Evidence(fixture.ev('earlier', 'Hosting is provided by the client', 19));
    await fixture.pump(tester, EvidenceScreen(version: fixture.versions[0], evidence: e));
    expect(find.bySemanticsLabel('Marked passage: Hosting is provided by the client'), findsOneWidget);
    semantics.dispose();
  });

  test('A8: the PDF page is described with its page number and the passage', () {
    final e = Evidence({'side': 'later', 'quote': 'Budget: EUR 15,000',
      'locator': {'page': 2, 'char_start': 0, 'char_end': 18}});
    expect(evidencePdfDescription(en, e, marked: true), 'PDF page 2. Marked passage: Budget: EUR 15,000');
    expect(evidencePdfDescription(en, e, marked: false),
        'PDF page 2. The passage is not marked on this page: Budget: EUR 15,000');
  });
}
