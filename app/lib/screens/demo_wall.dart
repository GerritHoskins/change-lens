// The demo period's line and wall (docs/demo-wall-handoff.md). The line is quiet `muted` text on Projects
// and Compare: "Demo · 2 of 3 comparisons left". The wall is the full screen that opens instead of Compare
// once no comparison is left: it offers the feedback form (the one black pill) and the early-bird list, and
// no way to start a comparison. Reports, findings and history stay reachable behind Back.
// It names no price, no store, no date and no way to buy (Apple 3.1.3). The sentence about a discount for
// feedback shows only when the server switches it on. The app has no package that opens a browser, so the
// list's address is shown as selectable text with "Copy link".
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';

import '../demo.dart';
import '../design/calm_theme.dart';
import '../design/calm_widgets.dart';
import '../l10n/app_localizations.dart';
import 'demo_feedback_screen.dart';

/// One quiet line from the demo state; nothing at all without one (limit off, an older server).
class DemoLine extends StatelessWidget {
  const DemoLine({super.key, required this.demo, this.padding = EdgeInsets.zero});

  final DemoController demo;
  final EdgeInsetsGeometry padding;

  @override
  Widget build(BuildContext context) => ListenableBuilder(listenable: demo, builder: (context, _) {
    final state = demo.state;
    if (state == null) return const SizedBox.shrink();
    return Padding(padding: padding, child: Text(
      AppLocalizations.of(context).demoLine(state.remaining, state.limit), key: const Key('demo-line'),
      style: Theme.of(context).textTheme.bodySmall?.copyWith(color: CalmColors.of(context).muted)));
  });
}

class DemoWallScreen extends StatelessWidget {
  const DemoWallScreen({super.key, required this.demo});

  final DemoController demo;

  Future<void> _copy(BuildContext context) async {
    final l = AppLocalizations.of(context);
    await Clipboard.setData(ClipboardData(text: demoLandingUrl(Localizations.localeOf(context).languageCode)));
    if (context.mounted) calmSnack(context, l.demoLinkCopied);
  }

  @override
  Widget build(BuildContext context) => ListenableBuilder(listenable: demo, builder: (context, _) {
    final l = AppLocalizations.of(context);
    final text = Theme.of(context).textTheme;
    final colors = CalmColors.of(context);
    final state = demo.state;
    // Signed out or the limit switched off while the wall is open: nothing to say, Back remains.
    if (state == null) return Scaffold(appBar: AppBar());
    // A comparison still running holds a place without being used: if it fails, the place is free again.
    final running = state.used < state.limit && state.inFlight > 0;
    return Scaffold(
      appBar: AppBar(),
      bottomNavigationBar: CalmPinnedBar(child: state.feedbackSubmitted
        ? Semantics(liveRegion: true, child: Text(l.demoFeedbackSent, key: const Key('demo-feedback-sent'),
            style: text.bodyLarge))
        : FilledButton(key: const Key('demo-give-feedback'),
            onPressed: () => Navigator.of(context).push(MaterialPageRoute<void>(
              builder: (_) => DemoFeedbackScreen(demo: demo))),
            child: Text(l.demoGiveFeedback))),
      // Short, and built whole: nothing here is a lazy list.
      body: SafeArea(top: false, child: SingleChildScrollView(padding: const EdgeInsets.fromLTRB(20, 8, 20, 32),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        CalmPageHeader(key: const Key('demo-wall'),
          title: running ? l.demoWallTitleInFlight(state.limit) : l.demoWallTitle(state.limit)),
        Text(l.demoWallBody, style: text.bodyLarge),
        if (running) Padding(padding: const EdgeInsets.only(top: 12),
          child: Text(l.demoWallInFlight, key: const Key('demo-wall-running'), style: text.bodyLarge)),
        if (state.discountOffered && !state.feedbackSubmitted) Padding(padding: const EdgeInsets.only(top: 12),
          child: Text(l.demoWallDiscount, key: const Key('demo-wall-discount'), style: text.bodyLarge)),
        const SizedBox(height: 32),
        Semantics(header: true, child: Text(l.demoListTitle, style: text.titleLarge)),
        const SizedBox(height: 8),
        Text(l.demoListBody, style: text.bodyMedium?.copyWith(color: colors.muted)),
        const SizedBox(height: 8),
        SelectableText(demoLandingHost, key: const Key('demo-list-address'),
          style: text.bodyLarge?.copyWith(fontWeight: FontWeight.w600)),
        const SizedBox(height: 4),
        Align(alignment: AlignmentDirectional.centerStart, child: CalmTextEdge(child: TextButton(
          key: const Key('demo-copy-link'), onPressed: () => _copy(context), child: Text(l.demoCopyLink)))),
      ]))),
    );
  });
}
