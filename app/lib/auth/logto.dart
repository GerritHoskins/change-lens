// Logto sign-in for the app (I-18; 03a P1). OAuth 2.0 authorization code with PKCE in an ephemeral
// system browser session (ASWebAuthenticationSession, Custom Tabs), then refresh-token rotation for the
// API resource. The browser runs Logto's own sign-in, where the email code and the user's MFA apply.
// Native Google and Apple sign-in end here too, with the one-time token the backend got from Logto.
// Nothing here logs a code, token or email.
import 'dart:async';
import 'dart:convert';
import 'dart:math';

import 'package:crypto/crypto.dart';
import 'package:flutter/services.dart';
import 'package:flutter_web_auth_2/flutter_web_auth_2.dart';
import 'package:http/http.dart' as http;

/// Production settings, from the build: `--dart-define=CHANGELENS_LOGTO_APP_ID=<Logto native app ID>`.
/// Without it the build is a development build that uses the dev settings (I-22).
class AuthConfig {
  const AuthConfig({required this.apiBase, required this.logtoEndpoint, required this.appId,
    this.redirectUri = defaultRedirectUri});

  static const defaultRedirectUri = 'dev.changelens.app://callback';

  final String apiBase, logtoEndpoint, appId, redirectUri;

  /// The Logto API resource; its identifier is the API's own URL (deploy/ionos C4.5).
  String get resource => apiBase.replaceAll(RegExp(r'/+$'), '');

  String get callbackScheme => Uri.parse(redirectUri).scheme;

  static AuthConfig? fromEnvironment() {
    const appId = String.fromEnvironment('CHANGELENS_LOGTO_APP_ID');
    if (appId.isEmpty) return null;
    return const AuthConfig(
      apiBase: String.fromEnvironment('CHANGELENS_API', defaultValue: 'https://api.pixeltronic.dev'),
      logtoEndpoint: String.fromEnvironment('CHANGELENS_LOGTO', defaultValue: 'https://auth.pixeltronic.dev'),
      appId: appId);
  }
}

class TokenSet {
  TokenSet(this.accessToken, this.refreshToken, this.expiresAt, {this.email});

  final String accessToken, refreshToken;
  final DateTime expiresAt;

  /// From the ID token, for the account screen only; kept in memory, never stored (AC-25).
  final String? email;
}

/// The user closed the browser or the provider sheet: nothing changed.
class AuthCancelled implements Exception {}

/// Logto or the network could not answer now; the stored session is kept.
class AuthUnavailable implements Exception {
  AuthUnavailable(this.code);
  final String code;
  @override
  String toString() => 'AuthUnavailable($code)';
}

/// The sign-in failed for a reason a retry won't fix without the user (an event code only).
class AuthFailed implements Exception {
  AuthFailed(this.code);
  final String code;
  @override
  String toString() => 'AuthFailed($code)';
}

/// Logto refused the refresh token: the session ended (expired, revoked, account deleted; O-22).
class SessionExpired implements Exception {}

/// Opens the sign-in page and returns the redirect URL; throws [AuthCancelled] when the user closes it.
abstract class WebAuthenticator {
  Future<String> authenticate(Uri url, String callbackScheme);
}

class SystemWebAuthenticator implements WebAuthenticator {
  const SystemWebAuthenticator();

  @override
  Future<String> authenticate(Uri url, String callbackScheme) async {
    try {
      // Ephemeral: no Logto cookie outlives the sign-in, so signing out of the app is complete.
      return await FlutterWebAuth2.authenticate(url: url.toString(), callbackUrlScheme: callbackScheme,
        options: const FlutterWebAuth2Options(preferEphemeral: true));
    } on PlatformException catch (e) {
      if (e.code == 'CANCELED') throw AuthCancelled();
      throw AuthFailed('browser_${e.code}');
    }
  }
}

String _base64Url(List<int> bytes) => base64Url.encode(bytes).replaceAll('=', '');

/// URL-safe random string from [bytes] random bytes.
String randomToken([int bytes = 32, Random? random]) {
  final r = random ?? Random.secure();
  return _base64Url(List<int>.generate(bytes, (_) => r.nextInt(256)));
}

/// PKCE S256 challenge for a verifier (RFC 7636).
String pkceChallenge(String verifier) => _base64Url(sha256.convert(ascii.encode(verifier)).bytes);

/// The `email` claim of an unverified ID token, for display only.
String? emailFromIdToken(Object? idToken) {
  if (idToken is! String) return null;
  final parts = idToken.split('.');
  if (parts.length != 3) return null;
  try {
    final claims = jsonDecode(utf8.decode(base64Url.decode(base64Url.normalize(parts[1]))));
    final email = claims is Map ? claims['email'] : null;
    return email is String && email.isNotEmpty ? email : null;
  } on FormatException {
    return null;
  }
}

class LogtoClient {
  LogtoClient(this.config, {http.Client? client, WebAuthenticator? browser, DateTime Function()? clock,
    this.random})
      : _client = client ?? http.Client(),
        _browser = browser ?? const SystemWebAuthenticator(),
        _clock = clock ?? DateTime.now;

  final AuthConfig config;
  final http.Client _client;
  final WebAuthenticator _browser;
  final DateTime Function() _clock;
  final Random? random;

  Uri _oidc(String path) => Uri.parse('${config.logtoEndpoint.replaceAll(RegExp(r'/+$'), '')}/oidc/$path');

  /// Logto's sign-in in the browser. [extraParams] carries `one_time_token` and `login_hint` after a
  /// native Google or Apple sign-in (I-8 S4); without them the user signs in with an email code.
  Future<TokenSet> signIn({Map<String, String> extraParams = const {}}) async {
    final verifier = randomToken(48, random);
    final state = randomToken(24, random);
    final url = _oidc('auth').replace(queryParameters: {
      'client_id': config.appId,
      'redirect_uri': config.redirectUri,
      'response_type': 'code',
      'scope': 'openid offline_access email',
      'resource': config.resource,
      'prompt': 'consent', // Logto issues a refresh token only with consent (offline_access)
      'code_challenge': pkceChallenge(verifier),
      'code_challenge_method': 'S256',
      'state': state,
      ...extraParams,
    });
    final Uri callback;
    try {
      callback = Uri.parse(await _browser.authenticate(url, config.callbackScheme));
    } on FormatException {
      throw AuthFailed('callback_malformed');
    }
    final query = callback.queryParameters;
    if (query['state'] != state) throw AuthFailed('state_mismatch');
    final error = query['error'];
    if (error != null) throw error == 'access_denied' ? AuthCancelled() : AuthFailed('authorize_$error');
    final code = query['code'];
    if (code == null || code.isEmpty) throw AuthFailed('code_missing');
    final body = await _token({
      'grant_type': 'authorization_code', 'code': code, 'redirect_uri': config.redirectUri,
      'code_verifier': verifier, 'client_id': config.appId,
    });
    final refresh = body['refresh_token'];
    if (refresh is! String || refresh.isEmpty) throw AuthFailed('refresh_token_missing');
    // The code grant answers for the ID token; the API token comes from the resource's refresh grant.
    final tokens = await this.refresh(refresh);
    final email = emailFromIdToken(body['id_token']);
    return TokenSet(tokens.accessToken, tokens.refreshToken, tokens.expiresAt, email: tokens.email ?? email);
  }

  /// A new API access token. With rotation on, Logto also returns a new refresh token, which replaces
  /// the old one. Throws [SessionExpired] when Logto no longer accepts the refresh token.
  Future<TokenSet> refresh(String refreshToken) async {
    final body = await _token({
      'grant_type': 'refresh_token', 'refresh_token': refreshToken, 'client_id': config.appId,
      'resource': config.resource,
    }, expiredOnInvalidGrant: true);
    final access = body['access_token'];
    final expiresIn = body['expires_in'];
    if (access is! String || access.isEmpty || expiresIn is! num) throw AuthFailed('token_malformed');
    final next = body['refresh_token'];
    return TokenSet(access, next is String && next.isNotEmpty ? next : refreshToken,
      _clock().add(Duration(seconds: expiresIn.toInt())), email: emailFromIdToken(body['id_token']));
  }

  /// Best effort: ends the refresh token at Logto on sign-out. Failures don't keep the user signed in.
  Future<void> revoke(String refreshToken) async {
    try {
      await _client.post(_oidc('token/revocation'), body: {
        'token': refreshToken, 'token_type_hint': 'refresh_token', 'client_id': config.appId,
      }).timeout(const Duration(seconds: 10));
    } on Exception {
      // offline or Logto down: the token still expires on its own
    }
  }

  Future<Map<String, dynamic>> _token(Map<String, String> form, {bool expiredOnInvalidGrant = false}) async {
    final http.Response response;
    try {
      response = await _client.post(_oidc('token'), body: form).timeout(const Duration(seconds: 20));
    } on http.ClientException {
      throw AuthUnavailable('token_unreachable');
    } on TimeoutException {
      throw AuthUnavailable('token_timeout');
    }
    Object? body;
    try {
      body = jsonDecode(response.body);
    } on FormatException {
      body = null;
    }
    if (response.statusCode == 200 && body is Map<String, dynamic>) return body;
    final error = body is Map ? body['error'] : null;
    if (response.statusCode == 400 && error == 'invalid_grant') {
      if (expiredOnInvalidGrant) throw SessionExpired();
      throw AuthFailed('invalid_grant');
    }
    if (response.statusCode >= 500 || response.statusCode == 429) {
      throw AuthUnavailable('token_status_${response.statusCode}');
    }
    throw AuthFailed('token_status_${response.statusCode}');
  }
}
