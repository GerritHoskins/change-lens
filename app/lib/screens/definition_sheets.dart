// In-context definition sheets (O-24 phase A): scope options, change types, evidence modes and
// the selected summary. Each row repeats the screen's own label word for word (scope*, type*,
// evidenceMode*, selectedSummary), then the explanation (def*). Read-only: Close dismisses.
import 'package:flutter/material.dart';

import '../design/calm_controls.dart';
import '../design/calm_icons.dart';
import '../design/calm_theme.dart';
import '../design/calm_widgets.dart';
import '../l10n/app_localizations.dart';
import 'onboarding_examples.dart';

/// One term on `ground` inside the sheet: the label, then its explanations and an optional preview.
class DefinitionRow extends StatelessWidget {
  const DefinitionRow({super.key, required this.title, this.details = const [], this.leading, this.preview});

  final String title;
  final List<String> details;
  final Widget? leading;
  /// Decorative; always excluded from semantics.
  final Widget? preview;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colors = CalmColors.of(context);
    return DecoratedBox(
      decoration: BoxDecoration(color: theme.scaffoldBackgroundColor,
        borderRadius: BorderRadius.circular(CalmRadius.md)),
      child: Padding(padding: const EdgeInsets.fromLTRB(16, 14, 16, 14),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          MergeSemantics(child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            Row(children: [
              if (leading != null) ...[leading!, const SizedBox(width: 10)],
              Expanded(child: Text(title, style: theme.textTheme.titleMedium)),
            ]),
            for (final d in details) Padding(padding: const EdgeInsets.only(top: 4),
              child: Text(d, style: theme.textTheme.bodyMedium?.copyWith(color: colors.muted))),
          ])),
          if (preview != null) Padding(padding: const EdgeInsets.only(top: 10),
            child: ExcludeSemantics(child: preview!)),
        ])),
    );
  }
}

class ScopeDefinitionSheet extends StatelessWidget {
  const ScopeDefinitionSheet({super.key});

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return CalmSheet(title: l.scopeQuestion, dismissLabel: l.close, children: [
      DefinitionRow(title: l.scopeComplete, details: [l.scopeCompleteHint, l.defScopeComplete]),
      DefinitionRow(title: l.scopePartial, details: [l.scopePartialHint, l.defScopePartial]),
      DefinitionRow(title: l.scopeUnknown, details: [l.scopeUnknownHint, l.defScopeUnknown]),
    ]);
  }
}

/// Types are named in words; only Uncertain gets a mark, the review disc.
class ChangeTypeDefinitionSheet extends StatelessWidget {
  const ChangeTypeDefinitionSheet({super.key});

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return CalmSheet(title: l.defChangeTypesTitle, dismissLabel: l.close, children: [
      DefinitionRow(title: l.typeAdded, details: [l.defAdded]),
      DefinitionRow(title: l.typeChanged, details: [l.defChanged]),
      DefinitionRow(title: l.typeRemoved, details: [l.defRemoved]),
      DefinitionRow(title: l.typeNotAddressed, details: [l.defNotAddressed]),
      DefinitionRow(title: l.typeUncertain, details: [l.defUncertain], leading: const CalmReviewDisc()),
      DefinitionRow(title: l.typeEquivalent, details: [l.defReworded]),
    ]);
  }
}

class EvidenceDefinitionSheet extends StatelessWidget {
  const EvidenceDefinitionSheet({super.key});

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final colors = CalmColors.of(context);
    final text = Theme.of(context).textTheme;
    const radius = BorderRadius.all(Radius.circular(CalmRadius.sm));
    const en = Locale('en');
    Widget bar(double width) => FractionallySizedBox(alignment: AlignmentDirectional.centerStart,
      widthFactor: width, child: Container(height: 6, decoration: BoxDecoration(
        color: CalmColors.light.line, borderRadius: BorderRadius.circular(3))));
    return CalmSheet(title: l.defEvidenceTitle, dismissLabel: l.close, children: [
      DefinitionRow(title: l.evidenceModePdf, details: [l.defModePdf],
        leading: const Icon(CalmIcons.document, size: 20),
        // A PDF page is white in both themes.
        preview: Container(padding: const EdgeInsets.all(12), decoration: BoxDecoration(color: Colors.white,
            border: Border.all(color: CalmColors.light.line), borderRadius: radius),
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, spacing: 7, children: [
            bar(.7),
            Text.rich(TextSpan(text: sampleQuote, style: text.bodySmall?.copyWith(
              color: CalmColors.ink, backgroundColor: CalmColors.markerFill)), locale: en),
            bar(.85),
            bar(.55),
          ]))),
      DefinitionRow(title: l.evidenceModeFallback, details: [l.defModeFallback],
        leading: const Icon(CalmIcons.text, size: 20),
        // The same 2px solid ink border as CalmWarning.
        preview: Container(padding: const EdgeInsets.fromLTRB(12, 10, 12, 10), decoration: BoxDecoration(
            color: colors.warningSurface, border: Border.all(color: colors.warning, width: CalmSize.dash),
            borderRadius: radius),
          child: Text(sampleQuote, locale: en, style: text.bodySmall?.copyWith(color: colors.warning)))),
      DefinitionRow(title: l.evidenceModeText, details: [l.defModeText],
        leading: const Icon(CalmIcons.paste, size: 20),
        preview: Container(padding: const EdgeInsets.fromLTRB(12, 10, 12, 10),
          decoration: BoxDecoration(color: colors.quote, borderRadius: radius),
          child: Text(sampleQuote, locale: en, style: text.bodySmall?.copyWith(
            color: Theme.of(context).colorScheme.onSurface)))),
    ]);
  }
}

/// The report is a selection; the one main action goes where the summary line goes.
class SummaryDefinitionSheet extends StatelessWidget {
  const SummaryDefinitionSheet({super.key, required this.otherDifferences, required this.onShowAll});

  final int otherDifferences;
  final VoidCallback onShowAll;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return CalmSheet(title: l.defSummaryTitle, dismissLabel: l.close,
      action: l.showAllDifferences, actionKey: const Key('summary-show-all'),
      onAction: () {
        Navigator.pop(context);
        onShowAll();
      },
      children: [DefinitionRow(title: l.selectedSummary(otherDifferences), details: [l.defSummaryBody])]);
  }
}
