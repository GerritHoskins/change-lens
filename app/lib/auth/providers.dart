// Native Google and Apple sign-in (I-18; I-8 S4, O-19, ADR-0020). The app only obtains the provider's
// authorization code; the backend redeems it once (`POST /session` without a bearer). Client IDs are
// public identifiers, not secrets.
import 'dart:async';
import 'dart:convert';

import 'package:crypto/crypto.dart';
import 'package:flutter/foundation.dart';
import 'package:google_sign_in/google_sign_in.dart';
import 'package:sign_in_with_apple/sign_in_with_apple.dart';

import 'logto.dart';

/// A provider's one-time authorization code, plus the raw nonce for Apple.
class ProviderCode {
  const ProviderCode(this.provider, this.code, {this.nonce});

  final String provider, code;
  final String? nonce;

  Map<String, String> toJson() => {'provider': provider, 'code': code, 'nonce': ?nonce};
}

/// The value the app gives Apple for a raw nonce: lowercase hex SHA-256 of its UTF-8 bytes, which the
/// backend recomputes from the raw nonce (backend/changelens/auth/id_tokens.py `_check_nonce`).
String appleNonceHash(String raw) => sha256.convert(utf8.encode(raw)).toString();

abstract class NativeSignIn {
  /// Sign in with Apple is offered on iOS only: on Android it would need Apple's web flow and a
  /// Services ID, which the backend's audience check (the bundle ID) doesn't accept.
  bool get appleAvailable;

  /// Throws [AuthCancelled] when the user closes the sheet, [AuthFailed] otherwise.
  Future<ProviderCode> google();

  Future<ProviderCode> apple();
}

class PlatformNativeSignIn implements NativeSignIn {
  /// The web client the backend redeems codes with (deploy/ionos C8).
  static const googleServerClientId = '309116612443-lahl2akrpnb7u45k05c3h04c68ehrinn.apps.googleusercontent.com';

  /// The iOS client; its reversed ID is the URL scheme in ios/Runner/Info.plist. Android needs no client
  /// ID here: Google matches the package name and signing certificate's SHA-1.
  static const googleIosClientId = '309116612443-oh1htaf8uod7hhu1srki9h85ubrmi89f.apps.googleusercontent.com';

  static const _googleScopes = ['openid', 'email'];

  Future<void>? _googleReady;

  bool get _ios => !kIsWeb && defaultTargetPlatform == TargetPlatform.iOS;

  @override
  bool get appleAvailable => _ios;

  @override
  Future<ProviderCode> google() async {
    final google = GoogleSignIn.instance;
    // No nonce: the ID token the backend receives comes from the code exchange, without one.
    _googleReady ??= google.initialize(clientId: _ios ? googleIosClientId : null,
      serverClientId: googleServerClientId);
    try {
      await _googleReady;
      final account = await google.authenticate(scopeHint: _googleScopes);
      final server = await account.authorizationClient.authorizeServer(_googleScopes);
      if (server == null) throw AuthCancelled();
      return ProviderCode('google', server.serverAuthCode);
    } on GoogleSignInException catch (e) {
      if (e.code == GoogleSignInExceptionCode.canceled) throw AuthCancelled();
      if (e.code == GoogleSignInExceptionCode.clientConfigurationError ||
          e.code == GoogleSignInExceptionCode.providerConfigurationError) {
        _googleReady = null;
      }
      throw AuthFailed('google_${e.code.name}');
    } finally {
      // The app keeps no Google session of its own; the next sign-in shows the account chooser.
      unawaited(google.signOut().catchError((_) {}));
    }
  }

  @override
  Future<ProviderCode> apple() async {
    final raw = randomToken(32);
    try {
      final credential = await SignInWithApple.getAppleIDCredential(
        scopes: const [AppleIDAuthorizationScopes.email], nonce: appleNonceHash(raw));
      return ProviderCode('apple', credential.authorizationCode, nonce: raw);
    } on SignInWithAppleAuthorizationException catch (e) {
      if (e.code == AuthorizationErrorCode.canceled) throw AuthCancelled();
      throw AuthFailed('apple_${e.code.name}');
    } on SignInWithAppleException {
      throw AuthFailed('apple_unavailable');
    }
  }
}
