// WP-A and WP-B on top of I-18: the Calm Bold sign-in (lockup, promise, topic chips, platform order,
// cancel announced without a banner, an error replacing the chips), the expired-session sheet over the
// current screen (draft kept; another account resets), the linkDone announcement, Settings, and the
// gated consent screen. Widget tests with fakes; not device evidence.
import 'package:changelens/auth/session.dart';
import 'package:changelens/l10n/app_localizations.dart';
import 'package:changelens/design/calm_theme.dart';
import 'package:changelens/screens/consent_screen.dart';
import 'package:changelens/screens/projects_screen.dart';
import 'package:changelens/screens/settings_screen.dart';
import 'package:changelens/screens/sign_in_screen.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'account_screens_test.dart' show pumpGate, tapKey;

List<String> announced(WidgetTester tester) => [for (final a in tester.takeAnnouncements()) a.message];

double top(WidgetTester tester, String key) => tester.getTopLeft(find.byKey(Key(key))).dy;

/// Signed in at Projects with a typed draft on a screen above it.
Future<dynamic> signedInWithDraft(WidgetTester tester, {String? lastMethod, String? subject}) async {
  final h = await pumpGate(tester, stored: true, onboarding: {'completed': true, 'step': null},
    before: (h) {
      if (lastMethod != null) h.store.values[AuthSession.lastMethodKey] = lastMethod;
      if (subject != null) h.server..jwtAccess = true..subject = subject;
    });
  Navigator.of(tester.element(find.byType(ProjectsScreen))).push(MaterialPageRoute<void>(
    builder: (_) => const Scaffold(body: TextField(key: Key('draft')))));
  await tester.pumpAndSettle();
  await tester.enterText(find.byKey(const Key('draft')), 'Pasted brief text');
  return h;
}

Future<void> expireSession(WidgetTester tester, dynamic h) async {
  h.server.projectsStatus = 401;
  h.server.sessionStatus = 401;
  await expectLater(h.session.api.projects(), throwsA(anything));
  await tester.pumpAndSettle();
  h.server.projectsStatus = 200;
  h.server.sessionStatus = 200;
}

void main() {
  group('Sign-in screen', () {
    testWidgets('Logo D lockup, the promise and the six topics; no separate sign-in headline', (tester) async {
      await pumpGate(tester);
      expect(find.bySemanticsLabel('ChangeLens'), findsOneWidget);
      expect(find.text('What changed, and which changes matter?'), findsOneWidget);
      expect(find.byKey(const Key('sign-in-topics')), findsOneWidget);
      for (final topic in ['Deadlines', 'Budget']) {
        expect(find.descendant(of: find.byKey(const Key('sign-in-topics')), matching: find.text(topic)), findsOneWidget);
      }
      expect(find.text('Sign in to ChangeLens'), findsNothing);
    });

    testWidgets('Android order: Google, Apple, email, all the same height', (tester) async {
      await pumpGate(tester);
      expect(top(tester, 'sign-in-google'), lessThan(top(tester, 'sign-in-apple')));
      expect(top(tester, 'sign-in-apple'), lessThan(top(tester, 'sign-in-email')));
      final heights = {for (final k in ['sign-in-google', 'sign-in-apple', 'sign-in-email'])
        tester.getSize(find.byKey(Key(k))).height};
      expect(heights, {CalmSize.buttonMain});
    });

    testWidgets('iOS order: Apple, Google, email', (tester) async {
      debugDefaultTargetPlatformOverride = TargetPlatform.iOS;
      try {
        await pumpGate(tester);
        expect(top(tester, 'sign-in-apple'), lessThan(top(tester, 'sign-in-google')));
        expect(top(tester, 'sign-in-google'), lessThan(top(tester, 'sign-in-email')));
      } finally {
        debugDefaultTargetPlatformOverride = null;
      }
    });

    testWidgets('Cancelled: announced, no banner; signing in is announced', (tester) async {
      final h = await pumpGate(tester);
      tester.takeAnnouncements();
      h.native.cancel = true;
      await tapKey(tester, 'sign-in-google');
      expect(announced(tester), ['Signing in…', 'Sign-in with Google was cancelled. Choose a method to try again.']);
      expect(find.byKey(const Key('sign-in-error')), findsNothing);
      expect(find.byKey(const Key('sign-in-topics')), findsOneWidget);
    });

    testWidgets('An error replaces the topic chips', (tester) async {
      final h = await pumpGate(tester);
      h.server.providerStatus = 503;
      await tapKey(tester, 'sign-in-google');
      expect(find.byKey(const Key('sign-in-error')), findsOneWidget);
      expect(find.byKey(const Key('sign-in-topics')), findsNothing);
    });

    testWidgets('German copy', (tester) async {
      await pumpGate(tester, locale: const Locale('de'));
      expect(find.text('Was hat sich geändert, und was davon ist wichtig?'), findsOneWidget);
    });

    testWidgets('A completed link is announced once', (tester) async {
      final h = await pumpGate(tester);
      h.server.providerAnswer = {'status': 'link_required', 'methods': ['email'], 'link_id': 'link-1'};
      await tapKey(tester, 'sign-in-google');
      tester.takeAnnouncements();
      await tapKey(tester, 'sign-in-email');
      expect(announced(tester), contains('Google is now linked to your account.'));
    });
  });

  group('Expired session', () {
    testWidgets('a sheet over the current screen keeps the draft and closes after signing in', (tester) async {
      final h = await signedInWithDraft(tester, lastMethod: 'google', subject: 'user-a');
      await expireSession(tester, h);
      expect(find.byType(SessionExpiredSheet), findsOneWidget);
      expect(find.text('You last signed in with Google.'), findsOneWidget);
      // Last-used method first, the others behind a text button.
      expect(find.byKey(const Key('sign-in-google')), findsOneWidget);
      expect(find.byKey(const Key('sign-in-email')), findsNothing);
      // Can't be dismissed: system back and the barrier leave it up.
      await tester.binding.handlePopRoute();
      await tester.pumpAndSettle();
      expect(find.byType(SessionExpiredSheet), findsOneWidget);
      await tapKey(tester, 'session-other-methods');
      expect(find.byKey(const Key('sign-in-email')), findsOneWidget);

      await tapKey(tester, 'sign-in-email');
      expect(find.byType(SessionExpiredSheet), findsNothing);
      expect(h.session.state, isA<SignedIn>());
      expect(find.text('Pasted brief text'), findsOneWidget); // same screen, same in-memory draft
    });

    testWidgets('another account signing in resets to its Projects, without the draft', (tester) async {
      final h = await signedInWithDraft(tester, subject: 'user-a');
      await expireSession(tester, h);
      h.server.subject = 'user-b';
      await tapKey(tester, 'sign-in-google');
      expect(find.byType(SessionExpiredSheet), findsNothing);
      expect(find.text('Pasted brief text'), findsNothing);
      expect(find.byType(ProjectsScreen), findsOneWidget);
    });

    testWidgets('Sign out leaves to the sign-in screen', (tester) async {
      final h = await signedInWithDraft(tester);
      await expireSession(tester, h);
      await tapKey(tester, 'session-sign-out');
      expect(find.byType(SessionExpiredSheet), findsNothing);
      expect(find.byType(SignInScreen), findsOneWidget);
      expect(find.text('Pasted brief text'), findsNothing);
    });
  });

  group('Settings', () {
    testWidgets('Projects menu → Settings: account, method, sign-out, delete; no Privacy without D-18', (tester) async {
      await pumpGate(tester, stored: true, onboarding: {'completed': true, 'step': null},
        before: (h) => h.store.values[AuthSession.lastMethodKey] = 'apple');
      await tapKey(tester, 'projects-menu');
      expect(find.text('Settings'), findsOneWidget);
      await tapKey(tester, 'account');
      expect(find.byType(SettingsScreen), findsOneWidget);
      expect(find.text('Account'), findsOneWidget);
      expect(find.text('Signed in with Apple'), findsOneWidget);
      expect(find.byKey(const Key('sign-out')), findsOneWidget);
      expect(find.byKey(const Key('delete-account')), findsOneWidget);
      expect(find.text('Privacy'), findsNothing);
      expect(find.byKey(const Key('usage-events')), findsNothing);
    });

    testWidgets('with an account consent the Privacy switch reflects and saves it', (tester) async {
      final h = await pumpGate(tester, stored: true, onboarding: {'completed': true, 'step': null});
      final consent = FakeConsent()..allowed = true;
      tester.view.physicalSize = const Size(390, 1200);
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      await pumpLocalized(tester, SettingsScreen(session: h.session, consent: consent));
      expect(find.text('Privacy'), findsOneWidget);
      await tester.ensureVisible(find.byKey(const Key('usage-events')));
      await tester.tap(find.byKey(const Key('usage-events')));
      await tester.pumpAndSettle();
      expect(consent.answers, [false]);
      consent.fail = true;
      await tester.tap(find.byKey(const Key('usage-events')));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('usage-events-error')), findsOneWidget);
    });
  });

  group('Consent (gated until D-18)', () {
    for (final locale in ['en', 'de']) {
      testWidgets('two identical pills, nothing chosen, no Back; an answer is stored then done ($locale)', (tester) async {
        final consent = FakeConsent();
        var done = 0;
        await pumpLocalized(tester, ConsentScreen(consent: consent, onDone: () => done++), locale: Locale(locale));
        final allow = tester.getSize(find.byKey(const Key('consent-allow')));
        expect(tester.getSize(find.byKey(const Key('consent-decline'))), allow);
        expect(allow.height, CalmSize.buttonMain);
        expect(find.byType(FilledButton), findsNothing); // no black main pill here
        expect(consent.answers, isEmpty);
        await tester.tap(find.byKey(const Key('consent-decline')));
        await tester.pumpAndSettle();
        expect(consent.answers, [false]);
        expect(done, 1);
      });
    }

    testWidgets('a failed save keeps the screen with an error', (tester) async {
      final consent = FakeConsent()..fail = true;
      var done = 0;
      await pumpLocalized(tester, ConsentScreen(consent: consent, onDone: () => done++));
      await tester.tap(find.byKey(const Key('consent-allow')));
      await tester.pumpAndSettle();
      expect(find.byKey(const Key('consent-error')), findsOneWidget);
      expect(done, 0);
    });
  });
}

class FakeConsent extends ChangeNotifier implements UsageConsent {
  @override
  bool? allowed;
  bool fail = false;
  final answers = <bool>[];

  @override
  Future<void> answer(bool allow) async {
    if (fail) throw Exception('offline');
    answers.add(allow);
    allowed = allow;
    notifyListeners();
  }
}

Future<void> pumpLocalized(WidgetTester tester, Widget home, {Locale locale = const Locale('en')}) async {
  await tester.pumpWidget(MaterialApp(locale: locale, theme: calmTheme(Brightness.light),
    localizationsDelegates: AppLocalizations.localizationsDelegates,
    supportedLocales: AppLocalizations.supportedLocales, home: home));
  await tester.pumpAndSettle();
}
