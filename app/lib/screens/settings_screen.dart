// Settings (WP-B; I-18; first-launch canvas "Settings"; ui-ux-handoff §5 "Account/privacy"), opened from
// the Projects menu: the account (signed in with, sign-out, in-app deletion: Apple 5.1.1(v), `DELETE /me`,
// I-8 S5; 204 and 202 both end the account for the app), then Privacy with the usage-events switch.
// Privacy appears only with a [UsageConsent]: the account's answer when [Services.consentFlow] is on. Legal links (Terms, Privacy,
// Imprint) wait for the reviewed I-20 texts and a link opener; they are not built.
// On iOS the account section also says how the Keychain protects the stored sign-in, read back from
// the system (task L29). The line is in release builds too: the L25 inspection reads it there.
import 'package:flutter/foundation.dart' show kReleaseMode;
import 'package:flutter/material.dart';

import '../auth/session.dart';
import '../design/calm_controls.dart';
import '../design/calm_theme.dart';
import '../design/calm_widgets.dart';
import '../l10n/app_localizations.dart';
import '../services.dart' show KeychainProtection, readKeychainProtection;
import 'consent_screen.dart';
import 'sign_in_screen.dart' show methodName;

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key, required this.session, this.consent,
    this.keychainProtection = readKeychainProtection});

  final AuthSession session;

  /// The account's usage-events answer (D-18); null hides the Privacy section until it exists.
  final UsageConsent? consent;

  /// Reads what iOS reports for the stored sign-in; null hides the line (other platforms, nothing stored).
  final Future<KeychainProtection?> Function() keychainProtection;

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  bool deleting = false, deleteFailed = false, consentSaving = false, consentFailed = false;
  late final Future<KeychainProtection?> protection = widget.keychainProtection();

  Future<void> _setConsent(bool allow) async {
    setState(() { consentSaving = true; consentFailed = false; });
    try {
      await widget.consent!.answer(allow);
    } on Exception {
      if (mounted) setState(() => consentFailed = true);
    } finally {
      if (mounted) setState(() => consentSaving = false);
    }
  }

  Future<void> _confirmDelete() async {
    final l = AppLocalizations.of(context);
    final confirmed = await showAdaptiveDialog<bool>(
      context: context,
      builder: (context) => AlertDialog.adaptive(
        scrollable: true,
        title: Text(l.deleteAccountConfirmTitle),
        content: Text(l.deleteAccountConfirmBody),
        actions: [
          calmDialogAction(context, label: l.cancel, onPressed: () => Navigator.pop(context, false)),
          calmDialogAction(context, key: const Key('confirm-delete-account'), label: l.deleteAccount,
            destructive: true, onPressed: () => Navigator.pop(context, true)),
        ],
      ),
    );
    if (confirmed != true || !mounted) return;
    setState(() { deleting = true; deleteFailed = false; });
    try {
      // On success the session signs out and the app returns to sign-in with a notice.
      await widget.session.deleteAccount();
    } on Exception {
      if (mounted) setState(() { deleting = false; deleteFailed = true; });
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final text = Theme.of(context).textTheme;
    final colors = CalmColors.of(context);
    final state = widget.session.state;
    final email = state is SignedIn ? state.email : null;
    final method = widget.session.lastMethod;
    final consent = widget.consent;
    return Scaffold(
      appBar: AppBar(),
      body: SafeArea(top: false, child: ListView(padding: const EdgeInsets.fromLTRB(20, 0, 20, 32), children: [
        CalmPageHeader(title: l.settingsTitle),
        Semantics(header: true, child: Text(l.settingsAccount, style: text.titleMedium)),
        const SizedBox(height: 8),
        Text(email == null ? l.accountSignedIn : l.accountSignedInAs(email), key: const Key('account-identity'),
          style: text.bodyLarge),
        if (method != null) Padding(padding: const EdgeInsets.only(top: 4),
          child: Text(l.settingsSignedInWith(methodName(l, method)), key: const Key('account-method'),
            style: text.bodyMedium?.copyWith(color: colors.muted))),
        FutureBuilder(future: protection, builder: (context, snapshot) {
          final found = snapshot.data;
          if (found == null) return const SizedBox.shrink();
          return Padding(padding: const EdgeInsets.only(top: 4), child: Text(
            found.asIntended ? l.settingsKeychainOk : l.settingsKeychainDiffers(found.found),
            key: const Key('keychain-protection'), style: text.bodyMedium?.copyWith(color: colors.muted)));
        }),
        const SizedBox(height: 16),
        Align(alignment: AlignmentDirectional.centerStart,
          child: OutlinedButton(key: const Key('sign-out'), onPressed: deleting ? null : widget.session.signOut,
            child: Text(l.signOut))),
        // Debug and profile builds only: the access token's lifetime for deploy/ionos E (never the token).
        if (!kReleaseMode && widget.session.accessTokenLifetime != null) Padding(
          padding: const EdgeInsets.only(top: 16),
          child: Text('Access token lifetime: ${widget.session.accessTokenLifetime} s',
            key: const Key('token-lifetime'), style: text.bodySmall?.copyWith(color: colors.muted))),
        Padding(padding: const EdgeInsets.symmetric(vertical: 28), child: Divider(color: colors.line, height: 1)),
        Semantics(header: true, child: Text(l.deleteAccount, style: text.titleMedium)),
        const SizedBox(height: 8),
        Text(l.deleteAccountIntro, style: text.bodyMedium),
        const SizedBox(height: 16),
        if (deleteFailed) Padding(padding: const EdgeInsets.only(bottom: 16),
          child: Semantics(liveRegion: true,
            child: CalmWarning(key: const Key('delete-account-error'), text: l.deleteAccountFailed))),
        Align(alignment: AlignmentDirectional.centerStart, child: TextButton(
          key: const Key('delete-account'),
          style: TextButton.styleFrom(foregroundColor: Theme.of(context).colorScheme.error),
          onPressed: deleting ? null : _confirmDelete,
          child: Semantics(liveRegion: true, child: Text(deleting ? l.deletingAccount : l.deleteAccount)))),
        if (consent != null) ...[
          Padding(padding: const EdgeInsets.symmetric(vertical: 28), child: Divider(color: colors.line, height: 1)),
          Semantics(header: true, child: Text(l.settingsPrivacy, style: text.titleMedium)),
          const SizedBox(height: 8),
          ListenableBuilder(listenable: consent, builder: (context, _) => SwitchListTile.adaptive(
            key: const Key('usage-events'), contentPadding: EdgeInsets.zero,
            title: Text(l.settingsUsageEvents), subtitle: Text(l.settingsUsageEventsHint),
            value: consent.allowed ?? false,
            onChanged: consentSaving ? null : _setConsent)),
          if (consentFailed) Semantics(liveRegion: true,
            child: CalmWarning(key: const Key('usage-events-error'), text: l.consentSaveFailed)),
        ],
      ])),
    );
  }
}
