// Sign-in (I-18, WP-A; first-launch canvas "Main", "LinkRequired", "SessionExpired"; direction §4):
// the Logo D lockup, the promise and the topic chips, then three equal methods: Apple, Google, email on
// iOS and Google, (Apple,) email on Android. Email, its code and MFA run on Logto's hosted page
// (docs/logto-branding-plan.md §1a). `link_required` offers only the account's existing methods
// (O-19, AC-26). An expired session is a sheet over the current screen, never a route reset.
// States: signed out, signing in (announced), cancelled (announced only), error (replaces the chips),
// the notices after sign-out, deletion or a failed link.
import 'package:flutter/material.dart';

import '../api.dart' show findingTopics;
import '../auth/session.dart';
import '../design/calm_actions.dart';
import '../design/calm_brand.dart';
import '../design/calm_controls.dart';
import '../design/calm_theme.dart';
import '../design/calm_widgets.dart';
import '../l10n/app_localizations.dart';
import 'report_widgets.dart' show topicLabel;

String methodName(AppLocalizations l, SignInMethod m) => switch (m) {
  SignInMethod.apple => l.providerApple,
  SignInMethod.google => l.providerGoogle,
  SignInMethod.email => l.providerEmail,
};

/// The order on this platform: Apple first on iOS (guideline 4.8, equal prominence), Google first on
/// Android. Apple appears only where the native flow is available (providers.dart).
List<SignInMethod> platformMethods(BuildContext context, AuthSession session) {
  final apple = session.native.appleAvailable;
  final ios = Theme.of(context).platform == TargetPlatform.iOS;
  return ios
      ? [if (apple) SignInMethod.apple, SignInMethod.google, SignInMethod.email]
      : [SignInMethod.google, if (apple) SignInMethod.apple, SignInMethod.email];
}

/// Runs one method at a time and reports how it ended, for the screen and the sheet alike.
mixin _SignInRunner<T extends StatefulWidget> on State<T> {
  SignInMethod? working;
  AuthFailureKind? failure;

  AuthSession get session;

  Future<void> signIn(SignInMethod method) async {
    if (working != null) return;
    final l = AppLocalizations.of(context);
    final before = session.state;
    setState(() { working = method; failure = null; });
    calmAnnounce(context, l.signInWorking);
    try {
      await (method == SignInMethod.email ? session.signInWithEmail() : session.signInWithProvider(method));
      // Nothing changed: the browser or the provider sheet was closed. Not an error, so no banner.
      if (mounted && identical(session.state, before)) calmAnnounce(context, l.signInCancelled(methodName(l, method)));
    } on AuthFailure catch (e) {
      if (mounted) setState(() => failure = e.kind);
    } finally {
      if (mounted) setState(() => working = null);
    }
  }

  String? failureText(AppLocalizations l) => switch (failure) {
    AuthFailureKind.unavailable => l.signInUnavailable,
    AuthFailureKind.failed => l.signInFailed,
    AuthFailureKind.rejected => l.signInRejected,
    null => null,
  };

  Widget methodButton(SignInMethod method) {
    final l = AppLocalizations.of(context);
    return Padding(padding: const EdgeInsets.only(bottom: 12), child: CalmProviderButton(
      key: Key('sign-in-${method.name}'),
      provider: CalmProvider.values.byName(method.name),
      label: switch (method) {
        SignInMethod.apple => l.signInApple,
        SignInMethod.google => l.signInGoogle,
        SignInMethod.email => l.signInEmail,
      },
      working: working == method,
      workingLabel: l.signInWorking,
      onPressed: working == null ? () => signIn(method) : null,
    ));
  }
}

class SignInScreen extends StatefulWidget {
  const SignInScreen({super.key, required this.session});

  final AuthSession session;

  @override
  State<SignInScreen> createState() => _SignInScreenState();
}

class _SignInScreenState extends State<SignInScreen> with _SignInRunner {
  @override
  AuthSession get session => widget.session;

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
    final error = failureText(l);
    final methods = link != null
        ? [for (final m in platformMethods(context, session)) if (link.methods.contains(m)) m]
        : platformMethods(context, session);
    final provider = link == null ? '' : methodName(l, link.provider);

    return PopScope(
      canPop: link == null,
      onPopInvokedWithResult: (didPop, _) { if (!didPop) session.cancelLink(); },
      child: Scaffold(body: SafeArea(child: ListView(
        padding: const EdgeInsets.fromLTRB(20, 32, 20, 32),
        children: [
          // Top-aligned, so the heading never moves between states (canvas round 2).
          const Align(alignment: AlignmentDirectional.centerStart, child: CalmLogoLockup()),
          const SizedBox(height: 28),
          if (link == null) ...[
            CalmPageHeader(title: l.signInPromise),
            Text(l.signInPromiseBody, style: text.bodyLarge),
            const SizedBox(height: 20),
          ] else ...[
            CalmPageHeader(title: l.linkTitle),
            Padding(padding: const EdgeInsets.only(bottom: 24),
              child: Text(l.linkBody(provider), key: const Key('link-body'), style: text.bodyLarge)),
          ],
          if (notice != null && link == null) Padding(padding: const EdgeInsets.only(bottom: 20),
            child: Semantics(liveRegion: true,
              child: CalmCard(key: const Key('sign-in-notice'), color: colors.soft,
                child: Text(notice, style: text.bodyMedium)))),
          // An error takes the chips' place, so the buttons don't move down.
          if (error != null) Padding(padding: const EdgeInsets.only(bottom: 20),
            child: Semantics(liveRegion: true, child: CalmWarning(key: const Key('sign-in-error'), text: error)))
          else if (link == null) const Padding(padding: EdgeInsets.only(bottom: 28), child: _TopicChips()),
          for (final method in methods) methodButton(method),
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

/// The six report topics in their pastel blocks: what ChangeLens sorts changes into. Pastel = topic.
class _TopicChips extends StatelessWidget {
  const _TopicChips();

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final colors = CalmColors.of(context);
    final style = Theme.of(context).textTheme.labelMedium;
    return Wrap(key: const Key('sign-in-topics'), spacing: 8, runSpacing: 8, children: [
      for (final topic in findingTopics)
        DecoratedBox(
          decoration: BoxDecoration(color: colors.topicSurface(topic), borderRadius: BorderRadius.circular(CalmRadius.xl)),
          child: Padding(padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 8),
            child: Text(topicLabel(l, topic), style: style?.copyWith(color: colors.topicForeground(topic))))),
    ]);
  }
}

/// Shows the expired-session sheet over whatever is on screen. It can't be dismissed: it closes itself
/// once the session is back, and "Sign out" leaves to the sign-in screen.
Future<void> showSessionExpiredSheet(BuildContext context, AuthSession session) => showModalBottomSheet<void>(
  context: context, isScrollControlled: true, useSafeArea: true, isDismissible: false, enableDrag: false,
  barrierColor: CalmColors.ink.withValues(alpha: .4),
  routeSettings: const RouteSettings(name: SessionExpiredSheet.routeName),
  builder: (_) => SessionExpiredSheet(session: session));

class SessionExpiredSheet extends StatefulWidget {
  const SessionExpiredSheet({super.key, required this.session});

  static const routeName = 'session-expired';

  final AuthSession session;

  @override
  State<SessionExpiredSheet> createState() => _SessionExpiredSheetState();
}

class _SessionExpiredSheetState extends State<SessionExpiredSheet> with _SignInRunner {
  bool showAll = false;

  @override
  AuthSession get session => widget.session;

  @override
  void initState() {
    super.initState();
    session.addListener(_changed);
  }

  @override
  void dispose() {
    session.removeListener(_changed);
    super.dispose();
  }

  void _changed() {
    if (session.state is ReauthRequired || !mounted) return;
    // Signed in again: back to the same screen. Signed out (or another account): the gate closes every
    // route, this one included, so only a sheet that is still on top closes itself.
    final route = ModalRoute.of(context);
    if (session.state is! SignedIn || route == null || !route.isActive) return;
    // Usually on top; if something was pushed above it meanwhile, remove it from under that.
    route.isCurrent ? Navigator.of(context).pop() : Navigator.of(context).removeRoute(route);
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final text = Theme.of(context).textTheme;
    final colors = CalmColors.of(context);
    final all = platformMethods(context, session);
    final last = session.lastMethod != null && all.contains(session.lastMethod) ? session.lastMethod : null;
    final shown = last == null || showAll ? [?last, ...all.where((m) => m != last)] : [last];
    final error = failureText(l);
    return PopScope(canPop: false, child: CalmSurfaceScope(child: SingleChildScrollView(
      padding: const EdgeInsets.fromLTRB(20, 8, 20, 16),
      child: SafeArea(top: false, child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Semantics(header: true, namesRoute: true, child: Text(l.sessionExpiredTitle, style: text.headlineMedium)),
        const SizedBox(height: 8),
        Text(l.sessionExpiredBody, style: text.bodyMedium?.copyWith(color: colors.muted)),
        if (last != null) Padding(padding: const EdgeInsets.only(top: 12),
          child: Text(l.sessionLastMethod(methodName(l, last)), key: const Key('session-last-method'),
            style: text.bodyMedium)),
        const SizedBox(height: 20),
        if (error != null) Padding(padding: const EdgeInsets.only(bottom: 16),
          child: Semantics(liveRegion: true, child: CalmWarning(key: const Key('sign-in-error'), text: error))),
        for (final method in shown) methodButton(method),
        if (shown.length < all.length) Align(alignment: AlignmentDirectional.centerStart,
          child: TextButton(key: const Key('session-other-methods'),
            onPressed: working == null ? () => setState(() => showAll = true) : null,
            child: Text(l.sessionOtherMethods))),
        Align(alignment: AlignmentDirectional.centerStart, child: TextButton(key: const Key('session-sign-out'),
          onPressed: working == null ? session.signOut : null, child: Text(l.signOut))),
      ])))));
  }
}
