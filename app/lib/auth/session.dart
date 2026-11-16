// The signed-in account (I-18; 03a P1, I-8 S2/S4/S5): sign-in by email code, Google or Apple, the
// `link_required` step, the session on start, the onboarding state (O-23), sign-out and account deletion.
// Only the Logto refresh token is stored, in the Keychain / Keystore (AC-25); the access token and the
// email live in memory. Logs and errors carry event codes only.
import 'dart:async';
import 'dart:convert';

import 'package:flutter/foundation.dart';
import 'package:http/http.dart' as http;

import '../api.dart';
import '../services.dart' show SettingsStore;
import 'logto.dart';
import 'providers.dart';

enum SignInMethod { email, google, apple }

SignInMethod? signInMethodOf(String name) => switch (name) {
  'email' => SignInMethod.email, 'google' => SignInMethod.google, 'apple' => SignInMethod.apple, _ => null,
};

/// Why the sign-in screen is showing, when it isn't a first visit.
enum SignedOutReason { signedOut, expired, accountDeleted, deletionPending, linkFailed }

sealed class AuthState {
  const AuthState();
}

/// Checking a stored session on start.
class AuthRestoring extends AuthState {
  const AuthRestoring();
}

/// A stored session exists but Logto or the API couldn't be reached; retrying keeps it.
class AuthOffline extends AuthState {
  const AuthOffline();
}

class SignedOut extends AuthState {
  const SignedOut([this.reason]);
  final SignedOutReason? reason;
}

/// A Google or Apple identity whose verified email belongs to an existing account (O-19, AC-26): the
/// user signs in once with one of [methods], then the backend links [provider] to that account.
class LinkRequired extends AuthState {
  const LinkRequired(this.provider, this.methods, this.linkId);
  final SignInMethod provider;
  final List<SignInMethod> methods;
  final String linkId;
}

class SignedIn extends AuthState {
  const SignedIn(this.onboarding, {this.email});
  final OnboardingState onboarding;
  final String? email;
}

enum AuthFailureKind { unavailable, failed, rejected }

/// A sign-in attempt that did not end signed in; the screen shows a message for [kind].
class AuthFailure implements Exception {
  const AuthFailure(this.kind, [this.code]);
  final AuthFailureKind kind;
  final String? code;
  @override
  String toString() => 'AuthFailure(${kind.name}${code == null ? '' : ', $code'})';
}

class AuthSession extends ChangeNotifier {
  AuthSession(this.config, this.store, {LogtoClient? logto, NativeSignIn? native, http.Client? client})
      : _inner = client ?? http.Client(),
        native = native ?? PlatformNativeSignIn() {
    this.logto = logto ?? LogtoClient(config, client: _inner);
  }

  static const refreshKey = 'logto_refresh_token';
  static const _expiryMargin = Duration(seconds: 60);

  final AuthConfig config;
  final SettingsStore store;
  final NativeSignIn native;
  late final LogtoClient logto;
  final http.Client _inner;

  AuthState _state = const AuthRestoring();
  AuthState get state => _state;

  TokenSet? _tokens;
  Future<TokenSet>? _refreshing;
  Future<void>? _rechecking;
  bool _busy = false;

  /// Adds the bearer to every API call and notices a session that ended.
  late final http.Client httpClient = _AuthorizedClient(_inner, this);
  late final Api api = Api(config.apiBase, '', client: httpClient);

  DateTime Function() clock = DateTime.now;

  void _set(AuthState next) {
    _state = next;
    notifyListeners();
  }

  Uri _u(String path) => Uri.parse(config.apiBase.replaceAll(RegExp(r'/+$'), '') + path);

  /// On start: the stored session, refreshed, then `POST /session` (03a P1 app sequence).
  Future<void> restore() async {
    _set(const AuthRestoring());
    final stored = await store.read(refreshKey);
    if (stored == null || stored.isEmpty) return _set(const SignedOut());
    try {
      await _keep(await logto.refresh(stored));
      _set(SignedIn(await _bootstrap(), email: _tokens?.email));
    } on SessionExpired {
      await _forget();
      _set(const SignedOut(SignedOutReason.expired));
    } on ApiException catch (e) {
      if (e.status == 401) {
        await _forget();
        return _set(const SignedOut(SignedOutReason.expired));
      }
      _set(const AuthOffline());
    } on Exception {
      _set(const AuthOffline()); // AuthUnavailable, AuthFailed, network: keep the stored session
    }
  }

  /// Email one-time code in Logto's sign-in (MFA applies there). Also completes a pending link when the
  /// existing account signs in this way.
  Future<void> signInWithEmail() => _attempt(() async {
    final link = _state is LinkRequired ? _state as LinkRequired : null;
    await _establish(await logto.signIn(), linkId: link?.linkId);
  });

  /// Native Google or Apple: the provider's code goes to the backend, which answers with a Logto
  /// one-time token for this account or with `link_required` (I-8 S4).
  Future<void> signInWithProvider(SignInMethod method) => _attempt(() async {
    assert(method != SignInMethod.email);
    final link = _state is LinkRequired ? _state as LinkRequired : null;
    final code = method == SignInMethod.apple ? await native.apple() : await native.google();
    final answer = decodeApiResponse(await _inner.post(_u('/session'),
        headers: {'Content-Type': 'application/json'}, body: jsonEncode(code.toJson())));
    if (answer is! Map) throw const AuthFailure(AuthFailureKind.failed, 'session_malformed');
    switch (answer['status']) {
      case 'sign_in':
        final token = answer['one_time_token'], hint = answer['login_hint'];
        if (token is! String || hint is! String) throw const AuthFailure(AuthFailureKind.failed, 'session_malformed');
        await _establish(await logto.signIn(extraParams: {'one_time_token': token, 'login_hint': hint}),
          linkId: link?.linkId);
      case 'link_required':
        final linkId = answer['link_id'];
        final methods = [
          for (final m in answer['methods'] as List? ?? const []) if (m is String) ?signInMethodOf(m),
        ];
        if (linkId is! String || methods.isEmpty || link != null) {
          // While linking, the chosen method must already belong to the account; anything else ends it.
          await _forget();
          _set(const SignedOut(SignedOutReason.linkFailed));
          return;
        }
        _set(LinkRequired(method, methods, linkId));
      default:
        throw const AuthFailure(AuthFailureKind.failed, 'session_malformed');
    }
  });

  /// Leaves the link step; the pending link expires on the server within the hour.
  void cancelLink() {
    if (_state is LinkRequired) _set(const SignedOut());
  }

  /// Runs one sign-in at a time and maps every outcome to a state or an [AuthFailure].
  Future<void> _attempt(Future<void> Function() run) async {
    if (_busy) return;
    _busy = true;
    try {
      await run();
    } on AuthCancelled {
      // closed the browser or the provider sheet: stay where we were
    } on AuthFailure {
      rethrow;
    } on ApiException catch (e) {
      if (e.status == 503 || e.status == 429) throw AuthFailure(AuthFailureKind.unavailable, e.code);
      if (e.status == 401) throw AuthFailure(AuthFailureKind.rejected, e.code);
      throw AuthFailure(AuthFailureKind.failed, e.code);
    } on AuthUnavailable catch (e) {
      throw AuthFailure(AuthFailureKind.unavailable, e.code);
    } on AuthFailed catch (e) {
      throw AuthFailure(AuthFailureKind.failed, e.code);
    } on SessionExpired {
      throw const AuthFailure(AuthFailureKind.failed, 'session_expired');
    } on http.ClientException {
      throw const AuthFailure(AuthFailureKind.unavailable, 'unreachable');
    } on TimeoutException {
      throw const AuthFailure(AuthFailureKind.unavailable, 'timeout');
    } finally {
      _busy = false;
    }
  }

  /// Keeps the tokens of a finished Logto sign-in and opens the account with `POST /session`.
  Future<void> _establish(TokenSet tokens, {String? linkId}) async {
    await _keep(tokens);
    try {
      _set(SignedIn(await _bootstrap(linkId: linkId), email: tokens.email));
    } on ApiException catch (e) {
      if (e.status != 401) rethrow;
      // A deleted account, or a link completed by another account than its target: nothing is linked.
      await _forget(revoke: true);
      if (linkId != null) return _set(const SignedOut(SignedOutReason.linkFailed));
      _set(const SignedOut());
      rethrow;
    }
  }

  Future<OnboardingState> _bootstrap({String? linkId}) async {
    final token = await accessToken();
    final body = decodeApiResponse(await _inner.post(_u('/session'),
        headers: {'Authorization': 'Bearer $token', 'Content-Type': 'application/json'},
        body: jsonEncode(linkId == null ? {} : {'link_id': linkId})));
    if (body is! Map || body['status'] != 'active') throw ApiException(200, 'session_malformed');
    final onboarding = body['onboarding'];
    return onboarding is Map<String, dynamic> ? OnboardingState.fromJson(onboarding) : OnboardingState.notStarted;
  }

  Future<void> _keep(TokenSet tokens) async {
    _tokens = tokens;
    await store.write(refreshKey, tokens.refreshToken);
  }

  Future<void> _forget({bool revoke = false}) async {
    final refresh = _tokens?.refreshToken;
    _tokens = null;
    await store.write(refreshKey, '');
    if (revoke && refresh != null) unawaited(logto.revoke(refresh));
  }

  /// `exp - iat` of the current access token, for the deployment evidence (deploy/ionos E; 900 expected).
  /// Read from the token's claims; the token itself is never shown.
  int? get accessTokenLifetime {
    final parts = _tokens?.accessToken.split('.');
    if (parts == null || parts.length != 3) return null;
    try {
      final claims = jsonDecode(utf8.decode(base64Url.decode(base64Url.normalize(parts[1]))));
      if (claims is! Map || claims['exp'] is! int || claims['iat'] is! int) return null;
      return (claims['exp'] as int) - (claims['iat'] as int);
    } on FormatException {
      return null;
    }
  }

  /// A valid API access token, refreshed shortly before it expires. One refresh at a time: with
  /// rotation, a second use of the same refresh token would fail.
  Future<String> accessToken() async {
    final tokens = _tokens;
    if (tokens == null) throw SessionExpired();
    if (tokens.expiresAt.isAfter(clock().add(_expiryMargin))) return tokens.accessToken;
    return (await _refresh()).accessToken;
  }

  Future<TokenSet> _refresh() => _refreshing ??= () async {
    try {
      final current = _tokens;
      if (current == null) throw SessionExpired();
      final next = await logto.refresh(current.refreshToken);
      if (!identical(_tokens, current)) throw SessionExpired(); // signed out meanwhile
      await _keep(TokenSet(next.accessToken, next.refreshToken, next.expiresAt, email: next.email ?? current.email));
      return _tokens!;
    } finally {
      _refreshing = null;
    }
  }();

  /// After a 401 from the API: refresh and ask `POST /session` again. If the account or session is gone,
  /// the app returns to sign-in (O-22); a network failure changes nothing.
  Future<void> _recheck() => _rechecking ??= () async {
    try {
      if (_state is! SignedIn) return;
      await _refresh();
      final onboarding = await _bootstrap();
      if (_state case SignedIn(:final email)) _set(SignedIn(onboarding, email: email));
    } on SessionExpired {
      await _expire();
    } on ApiException catch (e) {
      if (e.status == 401) await _expire();
    } on Exception {
      // offline: the next call tries again
    } finally {
      _rechecking = null;
    }
  }();

  Future<void> _expire() async {
    if (_state is! SignedIn) return;
    await _forget();
    _set(const SignedOut(SignedOutReason.expired));
  }

  /// Saves the last onboarding step reached (1-based). Best effort: a failed save only means resuming
  /// one step earlier.
  Future<void> saveOnboardingStep(int step) async {
    try {
      await api.saveOnboarding(step: step);
    } on Exception {
      // offline: the next step saves again
    }
  }

  /// Start or Skip on first-run onboarding: Projects at once, completion saved to the account (O-23).
  Future<void> completeOnboarding() async {
    final current = _state;
    if (current is! SignedIn) return;
    _set(SignedIn(const OnboardingState(completed: true), email: current.email));
    try {
      await api.saveOnboarding(completed: true);
    } on Exception {
      // not saved: onboarding shows again on the next start, at the saved step
    }
  }

  Future<void> signOut() async {
    await _forget(revoke: true);
    _set(const SignedOut(SignedOutReason.signedOut));
  }

  /// `DELETE /me` (I-8 S5). 204 and 202 both end the account for the app; errors are rethrown with the
  /// account untouched on this device.
  Future<void> deleteAccount() async {
    final complete = await api.deleteAccount();
    await _forget(); // the Logto user is deleted with the account, and its tokens with it
    _set(SignedOut(complete ? SignedOutReason.accountDeleted : SignedOutReason.deletionPending));
  }
}

class _AuthorizedClient extends http.BaseClient {
  _AuthorizedClient(this._inner, this._session);

  final http.Client _inner;
  final AuthSession _session;

  @override
  Future<http.StreamedResponse> send(http.BaseRequest request) async {
    final String token;
    try {
      token = await _session.accessToken();
    } on SessionExpired {
      unawaited(_session._expire());
      throw ApiException(401, 'unauthenticated');
    } on AuthUnavailable {
      throw http.ClientException('sign-in service unreachable', request.url);
    }
    request.headers['Authorization'] = 'Bearer $token';
    final response = await _inner.send(request);
    if (response.statusCode == 401) unawaited(_session._recheck());
    return response;
  }
}
