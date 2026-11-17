// Usage-events consent on the account (D-18 tier B; Task 2): the answer `POST /session` carries, and
// answering through `PUT /me/consent` with the policy version the server names. Fakes only, no network.
import 'dart:convert';

import 'package:changelens/auth/account_consent.dart';
import 'package:changelens/auth/session.dart';
import 'package:flutter_test/flutter_test.dart';

import 'fixtures/auth_fakes.dart';

Future<AuthHarness> signedIn({bool? consent, Map<String, dynamic>? onboarding}) async {
  final h = AuthHarness()..storeSession();
  h.server.consent = consent;
  h.server.onboarding = onboarding ?? {'completed': true, 'step': null};
  await h.session.restore();
  expect(h.session.state, isA<SignedIn>());
  return h;
}

bool? stateConsent(AuthHarness h) => (h.session.state as SignedIn).consent;

void main() {
  group('the session carries the answer', () {
    test('unanswered reads as null', () async {
      final h = await signedIn();
      expect(stateConsent(h), isNull);
      expect(AccountConsent(h.session).allowed, isNull);
    });

    for (final answer in [true, false]) {
      test('an answer ($answer) is read from POST /session', () async {
        final h = await signedIn(consent: answer);
        expect(stateConsent(h), answer);
        expect(AccountConsent(h.session).allowed, answer);
      });
    }

    test('completing onboarding keeps the consent answer', () async {
      final h = await signedIn(consent: false, onboarding: {'completed': false, 'step': 2});
      await h.session.completeOnboarding();
      expect(stateConsent(h), isFalse);
    });
  });

  group('answering', () {
    test('sends the policy version the server names and updates the session', () async {
      final h = await signedIn();
      h.server.policyVersion = '2027-01-01';
      final consent = AccountConsent(h.session);
      var notified = 0;
      consent.addListener(() => notified++);
      await consent.answer(true);
      expect(h.server.consentPuts, [{'granted': true, 'policy_version': '2027-01-01'}]);
      expect(consent.allowed, isTrue);
      expect(stateConsent(h), isTrue);
      expect(notified, greaterThan(0));
    });

    test('withdrawal is the same call with false', () async {
      final h = await signedIn(consent: true);
      await AccountConsent(h.session).answer(false);
      expect(h.server.consentPuts.single['granted'], isFalse);
      expect(stateConsent(h), isFalse);
    });

    test('a policy change between reading and answering is retried once with the new version', () async {
      final h = await signedIn();
      h.server.consentStatus = 409;
      await AccountConsent(h.session).answer(true);
      expect(h.server.consentPuts.length, 2);
      expect(stateConsent(h), isTrue);
    });

    test('a failed save throws and leaves the answer unchanged', () async {
      final h = await signedIn();
      h.server.consentStatus = 500;
      await expectLater(AccountConsent(h.session).answer(true), throwsA(isA<Exception>()));
      expect(stateConsent(h), isNull);
    });

    test('no consent request carries document content or anything but the answer', () async {
      final h = await signedIn();
      await AccountConsent(h.session).answer(false);
      final put = h.server.requests.lastWhere((r) => r.method == 'PUT');
      expect((jsonDecode(put.body) as Map).keys, ['usage_events']);
    });
  });
}
