import 'package:changelens/api.dart';
import 'package:changelens/screens/report_screen.dart';
import 'package:changelens/screens/report_widgets.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'report_test.dart' as fixture;

void main() {
  test('topic DTO supports canonical backend values and legacy category mapping', () {
    for (final (category, topic) in [
      ('date_deadline', 'deadlines'), ('deliverable', 'deliverables'), ('quantity', 'deliverables'),
      ('responsibility_owner', 'responsibilities'), ('approval', 'approval_wording'),
      ('approval_wording', 'approval_wording'), ('budget', 'budget'), ('structure', 'other'),
    ]) {
      expect(Finding(fixture.finding('f', 'changed', category, 'prioritised', [])).topic, topic);
    }
    final report = Report({'status': 'complete', 'findings': [
      fixture.finding('f', 'changed', 'budget', 'prioritised', []),
    ], 'topic_counts': {'budget': 7}});
    expect(report.topicCounts['budget'], 7); // consume server's revision-aware counts
    expect(report.topicCounts['deadlines'], 0);
    expect(report.topicCounts.keys, findingTopics);
  });

  testWidgets('filter keeps uncertain findings in their own group and all differences reachable', (tester) async {
    await fixture.pump(tester, ReportScreen(comparisonId: 'c1', versions: fixture.versions));
    expect(find.byKey(const ValueKey('topic-deliverables')), findsOneWidget);
    await tester.tap(find.byKey(const ValueKey('topic-deliverables')));
    await tester.pumpAndSettle();
    final tiles = tester.widgetList<FindingTile>(find.byType(FindingTile)).toList();
    expect(tiles.map((tile) => tile.finding.id), ['f1', 'f2']);
    expect(find.text('Needs your review'), findsOneWidget);
    expect(tester.getTopLeft(find.text('Needs your review')).dy,
      lessThan(tester.getTopLeft(find.textContaining('Hosting is provided')).dy));
    await tester.tap(find.textContaining('Selected summary'));
    await tester.pumpAndSettle();
    expect(tester.widget<ChoiceChip>(find.byKey(const ValueKey('topic-deliverables'))).selected, true);
    expect(tester.widgetList<FindingTile>(find.byType(FindingTile)).map((tile) => tile.finding.id), ['f1', 'f2', 'f3']);
    expect(find.text('Other findings'), findsOneWidget);
  });

  testWidgets('different topic filter hides findings without hiding unmapped source differences', (tester) async {
    final report = Report({'status': 'complete', 'findings': [
      fixture.finding('budget', 'changed', 'budget', 'prioritised', []),
      fixture.finding('date', 'uncertain', 'date_deadline', 'needs_review', []),
    ], 'unexplained_differences': [fixture.ev('later', 'Unmapped text', 0)]});
    await fixture.pump(tester, AllDifferencesScreen(report: report, versions: fixture.versions, onOpen: (_) async {}));
    await tester.ensureVisible(find.byKey(const ValueKey('topic-budget')));
    await tester.pumpAndSettle();
    await tester.tap(find.byKey(const ValueKey('topic-budget')));
    await tester.pumpAndSettle();
    expect(tester.widgetList<FindingTile>(find.byType(FindingTile)).map((tile) => tile.finding.id), ['budget']);
    expect(find.text('Needs your review'), findsNothing);
    expect(find.textContaining('Other text differences (1)'), findsOneWidget);
    await tester.ensureVisible(find.text('All topics'));
    await tester.pumpAndSettle();
    await tester.tap(find.text('All topics'));
    await tester.pumpAndSettle();
    expect(find.text('Needs your review'), findsOneWidget);
  });
}
