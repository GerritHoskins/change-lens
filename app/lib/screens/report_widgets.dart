// Shared pieces of the report screens (I-10): labels, finding tiles and quoted evidence.
// Wording rule (02 §5, AC-12): a reviewed finding is never shown as "approved" or "agreed".
import 'package:flutter/material.dart';

import '../api.dart';
import '../l10n/app_localizations.dart';

String typeLabel(AppLocalizations l, String t) => switch (t) {
      'added' => l.typeAdded,
      'changed' => l.typeChanged,
      'removed' => l.typeRemoved,
      'not_addressed' => l.typeNotAddressed,
      'equivalent' => l.typeEquivalent,
      _ => l.typeUncertain,
    };

String categoryLabel(AppLocalizations l, String c) => switch (c) {
      'deliverable' => l.catDeliverable,
      'quantity' => l.catQuantity,
      'date_deadline' => l.catDate,
      'responsibility_owner' => l.catOwner,
      'approval' => l.catApproval,
      'structure' => l.catStructure,
      _ => l.catOther,
    };

String? reviewLabel(AppLocalizations l, Review? r) => switch (r?.action) {
      'confirmed' => l.reviewConfirmed,
      'corrected' => l.reviewCorrected,
      'dismissed' => l.reviewDismissed,
      _ => null,
    };

IconData typeIcon(String t) => switch (t) {
      'added' => Icons.add_circle_outline,
      'changed' => Icons.change_circle_outlined,
      'removed' || 'not_addressed' => Icons.remove_circle_outline,
      'equivalent' => Icons.drag_handle,
      _ => Icons.help_outline,
    };

/// One quoted passage, labelled with its side; tap to open it in the document.
class QuoteCard extends StatelessWidget {
  const QuoteCard({super.key, required this.evidence, this.onTap});

  final Evidence evidence;
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final scheme = Theme.of(context).colorScheme;
    return Card(
      margin: const EdgeInsets.symmetric(vertical: 4),
      color: evidence.earlier ? scheme.errorContainer.withValues(alpha: 0.35) : scheme.primaryContainer.withValues(alpha: 0.35),
      child: InkWell(
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(10),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(evidence.earlier ? l.sideEarlier : l.sideNewer, style: Theme.of(context).textTheme.labelSmall),
            const SizedBox(height: 4),
            Text(evidence.quote),
          ]),
        ),
      ),
    );
  }
}

/// A finding in a list: type and category, the quotes, the explanation and its review state.
class FindingTile extends StatelessWidget {
  const FindingTile({super.key, required this.finding, required this.onTap});

  final Finding finding;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final f = finding;
    final reviewed = reviewLabel(l, f.review);
    final dismissed = f.review?.action == 'dismissed';
    return Opacity(
      opacity: dismissed ? 0.55 : 1,
      child: Card(
        margin: const EdgeInsets.symmetric(vertical: 6),
        child: InkWell(
          onTap: onTap,
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                Icon(typeIcon(f.changeType), size: 18),
                const SizedBox(width: 6),
                Expanded(child: Text('${typeLabel(l, f.changeType)} · ${categoryLabel(l, f.category)}',
                    style: Theme.of(context).textTheme.titleSmall)),
              ]),
              for (final e in f.evidence)
                Padding(
                  padding: const EdgeInsets.only(top: 6),
                  child: Text('${e.earlier ? l.sideEarlier : l.sideNewer}: ${e.quote}',
                      maxLines: 3, overflow: TextOverflow.ellipsis),
                ),
              if (f.explanation != null)
                Padding(padding: const EdgeInsets.only(top: 6), child: Text(f.explanation!,
                    style: Theme.of(context).textTheme.bodySmall)),
              if (reviewed != null || f.clientApprovalRecorded)
                Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Wrap(spacing: 6, runSpacing: 4, children: [
                    if (reviewed != null) Chip(label: Text(reviewed), visualDensity: VisualDensity.compact),
                    if (f.clientApprovalRecorded)
                      Chip(label: Text(l.approvalRecorded), visualDensity: VisualDensity.compact),
                  ]),
                ),
            ]),
          ),
        ),
      ),
    );
  }
}

class SectionHeader extends StatelessWidget {
  const SectionHeader(this.text, {super.key, this.hint});

  final String text;
  final String? hint;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(top: 20, bottom: 4),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(text, style: Theme.of(context).textTheme.titleMedium),
          if (hint != null) Text(hint!, style: Theme.of(context).textTheme.bodySmall),
        ]),
      );
}
