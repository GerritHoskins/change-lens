// O-24 phase B: the six onboarding steps, the import sheet and the Projects-menu replay
// (docs/onboarding-implementation-handoff.md §6). Widget tests only; not device evidence.
import 'package:changelens/design/calm_icons.dart';
import 'package:changelens/l10n/app_localizations.dart';
import 'package:changelens/main.dart';
import 'package:changelens/screens/onboarding_screen.dart';
import 'package:changelens/screens/projects_screen.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fixtures/calm_scenario.dart';

const steps = OnboardingScreen.steps;
final platforms = TargetPlatformVariant(const {TargetPlatform.android, TargetPlatform.iOS});

Future<void> loadFonts() async {
  final loader = FontLoader('Roboto');
  for (final weight in ['Regular', 'SemiBold', 'Bold']) {
    loader.addFont(rootBundle.load('assets/fonts/Roboto-$weight.ttf'));
  }
  await loader.load();
}

void setView(WidgetTester tester, Size size, double scale) {
  tester.view.physicalSize = size;
  tester.view.devicePixelRatio = 1;
  tester.platformDispatcher.textScaleFactorTestValue = scale;
  addTearDown(tester.view.reset);
  addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
}

/// A launcher route under onboarding, so leaving it is observable.
Future<void> openOnboarding(WidgetTester tester, OnboardingMode mode,
    {String locale = 'en', ThemeMode theme = ThemeMode.light}) async {
  final services = await CedarScenario().services();
  await tester.pumpWidget(const SizedBox()); // a fresh navigator, not the previous run's stack
  await tester.pumpWidget(ChangeLensApp(services: services, locale: Locale(locale), themeMode: theme,
    home: Builder(builder: (context) => Scaffold(body: Center(child: TextButton(key: const Key('open'),
      onPressed: () => Navigator.of(context).push(MaterialPageRoute<void>(
        builder: (_) => OnboardingScreen(mode: mode))),
      child: const Text('launcher')))))));
  await tester.pumpAndSettle();
  await tester.tap(find.byKey(const Key('open')));
  await tester.pumpAndSettle();
}

Finder body(int step) => find.descendant(of: find.byKey(ValueKey('onb-body-$step')), matching: find.byType(Scrollable));

double overflow(WidgetTester tester, int step) =>
    tester.state<ScrollableState>(body(step).first).position.maxScrollExtent;

Future<void> next(WidgetTester tester) async {
  await tester.tap(find.byKey(const Key('onb-main')));
  await tester.pumpAndSettle();
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  setUpAll(loadFonts);

  for (final size in [const Size(320, 568), const Size(390, 844)]) {
    for (final locale in ['en', 'de']) {
      for (final scale in [1.0, 2.0]) {
        for (final theme in [ThemeMode.light, ThemeMode.dark]) {
          final name = '${size.width.toInt()}x${size.height.toInt()}-$locale-${scale}x-${theme.name}';
          testWidgets('Every step and the import sheet lay out with a reachable main button: $name', (tester) async {
            setView(tester, size, scale);
            for (final mode in OnboardingMode.values) {
              await openOnboarding(tester, mode, locale: locale, theme: theme);
              for (var step = 0; step < steps; step++) {
                expect(tester.takeException(), isNull, reason: '${mode.name} step ${step + 1}');
                final main = find.byKey(const Key('onb-main'));
                expect(main.hitTestable(), findsOneWidget, reason: '${mode.name} step ${step + 1}');
                final rect = tester.getRect(main);
                expect(rect.bottom, lessThanOrEqualTo(size.height), reason: '${mode.name} step ${step + 1}');
                expect(rect.top, greaterThanOrEqualTo(0));
                if (step < steps - 1) await next(tester);
              }
              await tester.ensureVisible(find.byKey(const Key('onb-import')));
              await tester.pumpAndSettle();
              await tester.tap(find.byKey(const Key('onb-import')));
              await tester.pumpAndSettle();
              expect(tester.takeException(), isNull, reason: '${mode.name} import sheet');
              final close = find.widgetWithText(TextButton, lookupAppLocalizations(Locale(locale)).close);
              expect(close.hitTestable(), findsOneWidget);
              await tester.tap(close);
              await tester.pumpAndSettle();
            }
            await tester.pumpWidget(const SizedBox());
          }, variant: platforms);
        }
      }
    }
  }

  // The design's done criterion: at 390×844 and 1.0 nothing in the step body scrolls. Measured
  // with an iPhone's safe-area insets (47 top, 34 bottom) on both platforms, the stricter case.
  final measured = <String, double>{}, spare = <String, double>{};
  for (final locale in ['en', 'de']) {
    testWidgets('No step body scrolls at 390×844, text scale 1.0: $locale', (tester) async {
      setView(tester, const Size(390, 844), 1);
      tester.view.padding = tester.view.viewPadding = const FakeViewPadding(top: 47, bottom: 34);
      final platform = debugDefaultTargetPlatformOverride!.name;
      for (final mode in OnboardingMode.values) {
        await openOnboarding(tester, mode, locale: locale);
        for (var step = 0; step < steps; step++) {
          if (mode == OnboardingMode.firstRun || step == steps - 1) {
            final key = '$platform $locale ${mode.name} step ${step + 1}';
            measured[key] = overflow(tester, step);
            final viewport = tester.getRect(body(step).first);
            final content = tester.getRect(find.descendant(of: body(step).first,
              matching: find.byType(Column)).first);
            spare[key] = viewport.height - content.height - 24; // minus the body's own padding
          }
          if (step < steps - 1) await next(tester);
        }
      }
      await tester.pumpWidget(const SizedBox());
    }, variant: platforms);
  }
  tearDownAll(() {
    final over = {for (final e in measured.entries) if (e.value > 0) e.key: e.value};
    final tightest = (spare.entries.toList()..sort((a, b) => a.value.compareTo(b.value))).take(4);
    // ignore: avoid_print
    print('No-scroll check, overflow in px: ${over.isEmpty ? 'none' : over}; '
      'least spare room: ${[for (final e in tightest) '${e.key} ${e.value.toStringAsFixed(0)} px']}');
    expect(measured, hasLength(2 * 2 * (steps + 1)));
    // Design round 4 shortened the German copy on steps 2 and 5, so no step may scroll any more.
    const reported = <String, double>{};
    for (final e in over.entries) {
      expect(reported[e.key], isNotNull, reason: '${e.key} scrolls by ${e.value} px at 390×844, 1.0');
      expect(e.value, lessThanOrEqualTo(reported[e.key]!), reason: '${e.key} grew');
    }
  });

  group('Controls', () {
    testWidgets('First run: Skip on steps 1–5 only, Back from step 2, Start leaves', (tester) async {
      await openOnboarding(tester, OnboardingMode.firstRun);
      final l = lookupAppLocalizations(const Locale('en'));
      for (var step = 0; step < steps; step++) {
        expect(find.text(l.onbStep(step + 1, steps)), findsOneWidget);
        expect(find.byKey(const Key('onb-skip')), step < steps - 1 ? findsOneWidget : findsNothing);
        expect(find.byKey(const Key('onb-close')), findsNothing);
        expect(find.byKey(const Key('onb-back')), step == 0 ? findsNothing : findsOneWidget);
        expect(find.text(step < steps - 1 ? l.onbNext : l.onbStart), findsOneWidget);
        if (step < steps - 1) await next(tester);
      }
      expect(find.text(l.onbStartTitle), findsOneWidget);
      expect(find.text(l.onbStartNext), findsOneWidget);
      await next(tester);
      expect(find.byType(OnboardingScreen), findsNothing);
      expect(find.text('launcher'), findsOneWidget);

      await tester.tap(find.byKey(const Key('open')));
      await tester.pumpAndSettle();
      await next(tester);
      await tester.tap(find.byKey(const Key('onb-skip')));
      await tester.pumpAndSettle();
      expect(find.byType(OnboardingScreen), findsNothing);
    });

    testWidgets('Replay: Close on every step, Done on step 6, its own step-6 title', (tester) async {
      await openOnboarding(tester, OnboardingMode.replay);
      final l = lookupAppLocalizations(const Locale('en'));
      for (var step = 0; step < steps; step++) {
        expect(find.byKey(const Key('onb-close')), findsOneWidget);
        expect(find.byKey(const Key('onb-skip')), findsNothing);
        if (step < steps - 1) await next(tester);
      }
      expect(find.text(l.onbStartTitleReplay), findsOneWidget);
      expect(find.text(l.onbStartNext), findsNothing);
      expect(find.text(l.onbDone), findsOneWidget);
      await tester.tap(find.byKey(const Key('onb-close')));
      await tester.pumpAndSettle();
      expect(find.byType(OnboardingScreen), findsNothing);

      await tester.tap(find.byKey(const Key('open')));
      await tester.pumpAndSettle();
      for (var step = 0; step < steps - 1; step++) { await next(tester); }
      await next(tester);
      expect(find.byType(OnboardingScreen), findsNothing);
    });

    testWidgets('Back and system back step back; on step 1 system back leaves', (tester) async {
      await openOnboarding(tester, OnboardingMode.firstRun);
      final l = lookupAppLocalizations(const Locale('en'));
      await next(tester);
      await next(tester);
      expect(find.text(l.onbStep(3, steps)), findsOneWidget);
      await tester.tap(find.byKey(const Key('onb-back')));
      await tester.pumpAndSettle();
      expect(find.text(l.onbStep(2, steps)), findsOneWidget);
      await tester.binding.handlePopRoute();
      await tester.pumpAndSettle();
      expect(find.text(l.onbStep(1, steps)), findsOneWidget);
      expect(find.byType(OnboardingScreen), findsOneWidget);
      await tester.binding.handlePopRoute();
      await tester.pumpAndSettle();
      expect(find.byType(OnboardingScreen), findsNothing);
    });

    testWidgets('Focus moves to the new step title, and the body starts at the top', (tester) async {
      await openOnboarding(tester, OnboardingMode.firstRun);
      for (var step = 1; step < steps; step++) {
        await next(tester);
        expect(FocusManager.instance.primaryFocus?.debugLabel, 'onboarding-title', reason: 'step ${step + 1}');
        expect(tester.state<ScrollableState>(body(step).first).position.pixels, 0);
      }
      await tester.tap(find.byKey(const Key('onb-back')));
      await tester.pumpAndSettle();
      expect(FocusManager.instance.primaryFocus?.debugLabel, 'onboarding-title');
    });

    testWidgets('Import sheet lists inputs and the parse limits with locale separators', (tester) async {
      for (final (locale, words) in [('en', '15,000'), ('de', '15.000')]) {
        await openOnboarding(tester, OnboardingMode.replay, locale: locale);
        final l = lookupAppLocalizations(Locale(locale));
        for (var step = 0; step < steps - 1; step++) { await next(tester); }
        await tester.tap(find.byKey(const Key('onb-import')));
        await tester.pumpAndSettle();
        final sheet = find.byType(ImportSheet);
        expect(find.descendant(of: sheet, matching: find.text(l.importSheetTitle)), findsOneWidget);
        for (final line in [l.onbStartInputs, l.onbStartOnline]) { expect(find.text(line), findsOneWidget); }
        // The language line is on step 6 and repeated in the sheet.
        expect(find.text(l.onbStartLanguage), findsNWidgets(2));
        final limits = l.onbStartLimits(ParseLimits.words, ParseLimits.pages, ParseLimits.megabytes);
        expect(limits, contains(words));
        expect(find.text(limits), findsOneWidget);
        await tester.tap(find.text(l.close));
        await tester.pumpAndSettle();
        expect(sheet, findsNothing);
      }
    });

    testWidgets('Nothing is stored: a new replay starts at step 1', (tester) async {
      final scenario = CedarScenario();
      final services = await scenario.services();
      final settings = Map.of((services.store as CedarSettings).values);
      await tester.pumpWidget(ChangeLensApp(services: services, home: Builder(builder: (context) => Scaffold(
        body: TextButton(key: const Key('open'), child: const Text('launcher'), onPressed: () =>
          Navigator.of(context).push(MaterialPageRoute<void>(
            builder: (_) => const OnboardingScreen(mode: OnboardingMode.replay))))))));
      await tester.tap(find.byKey(const Key('open')));
      await tester.pumpAndSettle();
      await next(tester);
      await next(tester);
      await tester.tap(find.byKey(const Key('onb-close')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('open')));
      await tester.pumpAndSettle();
      expect(find.text('Step 1 of 6'), findsOneWidget);
      expect((services.store as CedarSettings).values, settings);
      expect(scenario.requests, isEmpty);
    });
  });

  group('Semantics', () {
    testWidgets('Reading order, illustrations and the example frame', (tester) async {
      final handle = tester.ensureSemantics();
      await openOnboarding(tester, OnboardingMode.firstRun);
      final l = lookupAppLocalizations(const Locale('en'));
      final titles = [l.onbIntroTitle, l.onbContextTitle, l.onbEvidenceTitle, l.onbUncertainTitle,
        l.onbReviewTitle, l.onbStartTitle];
      final bodies = [l.onbIntroBody, l.confirmIntro, l.onbEvidenceBody, l.onbUncertainBody,
        l.onbReviewBody, l.onbStartNext];
      final alts = {0: l.onbIntroAlt, 1: l.onbContextAlt, 4: l.onbReviewAlt};
      for (var step = 0; step < steps; step++) {
        final labels = [for (final node in tester.semantics.simulatedAccessibilityTraversal()) node.label.isEmpty ? node.tooltip : node.label];
        int at(String label) {
          final index = labels.indexWhere((x) => x == label);
          expect(index, isNot(-1), reason: 'step ${step + 1}: "$label" not announced in $labels');
          return index;
        }
        final order = [
          if (step > 0) at('Back'),
          at(l.onbStep(step + 1, steps)),
          at(titles[step]),
          at(bodies[step]),
          at(step < steps - 1 ? l.onbNext : l.onbStart),
        ];
        expect(order, orderedEquals([...order]..sort()), reason: 'step ${step + 1}: $labels');

        if (alts[step] case final alt?) {
          final image = find.bySemanticsLabel(alt);
          expect(image, findsOneWidget, reason: 'step ${step + 1}');
          expect(tester.getSemantics(image), matchesSemantics(label: alt, isImage: true));
          expect(tester.getSemantics(image).childrenCount, 0, reason: 'nothing announced inside the image');
        }
        if (step >= 2 && step <= 4) {
          // The frame is one container announced first as "Example"; its card text follows.
          final example = find.bySemanticsLabel(RegExp('^${l.onbExample}(\n|\$)'));
          expect(example, findsOneWidget, reason: 'step ${step + 1}');
        }
        if (step < steps - 1) await next(tester);
      }
      handle.dispose();
    });
  });

  group('Entry point', () {
    testWidgets('The Projects menu opens the replay and still reaches Developer settings', (tester) async {
      final services = await CedarScenario().services();
      await tester.pumpWidget(ChangeLensApp(services: services));
      await tester.pumpAndSettle();
      final l = lookupAppLocalizations(const Locale('en'));
      await tester.tap(find.byKey(const Key('projects-menu')));
      await tester.pumpAndSettle();
      expect(find.text(l.onbReplayEntry), findsOneWidget);
      expect(find.text(l.devSettings), findsOneWidget);
      await tester.tap(find.byKey(const Key('how-it-works')));
      await tester.pumpAndSettle();
      expect(find.byType(OnboardingScreen), findsOneWidget);
      expect(find.byKey(const Key('onb-close')), findsOneWidget);
      expect(find.byKey(const Key('onb-skip')), findsNothing);
      await tester.tap(find.byKey(const Key('onb-close')));
      await tester.pumpAndSettle();
      expect(find.byType(ProjectsScreen), findsOneWidget);
      await tester.tap(find.byKey(const Key('projects-menu')));
      await tester.pumpAndSettle();
      await tester.tap(find.byKey(const Key('settings')));
      await tester.pumpAndSettle();
      expect(find.byType(DevSettingsScreen), findsOneWidget);
      await tester.pumpWidget(const SizedBox());
    });

    testWidgets('The menu button uses the platform overflow icon', (tester) async {
      final services = await CedarScenario().services();
      await tester.pumpWidget(ChangeLensApp(services: services));
      await tester.pumpAndSettle();
      final ios = debugDefaultTargetPlatformOverride == TargetPlatform.iOS;
      final icon = tester.widget<Icon>(find.descendant(of: find.byKey(const Key('projects-menu')),
        matching: find.byType(Icon)));
      expect(icon.icon, ios ? CalmIcons.moreIOS : CalmIcons.more);
      await tester.pumpWidget(const SizedBox());
    }, variant: platforms);
  });
}
