// Fixes from the UI audit of 2026-11-21: history rows keep their tap action for screen readers,
// the iOS edge swipe steps back in onboarding, and an original PDF is fetched once per version.
// Widget and unit tests; not VoiceOver, TalkBack or device evidence.
import 'package:changelens/api.dart';
import 'package:changelens/design/calm_theme.dart';
import 'package:changelens/l10n/app_localizations.dart';
import 'package:changelens/screens/onboarding_screen.dart';
import 'package:changelens/screens/project_timeline.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'onboarding_test.dart' show openOnboarding, next, steps;

Version v(String id, {String status = 'parsed'}) =>
    Version({'id': id, 'label': id, 'kind': 'pdf', 'status': status});

void main() {
  testWidgets('History: version rows and comparison cards carry a tap action; Compare again is a custom action',
      (tester) async {
    final handle = tester.ensureSemantics();
    final from = <String>[], again = <String>[];
    await tester.pumpWidget(MaterialApp(theme: calmTheme(Brightness.light),
      localizationsDelegates: AppLocalizations.localizationsDelegates,
      supportedLocales: AppLocalizations.supportedLocales,
      home: Scaffold(body: ListView(children: [ProjectTimeline(versions: [v('a'), v('b')], loading: false,
        comparisons: [Comparison({'id': '1', 'earlier_id': 'a', 'later_id': 'b', 'scope': 'complete', 'status': 'failed'})],
        onCompareFrom: (x) => from.add(x.id), onCompareAgain: (x) => again.add(x.id))]))));
    await tester.pumpAndSettle();

    final version = tester.getSemantics(find.byKey(const Key('version-a')));
    expect(version.getSemanticsData().hasAction(SemanticsAction.tap), isTrue);
    version.owner!.performAction(version.id, SemanticsAction.tap);
    expect(from, ['a']);

    final card = tester.getSemantics(find.bySemanticsLabel(RegExp('^Comparison of a with the newer b')));
    final data = card.getSemanticsData();
    expect(data.hasAction(SemanticsAction.tap), isTrue);
    final ids = data.customSemanticsActionIds!;
    expect([for (final id in ids) CustomSemanticsAction.getAction(id)!.label], ['Compare again']);
    card.owner!.performAction(card.id, SemanticsAction.customAction, ids.single);
    expect(again, ['1']);
    handle.dispose();
  });

  testWidgets('Onboarding on iOS: a swipe from the left edge steps back; a swipe elsewhere does not', (tester) async {
    debugDefaultTargetPlatformOverride = TargetPlatform.iOS;
    tester.view.physicalSize = const Size(390, 844);
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    await openOnboarding(tester, OnboardingMode.firstRun);
    final l = lookupAppLocalizations(const Locale('en'));
    await next(tester);
    await next(tester);
    expect(find.text(l.onbStep(3, steps)), findsOneWidget);

    await tester.flingFrom(const Offset(300, 300), const Offset(250, 0), 1200);
    await tester.pumpAndSettle();
    expect(find.text(l.onbStep(3, steps)), findsOneWidget);

    await tester.flingFrom(const Offset(6, 300), const Offset(250, 0), 1200);
    await tester.pumpAndSettle();
    expect(find.text(l.onbStep(2, steps)), findsOneWidget);
    debugDefaultTargetPlatformOverride = null;
  });

  test('An original is fetched once per version; a failed fetch is not kept', () async {
    final requests = <String>[];
    var fail = true;
    final api = Api('http://dev.test', 'token', client: MockClient((request) async {
      requests.add(request.url.path);
      return fail ? http.Response('', 503) : http.Response.bytes([1, 2], 200);
    }));
    await expectLater(api.original('v1'), throwsA(isA<ApiException>()));
    fail = false;
    expect(await api.original('v1'), [1, 2]);
    expect(await api.original('v1'), [1, 2]);
    expect(await api.original('v2'), [1, 2]);
    expect(await api.original('v1'), [1, 2]);
    expect(requests, ['/versions/v1/original', '/versions/v1/original', '/versions/v2/original']);
    // Only the two most recently used stay in memory.
    await api.original('v3');
    await api.original('v2');
    expect(requests, hasLength(5));
  });
}
