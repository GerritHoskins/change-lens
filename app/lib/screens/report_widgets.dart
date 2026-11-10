// Shared pieces of the report screens (I-10): labels, finding tiles and quoted evidence.
// Wording rule (02 §5, AC-12): a reviewed finding is never shown as "approved" or "agreed".
import 'package:flutter/material.dart';

import '../api.dart';
import '../design/calm_theme.dart';
import '../design/calm_icons.dart';
import '../design/calm_widgets.dart';
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
      'approval' || 'approval_wording' => l.catApproval,
      'budget' => l.topicBudget,
      'structure' => l.catStructure,
      _ => l.catOther,
    };

String topicLabel(AppLocalizations l, String topic) => switch (topic) {
  'deadlines' => l.topicDeadlines,
  'deliverables' => l.topicDeliverables,
  'responsibilities' => l.topicResponsibilities,
  'approval_wording' => l.topicApprovalWording,
  'budget' => l.topicBudget,
  _ => l.topicOther,
};

class TopicFilters extends StatelessWidget {
  const TopicFilters({super.key, required this.counts, required this.selected, required this.onSelected});
  final Map<String, int> counts;
  final String? selected;
  final ValueChanged<String?> onSelected;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 12),
      child: SingleChildScrollView(scrollDirection: Axis.horizontal, child: Row(spacing: 8, children: [
        ChoiceChip(label: Text(l.topicAll), selected: selected == null,
          onSelected: (_) => onSelected(null)),
        for (final topic in findingTopics)
          ChoiceChip(key: ValueKey('topic-$topic'),
            label: Text('${topicLabel(l, topic)} (${counts[topic] ?? 0})'),
            selected: selected == topic, onSelected: (_) => onSelected(topic)),
      ])),
    );
  }
}

/// Group only inside the existing priority/review section: topics never change certainty.
List<Widget> topicFindings(AppLocalizations l, List<Finding> findings, String? selected,
    void Function(Finding) onOpen) => [
  for (final topic in findingTopics)
    if ((selected == null || selected == topic) && findings.any((f) => f.topic == topic)) ...[
      Semantics(header: true, child: Padding(
        padding: const EdgeInsets.only(top: 18, bottom: 4),
        child: Text(topicLabel(l, topic)))),
      for (final f in findings.where((f) => f.topic == topic)) FindingTile(finding: f, onTap: () => onOpen(f)),
    ],
];

String? reviewLabel(AppLocalizations l, Review? r) => switch (r?.action) {
      'confirmed' => l.reviewConfirmed,
      'corrected' => l.reviewCorrected,
      'dismissed' => l.reviewDismissed,
      _ => null,
    };

/// One quoted passage, labelled with its side; tap to open it in the document.
class QuoteCard extends StatelessWidget {
  const QuoteCard({super.key, required this.evidence, this.onTap,
    this.versionLabel, this.evidenceLabel});

  final Evidence evidence;
  final VoidCallback? onTap;
  final String? versionLabel;
  /// A localized observation supplied by the device's evidence resolver, never inferred here.
  final String? evidenceLabel;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final colors = CalmColors.of(context);
    final type = Theme.of(context).textTheme;
    final source = [evidence.earlier ? l.sideEarlier : l.sideNewer,
      ?versionLabel,
      if (evidence.page != null && evidence.page! > 0) l.evidencePage(evidence.page!),
    ].join(' · ');
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 7),
      child: Material(
        color: colors.quote,
        borderRadius: BorderRadius.circular(CalmRadius.lg),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(CalmRadius.lg),
          child: Padding(
            padding: const EdgeInsets.all(18),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text(source, style: type.labelLarge?.copyWith(color: colors.muted)),
              if (evidenceLabel != null) Padding(
                padding: const EdgeInsets.only(top: 4),
                child: Text(evidenceLabel!, style: type.bodySmall?.copyWith(color: colors.muted))),
              const SizedBox(height: 12),
              Text(evidence.quote, style: type.bodyLarge),
              if (onTap != null) Padding(
                padding: const EdgeInsets.only(top: 12),
                child: Row(children: [
                  Expanded(child: Text(l.showInDocument, style: type.labelLarge?.copyWith(
                    decoration: TextDecoration.underline))),
                  const SizedBox(width: 8),
                  const Icon(CalmIcons.openExternal, size: 18),
                ])),
            ]),
          ),
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
    final colors = CalmColors.of(context);
    final type = Theme.of(context).textTheme;
    final uncertain = f.group == 'needs_review';
    final foreground = uncertain ? Theme.of(context).colorScheme.onSurface : colors.topicForeground(f.topic);
    final tile = Material(
        color: uncertain ? colors.quote : colors.topicSurface(f.topic),
        shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(CalmRadius.lg)),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(CalmRadius.lg),
          child: Padding(
            padding: const EdgeInsets.all(18),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(children: [
                // The type is named in words; only uncertainty gets a mark, the review disc.
                if (uncertain) ...[const CalmReviewDisc(), const SizedBox(width: 8)],
                Expanded(child: Text('${typeLabel(l, f.changeType)} · ${categoryLabel(l, f.category)}',
                    style: type.titleMedium?.copyWith(color: foreground, fontWeight: FontWeight.w600))),
              ]),
              for (final e in f.evidence)
                Padding(
                  padding: const EdgeInsets.only(top: 12),
                  child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    Text(e.earlier ? l.sideEarlier : l.sideNewer,
                      style: type.labelMedium?.copyWith(color: foreground)),
                    const SizedBox(height: 3),
                    // The API supplies passages, not extracted display values. Keep its exact text.
                    Text(e.quote, maxLines: 3, overflow: TextOverflow.ellipsis,
                      style: type.bodyLarge?.copyWith(color: foreground, height: 1.45)),
                  ]),
                ),
              if (f.explanation != null)
                Padding(padding: const EdgeInsets.only(top: 12), child: Text(f.explanation!,
                    style: type.bodyMedium?.copyWith(color: foreground))),
              Padding(padding: const EdgeInsets.only(top: 14), child: Row(children: [
                Expanded(child: Text(reviewed ?? l.notReviewed,
                  style: type.labelLarge?.copyWith(color: foreground))),
                const SizedBox(width: 8),
                Icon(CalmIcons.chevronRight, color: foreground),
              ])),
              if (f.clientApprovalRecorded) Padding(
                padding: const EdgeInsets.only(top: 10),
                child: Text(l.approvalRecorded, style: type.bodySmall?.copyWith(color: foreground))),
            ]),
          ),
        ),
      );
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 7),
      child: uncertain ? CalmDashedBorder(child: tile) : tile,
    );
  }
}

class SectionHeader extends StatelessWidget {
  const SectionHeader(this.text, {super.key, this.hint});

  final String text;
  final String? hint;

  @override
  Widget build(BuildContext context) => Padding(
        padding: const EdgeInsets.only(top: 26, bottom: 8),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Semantics(header: true, child: Text(text, style: Theme.of(context).textTheme.titleLarge)),
          if (hint != null) Padding(padding: const EdgeInsets.only(top: 5),
            child: Text(hint!, style: Theme.of(context).textTheme.bodyMedium?.copyWith(
              color: CalmColors.of(context).muted))),
        ]),
      );
}
