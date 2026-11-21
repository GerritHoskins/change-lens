import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart';

import '../api.dart';
import '../l10n/app_localizations.dart';
import 'calm_controls.dart';
import 'calm_icons.dart';
import 'calm_theme.dart';

/// Announces a state change to TalkBack and VoiceOver without showing anything (a cancelled sign-in,
/// a linked method).
void calmAnnounce(BuildContext context, String message) =>
    SemanticsService.sendAnnouncement(View.of(context), message, Directionality.of(context));

/// Opens a definition sheet in context: a 48px info disc labelled "About {term}".
class CalmInfoButton extends StatelessWidget {
  const CalmInfoButton({super.key, required this.term, required this.sheet});
  final String term;
  final WidgetBuilder sheet;

  @override
  Widget build(BuildContext context) {
    final label = AppLocalizations.of(context).defInfo(term);
    // The label is announced once, as the button's label; the tooltip is visual only.
    return Tooltip(message: label, excludeFromSemantics: true, child: IconButton(
      icon: Icon(CalmIcons.info, semanticLabel: label),
      onPressed: () => showCalmSheet<void>(context, builder: sheet),
    ));
  }
}

class CalmCard extends StatelessWidget {
  const CalmCard({super.key, required this.child, this.color, this.padding = const EdgeInsets.all(18)});
  final Widget child;
  final Color? color;
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) => DecoratedBox(
    decoration: BoxDecoration(color: color ?? Theme.of(context).cardTheme.color,
      borderRadius: BorderRadius.circular(CalmRadius.lg)),
    child: Padding(padding: padding, child: child),
  );
}

/// The main action pinned under a scrolling screen (Projects, Project, Compare). A `line` hairline
/// closes the list above it, so content scrolling underneath is not cut off mid-word.
class CalmPinnedBar extends StatelessWidget {
  const CalmPinnedBar({super.key, required this.child});
  final Widget child;

  @override
  Widget build(BuildContext context) => DecoratedBox(
    decoration: BoxDecoration(color: Theme.of(context).scaffoldBackgroundColor,
      border: Border(top: BorderSide(color: CalmColors.of(context).line))),
    child: SafeArea(top: false, child: Padding(padding: const EdgeInsets.fromLTRB(20, 12, 20, 16), child: child)));
}

class CalmPageHeader extends StatelessWidget {
  const CalmPageHeader({super.key, required this.title, this.subtitle, this.liveRegion = false, this.style});
  final String title;
  final String? subtitle;
  /// The title's style when a screen's artboard sets it smaller than `headline` (onboarding steps 2 to 6).
  final TextStyle? style;
  /// Announce changes to the title (a polled status) instead of repeating it in a second line.
  final bool liveRegion;

  @override
  Widget build(BuildContext context) => Padding(
    padding: const EdgeInsets.only(top: 8, bottom: 20),
    child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      // The headline names the route: screens show it once here instead of again in the app bar.
      Semantics(header: true, namesRoute: true, liveRegion: liveRegion,
        child: CalmFitText(title, style: style ?? Theme.of(context).textTheme.headlineLarge!)),
      if (subtitle?.isNotEmpty ?? false) Padding(padding: const EdgeInsets.only(top: 10),
        child: Text(subtitle!, style: Theme.of(context).textTheme.bodySmall)),
    ]),
  );
}

/// A heading that never breaks inside a word. With large text, when its longest word is wider than
/// the line, the text scale shrinks just enough for that word to fit, but never below 1×.
class CalmFitText extends StatelessWidget {
  const CalmFitText(this.text, {super.key, required this.style});
  final String text;
  final TextStyle style;

  @override
  Widget build(BuildContext context) => LayoutBuilder(builder: (context, box) {
    final scaler = MediaQuery.textScalerOf(context);
    var fitted = scaler;
    if (box.maxWidth.isFinite && scaler.scale(10) > 10) {
      var widest = 0.0;
      for (final word in text.split(RegExp(r'\s+'))) {
        final painter = TextPainter(text: TextSpan(text: word, style: style), textScaler: scaler,
          textDirection: Directionality.of(context), maxLines: 1)..layout();
        if (painter.width > widest) widest = painter.width;
        painter.dispose();
      }
      if (widest > box.maxWidth) {
        // Tracking doesn't scale with the text, so aim slightly under the line width.
        final factor = scaler.scale(10) / 10 * box.maxWidth * 0.97 / widest;
        fitted = TextScaler.linear(factor < 1 ? 1 : factor);
      }
    }
    return Text(text, style: style, textScaler: fitted);
  });
}

/// What went wrong, in the user's words, never the exception's text: no connection, sign-in ended,
/// gone, not accepted, or a server problem. Callers offer Retry where it makes sense.
String userErrorMessage(AppLocalizations l, Object error) => switch (error) {
  ApiException(status: 401 || 403) => l.errorSignedOut,
  ApiException(status: 404 || 410) => l.errorNotFound,
  ApiException(:final status) when status >= 400 && status < 500 => l.errorRejected,
  ApiException() => l.errorServer,
  _ => l.errorConnection, // transport failures: no response reached the app
};

/// What a message is. Each kind has its own colour and its own icon, so the kind never rests on
/// colour alone: error (red, a circled "!"), warning (amber, a triangle), info (blue, a circled "i").
enum CalmMessageKind { error, warning, info }

({Color accent, Color surface, IconData icon}) calmMessageLook(BuildContext context, CalmMessageKind kind) {
  final colors = CalmColors.of(context);
  return switch (kind) {
    CalmMessageKind.error => (accent: colors.error, surface: colors.errorSurface, icon: CalmIcons.error),
    CalmMessageKind.warning => (accent: colors.caution, surface: colors.cautionSurface, icon: CalmIcons.warning),
    CalmMessageKind.info => (accent: colors.link, surface: colors.infoSurface, icon: CalmIcons.info),
  };
}

/// A message banner: tinted surface, 2px solid border and icon in the kind's colour, ink text.
/// Solid, never the dashed review style. Errors are the default; pass [kind] for anything else.
class CalmWarning extends StatelessWidget {
  const CalmWarning({super.key, required this.text, this.child, this.kind = CalmMessageKind.error});
  final String text;
  final Widget? child;
  final CalmMessageKind kind;

  @override
  Widget build(BuildContext context) {
    final look = calmMessageLook(context, kind);
    final ink = Theme.of(context).colorScheme.onSurface;
    return DecoratedBox(
      decoration: BoxDecoration(color: look.surface,
        border: Border.all(color: look.accent, width: CalmSize.dash),
        borderRadius: BorderRadius.circular(CalmRadius.lg)),
      child: Padding(padding: const EdgeInsets.all(16),
        child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          ExcludeSemantics(child: Icon(look.icon, size: 20, color: look.accent)),
          const SizedBox(width: 12),
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(text, style: Theme.of(context).textTheme.bodySmall?.copyWith(color: ink, height: 1.55)),
            if (child != null) Padding(padding: const EdgeInsets.only(top: 6), child: child!),
          ])),
        ])),
    );
  }
}

/// A floating snackbar for something that just happened. Errors and warnings fill with their colour;
/// info keeps the ink snackbar. Every kind carries its icon.
void calmSnack(BuildContext context, String message, {CalmMessageKind kind = CalmMessageKind.info}) {
  final look = calmMessageLook(context, kind);
  final theme = Theme.of(context);
  final filled = kind != CalmMessageKind.info;
  // On the light theme the accents are dark (white reads at 5.7:1+); on dark they are light (ink, 8:1+).
  final foreground = !filled ? theme.scaffoldBackgroundColor
      : CalmColors.of(context).dark ? CalmColors.ink : Colors.white;
  ScaffoldMessenger.of(context).showSnackBar(SnackBar(
    backgroundColor: filled ? look.accent : null,
    content: Row(children: [
      ExcludeSemantics(child: Icon(look.icon, size: 20, color: foreground)),
      const SizedBox(width: 12),
      Expanded(child: Text(message, style: theme.textTheme.bodyMedium?.copyWith(color: foreground))),
    ])));
}

class SourcePairSummary extends StatelessWidget {
  const SourcePairSummary({super.key, required this.earlier, required this.newer, this.scope,
    this.framed = true});
  final String earlier, newer;
  final String? scope;
  /// Hairlines above and below; off inside list rows that draw their own separator.
  final bool framed;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final colors = CalmColors.of(context);
    return Container(
      padding: framed ? const EdgeInsets.symmetric(vertical: 12) : EdgeInsets.zero,
      margin: framed ? const EdgeInsets.only(bottom: 16) : EdgeInsets.zero,
      decoration: framed ? BoxDecoration(border: Border.symmetric(horizontal: BorderSide(color: colors.line))) : null,
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Wrap(spacing: 8, runSpacing: 4, crossAxisAlignment: WrapCrossAlignment.center, children: [
          Text('${l.sideEarlier} · $earlier', style: Theme.of(context).textTheme.labelMedium),
          const ExcludeSemantics(child: Icon(CalmIcons.arrowForward, size: 16)),
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

/// Android's "Remove animations" sets `disableAnimations`; iOS's Reduce Motion sets `reduceMotion`
/// instead, which MediaQuery does not carry, so it is read from the platform dispatcher.
bool calmReduceMotion(BuildContext context) =>
    MediaQuery.disableAnimationsOf(context) || MediaQuery.accessibleNavigationOf(context) ||
    View.of(context).platformDispatcher.accessibilityFeatures.reduceMotion;

/// Recovery stays reachable even when the message needs to scroll at large text sizes.
class CalmLoadError extends StatelessWidget {
  const CalmLoadError({super.key, this.onRetry});
  final VoidCallback? onRetry;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return Center(child: Padding(padding: const EdgeInsets.all(20),
      child: Column(mainAxisSize: MainAxisSize.min, children: [
        ExcludeSemantics(child: Icon(CalmIcons.error, size: 28, color: Theme.of(context).colorScheme.error)),
        const SizedBox(height: 12),
        Flexible(child: SingleChildScrollView(child: Text(l.contentLoadFailed, textAlign: TextAlign.center))),
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

/// "Needs a second look": the 2px dashed `review` border. Always paired with [CalmReviewDisc].
class CalmDashedBorder extends StatelessWidget {
  const CalmDashedBorder({super.key, required this.child});
  final Widget child;

  @override
  Widget build(BuildContext context) => CustomPaint(
    foregroundPainter: _DashedRRect(CalmColors.of(context).review), child: child);
}

class _DashedRRect extends CustomPainter {
  const _DashedRRect(this.color);
  final Color color;

  @override
  void paint(Canvas canvas, Size size) {
    const inset = CalmSize.dash / 2;
    final rrect = RRect.fromRectAndRadius(
      (Offset.zero & size).deflate(inset), const Radius.circular(CalmRadius.lg - inset));
    final paint = Paint()..color = color..style = PaintingStyle.stroke..strokeWidth = CalmSize.dash;
    for (final metric in (Path()..addRRect(rrect)).computeMetrics()) {
      for (var d = 0.0; d < metric.length; d += 10) {
        canvas.drawPath(metric.extractPath(d, d + 6), paint);
      }
    }
  }

  @override
  bool shouldRepaint(_DashedRRect old) => old.color != color;
}

/// The "?" disc in `review` with `on-review` ink; excluded from semantics because the text says it.
class CalmReviewDisc extends StatelessWidget {
  const CalmReviewDisc({super.key});

  @override
  Widget build(BuildContext context) => ExcludeSemantics(child: Container(
    width: 24, height: 24, alignment: Alignment.center,
    decoration: BoxDecoration(color: CalmColors.of(context).review, shape: BoxShape.circle),
    child: const Text('?', textScaler: TextScaler.noScaling, style: TextStyle(
      color: CalmColors.ink, fontSize: 15, fontWeight: FontWeight.w700, height: 1))));
}
