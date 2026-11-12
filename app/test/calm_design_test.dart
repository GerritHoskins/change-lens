import 'dart:convert';
import 'dart:io';
import 'dart:ui' as ui;

import 'package:changelens/design/calm_controls.dart';
import 'package:changelens/api.dart';
import 'package:changelens/design/calm_widgets.dart';
import 'package:changelens/main.dart';
import 'package:changelens/screens/compare_screen.dart';
import 'package:changelens/screens/evidence_resolution.dart';
import 'package:changelens/screens/finding_screen.dart';
import 'package:changelens/screens/projects_screen.dart';
import 'package:changelens/screens/report_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fixtures/calm_scenario.dart';

const captureDirectory = String.fromEnvironment('CALM_CAPTURE_DIR');

Future<void> capture(WidgetTester tester, GlobalKey key, String name) async {
  if (captureDirectory.isEmpty) return;
  await tester.runAsync(() async {
    final image = await (key.currentContext!.findRenderObject()! as RenderRepaintBoundary).toImage();
    final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
    await Directory(captureDirectory).create(recursive: true);
    await File('$captureDirectory/$name.png').writeAsBytes(bytes!.buffer.asUint8List());
    image.dispose();
  });
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUpAll(() async {
    final loader = FontLoader('Roboto');
    for (final weight in ['Regular', 'SemiBold', 'Bold']) {
      loader.addFont(rootBundle.load('assets/fonts/Roboto-$weight.ttf'));
    }
    await loader.load();
    final icons = FontLoader('MaterialIcons')..addFont(rootBundle.load('fonts/MaterialIcons-Regular.otf'));
    await icons.load();
  });

  for (final size in [const Size(320, 568), const Size(390, 844)]) {
    for (final locale in ['en', 'de']) {
      for (final scale in [1.0, 2.0]) {
        for (final theme in [ThemeMode.light, ThemeMode.dark]) {
          final name = '${size.width.toInt()}-$locale-${scale.toInt()}x-${theme.name}';
          testWidgets('Core screens remain scrollable and usable: $name', (tester) async {
            tester.view.physicalSize = size;
            tester.view.devicePixelRatio = 1;
            tester.platformDispatcher.textScaleFactorTestValue = scale;
            addTearDown(tester.view.reset);
            addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
            final scenario = CedarScenario();
            final services = await scenario.services();
            final versions = cedarVersions.map(Version.new).toList();
            final screens = <String, Widget>{
              'projects': const ProjectsScreen(),
              'compare': CompareScreen(project: Project(cedarProject), versions: versions),
              'report': ReportScreen(comparisonId: 'cedar-comparison', versions: versions),
              'finding': FindingScreen(comparisonId: 'cedar-comparison', findingId: 'budget',
                report: scenario.report, versions: versions,
                resolve: (_, _, _) async => const EvidencePresentation('text_fallback')),
            };
            for (final entry in screens.entries) {
              final boundary = GlobalKey();
              await tester.pumpWidget(RepaintBoundary(key: boundary, child: ChangeLensApp(
                services: services, locale: Locale(locale), themeMode: theme, home: entry.value)));
              await tester.pumpAndSettle();
              expect(tester.takeException(), isNull, reason: '${entry.key} initial viewport');
              if (scale == 1 && locale == 'en' && size.width == 390 ||
                  entry.key == 'finding' && locale == 'de' && scale == 2 && size.width == 320) {
                await capture(tester, boundary, '${entry.key}-$name');
              }
              if (entry.key == 'finding') {
                final warning = find.byKey(const Key('review-fallback'));
                final confirm = find.byKey(const Key('review-confirm'));
                await tester.ensureVisible(confirm);
                await tester.pumpAndSettle();
                expect(confirm.hitTestable(), findsOneWidget);
                expect(tester.getBottomLeft(warning).dy, lessThan(tester.getTopLeft(confirm).dy));
                expect(tester.widget<FilledButton>(confirm).onPressed, isNotNull);
              }
              // Check content beyond the initial viewport as well as its first paint.
              final scroll = find.descendant(of: find.byType(ListView), matching:
                find.byWidgetPredicate((widget) => widget is Scrollable && widget.axisDirection == AxisDirection.down));
              if (scroll.evaluate().isNotEmpty) {
                final position = tester.state<ScrollableState>(scroll.first).position;
                for (var step = 0; step < 12 && position.pixels < position.maxScrollExtent; step++) {
                  position.jumpTo((position.pixels + size.height / 2).clamp(0, position.maxScrollExtent));
                  await tester.pump();
                  expect(tester.takeException(), isNull, reason: '${entry.key} scrolled viewport');
                }
              } else {
                await tester.ensureVisible(find.byKey(const Key('start')));
                await tester.pumpAndSettle();
                expect(tester.takeException(), isNull);
              }
            }
          });
        }
      }
    }
  }

  testWidgets('Reduced motion is immediate; privacy cover follows lifecycle', (tester) async {
    final semantics = tester.ensureSemantics();
    tester.platformDispatcher.accessibilityFeaturesTestValue = const FakeAccessibilityFeatures(disableAnimations: true);
    addTearDown(tester.platformDispatcher.clearAccessibilityFeaturesTestValue);
    await tester.pumpWidget(ChangeLensApp(services: await CedarScenario().services(), home: const Scaffold(
      body: CalmArrival(child: CalmReviewMark(text: 'Confirmed by you', active: true, animate: true)))));
    await tester.pumpAndSettle();
    for (final tween in tester.widgetList<TweenAnimationBuilder<double>>(find.byType(TweenAnimationBuilder<double>))) {
      expect(tween.duration, Duration.zero);
    }
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
    await tester.pump();
    expect(find.text('ChangeLens'), findsOneWidget);
    expect(tester.getSemantics(find.byType(PrivacyCover)).toStringDeep(), isNot(contains('Confirmed by you')));
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await tester.pump();
    expect(find.text('ChangeLens'), findsNothing);
    semantics.dispose();
  });

  testWidgets('German correction sheet remains operable with large text and keyboard', (tester) async {
    tester.view.physicalSize = const Size(320, 568);
    tester.view.devicePixelRatio = 1;
    tester.platformDispatcher.textScaleFactorTestValue = 2;
    addTearDown(tester.view.reset);
    addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
    await tester.pumpWidget(ChangeLensApp(services: await CedarScenario().services(), locale: const Locale('de'),
      home: Scaffold(body: Builder(builder: (context) => TextButton(onPressed: () => showCalmSheet<void>(
        context, builder: (_) => CorrectionSheet(finding: CedarScenario().report.findings.first)),
        child: const Text('Open'))))));
    await tester.tap(find.text('Open'));
    await tester.pumpAndSettle();
    tester.view.viewInsets = const FakeViewPadding(bottom: 230);
    await tester.pumpAndSettle();
    expect(find.text('Speichern').hitTestable(), findsOneWidget);
    expect(find.text('Abbrechen').hitTestable(), findsOneWidget);
    await tester.ensureVisible(find.byKey(const Key('category-field')));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
  }, variant: TargetPlatformVariant.only(TargetPlatform.iOS));

  testWidgets('Bundled Roboto declares all three real weights', (tester) async {
    final manifest = jsonDecode(await rootBundle.loadString('FontManifest.json')) as List;
    final roboto = manifest.singleWhere((entry) => entry['family'] == 'Roboto');
    expect((roboto['fonts'] as List).map((font) => font['weight']), [400, 600, 700]);
    expect(await rootBundle.loadString('assets/fonts/OFL.txt'), contains('SIL OPEN FONT LICENSE'));
  });
}
