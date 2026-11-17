// Calm Bold action shapes beyond the single main pill (DESIGN.md, "Recorded exceptions"):
// the sign-in provider buttons, two equal outlined pills for an answer that must be as easy either way
// (consent), and ink-only review counts.
import 'package:flutter/material.dart';
import 'package:sign_in_with_apple/sign_in_with_apple.dart';

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

/// One sign-in method. Apple uses Apple's own button (logo and black or white style, per Apple's
/// guidelines); Google and email are outlined ink pills until Google's official "G" asset is bundled.
/// All three share the main-button height, so none reads as the main action.
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
    final dark = Theme.of(context).brightness == Brightness.dark;
    final progress = Row(mainAxisSize: MainAxisSize.min, children: [
      const SizedBox.square(dimension: 18, child: CircularProgressIndicator(strokeWidth: 2)),
      const SizedBox(width: 12),
      Flexible(child: Text(workingLabel ?? label)),
    ]);
    if (provider == CalmProvider.apple) {
      if (working) {
        return FilledButton(onPressed: null, style: FilledButton.styleFrom(
          disabledBackgroundColor: dark ? Colors.white : Colors.black,
          disabledForegroundColor: dark ? Colors.black : Colors.white), child: progress);
      }
      final enabled = onPressed != null;
      return Semantics(button: true, enabled: enabled, label: label, excludeSemantics: true,
        onTap: onPressed,
        child: IgnorePointer(ignoring: !enabled, child: Opacity(opacity: enabled ? 1 : .4,
          child: SignInWithAppleButton(
            onPressed: onPressed ?? () {},
            text: label,
            height: CalmSize.buttonMain,
            borderRadius: const BorderRadius.all(Radius.circular(CalmSize.buttonMain / 2)),
            style: dark ? SignInWithAppleButtonStyle.white : SignInWithAppleButtonStyle.black))));
    }
    return OutlinedButton(onPressed: working ? null : onPressed, style: calmOutlinedPill(context),
      child: working ? progress : Text(label, textAlign: TextAlign.center));
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
          SizedBox(width: 64, child: Text('${rows[i].$1}', style: text.headlineMedium)),
          Expanded(child: Text(rows[i].$2, style: text.bodyLarge)),
        ]))),
      ],
    ]);
  }
}
