// The block a finding opens with (Calm Bold: "a full-width block in its topic colour"). It runs edge to
// edge under the app bar, which takes the same colour, and ends in `radius-sheet` bottom corners.
// It holds what the API provides: the position, the topic as the title, the change label and the
// explanation. The struck-out old value and the new value in `display` need extracted values the
// finding DTO does not carry, so they are not drawn (DESIGN.md, "Direction and scope").
import 'package:flutter/material.dart';

import '../api.dart';
import '../design/calm_theme.dart';
import '../design/calm_widgets.dart';
import '../l10n/app_localizations.dart';
import 'definition_sheets.dart';
import 'report_widgets.dart';

class FindingHeader extends StatelessWidget {
  const FindingHeader({super.key, required this.finding, this.position});

  final Finding finding;

  /// "Finding 2 of 3", or null when the finding is not in the report's list.
  final String? position;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final f = finding;
    final fill = CalmColors.of(context).topicSurface(f.topic);
    final topic = topicLabel(l, f.topic);
    // The title already names the topic; repeat the category only when it says more.
    final change = categoryLabel(l, f.category) == topic ? typeLabel(l, f.changeType)
        : '${typeLabel(l, f.changeType)} · ${categoryLabel(l, f.category)}';
    // `on-topic` is ink in both themes, so every style here sets it instead of following the theme.
    final text = Theme.of(context).textTheme.apply(bodyColor: CalmColors.ink, displayColor: CalmColors.ink);
    return DecoratedBox(
      decoration: BoxDecoration(color: fill,
        borderRadius: const BorderRadius.vertical(bottom: Radius.circular(CalmRadius.sheet))),
      child: Padding(padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          // On a colour, secondary text stays ink: grey on a pastel reads as washed out.
          if (position != null) Padding(padding: const EdgeInsets.only(bottom: 6),
            child: Text(position!, style: text.bodySmall)),
          Semantics(header: true, namesRoute: true,
            child: CalmFitText(topic, style: text.headlineLarge!)),
          const SizedBox(height: 16),
          Row(children: [
            Expanded(child: Text(change, style: text.titleMedium)),
            CalmInfoButton(key: const Key('info-change-types'), term: l.defChangeTypesTitle, onColor: true,
              sheet: (_) => const ChangeTypeDefinitionSheet()),
          ]),
          if (f.explanation != null) Padding(padding: const EdgeInsets.only(top: 8),
            child: Text(f.explanation!, style: text.titleLarge)),
          if (f.group == 'needs_review') Padding(padding: const EdgeInsets.only(top: 16),
            child: Row(children: [
              const CalmReviewDisc(),
              const SizedBox(width: 10),
              Expanded(child: Text(l.groupNeedsReview, style: text.titleSmall)),
            ])),
        ])));
  }
}
