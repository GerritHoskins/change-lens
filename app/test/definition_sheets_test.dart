// O-24 phase A: the four in-context definition sheets (docs/onboarding-implementation-handoff.md
// §3, §6). Widget tests only; not device evidence.
import 'package:changelens/api.dart';
import 'package:changelens/design/calm_controls.dart';
import 'package:changelens/design/calm_widgets.dart';
import 'package:changelens/l10n/app_localizations.dart';
import 'package:changelens/main.dart';
import 'package:changelens/screens/compare_screen.dart';
import 'package:changelens/screens/definition_sheets.dart';
import 'package:changelens/screens/evidence_resolution.dart';
import 'package:changelens/screens/finding_screen.dart';
import 'package:changelens/screens/report_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fixtures/calm_scenario.dart';

final platforms = TargetPlatformVariant(const {TargetPlatform.android, TargetPlatform.iOS});
final en = lookupAppLocalizations(const Locale('en'));
final versions = cedarVersions.map(Version.new).toList();

Future<void> pumpScreen(WidgetTester tester, Widget home, {String locale = 'en',
    ThemeMode theme = ThemeMode.light}) async {
  final services = await CedarScenario().services();
  await tester.pumpWidget(const SizedBox());
  await tester.pumpWidget(ChangeLensApp(services: services, locale: Locale(locale), themeMode: theme, home: home));
  await tester.pumpAndSettle();
}

Future<void> openInfo(WidgetTester tester, Key key) async {
  await tester.ensureVisible(find.byKey(key));
  await tester.pumpAndSettle();
  await tester.tap(find.byKey(key));
  await tester.pumpAndSettle();
}

Future<void> close(WidgetTester tester, AppLocalizations l) async {
  final button = find.descendant(of: find.byType(CalmSheet), matching: find.widgetWithText(TextButton, l.close));
  expect(button.hitTestable(), findsOneWidget);
  await tester.tap(button);
  await tester.pumpAndSettle();
  expect(find.byType(CalmSheet), findsNothing);
}

/// Row titles and explanations, in order, exactly as the sheet shows them.
List<String> rows(WidgetTester tester) => [
  for (final row in tester.widgetList<DefinitionRow>(find.byType(DefinitionRow))) row.title,
  for (final row in tester.widgetList<DefinitionRow>(find.byType(DefinitionRow))) ...row.details,
];

Widget finding() => FindingScreen(comparisonId: 'cedar-comparison', findingId: 'deadline',
  report: CedarScenario().report, versions: versions,
  resolve: (_, _, _) async => const EvidencePresentation('pdf_highlight'));

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUpAll(() async {
    final loader = FontLoader('Roboto');
    for (final weight in ['Regular', 'SemiBold', 'Bold']) {
      loader.addFont(rootBundle.load('assets/fonts/Roboto-$weight.ttf'));
    }
    await loader.load();
  });

  testWidgets('Scope: opens from the scope question, repeats the screen labels, Close dismisses', (tester) async {
    final handle = tester.ensureSemantics();
    await pumpScreen(tester, CompareScreen(project: Project(cedarProject), versions: versions));
    expect(find.bySemanticsLabel(en.defInfo(en.scopeQuestion)), findsOneWidget);
    await openInfo(tester, const Key('info-scope'));
    expect(find.descendant(of: find.byType(CalmSheet), matching: find.text(en.scopeQuestion)), findsOneWidget);
    expect(rows(tester), [en.scopeComplete, en.scopePartial, en.scopeUnknown, en.scopeCompleteHint, en.defScopeComplete, en.scopePartialHint, en.defScopePartial, en.scopeUnknownHint, en.defScopeUnknown]);
    expect(find.widgetWithText(FilledButton, en.showAllDifferences), findsNothing, reason: 'no main action');
    await close(tester, en);
    handle.dispose();
  });

  testWidgets('Change types: six rows, the disc only on Uncertain, no other marks', (tester) async {
    await pumpScreen(tester, finding());
    await openInfo(tester, const Key('info-change-types'));
    expect(find.descendant(of: find.byType(CalmSheet), matching: find.text(en.defChangeTypesTitle)), findsOneWidget);
    expect(rows(tester), [en.typeAdded, en.typeChanged, en.typeRemoved, en.typeNotAddressed, en.typeUncertain, en.typeEquivalent, en.defAdded, en.defChanged, en.defRemoved, en.defNotAddressed, en.defUncertain, en.defReworded]);
    final sheet = find.byType(ChangeTypeDefinitionSheet);
    final disc = find.descendant(of: sheet, matching: find.byType(CalmReviewDisc));
    expect(disc, findsOneWidget);
    expect(tester.widget<DefinitionRow>(find.ancestor(of: disc, matching: find.byType(DefinitionRow))).title,
      en.typeUncertain);
    expect(find.descendant(of: sheet, matching: find.byType(Icon)), findsNothing);
    await close(tester, en);
  });

  testWidgets('Evidence: opens beside the evidence label, three modes with decorative previews', (tester) async {
    final handle = tester.ensureSemantics();
    await pumpScreen(tester, finding());
    expect(find.text(en.evidenceModePdf), findsNWidgets(2));
    await openInfo(tester, const ValueKey('info-evidence-earlier'));
    expect(find.descendant(of: find.byType(CalmSheet), matching: find.text(en.defEvidenceTitle)), findsOneWidget);
    expect(rows(tester), [en.evidenceModePdf, en.evidenceModeFallback, en.evidenceModeText, en.defModePdf, en.defModeFallback, en.defModeText]);
    // Previews are drawn but never announced.
    final sheet = find.byType(EvidenceDefinitionSheet);
    expect(find.descendant(of: sheet, matching: find.text(sampleQuoteForTest, findRichText: true)),
      findsNWidgets(3));
    expect(find.descendant(of: sheet,
      matching: find.bySemanticsLabel(RegExp(RegExp.escape(sampleQuoteForTest)))), findsNothing);
    await close(tester, en);
    handle.dispose();
  });

  testWidgets('Selected summary: the main pill reaches All differences', (tester) async {
    await pumpScreen(tester, ReportScreen(comparisonId: 'cedar-comparison', versions: versions));
    await openInfo(tester, const Key('info-summary'));
    expect(rows(tester), [en.selectedSummary(1), en.defSummaryBody]);
    await close(tester, en);
    await openInfo(tester, const Key('info-summary'));
    final main = find.byKey(const Key('summary-show-all'));
    expect(tester.widget<FilledButton>(main).child, isA<Text>().having((t) => t.data, 'label', en.showAllDifferences));
    await tester.tap(main);
    await tester.pumpAndSettle();
    expect(find.byType(CalmSheet), findsNothing);
    expect(find.byType(AllDifferencesScreen), findsOneWidget);
    expect(find.text(en.allDifferencesTitle), findsOneWidget);
  });

  testWidgets('Info buttons are 48 px targets labelled "About {term}"', (tester) async {
    final handle = tester.ensureSemantics();
    await pumpScreen(tester, finding());
    for (final (key, term) in [(const Key('info-change-types'), en.defChangeTypesTitle),
        (const ValueKey('info-evidence-later'), en.defEvidenceTitle)]) {
      final size = tester.getSize(find.descendant(of: find.byKey(key), matching: find.byType(IconButton)));
      expect(size.width, greaterThanOrEqualTo(48));
      expect(size.height, greaterThanOrEqualTo(48));
      expect(tester.getSemantics(find.bySemanticsLabel(en.defInfo(term)).first), matchesSemantics(label: en.defInfo(term),
        isButton: true, hasTapAction: true, hasFocusAction: true, isFocusable: true, hasEnabledState: true,
        isEnabled: true));
    }
    handle.dispose();
  });

  // Layout matrix: each sheet at both sizes, EN/DE, light/dark, 1.0 and 2.0, Android and iOS.
  final sheets = <String, WidgetBuilder>{
    'scope': (_) => const ScopeDefinitionSheet(),
    'change-types': (_) => const ChangeTypeDefinitionSheet(),
    'evidence': (_) => const EvidenceDefinitionSheet(),
    'summary': (_) => SummaryDefinitionSheet(otherDifferences: 1, onShowAll: () {}),
  };
  for (final size in [const Size(320, 568), const Size(390, 844)]) {
    for (final locale in ['en', 'de']) {
      for (final scale in [1.0, 2.0]) {
        for (final theme in [ThemeMode.light, ThemeMode.dark]) {
          final name = '${size.width.toInt()}x${size.height.toInt()}-$locale-${scale}x-${theme.name}';
          testWidgets('Sheets lay out with reachable actions: $name', (tester) async {
            tester.view.physicalSize = size;
            tester.view.devicePixelRatio = 1;
            tester.platformDispatcher.textScaleFactorTestValue = scale;
            addTearDown(tester.view.reset);
            addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
            final l = lookupAppLocalizations(Locale(locale));
            await pumpScreen(tester, locale: locale, theme: theme, Scaffold(body: Builder(builder: (context) =>
              Column(children: [for (final e in sheets.entries) TextButton(key: Key('open-${e.key}'),
                onPressed: () => showCalmSheet<void>(context, builder: e.value), child: Text(e.key))]))));
            for (final entry in sheets.entries) {
              await tester.tap(find.byKey(Key('open-${entry.key}')));
              await tester.pumpAndSettle();
              expect(tester.takeException(), isNull, reason: entry.key);
              if (entry.key == 'summary') {
                expect(find.byKey(const Key('summary-show-all')).hitTestable(), findsOneWidget);
              }
              await close(tester, l);
            }
            await tester.pumpWidget(const SizedBox());
          }, variant: platforms);
        }
      }
    }
  }
}

const sampleQuoteForTest = 'Final files are due on 27 November 2026.';
