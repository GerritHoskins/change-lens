// Layout matrix for the WP-A to WP-C screens (handoff "Order, verification and done"): 320×568 and
// 390×844, EN and DE, light and dark, text 1.0 and 2.0. No overflow, and each screen's actions stay
// reachable: pinned ones without scrolling, list ones after scrolling. Widget tests, not device evidence.
// The demo wall, the demo feedback form and the Settings demo row (docs/demo-wall-handoff.md) run through
// the same matrix in their own test.
import 'package:changelens/api.dart';
import 'package:changelens/auth/session.dart';
import 'package:changelens/design/calm_controls.dart';
import 'package:changelens/design/calm_theme.dart';
import 'package:changelens/l10n/app_localizations.dart';
import 'package:changelens/main.dart';
import 'package:changelens/screens/consent_screen.dart';
import 'package:changelens/screens/demo_feedback_screen.dart';
import 'package:changelens/screens/demo_wall.dart';
import 'package:changelens/screens/project_timeline.dart';
import 'package:changelens/screens/review_completion.dart';
import 'package:changelens/screens/settings_screen.dart';
import 'package:changelens/services.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'account_screens_test.dart' show NoPicker;
import 'fixtures/auth_fakes.dart';
import 'fixtures/demo_fakes.dart';
import 'review_completion_test.dart' show summaryReport;
import 'session_settings_test.dart' show FakeConsent;

void noError(WidgetTester tester, String where) {
  final error = tester.takeException();
  expect(error, isNull, reason: '$where: ${error is FlutterError ? error.toStringDeep() : error}');
}

Future<void> reachable(WidgetTester tester, String key, {bool pinned = false}) async {
  final finder = find.byKey(Key(key));
  if (!pinned) {
    // Lists build lazily: scroll until the control exists, then into full view.
    if (finder.evaluate().isEmpty) {
      await tester.scrollUntilVisible(finder, 150, scrollable: find.byType(Scrollable).last);
    }
    await tester.ensureVisible(finder);
  }
  await tester.pumpAndSettle();
  // Pinned controls must be hittable at their centre; list items (some taller than half the screen at
  // 2× text) at their leading edge once scrolled to.
  expect(finder.hitTestable(at: pinned ? Alignment.center : const Alignment(-0.9, -0.9)), findsOneWidget,
    reason: key);
}

Widget localized(Widget home, String locale, ThemeMode theme) => MaterialApp(key: UniqueKey(),
  locale: Locale(locale), theme: calmTheme(Brightness.light), darkTheme: calmTheme(Brightness.dark), themeMode: theme,
  localizationsDelegates: AppLocalizations.localizationsDelegates, supportedLocales: AppLocalizations.supportedLocales,
  home: home);

void main() {
  for (final size in [const Size(320, 568), const Size(390, 844)]) {
    for (final locale in ['en', 'de']) {
      for (final scale in [1.0, 2.0]) {
        for (final theme in [ThemeMode.light, ThemeMode.dark]) {
          final name = '${size.width.toInt()}x${size.height.toInt()}-$locale-${scale}x-${theme.name}';
          testWidgets('Sign-in, expired sheet, Settings, consent, P5, P6 and P7 lay out: $name', (tester) async {
            tester.view.physicalSize = size;
            tester.view.devicePixelRatio = 1;
            tester.platformDispatcher.textScaleFactorTestValue = scale;
            addTearDown(tester.view.reset);
            addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);

            // Sign-in, signed out.
            final h = AuthHarness()..storeSession();
            h.server.onboarding = {'completed': true, 'step': null};
            final services = Services(h.store, NoPicker(), auth: h.session);
            await h.session.restore();
            await h.session.signOut();
            await tester.pumpWidget(ChangeLensApp(services: services, locale: Locale(locale), themeMode: theme));
            await tester.pumpAndSettle();
            noError(tester, 'sign-in');
            for (final key in ['sign-in-google', 'sign-in-apple', 'sign-in-email']) {
              await reachable(tester, key);
            }

            // Signed in, then the session ends: the sheet's methods and Sign out are reachable.
            await tester.tap(find.byKey(const Key('sign-in-email')));
            await tester.pumpAndSettle();
            h.server..projectsStatus = 401..sessionStatus = 401;
            await expectLater(h.session.api.projects(), throwsA(anything));
            await tester.pumpAndSettle();
            expect(h.session.state, isA<ReauthRequired>());
            noError(tester, 'expired sheet');
            await reachable(tester, 'sign-in-email');
            await reachable(tester, 'session-sign-out');

            // Settings, with the (gated) Privacy section and the iOS Keychain line shown.
            await tester.pumpWidget(localized(SettingsScreen(session: h.session, consent: FakeConsent(),
              keychainProtection: () async => const KeychainProtection({KeychainProtection.intended}, synchronised: false)),
              locale, theme));
            await tester.pumpAndSettle();
            noError(tester, 'settings');
            await reachable(tester, 'keychain-protection');
            await reachable(tester, 'delete-account');
            await reachable(tester, 'usage-events');

            // Consent: both answers pinned, no scrolling needed.
            await tester.pumpWidget(localized(ConsentScreen(consent: FakeConsent(), onDone: () {}), locale, theme));
            await tester.pumpAndSettle();
            noError(tester, 'consent');
            await reachable(tester, 'consent-allow', pinned: true);
            await reachable(tester, 'consent-decline', pinned: true);

            // P5 dismissal sheet: the action stays pinned above the reasons.
            await tester.pumpWidget(localized(Scaffold(body: Builder(builder: (context) => TextButton(
              key: const Key('open'), child: const Text('open'),
              onPressed: () => showCalmSheet<void>(context, builder: (_) => const DismissSheet(hasNext: true))))),
              locale, theme));
            await tester.tap(find.byKey(const Key('open')));
            await tester.pumpAndSettle();
            noError(tester, 'dismiss sheet');
            await reachable(tester, 'dismiss-confirm', pinned: true);
            await reachable(tester, 'dismiss-reason-other');

            // P6 timeline: a fork, both directions and an unplaced version, with long labels.
            await tester.pumpWidget(localized(Scaffold(body: ListView(padding: const EdgeInsets.all(20), children: [
              ProjectTimeline(loading: false, onCompareFrom: (_) {}, onCompareAgain: (_) {}, versions: [
                for (final id in ['a', 'b', 'c', 'd', 'e'])
                  Version({'id': id, 'label': 'Kampagnenbriefing Frühjahr, Fassung $id mit Änderungen', 'kind': 'pdf',
                    'status': 'parsed'}),
              ], comparisons: [
                for (final (id, e, l) in [('1', 'a', 'b'), ('2', 'a', 'c'), ('3', 'c', 'd'), ('4', 'd', 'c')])
                  Comparison({'id': id, 'earlier_id': e, 'later_id': l, 'scope': id == '1' ? 'complete' : 'partial',
                    'status': id == '2' ? 'failed' : 'partial'}),
              ]),
            ])), locale, theme));
            await tester.pumpAndSettle();
            noError(tester, 'timeline');
            await reachable(tester, 'version-e');

            // P7 summary: Back to the project pinned.
            await tester.pumpWidget(localized(ReviewSummaryScreen(report: summaryReport()), locale, theme));
            await tester.pumpAndSettle();
            noError(tester, 'summary');
            await reachable(tester, 'review-back-to-project', pinned: true);
            await reachable(tester, 'review-not-approval');
            await tester.pumpWidget(const SizedBox());
          });

          testWidgets('Demo wall, feedback form and the Settings demo row lay out: $name', (tester) async {
            tester.view.physicalSize = size;
            tester.view.devicePixelRatio = 1;
            tester.platformDispatcher.textScaleFactorTestValue = scale;
            addTearDown(tester.view.reset);
            addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
            final l = lookupAppLocalizations(Locale(locale));

            // The wall with every optional sentence: a comparison still running and the discount line.
            final wall = DemoBackend(demoJson(remaining: 0, inFlight: 1, discount: true));
            await tester.pumpWidget(localized(DemoWallScreen(demo: wall.controller()), locale, theme));
            await tester.pumpAndSettle();
            noError(tester, 'demo wall');
            await reachable(tester, 'demo-give-feedback', pinned: true);
            await reachable(tester, 'demo-wall-discount');
            await reachable(tester, 'demo-list-address');
            // A text button moved out to the text edge: checked at its centre once scrolled to.
            await tester.ensureVisible(find.byKey(const Key('demo-copy-link')));
            await tester.pumpAndSettle();
            expect(find.byKey(const Key('demo-copy-link')).hitTestable(), findsOneWidget);

            // The wall after feedback: the line that replaces the pill.
            await tester.pumpWidget(localized(DemoWallScreen(
              demo: DemoBackend(demoJson(remaining: 0, submitted: true)).controller()), locale, theme));
            await tester.pumpAndSettle();
            noError(tester, 'demo wall, feedback sent');
            await reachable(tester, 'demo-feedback-sent', pinned: true);

            // The form: empty, then the choice sheet, "Other" with its field, a price and a failed send.
            final backend = DemoBackend(demoJson(remaining: 0))..feedbackStatus = 500;
            await tester.pumpWidget(localized(DemoFeedbackScreen(demo: backend.controller()), locale, theme));
            await tester.pumpAndSettle();
            noError(tester, 'demo form');
            await reachable(tester, 'demo-send', pinned: true);
            await reachable(tester, 'demo-send-hint', pinned: true);
            await reachable(tester, 'demo-missing');
            await tester.tap(find.byKey(const Key('demo-missing')));
            await tester.pumpAndSettle();
            noError(tester, 'demo form, choice sheet');
            final other = find.text(l.demoMissingOther).last;
            await tester.ensureVisible(other);
            await tester.pumpAndSettle();
            await tester.tap(other);
            await tester.pumpAndSettle();
            noError(tester, 'demo form, other');
            await reachable(tester, 'demo-missing-other');
            await tester.enterText(find.byKey(const Key('demo-missing-other')),
              'Ein Export, den ich meinem Kunden schicken kann, mit allen Befunden und Belegstellen.');
            await reachable(tester, 'demo-missing-other-hint');
            await reachable(tester, 'demo-anything-else');
            await reachable(tester, 'demo-anything-else-hint');
            await reachable(tester, 'demo-plan');
            for (final code in ['eur_0', 'eur_over_15', 'not_sure']) {
              await reachable(tester, 'demo-price-$code');
            }
            await reachable(tester, 'demo-price-note');
            await tester.ensureVisible(find.byKey(const Key('demo-price-eur_over_15')));
            await tester.pumpAndSettle();
            await tester.tap(find.byKey(const Key('demo-price-eur_over_15')));
            await tester.pumpAndSettle();
            // With the error above it the pinned bar may scroll (large text): Send is reached by scrolling it.
            await tester.ensureVisible(find.byKey(const Key('demo-send')));
            await tester.pumpAndSettle();
            await tester.tap(find.byKey(const Key('demo-send')));
            await tester.pumpAndSettle();
            noError(tester, 'demo form, failed send');
            expect(find.byKey(const Key('demo-send-error')), findsOneWidget);
            await tester.ensureVisible(find.byKey(const Key('demo-send')));
            await tester.pumpAndSettle();
            expect(find.byKey(const Key('demo-send')).hitTestable(), findsOneWidget);

            // Sent: the line and Done.
            backend.feedbackStatus = 201;
            await tester.tap(find.byKey(const Key('demo-send')));
            await tester.pumpAndSettle();
            noError(tester, 'demo form, sent');
            await reachable(tester, 'demo-done', pinned: true);
            await reachable(tester, 'demo-feedback-sent');

            // Settings with the Demo section: the row, then the sent line.
            final h = AuthHarness()..storeSession();
            await h.session.restore();
            for (final submitted in [false, true]) {
              await tester.pumpWidget(localized(SettingsScreen(session: h.session,
                demo: DemoBackend(demoJson(remaining: 1, submitted: submitted)).controller(),
                consent: FakeConsent(), keychainProtection: () async => null), locale, theme));
              await tester.pumpAndSettle();
              noError(tester, 'settings with demo');
              await reachable(tester, submitted ? 'settings-demo-feedback-sent' : 'settings-demo-feedback');
              await reachable(tester, 'usage-events');
            }
            await tester.pumpWidget(const SizedBox());
          });
        }
      }
    }
  }
}
