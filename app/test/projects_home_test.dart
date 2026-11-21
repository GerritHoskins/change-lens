// Projects home (Calm Bold "A+B · Home"): hero, tiles and rows are built from the server's
// `latest_comparison` summary only. Set CALM_CAPTURE_DIR to write PNG renders for comparison with the artboard.
import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;

import 'package:changelens/api.dart';
import 'package:changelens/design/calm_theme.dart';
import 'package:changelens/main.dart';
import 'package:changelens/screens/project_screen.dart';
import 'package:changelens/screens/projects_home.dart';
import 'package:changelens/screens/projects_screen.dart';
import 'package:changelens/screens/report_screen.dart';
import 'package:changelens/services.dart';
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'fixtures/calm_scenario.dart';

const captureDirectory = String.fromEnvironment('CALM_CAPTURE_DIR');

Map<String, dynamic> latest(String id, String status, {String earlier = 'v1', String later = 'v2', int? findings,
    int? needsReview, int? reviewed, Map<String, int>? topics, String at = '2026-11-20T10:00:00Z'}) => {
  'id': id, 'status': status, 'earlier_label': earlier, 'later_label': later, 'created_at': at,
  'findings': findings, 'needs_review': needsReview, 'reviewed': reviewed,
  'topic_counts': findings == null ? null : {for (final t in findingTopics) t: topics?[t] ?? 0},
};

Map<String, dynamic> project(String id, String name, [Map<String, dynamic>? latestComparison]) =>
    {'id': id, 'name': name, 'client_label': null, 'comparison_counts': <String, int>{},
      'latest_comparison': latestComparison};

/// The artboard's four projects, as the server would send them.
List<Map<String, dynamic>> artboard() => [
  project('fair', 'Trade fair stand', latest('c4', 'complete', findings: 4, needsReview: 0, reviewed: 4,
    topics: {'budget': 4})),
  project('annual', 'Annual report layout', latest('c3', 'waiting_for_versions', earlier: 'v2', later: 'v3')),
  project('web', 'Website relaunch', latest('c2', 'partial', findings: 5, needsReview: 1, reviewed: 2,
    topics: {'deliverables': 5}, at: '2026-11-19T10:00:00Z')),
  project('spring', 'Spring campaign 2027', latest('c1', 'complete', findings: 6, needsReview: 2, reviewed: 0,
    topics: {'deadlines': 1, 'deliverables': 2, 'budget': 2, 'other': 1}, at: '2026-11-21T08:00:00Z')),
];

Future<List<http.Request>> pumpHome(WidgetTester tester, List<Map<String, dynamic>> projects,
    {String locale = 'en', ThemeMode theme = ThemeMode.light, GlobalKey? boundary}) async {
  final requests = <http.Request>[];
  final services = Services(CedarSettings(), CedarPicker(), apiFactory: (base, token) =>
    Api(base, token, client: MockClient((r) async {
      requests.add(r);
      if (r.url.path == '/projects') {
        return http.Response(jsonEncode({'projects': projects}), 200,
          headers: {'content-type': 'application/json; charset=utf-8'});
      }
      return http.Response('{"code":"not_found"}', 404);
    })));
  await services.load();
  await tester.pumpWidget(RepaintBoundary(key: boundary, child: ChangeLensApp(services: services,
    locale: Locale(locale), themeMode: theme, home: const ProjectsScreen())));
  await tester.pumpAndSettle();
  return requests;
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUpAll(() async {
    final roboto = FontLoader('Roboto');
    for (final weight in ['Regular', 'SemiBold', 'Bold']) {
      roboto.addFont(rootBundle.load('assets/fonts/Roboto-$weight.ttf'));
    }
    await roboto.load();
    await (FontLoader('packages/lucide_icons_flutter/Lucide500')..addFont(rootBundle.load(
      'packages/lucide_icons_flutter/assets/build_font/LucideVariable-w500.ttf'))).load();
  });

  test('The summary keeps null counts apart from zero', () {
    final running = Project(project('p', 'P', latest('c', 'running')));
    expect(running.latest!.hasReport, isFalse);
    expect(running.changed, isFalse);
    final empty = Project(project('p', 'P', latest('c', 'complete', findings: 0, needsReview: 0, reviewed: 0)));
    expect(empty.latest!.hasReport, isTrue);
    expect(empty.changed, isFalse);
    expect(Project({'id': 'p', 'name': 'P'}).latest, isNull); // an older server sends no summary
    expect(Project(project('p', 'P', latest('c', 'complete', findings: 3, needsReview: 1, reviewed: 1)))
      .latest!.toCheck, 2);
  });

  test('The hero is the changed project compared most recently; tiles come as a pair', () {
    final home = HomeLayout(artboard().map(Project.new).toList());
    expect(home.changed, 2);
    expect(home.hero!.id, 'spring');
    expect([for (final p in home.tiles) p.id], ['web', 'annual']);
    expect([for (final p in home.rows) p.id], ['fair']);
    // One candidate only: no lone tile, it becomes a row.
    final single = HomeLayout(artboard().where((p) => p['id'] != 'annual').map(Project.new).toList());
    expect(single.tiles, isEmpty);
    expect([for (final p in single.rows) p.id], ['fair', 'web']);
    // Nothing changed: no hero, and the headline count is 0.
    final quiet = HomeLayout([Project(artboard().first)]);
    expect((quiet.hero, quiet.changed, quiet.rows.length), (null, 0, 1));
  });

  for (final theme in [ThemeMode.light, ThemeMode.dark]) {
    testWidgets('Home shows the server counts as hero, tiles and rows (${theme.name})', (tester) async {
      tester.view.physicalSize = const Size(390, 844);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      final boundary = GlobalKey();
      await pumpHome(tester, artboard(), theme: theme, boundary: boundary);
      expect(tester.takeException(), isNull);
      expect(find.text('2 briefs changed.'), findsOneWidget);
      expect(find.text("Let's see what moved."), findsOneWidget);

      final hero = find.byKey(const Key('home-hero-spring'));
      Finder inHero(String text) => find.descendant(of: hero, matching: find.text(text));
      for (final text in ['Spring campaign 2027', '6', 'things moved', '1 deadline', '2 deliverables',
          '+3', '2 need a second look']) {
        expect(inHero(text), findsOneWidget, reason: text);
      }
      // The arrow is a drawn icon (a placeholder in the text), not a font glyph the bundled Roboto lacks.
      expect(find.descendant(of: hero, matching: find.text('v1 ￼ v2', findRichText: true)), findsOneWidget);
      // Marker means "new" and stays marker in both themes; the hero is the only marker block.
      final block = tester.widget<Material>(find.descendant(of: hero, matching: find.byType(Material)).first);
      expect(block.color, const Color(0xffdfff4f));
      expect((block.shape! as RoundedRectangleBorder).borderRadius, BorderRadius.circular(CalmRadius.xl));
      // `review` only inside its dashed border.
      expect(find.descendant(of: find.byType(HomeReviewPill), matching: find.byType(CustomPaint)), findsWidgets);
      expect(tester.widget<Text>(inHero('6')).style!.fontSize, 64);

      final web = find.byKey(const Key('home-tile-web'));
      expect(find.descendant(of: web, matching: find.text('3')), findsOneWidget);
      expect(find.descendant(of: web, matching: find.text('to check')), findsOneWidget);
      expect(find.descendant(of: find.byKey(const Key('home-tile-annual')), matching: find.text('Reading v3…')),
        findsOneWidget);
      expect(tester.getSize(web).height, tester.getSize(find.byKey(const Key('home-tile-annual'))).height);
      expect(tester.getSize(web).height, greaterThanOrEqualTo(148));
      expect(find.descendant(of: find.byKey(const Key('home-row-fair')), matching: find.text('All checked')),
        findsOneWidget);
      expect(tester.getSize(find.byKey(const Key('home-row-fair'))).height, greaterThanOrEqualTo(56));
      expect(find.byKey(const Key('compare-briefs')), findsOneWidget);
      expect(find.byKey(const Key('new-project')), findsOneWidget);

      if (captureDirectory.isNotEmpty) {
        await tester.runAsync(() async {
          final image = await (boundary.currentContext!.findRenderObject()! as RenderRepaintBoundary).toImage(pixelRatio: 2);
          final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
          await Directory(captureDirectory).create(recursive: true);
          await File('$captureDirectory/home-${theme.name}.png').writeAsBytes(bytes!.buffer.asUint8List());
          image.dispose();
        });
      }
    });
  }

  testWidgets('Each block is one button that says everything it shows', (tester) async {
    final handle = tester.ensureSemantics();
    tester.view.physicalSize = const Size(390, 1200); // every block built, none below the fold
    tester.view.devicePixelRatio = 1;
    addTearDown(tester.view.reset);
    await pumpHome(tester, artboard());
    expect(find.bySemanticsLabel('Spring campaign 2027, v1 compared with the newer v2, 6 things moved, 1 deadline, '
      '2 deliverables, 2 budget, 1 other, 2 need a second look, 6 to check, Open the report'), findsOneWidget);
    expect(tester.getSemantics(find.byKey(const Key('home-hero-spring'))),
      matchesSemantics(isButton: true, hasTapAction: true, label: 'Spring campaign 2027, v1 compared with the newer v2, '
        '6 things moved, 1 deadline, 2 deliverables, 2 budget, 1 other, 2 need a second look, 6 to check, Open the report'));
    expect(find.bySemanticsLabel('Website relaunch, 3 to check'), findsOneWidget);
    expect(find.bySemanticsLabel('Annual report layout, Reading v3…'), findsOneWidget);
    expect(find.bySemanticsLabel('Trade fair stand, All checked'), findsOneWidget);
    handle.dispose();
  });

  testWidgets('The hero opens the report on top of its project; a tile opens the project', (tester) async {
    final requests = await pumpHome(tester, artboard());
    await tester.tap(find.byKey(const Key('home-hero-spring')));
    await tester.pump();
    await tester.pump(const Duration(seconds: 1));
    expect(find.byType(ReportScreen), findsOneWidget);
    expect([for (final r in requests) r.url.path], contains('/comparisons/c1/opened'));
    final navigator = tester.state<NavigatorState>(find.byType(Navigator));
    navigator.pop();
    await tester.pump();
    await tester.pump(const Duration(seconds: 1));
    expect(find.byType(ReportScreen), findsNothing);
    expect(find.byType(ProjectScreen), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
  });

  testWidgets('States without a report are words, never a count', (tester) async {
    await pumpHome(tester, [
      project('a', 'Never compared'),
      project('b', 'Queued', latest('c', 'queued')),
      project('d', 'Broken', latest('e', 'failed')),
      project('f', 'Nothing moved', latest('g', 'complete', findings: 0, needsReview: 0, reviewed: 0)),
    ]);
    expect(find.text('Nothing new to check.'), findsOneWidget);
    expect(find.byType(HomeHero), findsNothing);
    expect(find.byType(HomeTile), findsNothing); // one project in progress: no lone tile
    for (final text in ['No comparison yet', 'Comparing…', 'Comparison failed', 'Nothing moved']) {
      expect(find.descendant(of: find.byType(HomeRow), matching: find.text(text)), findsWidgets, reason: text);
    }
    final failed = tester.widget<Text>(find.text('Comparison failed'));
    expect(failed.style!.color, CalmColors.light.dark ? isNull : const Color(0xffc4320a));
    expect(find.textContaining('0 to check'), findsNothing);
  });

  testWidgets('German at 2× text on a small phone: rows instead of tiles, nothing overflows', (tester) async {
    tester.view.physicalSize = const Size(320, 568);
    tester.view.devicePixelRatio = 1;
    tester.platformDispatcher.textScaleFactorTestValue = 2;
    addTearDown(tester.view.reset);
    addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
    await pumpHome(tester, artboard(), locale: 'de', theme: ThemeMode.dark);
    expect(tester.takeException(), isNull);
    expect(find.text('2 Briefings geändert.'), findsOneWidget);
    expect(find.byType(HomeTile), findsNothing);
    final position = tester.state<ScrollableState>(find.byWidgetPredicate((w) =>
      w is Scrollable && w.axisDirection == AxisDirection.down).first).position;
    // The list builds what is near the viewport, so the texts are collected while scrolling.
    final wanted = {'2 brauchen einen zweiten Blick', '3 zu prüfen', 'v3 wird gelesen …', 'Alles geprüft'};
    final seen = <String>{};
    for (var step = 0; step < 40; step++) {
      seen.addAll(wanted.where((text) => find.text(text).evaluate().isNotEmpty));
      if (position.pixels >= position.maxScrollExtent) break;
      position.jumpTo((position.pixels + 280).clamp(0, position.maxScrollExtent));
      await tester.pump();
      expect(tester.takeException(), isNull);
    }
    expect(seen, wanted);
  });
}
