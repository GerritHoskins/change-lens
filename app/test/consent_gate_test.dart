// The usage-events consent in the app (D-18 tier B; Task 2): the first-launch order sign-in → onboarding
// → consent → Projects behind the consent flag (off until the I-20 legal review), and withdrawal in
// Settings. Widget tests with fakes; not device evidence.
import 'package:changelens/screens/consent_screen.dart';
import 'package:changelens/screens/onboarding_screen.dart';
import 'package:changelens/screens/projects_screen.dart';
import 'package:changelens/screens/settings_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'account_screens_test.dart' show pumpGate, tapKey;

const done = {'completed': true, 'step': null};

Future<void> openSettings(WidgetTester tester) async {
  await tapKey(tester, 'projects-menu');
  await tapKey(tester, 'account');
  expect(find.byType(SettingsScreen), findsOneWidget);
}

void main() {
  group('with the consent flag on', () {
    testWidgets('an unanswered account sees consent before Projects; Allow saves and opens Projects', (tester) async {
      final h = await pumpGate(tester, stored: true, onboarding: done, consentFlow: true);
      expect(find.byType(ConsentScreen), findsOneWidget);
      expect(find.byType(ProjectsScreen), findsNothing);
      await tapKey(tester, 'consent-allow');
      expect(h.server.consentPuts, [{'granted': true, 'policy_version': '2026-11-13'}]);
      expect(find.byType(ConsentScreen), findsNothing);
      expect(find.byType(ProjectsScreen), findsOneWidget);
    });

    testWidgets('Decline is an answer too: saved, then Projects', (tester) async {
      final h = await pumpGate(tester, stored: true, onboarding: done, consentFlow: true);
      await tapKey(tester, 'consent-decline');
      expect(h.server.consent, isFalse);
      expect(find.byType(ProjectsScreen), findsOneWidget);
    });

    testWidgets('a failed save keeps the consent screen with an error', (tester) async {
      final h = await pumpGate(tester, stored: true, onboarding: done, consentFlow: true,
        before: (h) => h.server.consentStatus = 500);
      await tapKey(tester, 'consent-allow');
      expect(find.byKey(const Key('consent-error')), findsOneWidget);
      expect(find.byType(ProjectsScreen), findsNothing);
      expect(h.server.consent, isNull);
    });

    testWidgets('an answered account goes straight to Projects', (tester) async {
      await pumpGate(tester, stored: true, onboarding: done, consentFlow: true,
        before: (h) => h.server.consent = false);
      expect(find.byType(ConsentScreen), findsNothing);
      expect(find.byType(ProjectsScreen), findsOneWidget);
    });

    testWidgets('onboarding comes first, then consent', (tester) async {
      await pumpGate(tester, stored: true, onboarding: {'completed': false, 'step': 2}, consentFlow: true);
      expect(find.byType(OnboardingScreen), findsOneWidget);
      expect(find.byType(ConsentScreen), findsNothing);
      await tapKey(tester, 'onb-skip');
      expect(find.byType(ConsentScreen), findsOneWidget);
    });

    testWidgets('Settings shows the Privacy switch with the account answer; turning it off withdraws', (tester) async {
      tester.view.physicalSize = const Size(390, 1200); // the whole Settings list on screen
      tester.view.devicePixelRatio = 1;
      addTearDown(tester.view.reset);
      final h = await pumpGate(tester, stored: true, onboarding: done, consentFlow: true,
        before: (h) => h.server.consent = true);
      await openSettings(tester);
      expect(find.text('Privacy'), findsOneWidget);
      final toggle = find.byKey(const Key('usage-events'));
      await tester.ensureVisible(toggle);
      expect(tester.widget<SwitchListTile>(toggle).value, isTrue);
      await tester.tap(toggle);
      await tester.pumpAndSettle();
      expect(h.server.consentPuts.single['granted'], isFalse);
      expect(tester.widget<SwitchListTile>(toggle).value, isFalse);
    });
  });

  group('with the consent flag off (default until legal review)', () {
    testWidgets('an unanswered account goes straight to Projects and nothing is sent', (tester) async {
      final h = await pumpGate(tester, stored: true, onboarding: done);
      expect(find.byType(ConsentScreen), findsNothing);
      expect(find.byType(ProjectsScreen), findsOneWidget);
      expect(h.server.requests.where((r) => r.url.path == '/me/consent'), isEmpty);
    });

    testWidgets('Settings has no Privacy section', (tester) async {
      await pumpGate(tester, stored: true, onboarding: done);
      await openSettings(tester);
      expect(find.text('Privacy'), findsNothing);
      expect(find.byKey(const Key('usage-events')), findsNothing);
    });
  });
}
