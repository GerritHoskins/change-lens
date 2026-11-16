// WP-D P6 timeline: order comes only from the comparisons the user ran (AC-14), never from list
// order, upload time or labels. Forks are not ranked; versions in no comparison stay apart.
import 'package:changelens/api.dart';
import 'package:changelens/design/calm_theme.dart';
import 'package:changelens/l10n/app_localizations.dart';
import 'package:changelens/screens/project_timeline.dart';
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

Version v(String id, {String? label, String kind = 'pdf', String status = 'parsed'}) =>
    Version({'id': id, 'label': label ?? id, 'kind': kind, 'status': status});

Comparison c(String id, String earlier, String later, {String scope = 'complete', String status = 'complete'}) =>
    Comparison({'id': id, 'earlier_id': earlier, 'later_id': later, 'scope': scope, 'status': status});

List<List<String>> groups(Timeline t, [int component = 0]) =>
    [for (final g in t.components[component]) [for (final e in g.entries) e.version.id]];

void main() {
  group('buildTimeline', () {
    test('a chain is newest first, whatever order the server lists versions in', () {
      final t = buildTimeline([v('b'), v('d'), v('a'), v('c')],
          [c('1', 'a', 'b'), c('2', 'b', 'c'), c('3', 'c', 'd')]);
      expect(groups(t), [['d'], ['c'], ['b'], ['a']]);
      expect(t.components[0].first.entries.single.links.single.id, '3');
      expect(t.unplaced, isEmpty);
    });

    test('a label or list position never places a version', () {
      // "v9" was compared as the earlier side: it sits below "v1".
      final t = buildTimeline([v('x', label: 'Brief v9'), v('y', label: 'Brief v1')], [c('1', 'x', 'y')]);
      expect(groups(t), [['y'], ['x']]);
    });

    test('two newer versions of the same earlier one are a fork, in label order, not ranked', () {
      final t = buildTimeline([v('a'), v('client', label: 'v3 client'), v('agency', label: 'v3 agency')],
          [c('1', 'a', 'client'), c('2', 'a', 'agency')]);
      expect(groups(t), [['agency', 'client'], ['a']]);
      expect(t.components[0].first.fork, isTrue);
    });

    test('versions in no comparison are unplaced; separate chains are separate components', () {
      final t = buildTimeline([v('a'), v('b'), v('x'), v('y'), v('lonely')],
          [c('1', 'x', 'y'), c('2', 'a', 'b')]);
      expect(t.components, hasLength(2));
      expect(groups(t, 0), [['y'], ['x']]);
      expect(groups(t, 1), [['b'], ['a']]);
      expect([for (final u in t.unplaced) u.id], ['lonely']);
    });

    test('both directions: finite, both links kept and flagged', () {
      final t = buildTimeline([v('a'), v('b')], [c('1', 'a', 'b'), c('2', 'b', 'a')]);
      final entries = [for (final g in t.components.single) ...g.entries];
      expect(entries, hasLength(2));
      expect(entries.every((e) => e.bothWays), isTrue);
      expect([for (final e in entries) ...e.links].map((l) => l.id).toSet(), {'1', '2'});
    });

    test('a comparison naming an unknown version is kept, not dropped', () {
      final t = buildTimeline([v('a')], [c('1', 'gone', 'a')]);
      expect(t.components, isEmpty);
      expect(t.unattached.single.id, '1');
      expect(t.unplaced.single.id, 'a');
    });

    test('nothing at all is empty', () => expect(buildTimeline([], []).isEmpty, isTrue));
  });

  group('ProjectTimeline', () {
    Future<List<Version>> pump(WidgetTester tester, List<Version> versions, List<Comparison> comparisons,
        {Locale locale = const Locale('en')}) async {
      final opened = <Version>[];
      await tester.pumpWidget(MaterialApp(locale: locale, theme: calmTheme(Brightness.light),
        localizationsDelegates: AppLocalizations.localizationsDelegates,
        supportedLocales: AppLocalizations.supportedLocales,
        home: Scaffold(body: ListView(padding: const EdgeInsets.all(20), children: [
          ProjectTimeline(versions: versions, comparisons: comparisons, loading: false, onCompareFrom: opened.add),
        ]))));
      await tester.pumpAndSettle();
      return opened;
    }

    testWidgets('links read earlier → newer with scope and status; newest version on top', (tester) async {
      await pump(tester, [v('a', label: 'Brief v1'), v('b', label: 'Brief v2', kind: 'text')],
          [c('1', 'a', 'b', scope: 'partial', status: 'failed')]);
      // The arrow is a drawn icon (a placeholder in the text), not a font glyph.
      expect(find.text('Brief v1 ￼ Brief v2', findRichText: true), findsOneWidget);
      expect(find.text('Partial update'), findsOneWidget);
      expect(find.text('Failed'), findsOneWidget);
      // A failure without a known cause still says what to do next.
      expect(find.textContaining('Start a new comparison'), findsOneWidget);
      expect(find.text('Pasted text · Ready'), findsOneWidget);
      expect(tester.getTopLeft(find.byKey(const Key('version-b'))).dy,
          lessThan(tester.getTopLeft(find.byKey(const Key('version-a'))).dy));
      expect(find.bySemanticsLabel(RegExp(r'^Comparison of Brief v1 with the newer Brief v2')), findsOneWidget);
    });

    testWidgets('a version says it opens Compare from it, and does', (tester) async {
      final opened = await pump(tester, [v('a', label: 'Brief v1')], []);
      expect(find.text('Not compared yet'), findsOneWidget);
      expect(find.descendant(of: find.byKey(const Key('version-a')), matching: find.text('Compare from here')),
          findsOneWidget);
      await tester.tap(find.byKey(const Key('version-a')));
      expect(opened.single.id, 'a');
    });

    testWidgets('a rejected version gives its reason and offers no comparison', (tester) async {
      final opened = await pump(tester, [
        Version({'id': 'r', 'label': 'Scan', 'kind': 'pdf', 'status': 'rejected', 'reject_reason': 'no_text_layer'}),
        Version({'id': 'n', 'label': 'Old', 'kind': 'pdf', 'status': 'rejected'}),
      ], []);
      expect(find.textContaining('Rejected: the PDF has no selectable text'), findsOneWidget);
      expect(find.textContaining('Rejected: the document could not be processed'), findsOneWidget);
      expect(find.text('Compare from here'), findsNothing);
      await tester.tap(find.byKey(const Key('version-r')));
      expect(opened, isEmpty);
    });

    testWidgets('a failed card names the rejected input', (tester) async {
      await pump(tester, [v('a', label: 'Brief v1'), v('b', label: 'Scan', status: 'rejected')], [
        Comparison({'id': '1', 'earlier_id': 'a', 'later_id': 'b', 'scope': 'complete', 'status': 'failed',
          'warnings': [{'code': 'version_rejected', 'version_id': 'b', 'reason': 'no_text_layer'}]}),
      ]);
      expect(find.textContaining('“Scan” could not be read'), findsOneWidget);
    });

    testWidgets('a fork sits inside one block whose rail joins the version below', (tester) async {
      await pump(tester, [v('a'), v('b'), v('c')], [c('1', 'a', 'b'), c('2', 'a', 'c')]);
      final note = tester.getTopLeft(find.textContaining('neither is shown as newer')).dy;
      // The note introduces the fork, above both members, instead of cutting the rail below them.
      expect(note, lessThan(tester.getTopLeft(find.byKey(const Key('version-b'))).dy));
      expect(note, lessThan(tester.getTopLeft(find.byKey(const Key('version-c'))).dy));
    });

    testWidgets('a fork says neither is newer; both directions say the order is open', (tester) async {
      await pump(tester, [v('a'), v('b'), v('c')], [c('1', 'a', 'b'), c('2', 'a', 'c')]);
      expect(find.textContaining('neither is shown as newer'), findsOneWidget);
      await pump(tester, [v('a'), v('b')], [c('1', 'a', 'b'), c('2', 'b', 'a')]);
      expect(find.textContaining('in both directions'), findsOneWidget);
    });

    testWidgets('German at 2× text on 320 px: card copy wraps between words, never inside one', (tester) async {
      // Real metrics: the default test font's square glyphs are far wider than Roboto.
      await tester.runAsync(() async {
        final roboto = FontLoader('Roboto');
        for (final w in ['Regular', 'SemiBold', 'Bold']) {
          roboto.addFont(rootBundle.load('assets/fonts/Roboto-$w.ttf'));
        }
        await roboto.load();
      });
      tester.view.physicalSize = const Size(320, 2400);
      tester.view.devicePixelRatio = 1;
      tester.platformDispatcher.textScaleFactorTestValue = 2;
      addTearDown(tester.view.reset);
      addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
      await pump(tester, [v('a'), v('b'), v('c'), v('d')], [
        c('1', 'a', 'b'), c('2', 'b', 'c', scope: 'partial', status: 'running'),
        c('3', 'b', 'd', status: 'failed'), c('4', 'a', 'd', scope: 'unknown', status: 'partial'),
      ], locale: const Locale('de'));
      for (final p in tester.renderObjectList<RenderParagraph>(find.descendant(
          of: find.byWidgetPredicate((w) => w.key is ValueKey<String> &&
              (w.key! as ValueKey<String>).value.startsWith('link-')), matching: find.byType(RichText)))) {
        final s = p.text.toPlainText();
        if (s.contains('￼')) continue; // the pair line holds user-chosen names
        for (final word in RegExp(r'\S+').allMatches(s)) {
          final tops = {for (final box in p.getBoxesForSelection(
              TextSelection(baseOffset: word.start, extentOffset: word.end))) box.top.round()};
          expect(tops, hasLength(1), reason: '"${word[0]}" in "$s" breaks inside the word');
        }
      }
    });

    testWidgets('empty, in German', (tester) async {
      await pump(tester, [], [], locale: const Locale('de'));
      expect(find.byKey(const Key('history-empty')), findsOneWidget);
      expect(find.text('Noch keine Versionen'), findsOneWidget);
    });
  });
}
