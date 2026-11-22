// Review completion (WP-C; v1 canvas P5, P7; owner decision 2026-11-16).
// P5: dismissing asks why (reworded, wrong passage, irrelevant to the work, other), with nothing
// preselected and an optional note. The finding stays in the report, dimmed, and is never relabelled
// as equivalent. P7: once every finding has a review, the counts the server reports, in ink only, and a
// line saying this is not client approval, which stays per finding (`/findings/{id}/client-approvals`).
import 'package:flutter/material.dart';

import '../api.dart';
import '../design/calm_actions.dart';
import '../design/calm_controls.dart';
import '../design/calm_widgets.dart';
import '../l10n/app_localizations.dart';
import 'project_screen.dart';

const dismissalReasons = ['reworded', 'wrong_passage', 'irrelevant', 'other'];

String dismissalReasonLabel(AppLocalizations l, String reason) => switch (reason) {
  'reworded' => l.dismissReasonReworded,
  'wrong_passage' => l.dismissReasonWrongPassage,
  'irrelevant' => l.dismissReasonIrrelevant,
  _ => l.dismissReasonOther,
};

const _reviewed = {'confirmed', 'corrected', 'dismissed'};

/// True when every finding in the report has a review (a note alone isn't one).
bool everyFindingReviewed(Report report) =>
    report.findings.isNotEmpty && report.findings.every((f) => _reviewed.contains(f.review?.action));

/// P5. Returns (reason, note or null), or null when cancelled.
class DismissSheet extends StatefulWidget {
  const DismissSheet({super.key, required this.hasNext});

  /// Another finding waits after this one: the action reads "Dismiss and next".
  final bool hasNext;

  @override
  State<DismissSheet> createState() => _DismissSheetState();
}

class _DismissSheetState extends State<DismissSheet> {
  String? reason;
  final note = TextEditingController();

  @override
  void dispose() { note.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final picked = reason;
    return CalmSheet(
      title: l.dismissTitle,
      lead: l.dismissLead,
      action: widget.hasNext ? l.dismissAndNext : l.actionDismiss,
      actionKey: const Key('dismiss-confirm'),
      // Disabled until a reason is chosen: there is no default, and the line under the button says so.
      actionHint: l.dismissNeedsReason,
      onAction: picked == null ? null : () {
        final text = note.text.trim();
        Navigator.pop(context, (picked, text.isEmpty ? null : text));
      },
      children: [
        RadioGroup<String>(groupValue: reason, onChanged: (v) => setState(() => reason = v),
          child: CalmRadioRows(children: [for (final r in dismissalReasons)
            CalmRadioRow<String>(key: Key('dismiss-reason-$r'), value: r, title: dismissalReasonLabel(l, r))])),
        TextField(key: const Key('dismiss-note'), controller: note, minLines: 2, maxLines: 4,
          decoration: InputDecoration(labelText: l.dismissNote)),
      ],
    );
  }
}

/// P7. Counts come from [report], as the server returned it after the last review.
class ReviewSummaryScreen extends StatelessWidget {
  const ReviewSummaryScreen({super.key, required this.report});

  final Report report;

  int _count(String action) => report.findings.where((f) => f.review?.action == action).length;

  void _back(BuildContext context) => Navigator.of(context).popUntil((route) =>
      route.settings.name == ProjectScreen.routeName || route.isFirst);

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final text = Theme.of(context).textTheme;
    return Scaffold(
      appBar: AppBar(),
      body: SafeArea(top: false, child: ListView(padding: const EdgeInsets.fromLTRB(20, 0, 20, 24), children: [
        CalmPageHeader(title: l.completeTitle),
        Text(l.completeLead, style: text.bodyLarge),
        const SizedBox(height: 8),
        CalmCountSummary(key: const Key('review-counts'), rows: [
          (_count('confirmed'), l.completeConfirmed),
          (_count('corrected'), l.completeCorrected),
          (_count('dismissed'), l.completeDismissed),
        ]),
        const SizedBox(height: 20),
        // Detection, personal review and client approval stay three separate states (AC-12).
        Text(l.completeNotApproval, key: const Key('review-not-approval'), style: text.bodyMedium),
      ])),
      bottomNavigationBar: SafeArea(child: Padding(padding: const EdgeInsets.fromLTRB(20, 8, 20, 16),
        child: FilledButton(key: const Key('review-back-to-project'), onPressed: () => _back(context),
          child: Text(l.completeBack)))),
    );
  }
}
