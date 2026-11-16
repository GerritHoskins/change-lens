// I-18: the Logto client, native-provider sign-in through `POST /session`, `link_required`, the stored
// session on start, onboarding saves, sign-out and account deletion. Fakes only (fixtures/auth_fakes.dart).
import 'dart:convert';

import 'package:changelens/api.dart';
import 'package:changelens/auth/logto.dart';
import 'package:changelens/auth/providers.dart';
import 'package:changelens/auth/session.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;

import 'fixtures/auth_fakes.dart';

Map<String, dynamic> body(http.Request r) => jsonDecode(r.body) as Map<String, dynamic>;

void main() {
  group('Logto client', () {
    test('PKCE S256 matches RFC 7636 appendix B', () {
      expect(pkceChallenge('dBjftJeZ4CVP-mB92K27uhbUJU1p1r_wW1gFWFOEjXk'),
        'E9Melhoa2OwvFrEMTJguCHaoeK1t8URWbuGJSstw-cM');
    });

    test('sign-in asks for the API resource with PKCE and returns the API token from the refresh grant', () async {
      final h = AuthHarness();
      final tokens = await h.session.logto.signIn(extraParams: {'one_time_token': 'ott', 'login_hint': 'a@b.test'});
      final url = h.browser.urls.single;
      expect(url.origin + url.path, 'https://auth.test/oidc/auth');
      expect(url.queryParameters, containsPair('client_id', 'app-123'));
      expect(url.queryParameters, containsPair('redirect_uri', 'dev.changelens.app://callback'));
      expect(url.queryParameters, containsPair('resource', 'https://api.test'));
      expect(url.queryParameters, containsPair('code_challenge_method', 'S256'));
      expect(url.queryParameters['scope'], contains('offline_access'));
      expect(url.queryParameters, containsPair('one_time_token', 'ott'));
      expect(url.queryParameters, containsPair('login_hint', 'a@b.test'));
      final grants = h.server.to('auth.test', '/oidc/token').map((r) => r.bodyFields).toList();
      expect(grants.first['code_verifier'], isNotEmpty);
      expect(pkceChallenge(grants.first['code_verifier']!), url.queryParameters['code_challenge']);
      expect(grants.last, containsPair('grant_type', 'refresh_token'));
      expect(grants.last, containsPair('resource', 'https://api.test'));
      expect(tokens.accessToken, 'at-1');
      expect(tokens.refreshToken, 'rt-2'); // rotated by the resource grant
      expect(tokens.email, 'person@example.test');
    });

    test('a callback with another state is refused before any token request', () async {
      final h = AuthHarness()..browser.wrongState = true;
      await expectLater(h.session.logto.signIn(), throwsA(isA<AuthFailed>()));
      expect(h.server.to('auth.test', '/oidc/token'), isEmpty);
    });

    test('a refused refresh token is an ended session; a server error is not', () async {
      final h = AuthHarness();
      await expectLater(h.session.logto.refresh('unknown'), throwsA(isA<SessionExpired>()));
      h.server.refreshError = 'down';
      await expectLater(h.session.logto.refresh('rt'), throwsA(isA<AuthUnavailable>()));
    });
  });

  group('Apple nonce', () {
    test('Apple gets the lowercase hex SHA-256 of the raw nonce; the backend gets the raw one', () {
      // hashlib.sha256(b"abc").hexdigest(), as backend/tests/social_fixture.py apple_nonce computes it
      expect(appleNonceHash('abc'), 'ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad');
      expect(const ProviderCode('apple', 'c', nonce: 'raw').toJson(), {'provider': 'apple', 'code': 'c', 'nonce': 'raw'});
      expect(const ProviderCode('google', 'c').toJson(), {'provider': 'google', 'code': 'c'});
      final raw = randomToken(32);
      expect(RegExp(r'^[\x21-\x7e]{8,256}$').hasMatch(raw), isTrue); // backend _NONCE
    });
  });

  group('Session on start (03a P1, O-22)', () {
    test('no stored session: signed out, nothing requested', () async {
      final h = AuthHarness();
      await h.session.restore();
      expect(h.session.state, isA<SignedOut>());
      expect(h.server.requests, isEmpty);
    });

    test('a stored session refreshes, calls POST /session and carries the onboarding state', () async {
      final h = AuthHarness()..storeSession();
      h.server.onboarding = {'completed': false, 'step': 3};
      await h.session.restore();
      final state = h.session.state as SignedIn;
      expect(state.onboarding.completed, isFalse);
      expect(state.onboarding.step, 3);
      final session = h.server.to('api.test', '/session').single;
      expect(session.headers['Authorization'], 'Bearer at-1');
      expect(body(session), isEmpty);
      expect(h.store.values[AuthSession.refreshKey], 'rt-1'); // the rotated token replaces the old one
    });

    test('a refused refresh token returns to sign-in and forgets the session', () async {
      final h = AuthHarness()..storeSession();
      h.server.refreshError = 'invalid_grant';
      await h.session.restore();
      expect((h.session.state as SignedOut).reason, SignedOutReason.expired);
      expect(h.store.values[AuthSession.refreshKey], '');
    });

    test('a deleted account (401 from POST /session) returns to sign-in', () async {
      final h = AuthHarness()..storeSession();
      h.server.sessionStatus = 401;
      await h.session.restore();
      expect((h.session.state as SignedOut).reason, SignedOutReason.expired);
      expect(h.store.values[AuthSession.refreshKey], '');
    });

    test('Logto unreachable: offline, and the stored session is kept for a retry', () async {
      final h = AuthHarness()..storeSession();
      h.server.refreshError = 'down';
      await h.session.restore();
      expect(h.session.state, isA<AuthOffline>());
      expect(h.store.values[AuthSession.refreshKey], 'rt-stored');
      h.server.refreshError = null;
      await h.session.restore();
      expect(h.session.state, isA<SignedIn>());
    });
  });

  group('Sign-in', () {
    test('email: Logto sign-in, then POST /session; only the refresh token is stored', () async {
      final h = AuthHarness();
      await h.session.signInWithEmail();
      final state = h.session.state as SignedIn;
      expect(state.email, 'person@example.test');
      expect(h.browser.urls.single.queryParameters.containsKey('one_time_token'), isFalse);
      expect(h.store.values.keys, [AuthSession.refreshKey]);
      expect(h.store.values.values.single, startsWith('rt-'));
    });

    test('Google: the code goes to POST /session without a bearer, the one-time token to Logto', () async {
      final h = AuthHarness();
      await h.session.signInWithProvider(SignInMethod.google);
      final calls = h.server.to('api.test', '/session').toList();
      expect(calls.first.headers.containsKey('Authorization'), isFalse);
      expect(body(calls.first), {'provider': 'google', 'code': 'google-code'});
      final url = h.browser.urls.single;
      expect(url.queryParameters, containsPair('one_time_token', 'ott-1'));
      expect(url.queryParameters, containsPair('login_hint', 'person@example.test'));
      expect(calls.last.headers['Authorization'], startsWith('Bearer at-'));
      expect(h.session.state, isA<SignedIn>());
    });

    test('Apple sends the raw nonce with the code', () async {
      final h = AuthHarness();
      await h.session.signInWithProvider(SignInMethod.apple);
      expect(body(h.server.to('api.test', '/session').first),
        {'provider': 'apple', 'code': 'apple-code', 'nonce': 'raw-nonce-0123456789'});
    });

    test('cancelling the sheet or the browser changes nothing and shows no error', () async {
      final h = AuthHarness()..native.cancel = true;
      await h.session.restore();
      await h.session.signInWithProvider(SignInMethod.google);
      h.browser.cancel = true;
      await h.session.signInWithEmail();
      expect(h.session.state, isA<SignedOut>());
      expect(h.server.to('api.test', '/session'), isEmpty);
    });

    test('a refused code is rejected; an unavailable provider is retryable', () async {
      final h = AuthHarness()..server.providerStatus = 401;
      await expectLater(h.session.signInWithProvider(SignInMethod.google),
        throwsA(isA<AuthFailure>().having((e) => e.kind, 'kind', AuthFailureKind.rejected)));
      h.server.providerStatus = 503;
      await expectLater(h.session.signInWithProvider(SignInMethod.google),
        throwsA(isA<AuthFailure>().having((e) => e.kind, 'kind', AuthFailureKind.unavailable)));
      expect(h.browser.urls, isEmpty);
    });
  });

  group('link_required (O-19, AC-22, AC-26)', () {
    void linkRequired(AuthHarness h, List<String> methods) => h.server.providerAnswer = {
      'status': 'link_required', 'methods': methods, 'link_id': 'link-1'};

    test('a matching email signs nothing in until the existing method signs in; then the link completes', () async {
      final h = AuthHarness();
      linkRequired(h, ['email']);
      await h.session.signInWithProvider(SignInMethod.apple);
      final link = h.session.state as LinkRequired;
      expect(link.provider, SignInMethod.apple);
      expect(link.methods, [SignInMethod.email]);
      expect(h.browser.urls, isEmpty); // no Logto sign-in, nothing stored
      expect(h.store.values, isEmpty);

      await h.session.signInWithEmail();
      final completing = h.server.to('api.test', '/session').last;
      expect(body(completing), {'link_id': 'link-1'});
      expect(completing.headers['Authorization'], startsWith('Bearer at-'));
      expect(h.session.state, isA<SignedIn>());
    });

    test('the existing account can complete the link with its own provider', () async {
      final h = AuthHarness();
      linkRequired(h, ['email', 'google']);
      await h.session.signInWithProvider(SignInMethod.apple);
      h.server.providerAnswer = {'status': 'sign_in', 'one_time_token': 'ott-2', 'login_hint': 'p@x.test'};
      await h.session.signInWithProvider(SignInMethod.google);
      expect(body(h.server.to('api.test', '/session').last), {'link_id': 'link-1'});
      expect(h.session.state, isA<SignedIn>());
    });

    test('signing in as another account fails the link: signed out, tokens forgotten and revoked', () async {
      final h = AuthHarness();
      linkRequired(h, ['email']);
      await h.session.signInWithProvider(SignInMethod.google);
      h.server.sessionStatus = 401; // the backend: not the link's target
      await h.session.signInWithEmail();
      expect((h.session.state as SignedOut).reason, SignedOutReason.linkFailed);
      expect(h.store.values[AuthSession.refreshKey], '');
      expect(h.server.to('auth.test', '/oidc/token/revocation'), hasLength(1));
    });

    test('a method that is itself unlinked ends the link instead of chaining a second one', () async {
      final h = AuthHarness();
      linkRequired(h, ['email', 'google']);
      await h.session.signInWithProvider(SignInMethod.apple);
      await h.session.signInWithProvider(SignInMethod.google); // answers link_required again
      expect((h.session.state as SignedOut).reason, SignedOutReason.linkFailed);
    });

    test('cancel leaves the link step', () async {
      final h = AuthHarness();
      linkRequired(h, ['email']);
      await h.session.signInWithProvider(SignInMethod.google);
      h.session.cancelLink();
      expect(h.session.state, isA<SignedOut>());
    });
  });

  group('Signed in', () {
    Future<AuthHarness> signedIn() async {
      final h = AuthHarness()..storeSession();
      await h.session.restore();
      return h;
    }

    test('an expired access token is refreshed once for concurrent calls', () async {
      final h = await signedIn();
      h.session.clock = () => DateTime.now().add(const Duration(hours: 1));
      final tokens = await Future.wait([h.session.accessToken(), h.session.accessToken(), h.session.accessToken()]);
      expect(tokens.toSet(), {'at-2'});
      expect(h.server.to('auth.test', '/oidc/token'), hasLength(2)); // restore + one refresh
    });

    test('a 401 from the API whose session is gone returns to sign-in', () async {
      final h = await signedIn();
      h.server.projectsStatus = 401;
      h.server.sessionStatus = 401;
      await expectLater(h.session.api.projects(), throwsA(isA<ApiException>()));
      await pumpEventQueue();
      expect((h.session.state as SignedOut).reason, SignedOutReason.expired);
    });

    test('onboarding steps and completion are saved to the account (O-23)', () async {
      final h = await signedIn();
      await h.session.saveOnboardingStep(4);
      await h.session.completeOnboarding();
      expect(h.server.onboardingPuts, [{'step': 4}, {'completed': true}]);
      expect((h.session.state as SignedIn).onboarding.completed, isTrue);
    });

    test('sign-out forgets and revokes the refresh token', () async {
      final h = await signedIn();
      await h.session.signOut();
      await pumpEventQueue();
      expect((h.session.state as SignedOut).reason, SignedOutReason.signedOut);
      expect(h.store.values[AuthSession.refreshKey], '');
      expect(h.server.to('auth.test', '/oidc/token/revocation').single.bodyFields,
        containsPair('token_type_hint', 'refresh_token'));
    });

    for (final (status, reason) in [(204, SignedOutReason.accountDeleted), (202, SignedOutReason.deletionPending)]) {
      test('DELETE /me $status signs out with its notice', () async {
        final h = await signedIn();
        h.server.deleteStatus = status;
        await h.session.deleteAccount();
        expect(h.server.to('api.test', '/me').single.method, 'DELETE');
        expect((h.session.state as SignedOut).reason, reason);
        expect(h.store.values[AuthSession.refreshKey], '');
      });
    }

    test('a failed deletion keeps the account signed in', () async {
      final h = await signedIn();
      h.server.deleteStatus = 503;
      await expectLater(h.session.deleteAccount(), throwsA(isA<ApiException>()));
      expect(h.session.state, isA<SignedIn>());
      expect(h.store.values[AuthSession.refreshKey], isNotEmpty);
    });
  });
}
