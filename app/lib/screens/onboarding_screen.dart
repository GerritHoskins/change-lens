// Onboarding (O-23, O-24 phase B): six steps and the import sheet. Reachable now only as the
// "How ChangeLens works" replay from Projects. First-run gating, resume and consent wait for the
// account fields, sign-in (I-8) and I-18, so nothing here is stored: the step lives in this State
// only (AC-25). Steps swap without animation and are never swipeable (horizontal swipe is iOS back).
import 'package:flutter/material.dart';

import '../design/calm_controls.dart';
import '../design/calm_icons.dart';
import '../design/calm_theme.dart';
import '../design/calm_widgets.dart';
import '../l10n/app_localizations.dart';
import 'onboarding_examples.dart';
import 'report_widgets.dart';

enum OnboardingMode { firstRun, replay }

/// The parse limits shown on the import sheet. They mirror backend/changelens/config.py:18-20
/// (max_text_words, max_pdf_bytes, max_pdf_pages) until an endpoint serves them.
abstract final class ParseLimits {
  static const words = 15000, pages = 20, megabytes = 10;
}

class OnboardingScreen extends StatefulWidget {
  const OnboardingScreen({super.key, required this.mode, this.resumeAt, this.onStep, this.onFinish});

  final OnboardingMode mode;
  static const steps = 6;

  /// First run: the account's saved step (1-based, O-23), clamped to the current step count.
  final int? resumeAt;

  /// First run: called with the step reached (1-based) so the account can resume there.
  final ValueChanged<int>? onStep;

  /// First run as the app's first screen: Start or Skip completes onboarding instead of popping.
  final VoidCallback? onFinish;

  @override
  State<OnboardingScreen> createState() => _OnboardingScreenState();
}

class _OnboardingScreenState extends State<OnboardingScreen> {
  late int step = ((widget.resumeAt ?? 1) - 1).clamp(0, OnboardingScreen.steps - 1);
  final titleFocus = FocusNode(debugLabel: 'onboarding-title');

  bool get replay => widget.mode == OnboardingMode.replay;
  bool get last => step == OnboardingScreen.steps - 1;

  @override
  void dispose() { titleFocus.dispose(); super.dispose(); }

  void _go(int to) {
    setState(() => step = to);
    if (!replay) widget.onStep?.call(to + 1); // the replay never writes (O-23)
    WidgetsBinding.instance.addPostFrameCallback((_) { if (mounted) titleFocus.requestFocus(); });
  }

  void _leave() {
    final finish = widget.onFinish;
    if (finish != null && !replay) return finish();
    Navigator.of(context).pop();
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final theme = Theme.of(context);
    final colors = CalmColors.of(context);
    final ios = theme.platform == TargetPlatform.iOS || theme.platform == TargetPlatform.macOS;
    final (title, content) = _step(context, l);
    return PopScope(
      // Step 1 back leaves like Skip or Close; later steps go back one step.
      canPop: step == 0,
      onPopInvokedWithResult: (didPop, _) { if (!didPop) _go(step - 1); },
      child: Scaffold(body: SafeArea(bottom: false, child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        Padding(padding: const EdgeInsets.symmetric(horizontal: 8), child: Row(children: [
          if (step > 0)
            IconButton(key: const Key('onb-back'), tooltip: MaterialLocalizations.of(context).backButtonTooltip,
              icon: Icon(ios ? CalmIcons.backIOS : CalmIcons.back), onPressed: () => _go(step - 1))
          else const SizedBox(width: CalmSize.targetMin),
          Expanded(child: Text(l.onbStep(step + 1, OnboardingScreen.steps), key: const Key('onb-step'),
            textAlign: TextAlign.center, style: theme.textTheme.bodySmall?.copyWith(color: colors.muted))),
          ConstrainedBox(
            constraints: BoxConstraints(minWidth: CalmSize.targetMin,
              maxWidth: MediaQuery.sizeOf(context).width * .4),
            child: replay
              ? Center(widthFactor: 1, child: IconButton(key: const Key('onb-close'), tooltip: l.close,
                  icon: const Icon(CalmIcons.close), onPressed: _leave))
              : last ? const SizedBox(width: CalmSize.targetMin)
              : TextButton(key: const Key('onb-skip'), onPressed: _leave, child: Text(l.onbSkip))),
        ])),
        Expanded(child: SingleChildScrollView(key: ValueKey('onb-body-$step'),
          // CalmPageHeader brings its own 8 px above the title.
          padding: const EdgeInsets.fromLTRB(20, 0, 20, 24),
          child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            Focus(focusNode: titleFocus, child: CalmPageHeader(title: title)),
            // Gaps follow the canvas artboards: tighter where a step carries more.
            ..._spaced(content, switch (step) { 0 || 5 => 20, 1 => 14, _ => 16 }),
          ]))),
        // Pinned: 12 px under the button, or the home-indicator inset where it is larger.
        SafeArea(top: false, minimum: const EdgeInsets.only(bottom: 12),
          child: Padding(padding: const EdgeInsets.fromLTRB(20, 12, 20, 0),
            child: FilledButton(key: const Key('onb-main'),
              onPressed: last ? _leave : () => _go(step + 1),
              child: Text(!last ? l.onbNext : replay ? l.onbDone : l.onbStart)))),
      ]))),
    );
  }

  (String, List<Widget>) _step(BuildContext context, AppLocalizations l) {
    final theme = Theme.of(context);
    final text = theme.textTheme;
    final colors = CalmColors.of(context);
    final body = text.bodyMedium;
    final strong = text.titleMedium;
    return switch (step) {
      0 => (l.onbIntroTitle, [
        Text(l.onbIntroBody, style: body),
        _Illustration(alt: l.onbIntroAlt, child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          IntrinsicHeight(child: Row(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            Expanded(child: _Slot(label: l.earlierVersion, newer: false, vertical: true)),
            const SizedBox(width: 10),
            Expanded(child: _Slot(label: l.newerVersion, newer: true, vertical: true)),
          ])),
          Padding(padding: const EdgeInsets.symmetric(vertical: 6),
            child: Icon(CalmIcons.chevronDown, color: colors.muted)),
          CalmCard(padding: const EdgeInsets.fromLTRB(18, 16, 18, 16),
            child: Text(l.reportHeading, style: text.headlineSmall)),
        ])),
        Text(l.onbIntroGoal, style: strong),
      ]),
      1 => (l.onbContextTitle, [
        Text(l.confirmIntro, style: body),
        _Illustration(alt: l.onbContextAlt, child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          _Slot(label: l.earlierVersion, newer: false),
          Padding(padding: const EdgeInsets.symmetric(vertical: 4),
            child: Icon(CalmIcons.swap, size: 20, color: colors.muted)),
          _Slot(label: l.newerVersion, newer: true),
        ])),
        Text(l.onbContextScope, style: body),
        Column(crossAxisAlignment: CrossAxisAlignment.stretch, spacing: 6, children: [
          for (final line in [l.onbScopeLineComplete, l.onbScopeLinePartial, l.onbScopeLineUnknown])
            Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
              ExcludeSemantics(child: Text('•  ', style: body)),
              Expanded(child: Text(line, style: body)),
            ]),
        ]),
        Text(l.onbContextNote, style: strong),
      ]),
      2 => (l.onbEvidenceTitle, [
        Text(l.onbEvidenceBody, style: body),
        _Example(children: [IgnorePointer(child: FindingTile(finding: deadlineExample, onTap: () {}))]),
      ]),
      3 => (l.onbUncertainTitle, [
        Text(l.onbUncertainBody, style: body),
        _Example(children: [
          // The report's own group header, then the real tile.
          Padding(padding: const EdgeInsets.only(top: 4), child: Row(children: [
            const CalmReviewDisc(),
            const SizedBox(width: 10),
            Expanded(child: Text('${l.groupNeedsReview} · 1', style: text.titleSmall)),
          ])),
          IgnorePointer(child: FindingTile(finding: hostingExample, onTap: () {})),
        ]),
        Text(l.onbUncertainSummary, style: body),
      ]),
      4 => (l.onbReviewTitle, [
        Text(l.onbReviewBody, style: body),
        _Example(children: [_Illustration(alt: l.onbReviewAlt, child: CalmCard(
          // The finding screen's own two sections, in miniature: outcomes, not controls.
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(l.yourReview, style: strong),
            const SizedBox(height: 8),
            CalmReviewMark(text: l.reviewConfirmed, active: true),
            const Divider(height: 28),
            Text(l.approvalTitle, style: strong),
            const SizedBox(height: 8),
            Text(l.approvalNone, style: body),
          ])))]),
        Text(l.onbReviewApproval, style: body),
        Text(l.onbReviewApprovalLabel(l.approvalRecorded), style: body?.copyWith(color: colors.muted)),
      ]),
      _ => (replay ? l.onbStartTitleReplay : l.onbStartTitle, [
        if (!replay) Text(l.onbStartNext, style: text.titleLarge),
        Text(l.onbStartLine, style: body),
        Text(l.onbStartLanguage, style: body?.copyWith(color: colors.muted)),
        Align(alignment: AlignmentDirectional.centerStart, child: TextButton(key: const Key('onb-import'),
          style: TextButton.styleFrom(padding: const EdgeInsets.symmetric(vertical: 12),
            textStyle: text.titleSmall?.copyWith(decoration: TextDecoration.underline)),
          onPressed: () => showCalmSheet<void>(context, builder: (_) => const ImportSheet()),
          child: Text(l.onbImportLink))),
      ]),
    };
  }
}

List<Widget> _spaced(List<Widget> children, double gap) => [
  for (var i = 0; i < children.length; i++) ...[if (i > 0) SizedBox(height: gap), children[i]],
];

/// A static picture: one image node with its alt text, nothing focusable inside.
class _Illustration extends StatelessWidget {
  const _Illustration({required this.alt, required this.child});
  final String alt;
  final Widget child;

  @override
  Widget build(BuildContext context) => Semantics(container: true, image: true, label: alt,
    child: ExcludeSemantics(child: IgnorePointer(child: child)));
}

/// A compare slot as the compare screen draws it: a surface card, the newer one with the lime marker.
class _Slot extends StatelessWidget {
  const _Slot({required this.label, required this.newer, this.vertical = false});
  final String label;
  final bool newer, vertical;

  @override
  Widget build(BuildContext context) {
    final colors = CalmColors.of(context);
    final style = Theme.of(context).textTheme.titleSmall;
    const icon = Icon(CalmIcons.document, size: 20);
    return DecoratedBox(
      position: DecorationPosition.foreground,
      decoration: BoxDecoration(borderRadius: BorderRadius.circular(CalmRadius.md),
        border: newer ? Border.all(color: colors.marker, width: CalmSize.dash) : null),
      child: DecoratedBox(
        decoration: BoxDecoration(color: Theme.of(context).cardTheme.color,
          borderRadius: BorderRadius.circular(CalmRadius.md)),
        child: Padding(padding: const EdgeInsets.fromLTRB(14, 12, 14, 12), child: vertical
          ? Column(crossAxisAlignment: CrossAxisAlignment.start, spacing: 10,
              children: [icon, Text(label, style: style)])
          : Row(spacing: 12, children: [icon, Expanded(child: Text(label, style: style))]))),
    );
  }
}

/// The frame around synthetic example content, announced once as "Example".
class _Example extends StatelessWidget {
  const _Example({required this.children});
  final List<Widget> children;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final colors = CalmColors.of(context);
    final ink = Theme.of(context).colorScheme.onSurface;
    return Semantics(container: true, label: l.onbExample, child: DecoratedBox(
      decoration: BoxDecoration(border: Border.all(color: colors.line),
        borderRadius: BorderRadius.circular(CalmRadius.xl)),
      child: Padding(padding: const EdgeInsets.all(10),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
          Align(alignment: AlignmentDirectional.centerStart, child: ExcludeSemantics(child: DecoratedBox(
            decoration: ShapeDecoration(shape: StadiumBorder(side: BorderSide(color: ink))),
            child: Padding(padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 2),
              child: Text(l.onbExample, style: Theme.of(context).textTheme.labelSmall))))),
          const SizedBox(height: 10),
          ...children,
        ]))));
  }
}

/// What can be imported, and the limits. An intentional repeat of step 6 in full.
class ImportSheet extends StatelessWidget {
  const ImportSheet({super.key});

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final theme = Theme.of(context);
    Widget row(IconData icon, String text) => DecoratedBox(
      decoration: BoxDecoration(color: theme.scaffoldBackgroundColor,
        borderRadius: BorderRadius.circular(CalmRadius.md)),
      child: Padding(padding: const EdgeInsets.fromLTRB(16, 14, 16, 14),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, spacing: 12, children: [
          ExcludeSemantics(child: Icon(icon, size: 22)),
          Expanded(child: Text(text, style: theme.textTheme.bodyMedium)),
        ])));
    return CalmSheet(title: l.importSheetTitle, dismissLabel: l.close, children: [
      row(CalmIcons.document, l.onbStartInputs),
      row(CalmIcons.limits, l.onbStartLimits(ParseLimits.words, ParseLimits.pages, ParseLimits.megabytes)),
      row(CalmIcons.online, l.onbStartOnline),
      row(CalmIcons.language, l.onbStartLanguage),
    ]);
  }
}
