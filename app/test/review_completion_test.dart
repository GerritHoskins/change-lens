// WP-C: P5 dismissal with a reason (none preselected, optional note, dismiss-and-next; the finding is
// never relabelled) and P7, the review summary counted from the server's report, which says it isn't
// client approval. Widget tests with a fake API; not device evidence.
import 'dart:convert';

import 'package:changelens/api.dart';
import 'package:changelens/l10n/app_localizations.dart';
import 'package:changelens/screens/review_completion.dart';
import 'package:changelens/screens/project_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'finding_progression_test.dart' show ProgressBackend, pumpProgress, reviewPosts;

Future<void> openDismiss(WidgetTester tester) async {
  await tester.ensureVisible(find.byKey(const Key('review-dismiss')));
  await tester.tap(find.byKey(const Key('review-dismiss')));
  await tester.pumpAndSettle();
}

Report summaryReport() => Report({
  'status': 'complete', 'earlier_id': 'v1', 'later_id': 'v2',
  'findings': [
    for (final (id, action) in [('a', 'confirmed'), ('b', 'confirmed'), ('c', 'dismissed')])
      {'id': id, 'change_type': 'changed', 'category': 'budget', 'topic': 'budget', 'evidence': [],
       'group': 'prioritised', 'priority': 0, 'revision': 1,
       'review': {'action': action, 'at': '2026-11-16T00:00:00Z'}, 'client_approval_recorded': false},
  ],
});

void main() {
  testWidgets('P5: four reasons, none chosen, the action waits for one', (tester) async {
    final backend = ProgressBackend();
    await pumpProgress(tester, backend);
    await openDismiss(tester);
    expect(find.text('Why dismiss this finding?'), findsOneWidget);
    for (final r in dismissalReasons) {
      expect(find.byKey(Key('dismiss-reason-$r')), findsOneWidget);
    }
    expect(find.byWidgetPredicate((w) => w is RadioGroup<String> && w.groupValue == null), findsOneWidget);
    expect(tester.widget<FilledButton>(find.byKey(const Key('dismiss-confirm'))).onPressed, isNull);
    expect(find.text('Choose a reason first.'), findsOneWidget); // the disabled button says why
    expect(find.text('Dismiss and next'), findsOneWidget);
    await tester.tap(find.text('Cancel'));
    await tester.pumpAndSettle();
    expect(reviewPosts(backend), isEmpty);
  });

  testWidgets('P5: dismiss with reason and note, then the next open finding', (tester) async {
    final backend = ProgressBackend();
    await pumpProgress(tester, backend);
    await openDismiss(tester);
    await tester.tap(find.byKey(const Key('dismiss-reason-wrong_passage')));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const Key('dismiss-note')), 'Quotes the appendix');
    await tester.tap(find.byKey(const Key('dismiss-confirm')));
    await tester.pumpAndSettle();
    final body = jsonDecode(reviewPosts(backend).single.body) as Map;
    expect(body['action'], 'dismissed');
    expect(body['dismissal_reason'], 'wrong_passage');
    expect(body['note'], 'Quotes the appendix');
    expect(body.containsKey('correction') && body['correction'] != null, isFalse); // never relabelled
    expect(find.text('Explanation of second.'), findsOneWidget); // "done" is skipped
  });

  testWidgets('P7: the last review shows server counts, not client approval, and goes back', (tester) async {
    final backend = ProgressBackend();
    await pumpProgress(tester, backend, findingId: 'second');
    // "second" is the last open finding after "first": dismiss "first" on the server first.
    backend.findings = [
      for (final f in backend.findings)
        f['id'] == 'first' ? {...f, 'review': {'action': 'corrected', 'at': '2026-11-07T00:00:00Z'}} : f,
    ];
    await openDismiss(tester);
    expect(find.text('Dismiss'), findsWidgets); // no next: plain "Dismiss"
    await tester.tap(find.byKey(const Key('dismiss-reason-irrelevant')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const Key('dismiss-confirm')));
    await tester.pumpAndSettle();
    expect(find.byType(ReviewSummaryScreen), findsOneWidget);
    expect(find.text('Every finding reviewed'), findsOneWidget);
    final counts = find.byKey(const Key('review-counts'));
    for (final label in ['Confirmed', 'Corrected', 'Dismissed']) {
      expect(find.descendant(of: counts, matching: find.text(label)), findsOneWidget);
    }
    expect(find.descendant(of: counts, matching: find.text('1')), findsNWidgets(3));
    expect(find.textContaining("not client approval"), findsOneWidget);
    // Counts are ink: nothing in the summary uses the marker or a topic colour.
    expect(find.descendant(of: counts, matching: find.byType(ColoredBox)), findsNothing);
    expect(find.byKey(const Key('review-back-to-project')), findsOneWidget);
  });

  testWidgets('P7 in German, and back stops at the project', (tester) async {
    final nav = GlobalKey<NavigatorState>();
    await tester.pumpWidget(MaterialApp(navigatorKey: nav, locale: const Locale('de'),
      localizationsDelegates: AppLocalizations.localizationsDelegates, supportedLocales: AppLocalizations.supportedLocales,
      home: const Scaffold(body: Text('home'))));
    nav.currentState!.push(MaterialPageRoute<void>(settings: const RouteSettings(name: ProjectScreen.routeName),
      builder: (_) => const Scaffold(body: Text('project'))));
    nav.currentState!.push(MaterialPageRoute<void>(builder: (_) => const Scaffold(body: Text('report'))));
    nav.currentState!.push(MaterialPageRoute<void>(builder: (_) => ReviewSummaryScreen(report: summaryReport())));
    await tester.pumpAndSettle();
    expect(find.text('Alle Befunde geprüft'), findsOneWidget);
    expect(find.text('Zurück zum Projekt'), findsOneWidget);
    await tester.tap(find.text('Zurück zum Projekt'));
    await tester.pumpAndSettle();
    expect(find.text('project'), findsOneWidget);
  });
}
