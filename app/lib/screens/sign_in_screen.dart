// Sign-in (I-18; ui-ux-handoff §5 "First use/auth"): Apple (iOS), Google and email code, and the
// `link_required` step, where the account's existing method must sign in before a new one is linked
// (O-19, AC-26). States: signed out, signing in, cancelled (no message), error, session expired, and
// the notices after sign-out or account deletion.
import 'package:flutter/material.dart';

import '../auth/session.dart';
import '../design/calm_theme.dart';
import '../design/calm_widgets.dart';
import '../l10n/app_localizations.dart';

class SignInScreen extends StatefulWidget {
  const SignInScreen({super.key, required this.session});

  final AuthSession session;

  @override
  State<SignInScreen> createState() => _SignInScreenState();
}

class _SignInScreenState extends State<SignInScreen> {
  SignInMethod? working;
  AuthFailureKind? failure;

  AuthSession get session => widget.session;

  Future<void> _signIn(SignInMethod method) async {
    if (working != null) return;
    setState(() { working = method; failure = null; });
    try {
      await (method == SignInMethod.email ? session.signInWithEmail() : session.signInWithProvider(method));
    } on AuthFailure catch (e) {
      if (mounted) setState(() => failure = e.kind);
    } finally {
      if (mounted) setState(() => working = null);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final text = Theme.of(context).textTheme;
    final colors = CalmColors.of(context);
    final state = session.state;
    final link = state is LinkRequired ? state : null;
    final reason = state is SignedOut ? state.reason : null;
    final notice = switch (reason) {
      SignedOutReason.expired => l.signedOutExpired,
      SignedOutReason.signedOut => l.signedOutDone,
      SignedOutReason.accountDeleted => l.accountDeletedNotice,
      SignedOutReason.deletionPending => l.accountDeletionPendingNotice,
      SignedOutReason.linkFailed => l.linkFailedNotice,
      null => null,
    };
    final error = switch (failure) {
      AuthFailureKind.unavailable => l.signInUnavailable,
      AuthFailureKind.failed => l.signInFailed,
      AuthFailureKind.rejected => l.signInRejected,
      null => null,
    };
    // Apple first on iOS (Apple's guideline 4.8 asks for equal prominence); link offers only the
    // methods the account already has.
    final methods = link != null
        ? [for (final m in link.methods) if (m != SignInMethod.apple || session.native.appleAvailable) m]
        : [if (session.native.appleAvailable) SignInMethod.apple, SignInMethod.google, SignInMethod.email];
    final provider = link == null ? '' : link.provider == SignInMethod.apple ? l.providerApple : l.providerGoogle;

    return PopScope(
      canPop: link == null,
      onPopInvokedWithResult: (didPop, _) { if (!didPop) session.cancelLink(); },
      child: Scaffold(body: SafeArea(child: ListView(
        padding: const EdgeInsets.fromLTRB(20, 32, 20, 32),
        children: [
          CalmPageHeader(title: link == null ? l.signInTitle : l.linkTitle,
            subtitle: link == null ? l.signInIntro : null),
          if (link != null) Padding(padding: const EdgeInsets.only(bottom: 24),
            child: Text(l.linkBody(provider), key: const Key('link-body'), style: text.bodyLarge)),
          if (notice != null && link == null) Padding(padding: const EdgeInsets.only(bottom: 20),
            child: Semantics(liveRegion: true,
              child: CalmCard(key: const Key('sign-in-notice'), color: colors.soft,
                child: Text(notice, style: text.bodyMedium)))),
          if (error != null) Padding(padding: const EdgeInsets.only(bottom: 20),
            child: Semantics(liveRegion: true, child: CalmWarning(key: const Key('sign-in-error'), text: error))),
          for (final method in methods) Padding(padding: const EdgeInsets.only(bottom: 12),
            child: _MethodButton(method: method, working: working == method,
              onPressed: working == null ? () => _signIn(method) : null)),
          if (methods.contains(SignInMethod.email))
            Text(l.signInEmailHint, style: text.bodySmall?.copyWith(color: colors.muted)),
          if (link != null && link.methods.contains(SignInMethod.apple) && !session.native.appleAvailable)
            Padding(padding: const EdgeInsets.only(top: 12),
              child: Text(l.linkAppleElsewhere, style: text.bodySmall?.copyWith(color: colors.muted))),
          if (link != null) Padding(padding: const EdgeInsets.only(top: 24),
            child: Align(alignment: AlignmentDirectional.centerStart,
              child: TextButton(key: const Key('link-cancel'),
                onPressed: working == null ? session.cancelLink : null, child: Text(l.linkCancel)))),
        ],
      ))),
    );
  }
}

class _MethodButton extends StatelessWidget {
  const _MethodButton({required this.method, required this.working, required this.onPressed});

  final SignInMethod method;
  final bool working;
  final VoidCallback? onPressed;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final label = switch (method) {
      SignInMethod.apple => l.signInApple,
      SignInMethod.google => l.signInGoogle,
      SignInMethod.email => l.signInEmail,
    };
    final child = working
        ? Row(mainAxisSize: MainAxisSize.min, children: [
            const SizedBox.square(dimension: 18, child: CircularProgressIndicator(strokeWidth: 2)),
            const SizedBox(width: 12),
            Text(l.signInWorking),
          ])
        : Text(label);
    final key = Key('sign-in-${method.name}');
    // Apple's button is black (white in dark mode) per its guidelines; the others follow the app.
    if (method == SignInMethod.apple) {
      final dark = Theme.of(context).brightness == Brightness.dark;
      return FilledButton(key: key, onPressed: onPressed,
        style: FilledButton.styleFrom(backgroundColor: dark ? Colors.white : Colors.black,
          foregroundColor: dark ? Colors.black : Colors.white),
        child: Semantics(liveRegion: working, child: child));
    }
    return OutlinedButton(key: key, onPressed: onPressed, child: Semantics(liveRegion: working, child: child));
  }
}
