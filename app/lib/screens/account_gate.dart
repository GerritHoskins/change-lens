// The app's first screen (I-18; 03a P1 app sequence, O-22, O-23): sign-in first, then onboarding until the
// account has completed it (resuming at the saved step), then Projects. Development builds without an
// account session go straight to Projects and the dev settings. A session that ends while the app is in
// use shows the sign-in sheet over the current screen (WP-A), so in-memory work stays.
import 'package:flutter/material.dart';

import '../auth/session.dart';
import '../design/calm_widgets.dart';
import '../l10n/app_localizations.dart';
import '../services.dart';
import 'onboarding_screen.dart';
import 'projects_screen.dart';
import 'sign_in_screen.dart';

class AccountGate extends StatefulWidget {
  const AccountGate({super.key});

  @override
  State<AccountGate> createState() => _AccountGateState();
}

class _AccountGateState extends State<AccountGate> {
  AuthSession? _session;
  bool _sheetOpen = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    final session = ServicesScope.of(context).auth;
    if (identical(session, _session)) return;
    _session?.removeListener(_changed);
    _session = session?..addListener(_changed);
  }

  @override
  void dispose() {
    _session?.removeListener(_changed);
    super.dispose();
  }

  /// Expired mid-use: the sign-in sheet over the current screen. Signed out anywhere (sign-out,
  /// deletion, another account): close every screen above, the sheet too.
  void _changed() {
    final state = _session?.state;
    if (!mounted || state == null) return;
    switch (state) {
      case ReauthRequired():
        _showSheet();
      case SignedIn(:final linked):
        if (linked != null) {
          final l = AppLocalizations.of(context);
          calmAnnounce(context, l.linkDone(methodName(l, linked)));
        }
      default:
        Navigator.of(context).popUntil((route) => route.isFirst);
    }
  }

  /// The sheet must stay while the session is gone: if something removed it (a screen below popping or
  /// replacing the top route), it comes back on the next frame.
  void _showSheet() {
    if (_sheetOpen) return;
    _sheetOpen = true;
    showSessionExpiredSheet(context, _session!).whenComplete(() {
      _sheetOpen = false;
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted && _session?.state is ReauthRequired) _showSheet();
      });
    });
  }

  @override
  Widget build(BuildContext context) {
    final session = ServicesScope.of(context).auth;
    if (session == null) return const ProjectsScreen();
    return ListenableBuilder(listenable: session, builder: (context, _) => switch (session.state) {
      AuthRestoring() => const _Waiting(),
      AuthOffline() => _Offline(onRetry: session.restore),
      SignedOut() || LinkRequired() => SignInScreen(session: session),
      SignedIn(:final onboarding) || ReauthRequired(previous: SignedIn(:final onboarding))
          when !onboarding.completed => OnboardingScreen(
        key: const ValueKey('first-run-onboarding'), mode: OnboardingMode.firstRun,
        resumeAt: onboarding.step, onStep: session.saveOnboardingStep, onFinish: session.completeOnboarding),
      // Same widget as signed in, so the screens above and their state stay while the sheet is up.
      // Keyed by account: a different account gets a fresh Projects, never the previous one's list.
      SignedIn() || ReauthRequired() => ProjectsScreen(key: ValueKey('projects-${session.account}')),
    });
  }
}

class _Waiting extends StatelessWidget {
  const _Waiting();

  @override
  Widget build(BuildContext context) => Scaffold(body: Center(child: Semantics(
    label: AppLocalizations.of(context).restoringSession, liveRegion: true,
    child: const CircularProgressIndicator())));
}

class _Offline extends StatelessWidget {
  const _Offline({required this.onRetry});

  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Scaffold(body: SafeArea(child: Center(child: Padding(padding: const EdgeInsets.all(24),
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        Text(l.sessionOffline, key: const Key('session-offline'), textAlign: TextAlign.center),
        const SizedBox(height: 12),
        TextButton(key: const Key('session-retry'), onPressed: onRetry, child: Text(l.retry)),
      ])))));
  }
}
