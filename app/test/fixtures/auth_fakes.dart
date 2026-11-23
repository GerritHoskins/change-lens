// Fakes for I-18: Logto (authorize + token endpoints), the API's `POST /session`, `/me/onboarding`,
// `/me/consent` (D-18) and `DELETE /me`, the system browser and the native Google and Apple sheets. No test reaches a network.
import 'dart:convert';

import 'package:changelens/auth/logto.dart';
import 'package:changelens/auth/providers.dart';
import 'package:changelens/auth/session.dart';
import 'package:changelens/services.dart';
import 'package:http/http.dart' as http;

const config = AuthConfig(apiBase: 'https://api.test', logtoEndpoint: 'https://auth.test', appId: 'app-123');

class MemoryStore implements SettingsStore {
  final values = <String, String>{};

  @override
  Future<String?> read(String key) async => values[key];

  @override
  Future<void> write(String key, String value) async => values[key] = value;
}

/// Logto plus the API, in one transport.
class FakeServer {
  final requests = <http.Request>[];

  // Logto
  int refreshCounter = 0, accessCounter = 0;
  int expiresIn = 900;
  bool jwtAccess = false; // access tokens shaped like Logto's JWTs (claims iat and exp)
  String? subject; // with jwtAccess: the account's `sub` claim
  String? refreshError; // 'invalid_grant' or 'down'
  final validRefresh = <String>{};
  final pendingCodes = <String>{};

  // API
  Map<String, dynamic> onboarding = {'completed': false, 'step': null};
  final onboardingPuts = <Map<String, dynamic>>[];
  int sessionStatus = 200; // bearer POST /session
  Map<String, dynamic> providerAnswer = {
    'status': 'sign_in', 'one_time_token': 'ott-1', 'login_hint': 'person@example.test', 'expires_in': 120,
  };
  int providerStatus = 200;
  int deleteStatus = 204;
  // Usage-events consent (D-18 tier B): the answer for [policyVersion]; null until answered.
  bool? consent;
  String policyVersion = '2026-11-13';
  final consentPuts = <Map<String, dynamic>>[];
  int consentStatus = 200; // PUT /me/consent; 409 answers policy_version_stale once
  int projectsStatus = 200;
  // The demo state `POST /session` carries (docs/demo-wall-handoff.md); null = an older server sends none.
  Map<String, dynamic>? demo;

  String issueCode() {
    final code = 'code-${pendingCodes.length + 1}';
    pendingCodes.add(code);
    return code;
  }

  String _refresh() {
    final token = 'rt-${++refreshCounter}';
    validRefresh.add(token);
    return token;
  }

  static String _b64(Object claims) => base64Url.encode(utf8.encode(jsonEncode(claims))).replaceAll('=', '');

  static String idToken(String email) => 'e30.${_b64({'email': email})}.sig';

  http.Response _json(Object body, [int status = 200]) =>
      http.Response(jsonEncode(body), status, headers: {'content-type': 'application/json'});

  Future<http.Response> handle(http.Request r) async {
    requests.add(r);
    final path = r.url.path;
    if (r.url.host == 'auth.test') {
      if (path == '/oidc/token/revocation') return http.Response('', 200);
      if (path != '/oidc/token') return http.Response('', 404);
      final form = r.bodyFields;
      if (form['grant_type'] == 'authorization_code') {
        if (!pendingCodes.remove(form['code'])) return _json({'error': 'invalid_grant'}, 400);
        return _json({'refresh_token': _refresh(), 'id_token': idToken('person@example.test'),
          'access_token': 'opaque', 'expires_in': 3600});
      }
      if (refreshError == 'down') return http.Response('', 502);
      if (refreshError != null || !validRefresh.remove(form['refresh_token'])) {
        return _json({'error': 'invalid_grant'}, 400);
      }
      final id = ++accessCounter;
      final access = jwtAccess ? 'at-$id.${_b64({'iat': 1000, 'exp': 1000 + expiresIn, 'sub': ?subject})}.sig' : 'at-$id';
      return _json({'access_token': access, 'refresh_token': _refresh(), 'expires_in': expiresIn});
    }
    final bearer = r.headers['Authorization'];
    if (r.method == 'POST' && path == '/session') {
      if (bearer == null) {
        if (providerStatus != 200) return _json({'code': 'unauthenticated'}, providerStatus);
        return _json(providerAnswer);
      }
      if (sessionStatus != 200) return _json({'code': 'unauthenticated'}, sessionStatus);
      return _json({'status': 'active', 'onboarding': onboarding, 'consent': {'usage_events': consent},
        'demo': ?demo});
    }
    if (bearer == null || !bearer.startsWith('Bearer at-')) return _json({'code': 'unauthenticated'}, 401);
    if (path == '/me/onboarding' && r.method == 'GET') return _json(onboarding);
    if (path == '/me/onboarding' && r.method == 'PUT') {
      final body = jsonDecode(r.body) as Map<String, dynamic>;
      onboardingPuts.add(body);
      onboarding = body['completed'] == true ? {'completed': true, 'step': null} : {'completed': false, 'step': body['step']};
      return _json(onboarding);
    }
    if (path == '/me/consent' && r.method == 'GET') return _json(_consentBody());
    if (path == '/me/consent' && r.method == 'PUT') {
      final body = (jsonDecode(r.body) as Map<String, dynamic>)['usage_events'] as Map<String, dynamic>;
      consentPuts.add(body);
      if (consentStatus == 409) {
        consentStatus = 200;
        return _json({'code': 'policy_version_stale'}, 409);
      }
      if (consentStatus != 200) return _json({'code': 'internal_error'}, consentStatus);
      if (body['policy_version'] != policyVersion) return _json({'code': 'policy_version_stale'}, 409);
      consent = body['granted'] as bool;
      return _json(_consentBody());
    }
    if (path == '/me' && r.method == 'DELETE') {
      return deleteStatus >= 300 ? _json({'code': 'unavailable'}, deleteStatus) : http.Response('', deleteStatus);
    }
    if (path == '/projects') {
      return projectsStatus == 200 ? _json({'projects': []}) : _json({'code': 'unauthenticated'}, projectsStatus);
    }
    return _json({'code': 'not_found'}, 404);
  }

  Map<String, dynamic> _consentBody() => {'usage_events': {
    'granted': consent, 'policy_version': policyVersion, 'decided_at': consent == null ? null : '2026-11-16T10:00:00+00:00'}};

  Iterable<http.Request> to(String host, String path) =>
      requests.where((r) => r.url.host == host && r.url.path == path);
}

/// The system browser: answers Logto's authorize URL with a code and the same state.
class FakeBrowser implements WebAuthenticator {
  FakeBrowser(this.server);

  final FakeServer server;
  final urls = <Uri>[];
  bool cancel = false;
  bool wrongState = false;

  /// The browser could not be opened; the code as [SystemWebAuthenticator] reports it.
  String? failCode;

  @override
  Future<String> authenticate(Uri url, String callbackScheme) async {
    urls.add(url);
    if (cancel) throw AuthCancelled();
    if (failCode != null) throw AuthFailed(failCode!);
    final state = wrongState ? 'other' : url.queryParameters['state'];
    return '${config.redirectUri}?code=${server.issueCode()}&state=$state';
  }
}

class FakeNative implements NativeSignIn {
  @override
  bool appleAvailable = true;
  bool cancel = false;
  int googleCalls = 0, appleCalls = 0;

  @override
  Future<ProviderCode> google() async {
    googleCalls++;
    if (cancel) throw AuthCancelled();
    return const ProviderCode('google', 'google-code');
  }

  @override
  Future<ProviderCode> apple() async {
    appleCalls++;
    if (cancel) throw AuthCancelled();
    return const ProviderCode('apple', 'apple-code', nonce: 'raw-nonce-0123456789');
  }
}

class AuthHarness {
  AuthHarness() {
    browser = FakeBrowser(server);
    final client = MockHttp(server.handle);
    session = AuthSession(config, store, logto: LogtoClient(config, client: client, browser: browser),
      native: native, client: client);
  }

  final server = FakeServer();
  final store = MemoryStore();
  final native = FakeNative();
  late final FakeBrowser browser;
  late final AuthSession session;

  /// A stored session, as after an earlier sign-in.
  void storeSession() {
    server.validRefresh.add('rt-stored');
    store.values[AuthSession.refreshKey] = 'rt-stored';
  }
}

/// `MockClient` without the testing import in this file's callers.
class MockHttp extends http.BaseClient {
  MockHttp(this.handler);

  final Future<http.Response> Function(http.Request) handler;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    final r = http.Request(request.method, request.url)..headers.addAll(request.headers);
    if (request is http.Request) {
      r.bodyBytes = request.bodyBytes;
    } else {
      r.bodyBytes = await request.finalize().toBytes();
    }
    final response = await handler(r);
    return http.StreamedResponse(Stream.value(response.bodyBytes), response.statusCode,
      headers: response.headers, request: request);
  }
}
