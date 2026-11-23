// The demo limit in the app (docs/demo-wall-handoff.md): the demo line, the wall instead of Compare, the
// feedback form and the Settings row. Widget tests with a fake API; not device evidence. The layout
// matrix is in new_screens_layout_test.dart. Set CALM_CAPTURE_DIR to write PNG renders of the wall and the
// form in English and German.
import 'dart:async';
import 'dart:io';
import 'dart:ui' as ui;

import 'package:changelens/api.dart';
import 'package:changelens/auth/session.dart';
import 'package:changelens/demo.dart';
import 'package:changelens/l10n/app_localizations.dart';
import 'package:changelens/main.dart';
import 'package:changelens/screens/compare_screen.dart';
import 'package:changelens/screens/demo_feedback_screen.dart';
import 'package:changelens/screens/demo_wall.dart';
import 'package:changelens/screens/project_screen.dart';
import 'package:changelens/screens/projects_screen.dart';
import 'package:changelens/screens/settings_screen.dart';
import 'package:changelens/services.dart';
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

import 'account_screens_test.dart' show NoPicker;
import 'fixtures/auth_fakes.dart';
import 'fixtures/calm_scenario.dart';
import 'fixtures/demo_fakes.dart';
import 'new_screens_layout_test.dart' show localized;

const captureDirectory = String.fromEnvironment('CALM_CAPTURE_DIR');
const line = Key('demo-line'), wall = Key('demo-wall'), send = Key('demo-send'), hint = Key('demo-send-hint');

Future<void> tapAndSettle(WidgetTester tester, Finder finder) async {
  await tester.ensureVisible(finder);
  await tester.pumpAndSettle();
  await tester.tap(finder);
  await tester.pumpAndSettle();
}

Future<void> pumpHome(WidgetTester tester, Services services, Widget home, {String locale = 'en'}) async {
  tester.view.physicalSize = const Size(390, 844);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
  await tester.pumpWidget(ChangeLensApp(services: services, home: home, locale: Locale(locale)));
  await tester.pumpAndSettle();
}

/// Chooses [answer] in the "What is missing" sheet.
Future<void> chooseMissing(WidgetTester tester, String answer) async {
  await tapAndSettle(tester, find.byKey(const Key('demo-missing')));
  await tapAndSettle(tester, find.text(answer).last);
}

bool enabled(WidgetTester tester, Key key) => tester.widget<FilledButton>(find.byKey(key)).onPressed != null;

String text(WidgetTester tester, Key key) => tester.widget<Text>(find.byKey(key)).data!;

Future<void> close(WidgetTester tester) => tester.pumpWidget(const SizedBox()); // ends the screens' timers

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

  group('State', () {
    test('only the documented object with a limit is a demo state', () {
      final state = DemoState.fromJson(demoJson(remaining: 1, inFlight: 1, discount: true))!;
      expect((state.limit, state.used, state.inFlight, state.remaining), (3, 1, 1, 1));
      expect((state.atLimit, state.feedbackSubmitted, state.discountOffered), (false, false, true));
      expect(DemoState.fromJson(demoJson(remaining: 0))!.atLimit, isTrue);
      for (final none in [null, 'demo', <String, dynamic>{}, {...demoJson(), 'limit': null}, {'limit': 3}]) {
        expect(DemoState.fromJson(none), isNull, reason: '$none');
      }
    });

    test('the session carries the state; a server without it means no demo, and sign-out clears it', () async {
      final h = AuthHarness()..storeSession();
      h.server.demo = demoJson(remaining: 1);
      final services = Services(h.store, NoPicker(), auth: h.session);
      await h.session.restore();
      expect(services.demo.state!.remaining, 1);
      await h.session.signOut();
      expect(services.demo.state, isNull);

      final old = AuthHarness()..storeSession(); // an older server: no `demo` in the answer
      final without = Services(old.store, NoPicker(), auth: old.session);
      await old.session.restore();
      expect(old.session.state, isA<SignedIn>());
      expect((without.demo.state, without.demo.atLimit), (null, false));
    });

    test('a refresh failure keeps what is known; a missing route means no demo', () async {
      final backend = DemoBackend(demoJson(remaining: 2));
      final demo = backend.controller();
      backend.demo = demoJson(remaining: 1);
      await demo.refresh();
      expect(demo.state!.remaining, 1);
      demo.limitReached();
      expect(demo.atLimit, isTrue);
      backend.demo = null;
      await demo.refresh();
      expect(demo.state, isNull);
    });
  });

  group('Demo line', () {
    for (final (remaining, expected) in [(3, 'Demo · 3 of 3 comparisons left'),
        (1, 'Demo · 1 of 3 comparisons left'), (0, 'Demo · 0 of 3 comparisons left')]) {
      testWidgets('Projects and Compare say "$expected"', (tester) async {
        final backend = DemoBackend(demoJson(remaining: remaining));
        final services = await backend.services();
        await pumpHome(tester, services, const ProjectsScreen());
        expect(text(tester, line), expected);
        final muted = tester.widget<Text>(find.byKey(line)).style!;
        expect(muted.color, Theme.of(tester.element(find.byKey(line))).textTheme.bodySmall!.color);
        expect(find.byType(LinearProgressIndicator), findsNothing); // text, not a bar or a badge

        await pumpHome(tester, services, CompareScreen(project: Project(cedarProject)));
        expect(text(tester, line), expected);
        await close(tester);
      });
    }

    testWidgets('German, and nothing at all without a demo state', (tester) async {
      final services = await DemoBackend(demoJson(remaining: 2)).services();
      await pumpHome(tester, services, const ProjectsScreen(), locale: 'de');
      expect(text(tester, line), 'Demo · 2 von 3 Vergleichen übrig');
      await close(tester);

      for (final none in [null, {...demoJson(), 'limit': null, 'remaining': null}]) {
        final off = await DemoBackend(none).services();
        await pumpHome(tester, off, const ProjectsScreen());
        expect(find.byKey(line), findsNothing);
        await tapAndSettle(tester, find.byKey(const Key('compare-briefs')));
        expect(find.byType(CompareScreen), findsOneWidget); // no wall either
        expect(find.byKey(line), findsNothing);
        await close(tester);
      }
    });
  });

  group('At the limit', () {
    testWidgets('Compare on Projects and on Project opens the wall, never the Compare screen', (tester) async {
      final services = await DemoBackend(demoJson(remaining: 0)).services();
      await pumpHome(tester, services, const ProjectsScreen());
      await tapAndSettle(tester, find.byKey(const Key('compare-briefs')));
      expect(find.byKey(wall), findsOneWidget);
      expect(find.byType(CompareScreen), findsNothing);
      await tester.pageBack();
      await tester.pumpAndSettle();
      expect(find.byType(ProjectsScreen), findsOneWidget); // Back: reports and history stay reachable

      await pumpHome(tester, services, ProjectScreen(project: Project(cedarProject)));
      await tapAndSettle(tester, find.byKey(const Key('compare')));
      expect(find.byKey(wall), findsOneWidget);
      expect(find.byType(CompareScreen), findsNothing);
      await close(tester);
    });

    testWidgets('with a comparison left, Compare opens as before', (tester) async {
      final services = await DemoBackend(demoJson(remaining: 1)).services();
      await pumpHome(tester, services, const ProjectsScreen());
      await tapAndSettle(tester, find.byKey(const Key('compare-briefs')));
      expect(find.byType(CompareScreen), findsOneWidget);
      expect(find.byKey(wall), findsNothing);
      await close(tester);
    });

    testWidgets('demo_limit_reached on Start opens the wall and keeps the draft', (tester) async {
      final backend = DemoBackend(demoJson(remaining: 1))..refuseStart = true; // the app's state is out of date
      final services = await backend.services();
      await pumpHome(tester, services, const ProjectsScreen());
      await pumpHome(tester, services, CompareScreen(project: Project(cedarProject), earlierId: 'v2', laterId: 'v3'));
      await tapAndSettle(tester, find.byKey(const Key('scope-partial')));
      await tapAndSettle(tester, find.byKey(const Key('start')));
      expect(find.byKey(wall), findsOneWidget);
      expect(services.demo.atLimit, isTrue);
      expect(find.text('The comparison could not be accepted. Check both inputs, then try again.'), findsNothing);

      // Back: the Compare screen with the same pair and scope, still only in memory.
      await tester.pageBack();
      await tester.pumpAndSettle();
      expect(find.text('Brief v2'), findsOneWidget);
      expect(find.text('Brief v3'), findsOneWidget);
      expect(text(tester, line), 'Demo · 0 of 3 comparisons left');
      // Start again opens the wall without asking the server a second time.
      final posts = backend.requests.where((r) => r.method == 'POST').length;
      await tapAndSettle(tester, find.byKey(const Key('start')));
      expect(find.byKey(wall), findsOneWidget);
      expect(backend.requests.where((r) => r.method == 'POST').length, posts);
      await close(tester);
    });
  });

  group('Wall', () {
    testWidgets('one black pill for feedback, the list address with Copy link, and no way to Compare',
        (tester) async {
      String? copied;
      tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(SystemChannels.platform, (call) async {
        if (call.method == 'Clipboard.setData') copied = (call.arguments as Map)['text'] as String;
        return null;
      });
      addTearDown(() => tester.binding.defaultBinaryMessenger.setMockMethodCallHandler(SystemChannels.platform, null));
      final demo = DemoBackend(demoJson(remaining: 0)).controller();
      await tester.pumpWidget(localized(DemoWallScreen(demo: demo), 'en', ThemeMode.light));
      await tester.pumpAndSettle();
      expect(find.text('Your 3 demo comparisons are used'), findsOneWidget);
      expect(find.textContaining('The full version is coming soon.'), findsOneWidget);
      expect(find.byType(FilledButton), findsOneWidget);
      expect(find.widgetWithText(FilledButton, 'Give feedback'), findsOneWidget);
      expect(find.text('Join the early-bird list'), findsOneWidget);
      expect(find.text('changelens.pixeltronic.dev'), findsOneWidget);
      expect(find.byKey(const Key('demo-wall-discount')), findsNothing); // the setting is off: not a word
      expect(find.textContaining('discount'), findsNothing);
      expect(find.byKey(const Key('demo-wall-running')), findsNothing);
      for (final word in ['€', 'price', 'App Store', 'Play', 'buy', 'Compare']) {
        expect(find.textContaining(word), findsNothing, reason: word);
      }
      await tapAndSettle(tester, find.byKey(const Key('demo-copy-link')));
      expect(copied, 'https://changelens.pixeltronic.dev/');
      expect(find.text('Link copied'), findsOneWidget);

      await tapAndSettle(tester, find.byKey(const Key('demo-give-feedback')));
      expect(find.byType(DemoFeedbackScreen), findsOneWidget);
    });

    testWidgets('the discount sentence shows only when the server offers it; sent feedback replaces the pill',
        (tester) async {
      final backend = DemoBackend(demoJson(remaining: 0, discount: true));
      final demo = backend.controller();
      await tester.pumpWidget(localized(DemoWallScreen(demo: demo), 'de', ThemeMode.light));
      await tester.pumpAndSettle();
      expect(find.text('Für dein Feedback bekommst du den Early-Bird-Rabatt, einen pro Person.'), findsOneWidget);
      expect(find.text('Deine 3 Demo-Vergleiche sind aufgebraucht'), findsOneWidget);

      await demo.sendFeedback(const DemoFeedback(missing: 'team', price: 'not_sure'));
      await tester.pumpAndSettle();
      expect(find.byType(FilledButton), findsNothing);
      expect(find.text('Dein Feedback wurde gesendet. Danke.'), findsOneWidget);
      expect(find.byKey(const Key('demo-wall-discount')), findsNothing);
      expect(demo.atLimit, isTrue); // feedback never gives a comparison back
    });

    testWidgets('a comparison still running is said so', (tester) async {
      final demo = DemoBackend(demoJson(remaining: 0, inFlight: 1)).controller();
      await tester.pumpWidget(localized(DemoWallScreen(demo: demo), 'en', ThemeMode.light));
      await tester.pumpAndSettle();
      expect(find.text('Your 3 demo comparisons are in use'), findsOneWidget);
      expect(find.byKey(const Key('demo-wall-running')), findsOneWidget);
    });
  });

  group('Form', () {
    Future<DemoBackend> pumpForm(WidgetTester tester, {String locale = 'en'}) async {
      tester.view.physicalSize = const Size(390, 1600); // every part built, none below the fold
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      final backend = DemoBackend(demoJson(remaining: 0));
      await tester.pumpWidget(localized(DemoFeedbackScreen(demo: backend.controller()), locale, ThemeMode.light));
      await tester.pumpAndSettle();
      return backend;
    }

    testWidgets('nothing is preselected and Send says what is missing, first thing first', (tester) async {
      await pumpForm(tester);
      expect(find.byType(FilledButton), findsOneWidget);
      expect(enabled(tester, send), isFalse);
      expect(text(tester, hint), 'Choose what is missing first.');
      expect(find.byKey(const Key('demo-missing-other')), findsNothing);
      expect(find.text('This is a question, not an offer. Nothing is charged.'), findsOneWidget);
      expect(find.text("Optional. Please don't paste text from your documents."), findsOneWidget);
      expect(find.textContaining('20 comparisons a month'), findsOneWidget);
      for (final amount in ['Nothing', '€5', '€10', '€15', 'More than €15', 'Not sure']) {
        expect(find.text(amount), findsOneWidget);
      }
      expect(find.textContaining('discount'), findsNothing);

      await chooseMissing(tester, 'Sharing or exporting a report');
      expect((enabled(tester, send), text(tester, hint)), (false, 'Choose an amount.'));
      await tapAndSettle(tester, find.byKey(const Key('demo-price-eur_10')));
      expect((enabled(tester, send), text(tester, hint)), (true, "Sent once. You can't change it afterwards."));
    });

    testWidgets('"Other" opens a required text field with its minimum', (tester) async {
      final backend = await pumpForm(tester);
      await chooseMissing(tester, 'Other');
      await tapAndSettle(tester, find.byKey(const Key('demo-price-eur_0')));
      expect(find.text('At least 20 characters.'), findsOneWidget);
      expect((enabled(tester, send), text(tester, hint)),
        (false, 'Describe what is missing, in at least 20 characters.'));
      await tester.enterText(find.byKey(const Key('demo-missing-other')), '   ${'x' * 19}   ');
      await tester.pump();
      expect(enabled(tester, send), isFalse); // spaces around 19 characters are still 19
      await tester.enterText(find.byKey(const Key('demo-missing-other')), 'x' * 20);
      await tester.pump();
      expect(enabled(tester, send), isTrue);
      await tester.enterText(find.byKey(const Key('demo-anything-else')), '  A calmer export.  ');
      await tapAndSettle(tester, find.byKey(send));
      expect(backend.feedback.single, {'missing': 'other', 'missing_other': 'x' * 20,
        'anything_else': 'A calmer export.', 'price': 'eur_0'});
      expect(find.text('Your feedback was sent. Thank you.'), findsOneWidget);
      expect(find.widgetWithText(FilledButton, 'Done'), findsOneWidget);
    });

    testWidgets('text typed for "Other" is not sent with another answer', (tester) async {
      final backend = await pumpForm(tester);
      await chooseMissing(tester, 'Other');
      await tester.enterText(find.byKey(const Key('demo-missing-other')), 'Something I changed my mind about.');
      await chooseMissing(tester, 'Faster results');
      await tapAndSettle(tester, find.byKey(const Key('demo-price-not_sure')));
      await tapAndSettle(tester, find.byKey(send));
      expect(backend.feedback.single, {'missing': 'faster_results', 'missing_other': null, 'anything_else': null,
        'price': 'not_sure'});
    });

    testWidgets('sending disables the form; a failed send keeps every entry and can be retried', (tester) async {
      final backend = await pumpForm(tester);
      backend..feedbackStatus = 500..hold = Completer<void>();
      await chooseMissing(tester, 'Other');
      await tester.enterText(find.byKey(const Key('demo-missing-other')), 'An export I can send to my client.');
      await tester.enterText(find.byKey(const Key('demo-anything-else')), 'Nothing else.');
      await tapAndSettle(tester, find.byKey(const Key('demo-price-eur_15')));
      await tester.tap(find.byKey(send));
      await tester.pump();
      expect(find.text('Sending…'), findsOneWidget);
      expect(enabled(tester, send), isFalse);
      backend.hold!.complete();
      await tester.pumpAndSettle();

      expect(find.byKey(const Key('demo-send-error')), findsOneWidget);
      expect(find.text('Your feedback could not be sent. Your entries are still here. Try again.'), findsOneWidget);
      expect(find.text('An export I can send to my client.'), findsOneWidget);
      expect(find.text('Nothing else.'), findsOneWidget);
      expect(enabled(tester, send), isTrue);
      backend..feedbackStatus = 201..hold = null;
      await tapAndSettle(tester, find.byKey(send));
      expect(backend.feedback.single['price'], 'eur_15');
      expect(find.byKey(const Key('demo-feedback-sent')), findsOneWidget);
    });

    testWidgets('already answered on another device counts as sent', (tester) async {
      final backend = await pumpForm(tester);
      backend.feedbackStatus = 409;
      await chooseMissing(tester, 'Working with a team');
      await tapAndSettle(tester, find.byKey(const Key('demo-price-eur_5')));
      await tapAndSettle(tester, find.byKey(send));
      expect(find.byKey(const Key('demo-feedback-sent')), findsOneWidget);
      expect(find.byKey(const Key('demo-send-error')), findsNothing);
    });

    testWidgets('German: the question is no offer, and the amounts', (tester) async {
      await pumpForm(tester, locale: 'de');
      expect(find.text('Das ist eine Frage, kein Angebot. Es wird nichts berechnet.'), findsOneWidget);
      expect(find.text('Optional. Bitte füge keinen Text aus deinen Dokumenten ein.'), findsOneWidget);
      expect(find.text('Mehr als 15 €'), findsOneWidget);
      expect(text(tester, hint), 'Wähle zuerst, was fehlt.');
    });
  });

  group('Settings', () {
    Future<void> pumpSettings(WidgetTester tester, DemoController? demo) async {
      final h = AuthHarness()..storeSession();
      await h.session.restore();
      tester.view.physicalSize = const Size(390, 1200);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      await tester.pumpWidget(localized(SettingsScreen(session: h.session, demo: demo,
        keychainProtection: () async => null), 'en', ThemeMode.light));
      await tester.pumpAndSettle();
    }

    testWidgets('the Demo feedback row opens the form, and says so once feedback was sent', (tester) async {
      final backend = DemoBackend(demoJson(remaining: 2)); // at any time, not only at the wall
      await pumpSettings(tester, backend.controller());
      expect(find.text('Demo'), findsOneWidget);
      await tapAndSettle(tester, find.byKey(const Key('settings-demo-feedback')));
      expect(find.byType(DemoFeedbackScreen), findsOneWidget);
      await chooseMissing(tester, 'Faster results');
      await tapAndSettle(tester, find.byKey(const Key('demo-price-eur_10')));
      await tapAndSettle(tester, find.byKey(send));
      await tapAndSettle(tester, find.byKey(const Key('demo-done')));
      expect(find.byKey(const Key('settings-demo-feedback')), findsNothing);
      expect(find.byKey(const Key('settings-demo-feedback-sent')), findsOneWidget);
      expect(find.text('Your feedback was sent. Thank you.'), findsOneWidget);
    });

    testWidgets('no demo state, no Demo section', (tester) async {
      await pumpSettings(tester, DemoBackend().controller());
      expect(find.text('Demo'), findsNothing);
      await pumpSettings(tester, null);
      expect(find.text('Demo'), findsNothing);
    });
  });

  // Pictures for the owner, from fake data: not device evidence (no keyboard, no system sheets).
  for (final locale in ['en', 'de']) {
    testWidgets('Renders of the wall and the form: $locale', (tester) async {
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      final l = lookupAppLocalizations(Locale(locale));
      Future<void> shot(String name, Widget screen, Size size) async {
        tester.view.physicalSize = size;
        final boundary = GlobalKey();
        await tester.pumpWidget(RepaintBoundary(key: boundary, child: localized(screen, locale, ThemeMode.light)));
        await tester.pumpAndSettle();
        expect(tester.takeException(), isNull, reason: name);
        if (name.endsWith('other')) {
          await chooseMissing(tester, l.demoMissingOther);
          await tester.enterText(find.byKey(const Key('demo-missing-other')), locale == 'de'
            ? 'Ein Export, den ich meinem Kunden schicken kann.' : 'An export I can send to my client.');
          await tapAndSettle(tester, find.byKey(const Key('demo-price-eur_10')));
        }
        if (captureDirectory.isEmpty) return;
        await tester.runAsync(() async {
          final image = await (boundary.currentContext!.findRenderObject()! as RenderRepaintBoundary)
              .toImage(pixelRatio: 2);
          final bytes = await image.toByteData(format: ui.ImageByteFormat.png);
          await Directory(captureDirectory).create(recursive: true);
          await File('$captureDirectory/$name-$locale.png').writeAsBytes(bytes!.buffer.asUint8List());
          image.dispose();
        });
      }

      DemoController demo({bool discount = false}) =>
          DemoBackend(demoJson(remaining: 0, discount: discount)).controller();
      await shot('demo-wall', DemoWallScreen(demo: demo()), const Size(390, 844));
      await shot('demo-wall-discount-on', DemoWallScreen(demo: demo(discount: true)), const Size(390, 844));
      await shot('demo-form', DemoFeedbackScreen(demo: demo()), const Size(390, 1500));
      await shot('demo-form-other', DemoFeedbackScreen(demo: demo()), const Size(390, 1700));
    });
  }
}
