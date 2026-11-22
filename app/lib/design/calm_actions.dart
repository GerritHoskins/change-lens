// Calm Bold action shapes beyond the single main pill (DESIGN.md, "Recorded exceptions"):
// the sign-in provider buttons, two equal outlined pills for an answer that must be as easy either way
// (consent), and ink-only review counts.
import 'package:flutter/material.dart';
import 'package:sign_in_with_apple/sign_in_with_apple.dart';

import 'calm_icons.dart';
import 'calm_theme.dart';

/// An outlined ink pill at main-button height: the email sign-in method and the consent answers.
/// Equal in size and weight to its neighbours, never the black main pill.
ButtonStyle calmOutlinedPill(BuildContext context) {
  final ink = Theme.of(context).colorScheme.onSurface;
  return OutlinedButton.styleFrom(
    minimumSize: const Size(CalmSize.targetMin, CalmSize.buttonMain),
    backgroundColor: Colors.transparent,
    foregroundColor: ink,
    side: BorderSide(color: ink, width: CalmSize.dash),
  );
}

enum CalmProvider { apple, google, email }

/// The sign-in method pill, in the two styles Apple allows for its button: white with an outline on the
/// light theme, plain white on the dark one, black content on both. Google and email use the same pill,
/// so the three stay equal (App Review 4.8). Unlike [calmOutlinedPill] it is filled, and it does not
/// flip with the theme: the label is always ink on white.
ButtonStyle calmProviderPill(BuildContext context) {
  final dark = Theme.of(context).brightness == Brightness.dark;
  return OutlinedButton.styleFrom(
    minimumSize: const Size(CalmSize.targetMin, CalmSize.buttonMain),
    backgroundColor: CalmColors.paper, disabledBackgroundColor: CalmColors.paper,
    foregroundColor: CalmColors.ink, disabledForegroundColor: CalmColors.ink.withValues(alpha: .38),
    side: dark ? BorderSide.none : const BorderSide(color: CalmColors.ink, width: CalmSize.dash),
  );
}

/// One sign-in method: [calmProviderPill] at main-button height with the same label style for all
/// three, so none reads as the main action. Apple adds Apple's logo before the label, in the label's
/// colour; Google stays without its "G" until the official asset is bundled.
class CalmProviderButton extends StatelessWidget {
  const CalmProviderButton({super.key, required this.provider, required this.label,
    required this.onPressed, this.working = false, this.workingLabel});

  final CalmProvider provider;
  final String label;
  /// Null while another method is signing in.
  final VoidCallback? onPressed;
  final bool working;
  final String? workingLabel;

  @override
  Widget build(BuildContext context) {
    final progress = Row(mainAxisSize: MainAxisSize.min, children: [
      // Ink, not the theme's primary: on the dark theme that is near-white, on a white pill.
      const SizedBox.square(dimension: 18, child: CircularProgressIndicator(strokeWidth: 2, color: CalmColors.ink)),
      const SizedBox(width: 12),
      Flexible(child: Text(workingLabel ?? label)),
    ]);
    final text = Text(label, textAlign: TextAlign.center);
    // Apple's logo or the mail icon before the label; Google waits for its official "G".
    final Widget? mark = switch (provider) {
      CalmProvider.apple => const _AppleLogo(),
      CalmProvider.email => const ExcludeSemantics(child: Icon(CalmIcons.mail, size: 20)),
      CalmProvider.google => null,
    };
    return OutlinedButton(onPressed: working ? null : onPressed, style: calmProviderPill(context),
      child: working ? progress : mark == null ? text
        : Row(mainAxisSize: MainAxisSize.min, children: [mark, const SizedBox(width: 8), Flexible(child: text)]));
  }
}

/// Apple's logo at the label's size and in the button's current foreground colour (ink, or dimmed
/// ink while disabled), so it dims with the label. Decorative: the label already names Apple.
class _AppleLogo extends StatelessWidget {
  const _AppleLogo();

  @override
  Widget build(BuildContext context) {
    final style = DefaultTextStyle.of(context).style;
    final height = MediaQuery.textScalerOf(context).scale(style.fontSize ?? 17) * 1.15;
    // Sits a little above the centre line, where it balances against the label's x-height.
    return Padding(padding: EdgeInsets.only(bottom: height * .12), child: SizedBox(
      width: height * 25 / 31, height: height,
      child: CustomPaint(painter: AppleLogoPainter(color: style.color ?? CalmColors.ink))));
  }
}

/// Two identical outlined ink pills, nothing preselected. Side by side when both labels fit at the
/// current text size, stacked otherwise; the order is the reading order either way.
class CalmEqualPillPair extends StatelessWidget {
  const CalmEqualPillPair({super.key, required this.first, required this.second,
    required this.onFirst, required this.onSecond, this.firstKey, this.secondKey});

  final String first, second;
  final VoidCallback? onFirst, onSecond;
  final Key? firstKey, secondKey;

  @override
  Widget build(BuildContext context) {
    final style = calmOutlinedPill(context);
    final a = OutlinedButton(key: firstKey, onPressed: onFirst, style: style, child: Text(first, textAlign: TextAlign.center));
    final b = OutlinedButton(key: secondKey, onPressed: onSecond, style: style, child: Text(second, textAlign: TextAlign.center));
    final stacked = MediaQuery.textScalerOf(context).scale(1) > 1.3;
    if (stacked) {
      return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [a, const SizedBox(height: 12), b]);
    }
    return Row(children: [Expanded(child: a), const SizedBox(width: 12), Expanded(child: b)]);
  }
}

/// Review counts in ink: no marker and no topic colours (those mean "new" and "topic", WP-C).
class CalmCountSummary extends StatelessWidget {
  const CalmCountSummary({super.key, required this.rows});

  /// (count, label) in display order.
  final List<(int, String)> rows;

  @override
  Widget build(BuildContext context) {
    final text = Theme.of(context).textTheme;
    final colors = CalmColors.of(context);
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      for (var i = 0; i < rows.length; i++) ...[
        if (i > 0) Divider(height: 1, color: colors.line),
        MergeSemantics(child: Padding(padding: const EdgeInsets.symmetric(vertical: 14), child: Row(children: [
          ConstrainedBox(constraints: const BoxConstraints(minWidth: 64),
            child: Padding(padding: const EdgeInsetsDirectional.only(end: 12),
              child: Text('${rows[i].$1}', style: text.headlineMedium))),
          Expanded(child: Text(rows[i].$2, style: text.bodyLarge)),
        ]))),
      ],
    ]);
  }
}
