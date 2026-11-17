// Usage-events consent (WP-B; D-18 tier B; direction §5; first-launch canvas "Consent"). Shown once per
// account after onboarding, never on replay. Allow and Don't allow are two identical outlined pills with
// nothing preselected (refusal as easy as acceptance: the recorded exception to one main action).
// Nothing is sent before an answer, and the answer is stored on the account, not the device.
//
// FLAGGED: `GET`/`PUT /me/consent` exist (Task 2; [AccountConsent]). The gate routes here only with
// `CHANGELENS_CONSENT=true` ([Services.consentFlow]), off until the I-20 legal review of the texts.
import 'package:flutter/material.dart';

import '../design/calm_actions.dart';
import '../design/calm_widgets.dart';
import '../l10n/app_localizations.dart';

/// The account's answer, read and written on the server (D-18). [allowed] is null until answered.
abstract class UsageConsent implements Listenable {
  bool? get allowed;

  /// Stores the answer on the account; throws when it couldn't be saved.
  Future<void> answer(bool allow);
}

class ConsentScreen extends StatefulWidget {
  const ConsentScreen({super.key, required this.consent, required this.onDone});

  final UsageConsent consent;
  final VoidCallback onDone;

  @override
  State<ConsentScreen> createState() => _ConsentScreenState();
}

class _ConsentScreenState extends State<ConsentScreen> {
  bool saving = false, failed = false;

  Future<void> _answer(bool allow) async {
    final l = AppLocalizations.of(context);
    setState(() { saving = true; failed = false; });
    calmAnnounce(context, l.saving);
    try {
      await widget.consent.answer(allow);
      if (mounted) widget.onDone();
    } on Exception {
      if (mounted) setState(() => failed = true);
    } finally {
      if (mounted) setState(() => saving = false);
    }
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final text = Theme.of(context).textTheme;
    // A legal question: no Back, no Skip. Both answers are one tap.
    return PopScope(canPop: false, child: Scaffold(
      body: SafeArea(child: ListView(padding: const EdgeInsets.fromLTRB(20, 32, 20, 24), children: [
        CalmPageHeader(title: l.consentTitle),
        Text(l.consentBody, style: text.bodyLarge),
        const SizedBox(height: 16),
        Text(l.consentDefault, style: text.bodyMedium),
        if (failed) Padding(padding: const EdgeInsets.only(top: 20),
          child: Semantics(liveRegion: true,
            child: CalmWarning(key: const Key('consent-error'), text: l.consentSaveFailed))),
      ])),
      bottomNavigationBar: SafeArea(child: Padding(padding: const EdgeInsets.fromLTRB(20, 8, 20, 16),
        child: CalmEqualPillPair(
          first: l.consentAllow, second: l.consentDecline,
          firstKey: const Key('consent-allow'), secondKey: const Key('consent-decline'),
          onFirst: saving ? null : () => _answer(true), onSecond: saving ? null : () => _answer(false)))),
    ));
  }
}
