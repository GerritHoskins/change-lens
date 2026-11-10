import 'package:flutter/material.dart';

import '../l10n/app_localizations.dart';
import 'calm_theme.dart';

class CalmCard extends StatelessWidget {
  const CalmCard({super.key, required this.child, this.color, this.padding = const EdgeInsets.all(16)});
  final Widget child;
  final Color? color;
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) => DecoratedBox(
    decoration: BoxDecoration(color: color ?? Theme.of(context).cardTheme.color,
      borderRadius: BorderRadius.circular(16)),
    child: Padding(padding: padding, child: child),
  );
}

class CalmPageHeader extends StatelessWidget {
  const CalmPageHeader({super.key, required this.title, this.subtitle});
  final String title;
  final String? subtitle;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(top: 8, bottom: 20),
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Semantics(header: true, child: Text(title, style: Theme.of(context).textTheme.headlineLarge)),
      if (subtitle?.isNotEmpty ?? false) Padding(padding: const EdgeInsets.only(top: 10),
        child: Text(subtitle!, style: Theme.of(context).textTheme.bodySmall)),
    ]),
  );
}

class CalmWarning extends StatelessWidget {
  const CalmWarning({super.key, required this.text, this.child});
  final String text;
  final Widget? child;

  @override
  Widget build(BuildContext context) {
    final colors = CalmColors.of(context);
    return DecoratedBox(
      decoration: BoxDecoration(color: colors.warningSurface, borderRadius: BorderRadius.circular(12)),
      child: Padding(padding: const EdgeInsets.all(14),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(text, style: Theme.of(context).textTheme.bodySmall?.copyWith(color: colors.warning, height: 1.55)),
          if (child != null) Padding(padding: const EdgeInsets.only(top: 6), child: child!),
        ])),
    );
  }
}

class SourcePairSummary extends StatelessWidget {
  const SourcePairSummary({super.key, required this.earlier, required this.newer, this.scope});
  final String earlier, newer;
  final String? scope;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final colors = CalmColors.of(context);
    return Container(
      padding: const EdgeInsets.symmetric(vertical: 12),
      margin: const EdgeInsets.only(bottom: 16),
      decoration: BoxDecoration(border: Border.symmetric(horizontal: BorderSide(color: colors.line))),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Wrap(spacing: 8, runSpacing: 4, crossAxisAlignment: WrapCrossAlignment.center, children: [
          Text('${l.sideEarlier} · $earlier', style: Theme.of(context).textTheme.labelMedium),
          const ExcludeSemantics(child: Icon(Icons.arrow_forward, size: 16)),
          Text('${l.sideNewer} · $newer', style: Theme.of(context).textTheme.labelMedium),
        ]),
        if (scope != null) Padding(padding: const EdgeInsets.only(top: 6),
          child: Text('${l.sideNewer} · ${switch (scope) {
            'complete' => l.scopeComplete, 'partial' => l.scopePartial,
            'unknown' => l.scopeUnknown, _ => l.scopeUnknown,
          }}', style: Theme.of(context).textTheme.bodySmall)),
      ]),
    );
  }
}

bool calmReduceMotion(BuildContext context) =>
    MediaQuery.disableAnimationsOf(context) || MediaQuery.accessibleNavigationOf(context);

/// Recovery stays reachable even when the message needs to scroll at large text sizes.
class CalmLoadError extends StatelessWidget {
  const CalmLoadError({super.key, this.onRetry});
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Center(child: Padding(padding: const EdgeInsets.all(20),
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        Flexible(child: SingleChildScrollView(child: Text(l.contentLoadFailed))),
        const SizedBox(height: 12),
        TextButton(onPressed: onRetry, child: Text(l.retry)),
      ])));
  }
}

/// A brief arrival on the changed content; warnings and review controls never move.
class CalmArrival extends StatelessWidget {
  const CalmArrival({super.key, required this.child});
  final Widget child;

  @override
  Widget build(BuildContext context) => TweenAnimationBuilder<double>(
    tween: Tween(begin: calmReduceMotion(context) ? 0 : 10, end: 0),
    duration: calmReduceMotion(context) ? Duration.zero : const Duration(milliseconds: 180),
    curve: Curves.easeOutCubic, child: child,
    builder: (_, offset, child) => Transform.translate(offset: Offset(offset, 0), child: child),
  );
}

/// Acknowledges a successful personal review, never certainty or client approval.
class CalmReviewMark extends StatelessWidget {
  const CalmReviewMark({super.key, required this.text, this.active = false, this.animate = false});
  final String text;
  final bool active;
  final bool animate;

  @override
  Widget build(BuildContext context) {
    final colors = CalmColors.of(context);
    return TweenAnimationBuilder<double>(
      tween: Tween(begin: calmReduceMotion(context) || !active || !animate ? 1 : 0, end: 1),
      duration: calmReduceMotion(context) ? Duration.zero : const Duration(milliseconds: 220),
      curve: Curves.easeOutCubic,
      builder: (_, value, _) => Stack(children: [
        if (active) Positioned.fill(child: Align(alignment: AlignmentDirectional.centerStart,
          child: FractionallySizedBox(widthFactor: value, heightFactor: 1,
            child: ColoredBox(color: colors.marker)))),
        Padding(padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 3),
          child: Text(text, style: Theme.of(context).textTheme.bodySmall?.copyWith(
            color: active ? colors.onMarker : colors.muted))),
      ]),
    );
  }
}
