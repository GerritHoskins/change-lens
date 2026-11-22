// The demo feedback form (docs/demo-wall-handoff.md), opened from the wall and from Settings, once per
// account: what is missing (a choice in a sheet of radio rows; "Other" opens a required text field), an
// optional "Anything else?", and what the person would pay per month for the described plan. Nothing is
// preselected. The price question is research: the form says it is no offer and nothing is charged.
// Sending is the one black pill; while it is disabled the line under it says what is missing. A failed
// send keeps every entry. Already answered on another device counts as sent. The text goes to the API
// only: never to a log, a snackbar or device storage.
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../demo.dart';
import '../design/calm_controls.dart';
import '../design/calm_theme.dart';
import '../design/calm_widgets.dart';
import '../l10n/app_localizations.dart';

String demoMissingLabel(AppLocalizations l, String code) => switch (code) {
  'screenshot_import' => l.demoMissingScreenshotImport,
  'more_file_types' => l.demoMissingMoreFileTypes,
  'share_report' => l.demoMissingShareReport,
  'better_accuracy' => l.demoMissingBetterAccuracy,
  'faster_results' => l.demoMissingFasterResults,
  'team' => l.demoMissingTeam,
  _ => l.demoMissingOther,
};

String demoPriceLabel(AppLocalizations l, String code) => switch (code) {
  'eur_0' => l.demoPriceNothing,
  'eur_5' => l.demoPrice5,
  'eur_10' => l.demoPrice10,
  'eur_15' => l.demoPrice15,
  'eur_over_15' => l.demoPriceOver15,
  _ => l.demoPriceNotSure,
};

/// The server counts code points; a field never holds more than it accepts.
class _CodePointLimit extends TextInputFormatter {
  const _CodePointLimit(this.max);
  final int max;

  @override
  TextEditingValue formatEditUpdate(TextEditingValue oldValue, TextEditingValue newValue) =>
      newValue.text.runes.length <= max ? newValue : oldValue;
}

class DemoFeedbackScreen extends StatefulWidget {
  const DemoFeedbackScreen({super.key, required this.demo});

  final DemoController demo;

  @override
  State<DemoFeedbackScreen> createState() => _DemoFeedbackScreenState();
}

class _DemoFeedbackScreenState extends State<DemoFeedbackScreen> {
  final other = TextEditingController(), more = TextEditingController();
  String? missing, price;
  bool sending = false, failed = false;

  @override
  void initState() {
    super.initState();
    other.addListener(_typed);
  }

  @override
  void dispose() {
    other.dispose();
    more.dispose();
    super.dispose();
  }

  void _typed() => setState(() {}); // the pill and its line follow the text's length

  bool get _otherGiven => other.text.trim().runes.length >= demoOtherMin;

  /// What Send still waits for, first thing first; null once nothing is missing.
  String? _missing(AppLocalizations l) =>
      missing == null ? l.demoNeedsMissing
      : missing == 'other' && !_otherGiven ? l.demoNeedsOther(demoOtherMin)
      : price == null ? l.demoNeedsPrice : null;

  Future<void> _send() async {
    final l = AppLocalizations.of(context);
    if (_missing(l) != null || sending) return;
    calmDismissKeyboard();
    setState(() { sending = true; failed = false; });
    calmAnnounce(context, l.demoSending);
    try {
      await widget.demo.sendFeedback(DemoFeedback(missing: missing!, missingOther: other.text,
        anythingElse: more.text, price: price!));
    } on Exception {
      if (mounted) setState(() => failed = true); // the entries stay as they are
    } finally {
      if (mounted) setState(() => sending = false);
    }
  }

  Widget _question(String title) => Semantics(header: true,
    child: Text(title, style: Theme.of(context).textTheme.titleLarge));

  Widget _note(String note, {Key? key}) => Padding(padding: const EdgeInsets.only(top: 8),
    child: Text(note, key: key,
      style: Theme.of(context).textTheme.bodySmall?.copyWith(color: CalmColors.of(context).muted)));

  /// [label] shows in the field; a field under its own question takes the question as [name] instead.
  Widget _field(TextEditingController controller, {required Key key, String? label, String? name}) =>
      Semantics(label: name, child: TextField(
        key: key, controller: controller, enabled: !sending, minLines: 3, maxLines: 6, maxLength: demoTextMax,
        maxLengthEnforcement: MaxLengthEnforcement.none, inputFormatters: const [_CodePointLimit(demoTextMax)],
        textCapitalization: TextCapitalization.sentences, keyboardType: TextInputType.multiline,
        decoration: InputDecoration(labelText: label, alignLabelWithHint: true)));

  @override
  Widget build(BuildContext context) => ListenableBuilder(listenable: widget.demo, builder: (context, _) {
    final l = AppLocalizations.of(context);
    final text = Theme.of(context).textTheme;
    final colors = CalmColors.of(context);
    if (widget.demo.state?.feedbackSubmitted ?? false) return _Sent(onDone: () => Navigator.of(context).pop());
    final waiting = _missing(l);
    return Scaffold(
      appBar: AppBar(),
      // The pill is pinned in the thumb zone; what blocks or follows it sits directly above or under it.
      // The bar scrolls if an error at large text makes it taller than half the screen.
      bottomNavigationBar: CalmPinnedBar(child: ConstrainedBox(
        constraints: BoxConstraints(maxHeight: MediaQuery.sizeOf(context).height * .5),
        child: SingleChildScrollView(child: Column(mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            if (failed) Semantics(liveRegion: true, child: Padding(padding: const EdgeInsets.only(bottom: 12),
              child: CalmWarning(key: const Key('demo-send-error'), text: l.demoSendFailed))),
            FilledButton(key: const Key('demo-send'), onPressed: waiting == null && !sending ? _send : null,
              child: Semantics(liveRegion: true, child: Text(sending ? l.demoSending : l.demoSend))),
            const SizedBox(height: 8),
            Text(waiting ?? l.demoSendHint, key: const Key('demo-send-hint'),
              style: text.bodySmall?.copyWith(color: colors.muted)),
          ])))),
      // A tap outside a field closes the keyboard, as does dragging the form.
      body: SafeArea(top: false, child: GestureDetector(
        behavior: HitTestBehavior.translucent, excludeFromSemantics: true, onTap: calmDismissKeyboard,
        // Built whole, not a lazy list: a field scrolled out of view keeps its focus and its text.
        child: SingleChildScrollView(keyboardDismissBehavior: ScrollViewKeyboardDismissBehavior.onDrag,
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 32),
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          CalmPageHeader(title: l.demoFeedbackTitle, subtitle: l.demoFeedbackIntro),
          _question(l.demoMissingQuestion),
          const SizedBox(height: 12),
          CalmSelectField<String>(key: const Key('demo-missing'), label: l.demoMissingChoose, value: missing,
            options: [for (final code in demoMissingCodes) CalmOption(code, demoMissingLabel(l, code))],
            onChanged: sending ? null : (code) => setState(() { missing = code; failed = false; })),
          if (missing == 'other') ...[
            const SizedBox(height: 12),
            _field(other, key: const Key('demo-missing-other'), label: l.demoMissingOtherLabel),
            _note(l.demoMissingOtherHint(demoOtherMin), key: const Key('demo-missing-other-hint')),
          ],
          const SizedBox(height: 28),
          _question(l.demoAnythingElse),
          const SizedBox(height: 12),
          _field(more, key: const Key('demo-anything-else'), name: l.demoAnythingElse),
          _note(l.demoAnythingElseHint, key: const Key('demo-anything-else-hint')),
          const SizedBox(height: 28),
          _question(l.demoPriceQuestion),
          const SizedBox(height: 8),
          Text(l.demoPlan, key: const Key('demo-plan'), style: text.bodyMedium),
          const SizedBox(height: 12),
          RadioGroup<String>(groupValue: price,
            onChanged: (code) { if (!sending) setState(() { price = code; failed = false; }); },
            child: CalmRadioRows(children: [for (final code in demoPriceCodes) CalmRadioRow<String>(
              key: Key('demo-price-$code'), value: code, enabled: !sending, title: demoPriceLabel(l, code))])),
          _note(l.demoPriceNote, key: const Key('demo-price-note')),
        ])))),
    );
  });
}

/// After sending, and when the account had already answered: one line, and Done.
class _Sent extends StatelessWidget {
  const _Sent({required this.onDone});

  final VoidCallback onDone;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Scaffold(
      appBar: AppBar(),
      bottomNavigationBar: CalmPinnedBar(
        child: FilledButton(key: const Key('demo-done'), onPressed: onDone, child: Text(l.demoDone))),
      body: SafeArea(top: false, child: ListView(padding: const EdgeInsets.fromLTRB(20, 8, 20, 32), children: [
        CalmPageHeader(title: l.demoFeedbackTitle),
        Semantics(liveRegion: true, child: Text(l.demoFeedbackSent, key: const Key('demo-feedback-sent'),
          style: Theme.of(context).textTheme.bodyLarge)),
      ])),
    );
  }
}
