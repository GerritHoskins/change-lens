// I-18 screens: the first-launch gate (sign-in → onboarding until completed → Projects; O-23), the
// sign-in methods per platform, the link_required prompt (AC-26), errors and notices, and in-app account
// deletion (Apple 5.1.1(v)). Widget tests with fakes; not device evidence.
import 'package:changelens/design/calm_widgets.dart';
import 'package:changelens/auth/session.dart';
import 'package:changelens/main.dart';
import 'package:changelens/screens/onboarding_screen.dart';
import 'package:changelens/screens/projects_screen.dart';
import 'package:changelens/services.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fixtures/auth_fakes.dart';

class NoPicker implements DocumentPicker {
  @override
  Future<PickedDocument?> pickPdf() async => null;

  @override
  Future<void> purge() async {}
}

/// A tall view at the app's 600 px content cap. The default 800×600 test surface is wider than the cap,
/// and the test font is wider than Roboto, so tests that need all sign-in methods built use this.
void tallView(WidgetTester tester) {
  tester.view.physicalSize = const Size(600, 1600);
  tester.view.devicePixelRatio = 1;
  addTearDown(tester.view.reset);
}

Future<AuthHarness> pumpGate(WidgetTester tester, {bool stored = false, Map<String, dynamic>? onboarding,
    bool apple = true, Locale locale = const Locale('en'), void Function(AuthHarness)? before,
    bool consentFlow = false}) async {
  final h = AuthHarness();
  h.native.appleAvailable = apple;
  if (stored) h.storeSession();
  if (onboarding != null) h.server.onboarding = onboarding;
  before?.call(h);
  final services = Services(h.store, NoPicker(), auth: h.session, consentFlow: consentFlow);
  await tester.pumpWidget(ChangeLensApp(services: services, locale: locale));
  await h.session.restore();
  await tester.pumpAndSettle();
  return h;
}

Future<void> tapKey(WidgetTester tester, String key) async {
  await tester.ensureVisible(find.byKey(Key(key)));
  await tester.tap(find.byKey(Key(key)));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('Signed out: Apple, Google and email on iOS; no Apple on Android', (tester) async {
    tallView(tester);
    await pumpGate(tester);
    expect(find.text('What changed, and which changes matter?'), findsOneWidget);
    for (final key in ['sign-in-apple', 'sign-in-google', 'sign-in-email']) {
      expect(find.byKey(Key(key)), findsOneWidget);
    }
    expect(find.text('Developer settings'), findsNothing);

    await pumpGate(tester, apple: false);
    expect(find.byKey(const Key('sign-in-apple')), findsNothing);
    expect(find.byKey(const Key('sign-in-google')), findsOneWidget);
  });

  testWidgets('First launch: sign-in, then onboarding saving each step, then Projects on Start', (tester) async {
    tallView(tester);
    final h = await pumpGate(tester);
    await tapKey(tester, 'sign-in-email');
    expect(find.byType(OnboardingScreen), findsOneWidget);
    expect(find.text('Step 1 of 6'), findsOneWidget);
    await tapKey(tester, 'onb-main');
    await tapKey(tester, 'onb-main');
    expect(h.server.onboardingPuts, [{'step': 2}, {'step': 3}]);
    await tapKey(tester, 'onb-back');
    expect(h.server.onboardingPuts.last, {'step': 2});
    for (var i = 0; i < 4; i++) {
      await tapKey(tester, 'onb-main');
    }
    expect(find.text('Step 6 of 6'), findsOneWidget);
    await tapKey(tester, 'onb-main'); // Start
    expect(h.server.onboardingPuts.last, {'completed': true});
    expect(find.byType(ProjectsScreen), findsOneWidget);
  });

  testWidgets('A returning account resumes onboarding at its saved step; Skip completes it', (tester) async {
    final h = await pumpGate(tester, stored: true, onboarding: {'completed': false, 'step': 4});
    expect(find.text('Step 4 of 6'), findsOneWidget);
    await tapKey(tester, 'onb-skip');
    expect(h.server.onboardingPuts, [{'completed': true}]);
    expect(find.byType(ProjectsScreen), findsOneWidget);
  });

  testWidgets('A saved step beyond the current design resumes at the last step', (tester) async {
    await pumpGate(tester, stored: true, onboarding: {'completed': false, 'step': 30});
    expect(find.text('Step 6 of 6'), findsOneWidget);
  });

  testWidgets('A completed account opens Projects; its menu has Account, not developer settings', (tester) async {
    await pumpGate(tester, stored: true, onboarding: {'completed': true, 'step': null});
    expect(find.byType(ProjectsScreen), findsOneWidget);
    await tapKey(tester, 'projects-menu');
    expect(find.byKey(const Key('account')), findsOneWidget);
    expect(find.byKey(const Key('settings')), findsNothing);
  });

  testWidgets('link_required asks for the existing method only, then links on its sign-in', (tester) async {
    final h = await pumpGate(tester);
    h.server.providerAnswer = {'status': 'link_required', 'methods': ['email'], 'link_id': 'link-1'};
    await tapKey(tester, 'sign-in-google');
    expect(find.text('You already have an account'), findsOneWidget);
    expect(find.textContaining('To add Google sign-in'), findsOneWidget);
    expect(find.byKey(const Key('sign-in-email')), findsOneWidget);
    expect(find.byKey(const Key('sign-in-google')), findsNothing);
    expect(find.byKey(const Key('sign-in-apple')), findsNothing);

    await tapKey(tester, 'sign-in-email');
    expect(h.server.to('api.test', '/session').last.body, '{"link_id":"link-1"}');
    expect(find.byType(OnboardingScreen), findsOneWidget);
  });

  testWidgets('link_required: cancel returns to every method; a failed link shows its notice', (tester) async {
    final h = await pumpGate(tester);
    h.server.providerAnswer = {'status': 'link_required', 'methods': ['email'], 'link_id': 'link-1'};
    await tapKey(tester, 'sign-in-apple');
    await tapKey(tester, 'link-cancel');
    expect(find.text('What changed, and which changes matter?'), findsOneWidget);

    await tapKey(tester, 'sign-in-apple');
    h.server.sessionStatus = 401;
    await tapKey(tester, 'sign-in-email');
    expect(find.textContaining("The accounts weren't linked"), findsOneWidget);
    expect(tester.widget<CalmWarning>(find.byKey(const Key('sign-in-notice'))).kind, CalmMessageKind.warning);
  });

  testWidgets('Errors: unavailable and rejected sign-ins say so; a cancel says nothing', (tester) async {
    final h = await pumpGate(tester);
    h.server.providerStatus = 503;
    await tapKey(tester, 'sign-in-google');
    expect(find.textContaining("isn't reachable"), findsOneWidget);
    h.server.providerStatus = 401;
    await tapKey(tester, 'sign-in-google');
    expect(find.textContaining("can't be used for a ChangeLens account"), findsOneWidget);
    h.native.cancel = true;
    await tapKey(tester, 'sign-in-google');
    expect(find.byKey(const Key('sign-in-error')), findsNothing);
  });

  testWidgets('An ended session on start shows the expired notice', (tester) async {
    final h = AuthHarness();
    h.storeSession();
    h.server.refreshError = 'invalid_grant';
    final services = Services(h.store, NoPicker(), auth: h.session);
    await tester.pumpWidget(ChangeLensApp(services: services, locale: const Locale('en')));
    await h.session.restore();
    await tester.pumpAndSettle();
    expect(find.text('Your session ended. Sign in again to continue.'), findsOneWidget);
    expect(tester.widget<CalmWarning>(find.byKey(const Key('sign-in-notice'))).kind, CalmMessageKind.warning);
  });

  testWidgets('Offline on start keeps the session and retries', (tester) async {
    final h = AuthHarness();
    h.storeSession();
    h.server.refreshError = 'down';
    final services = Services(h.store, NoPicker(), auth: h.session);
    await tester.pumpWidget(ChangeLensApp(services: services, locale: const Locale('en')));
    await h.session.restore();
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('session-offline')), findsOneWidget);
    h.server.refreshError = null;
    h.server.onboarding = {'completed': true, 'step': null};
    await tapKey(tester, 'session-retry');
    expect(find.byType(ProjectsScreen), findsOneWidget);
  });

  for (final platform in [TargetPlatform.iOS, TargetPlatform.android]) {
    testWidgets('Account deletion on ${platform.name}: confirm, DELETE /me, back to sign-in with the notice',
        (tester) async {
      debugDefaultTargetPlatformOverride = platform;
      try {
        final h = await pumpGate(tester, stored: true, onboarding: {'completed': true, 'step': null});
        await tapKey(tester, 'projects-menu');
        await tapKey(tester, 'account');
        expect(find.text('Account'), findsWidgets);
        await tapKey(tester, 'delete-account');
        expect(find.text('Delete your account?'), findsOneWidget);
        await tapKey(tester, 'confirm-delete-account');
        expect(h.server.to('api.test', '/me').single.method, 'DELETE');
        expect(find.text('Your account and all its projects were deleted.'), findsOneWidget);
        expect(find.byType(ProjectsScreen), findsNothing);
        expect(h.store.values[AuthSession.refreshKey], '');
      } finally {
        debugDefaultTargetPlatformOverride = null;
      }
    });
  }

  testWidgets('Account deletion that fails stays on the account screen with an error', (tester) async {
    final h = await pumpGate(tester, stored: true, onboarding: {'completed': true, 'step': null});
    h.server.deleteStatus = 503;
    await tapKey(tester, 'projects-menu');
    await tapKey(tester, 'account');
    await tapKey(tester, 'delete-account');
    await tapKey(tester, 'confirm-delete-account');
    expect(find.byKey(const Key('delete-account-error')), findsOneWidget);
  });

  testWidgets('Sign-out from the account screen returns to sign-in', (tester) async {
    await pumpGate(tester, stored: true, onboarding: {'completed': true, 'step': null});
    await tapKey(tester, 'projects-menu');
    await tapKey(tester, 'account');
    expect(find.text("You're signed in."), findsOneWidget); // a refresh on start carries no ID token here
    await tapKey(tester, 'sign-out');
    expect(find.text("You're signed out."), findsOneWidget);
    expect(tester.widget<CalmWarning>(find.byKey(const Key('sign-in-notice'))).kind, CalmMessageKind.info);
  });
}
