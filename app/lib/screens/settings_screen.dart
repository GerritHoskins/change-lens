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
import '../design/calm_icons.dart';
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
    final hairline = Divider(color: colors.line, height: 1);
    return Scaffold(
      appBar: AppBar(),
      body: SafeArea(top: false, child: ListView(padding: const EdgeInsets.fromLTRB(20, 0, 20, 32), children: [
        CalmPageHeader(title: l.settingsTitle),
        _SectionLabel(l.settingsAccount),
        // One grouped card per section (artboard "Settings"): who is signed in, then what they can do.
        CalmCard(padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6), child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            Padding(padding: const EdgeInsets.symmetric(vertical: 14), child: Row(
              crossAxisAlignment: CrossAxisAlignment.start, children: [
                ExcludeSemantics(child: Icon(CalmIcons.account, size: 22, color: colors.muted)),
                const SizedBox(width: 14),
                Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(email == null ? l.accountSignedIn : l.accountSignedInAs(email),
                    key: const Key('account-identity'), style: text.bodyLarge),
                  if (method != null) Padding(padding: const EdgeInsets.only(top: 2),
                    child: Text(l.settingsSignedInWith(methodName(l, method)), key: const Key('account-method'),
                      style: text.bodySmall)),
                  FutureBuilder(future: protection, builder: (context, snapshot) {
                    final found = snapshot.data;
                    if (found == null) return const SizedBox.shrink();
                    return Padding(padding: const EdgeInsets.only(top: 6), child: Text(
                      found.asIntended ? l.settingsKeychainOk : l.settingsKeychainDiffers(found.found),
                      key: const Key('keychain-protection'), style: text.bodySmall));
                  }),
                ])),
              ])),
            hairline,
            _SettingsRow(key: const Key('sign-out'), icon: CalmIcons.signOut, label: l.signOut,
              onPressed: deleting ? null : widget.session.signOut),
            hairline,
            _SettingsRow(key: const Key('delete-account'), icon: CalmIcons.delete,
              label: deleting ? l.deletingAccount : l.deleteAccount, liveRegion: true,
              color: Theme.of(context).colorScheme.error, onPressed: deleting ? null : _confirmDelete),
          ])),
        Padding(padding: const EdgeInsets.fromLTRB(16, 10, 16, 0),
          child: Text(l.deleteAccountIntro, style: text.bodySmall)),
        if (deleteFailed) Padding(padding: const EdgeInsets.only(top: 16),
          child: Semantics(liveRegion: true,
            child: CalmWarning(key: const Key('delete-account-error'), text: l.deleteAccountFailed))),
        // Debug and profile builds only: the access token's lifetime for deploy/ionos E (never the token).
        if (!kReleaseMode && widget.session.accessTokenLifetime != null) Padding(
          padding: const EdgeInsets.fromLTRB(16, 10, 16, 0),
          child: Text('Access token lifetime: ${widget.session.accessTokenLifetime} s',
            key: const Key('token-lifetime'), style: text.bodySmall)),
        if (consent != null) ...[
          const SizedBox(height: 28),
          _SectionLabel(l.settingsPrivacy),
          // A Material, not a CalmCard: the switch row paints its ink on the nearest Material.
          Material(color: Theme.of(context).cardTheme.color, borderRadius: BorderRadius.circular(CalmRadius.lg),
            child: Padding(padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6), child: ListenableBuilder(listenable: consent, builder: (context, _) => SwitchListTile.adaptive(
              key: const Key('usage-events'), contentPadding: EdgeInsets.zero,
              title: Text(l.settingsUsageEvents), subtitle: Text(l.settingsUsageEventsHint),
              value: consent.allowed ?? false,
              // Named here as well as in the theme: the iOS switch does not read `switchTheme`.
              trackColor: Theme.of(context).switchTheme.trackColor,
              thumbColor: Theme.of(context).switchTheme.thumbColor,
              onChanged: consentSaving ? null : _setConsent)))),
          if (consentFailed) Padding(padding: const EdgeInsets.only(top: 16), child: Semantics(liveRegion: true,
            child: CalmWarning(key: const Key('usage-events-error'), text: l.consentSaveFailed))),
        ],
      ])),
    );
  }
}

/// A section's name above its card: `eyebrow` in `muted`, aligned with the card's text edge.
class _SectionLabel extends StatelessWidget {
  const _SectionLabel(this.text);
  final String text;

  @override
  Widget build(BuildContext context) => Padding(padding: const EdgeInsets.fromLTRB(16, 0, 16, 8),
    child: Semantics(header: true, child: Text(text,
      style: Theme.of(context).textTheme.labelSmall?.copyWith(color: CalmColors.of(context).muted))));
}

/// One action in a settings card: icon and label; the whole row is the button (52px or taller).
class _SettingsRow extends StatelessWidget {
  const _SettingsRow({super.key, required this.icon, required this.label, required this.onPressed,
    this.color, this.liveRegion = false});
  final IconData icon;
  final String label;
  final VoidCallback? onPressed;
  final Color? color;
  final bool liveRegion;

  @override
  Widget build(BuildContext context) => TextButton(
    onPressed: onPressed,
    style: TextButton.styleFrom(foregroundColor: color, iconColor: color,
      minimumSize: const Size.fromHeight(52), padding: const EdgeInsets.symmetric(vertical: 12),
      alignment: AlignmentDirectional.centerStart, textStyle: Theme.of(context).textTheme.titleSmall,
      shape: const RoundedRectangleBorder(borderRadius: BorderRadius.all(Radius.circular(12)))),
    child: Row(children: [
      ExcludeSemantics(child: Icon(icon, size: 22)),
      const SizedBox(width: 14),
      Expanded(child: Semantics(liveRegion: liveRegion, child: Text(label))),
    ]));
}
