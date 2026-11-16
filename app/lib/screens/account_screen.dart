// Account (I-18; ui-ux-handoff §5 "Account/privacy"): who is signed in, sign-out, and in-app account
// deletion (Apple 5.1.1(v); `DELETE /me`, I-8 S5). 204 and 202 both end the account for the app.
import 'package:flutter/material.dart';

import '../auth/session.dart';
import '../design/calm_theme.dart';
import '../design/calm_widgets.dart';
import '../l10n/app_localizations.dart';

class AccountScreen extends StatefulWidget {
  const AccountScreen({super.key, required this.session});

  final AuthSession session;

  @override
  State<AccountScreen> createState() => _AccountScreenState();
}

class _AccountScreenState extends State<AccountScreen> {
  bool deleting = false, deleteFailed = false;

  Future<void> _confirmDelete() async {
    final l = AppLocalizations.of(context);
    final confirmed = await showAdaptiveDialog<bool>(
      context: context,
      builder: (context) => AlertDialog.adaptive(
        scrollable: true,
        title: Text(l.deleteAccountConfirmTitle),
        content: Text(l.deleteAccountConfirmBody),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: Text(l.cancel)),
          TextButton(
            key: const Key('confirm-delete-account'),
            style: TextButton.styleFrom(foregroundColor: Theme.of(context).colorScheme.error),
            onPressed: () => Navigator.pop(context, true),
            child: Text(l.deleteAccount),
          ),
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
    return Scaffold(
      appBar: AppBar(),
      body: SafeArea(top: false, child: ListView(padding: const EdgeInsets.fromLTRB(20, 0, 20, 32), children: [
        CalmPageHeader(title: l.account),
        Text(email == null ? l.accountSignedIn : l.accountSignedInAs(email), key: const Key('account-identity'),
          style: text.bodyLarge),
        const SizedBox(height: 16),
        Align(alignment: AlignmentDirectional.centerStart,
          child: OutlinedButton(key: const Key('sign-out'), onPressed: deleting ? null : widget.session.signOut,
            child: Text(l.signOut))),
        Padding(padding: const EdgeInsets.symmetric(vertical: 28), child: Divider(color: colors.line, height: 1)),
        Text(l.deleteAccount, style: text.titleMedium),
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
      ])),
    );
  }
}
