// The Projects home bento (Calm Bold "A+B · Home"): a headline that leads with the result, one wide
// `marker` hero for the project whose latest comparison has findings nobody reviewed yet, two square
// `surface` tiles, then plain `surface` rows. Every number is the server's (`Project.latest`).
// Marker means "new"; the white pills carry topic counts as words; `review` appears only with its dashes.
import 'package:flutter/material.dart';

import '../api.dart';
import '../design/calm_icons.dart';
import '../design/calm_theme.dart';
import '../design/calm_widgets.dart';
import '../l10n/app_localizations.dart';

/// Which project goes where. The hero is the changed project compared most recently; a pair of tiles
/// holds the next two that changed or are being read; everything else is a row, in the server's order.
class HomeLayout {
  HomeLayout(List<Project> projects, {bool tiles = true}) : changed = projects.where((p) => p.changed).length {
    final byRecency = [...projects.where((p) => p.changed)]..sort((a, b) =>
        (b.latest!.createdAt ?? DateTime(0)).compareTo(a.latest!.createdAt ?? DateTime(0)));
    hero = byRecency.isEmpty ? null : byRecency.first;
    // Tile candidates: what still needs checking first, then what is being read.
    final live = [for (final p in projects) if (p != hero && p.changed) p,
      for (final p in projects) if (p.latest?.inProgress ?? false) p];
    // Tiles come as a pair or not at all: a single square beside a gap reads as a missing project.
    this.tiles = tiles && live.length >= 2 ? live.sublist(0, 2) : const [];
    rows = [for (final p in projects) if (p != hero && !this.tiles.contains(p)) p];
  }

  /// Projects whose latest comparison has unreviewed findings: the headline's count.
  final int changed;
  late final Project? hero;
  late final List<Project> tiles, rows;
}

String homeTopicCount(AppLocalizations l, String topic, int count) => switch (topic) {
  'deadlines' => l.homeTopicDeadlines(count),
  'deliverables' => l.homeTopicDeliverables(count),
  'responsibilities' => l.homeTopicResponsibilities(count),
  'approval_wording' => l.homeTopicApprovalWording(count),
  'budget' => l.homeTopicBudget(count),
  _ => l.homeTopicOther(count),
};

/// What a tile or row says about a project, in words; [error] marks a failed comparison.
({String text, bool error}) homeStatus(AppLocalizations l, Project p) {
  final c = p.latest;
  if (c == null) return (text: l.homeNotCompared, error: false);
  if (c.status == 'waiting_for_versions' && c.laterLabel != null) return (text: l.homeReading(c.laterLabel!), error: false);
  if (c.inProgress) return (text: l.homeComparing, error: false);
  if (!c.hasReport) return (text: l.homeFailed, error: true);
  if (c.findings == 0) return (text: l.reportCount(0), error: false);
  return (text: c.toCheck > 0 ? l.homeToCheck(c.toCheck) : l.homeAllChecked, error: false);
}

/// "2 briefs changed." in `headline`, then a `muted` second line in the same style.
class HomeHeadline extends StatelessWidget {
  const HomeHeadline({super.key, required this.changed});
  final int changed;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final style = Theme.of(context).textTheme.headlineLarge!;
    return Padding(padding: const EdgeInsets.only(top: 8, bottom: 24),
      // One heading for the screen reader; it also names the route.
      child: Semantics(header: true, namesRoute: true, child: Column(
        crossAxisAlignment: CrossAxisAlignment.start, children: [
          CalmFitText(changed > 0 ? l.homeHeadline(changed) : l.homeQuiet, style: style),
          CalmFitText(changed > 0 ? l.homeHeadlineLead : l.homeQuietLead,
            style: style.copyWith(color: CalmColors.of(context).muted)),
        ])));
  }
}

/// A tappable block: one button for assistive tech, with [label] as everything it says.
class _HomeBlock extends StatelessWidget {
  const _HomeBlock({required this.color, required this.radius, required this.label, required this.onTap,
    required this.child});
  final Color color;
  final double radius;
  final String label;
  final VoidCallback onTap;
  final Widget child;

  @override
  Widget build(BuildContext context) => Semantics(button: true, label: label, excludeSemantics: true,
    onTap: onTap, child: Material(color: color, clipBehavior: Clip.antiAlias,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(radius)),
      child: InkWell(onTap: onTap, child: child)));
}

class HomeHero extends StatelessWidget {
  const HomeHero({super.key, required this.project, required this.onTap});
  final Project project;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final colors = CalmColors.of(context);
    final text = Theme.of(context).textTheme;
    final c = project.latest!;
    final ink = colors.onMarker;
    final topics = [for (final t in findingTopics) if ((c.topicCounts?[t] ?? 0) > 0) (t, c.topicCounts![t]!)];
    // Two topics by name, the rest as "+N" (artboard); the screen reader hears all of them.
    final rest = topics.skip(2).fold(0, (sum, t) => sum + t.$2);
    final pair = c.earlierLabel != null && c.laterLabel != null;
    final label = [
      project.name,
      if (pair) l.homePairA11y(c.earlierLabel!, c.laterLabel!),
      l.reportCount(c.findings!),
      for (final (topic, count) in topics) homeTopicCount(l, topic, count),
      if (c.needsReview! > 0) l.homeSecondLook(c.needsReview!),
      l.homeToCheck(c.toCheck),
      l.homeOpenReport,
    ].join(', ');
    return _HomeBlock(color: colors.marker, radius: CalmRadius.xl, label: label, onTap: onTap,
      child: Padding(padding: const EdgeInsets.all(22), child: Column(
        crossAxisAlignment: CrossAxisAlignment.start, children: [
          SizedBox(width: double.infinity, child: Wrap(alignment: WrapAlignment.spaceBetween,
            crossAxisAlignment: WrapCrossAlignment.center, spacing: 12, runSpacing: 4, children: [
              Text(project.name, style: text.titleSmall?.copyWith(color: ink)),
              // The arrow is drawn, not a font glyph: the bundled Roboto has no U+2192.
              if (pair) Text.rich(TextSpan(style: text.bodySmall?.copyWith(color: ink), children: [
                TextSpan(text: '${c.earlierLabel!} '),
                WidgetSpan(alignment: PlaceholderAlignment.middle,
                  child: Icon(CalmIcons.arrowForward, size: 16, color: ink)),
                TextSpan(text: ' ${c.laterLabel!}'),
              ])),
            ])),
          const SizedBox(height: 16),
          Wrap(crossAxisAlignment: WrapCrossAlignment.end, spacing: 10, children: [
            Text('${c.findings}', style: text.displayMedium?.copyWith(color: ink)),
            // "6 things moved": the count is the figure, the words follow it on its baseline.
            Padding(padding: const EdgeInsets.only(bottom: 4),
              child: Text(l.homeMovedUnit(c.findings!), style: text.titleLarge?.copyWith(color: ink))),
          ]),
          if (topics.isNotEmpty) Padding(padding: const EdgeInsets.only(top: 16),
            child: Wrap(spacing: 8, runSpacing: 8, children: [
              for (final (topic, count) in topics.take(2)) _Pill(homeTopicCount(l, topic, count)),
              if (rest > 0) _Pill('+$rest'),
            ])),
          const SizedBox(height: 16),
          Row(children: [
            Expanded(child: Align(alignment: AlignmentDirectional.centerStart,
              child: c.needsReview! > 0 ? HomeReviewPill(text: l.homeSecondLook(c.needsReview!)) : null)),
            const SizedBox(width: 12),
            // The arrow disc is `on-marker` ink with white, in both themes: it sits on marker.
            Container(width: 52, height: 52, alignment: Alignment.center,
              decoration: const BoxDecoration(color: CalmColors.ink, shape: BoxShape.circle),
              child: const Icon(CalmIcons.arrowForward, color: CalmColors.paper, size: 22)),
          ]),
        ])));
  }
}

/// A white pill on the hero: a topic count in words. White, not the topic colour, because the block
/// under it is `marker`.
class _Pill extends StatelessWidget {
  const _Pill(this.text);
  final String text;

  @override
  Widget build(BuildContext context) => DecoratedBox(
    decoration: const ShapeDecoration(color: CalmColors.paper, shape: StadiumBorder()),
    child: Padding(padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
      child: Text(text, style: Theme.of(context).textTheme.labelMedium?.copyWith(color: CalmColors.ink))));
}

/// The "needs a second look" count: `review` fill, always inside its 2px dashed ink border.
class HomeReviewPill extends StatelessWidget {
  const HomeReviewPill({super.key, required this.text});
  final String text;

  @override
  Widget build(BuildContext context) => CustomPaint(
    foregroundPainter: const _DashedPill(),
    child: DecoratedBox(
      decoration: ShapeDecoration(color: CalmColors.of(context).review, shape: const StadiumBorder()),
      child: Padding(padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 7),
        child: Text(text, style: Theme.of(context).textTheme.labelMedium?.copyWith(color: CalmColors.ink)))));
}

class _DashedPill extends CustomPainter {
  const _DashedPill();

  @override
  void paint(Canvas canvas, Size size) {
    const inset = CalmSize.dash / 2;
    final rect = (Offset.zero & size).deflate(inset);
    final paint = Paint()..color = CalmColors.ink..style = PaintingStyle.stroke..strokeWidth = CalmSize.dash;
    final path = Path()..addRRect(RRect.fromRectAndRadius(rect, Radius.circular(rect.height / 2)));
    for (final metric in path.computeMetrics()) {
      for (var d = 0.0; d < metric.length; d += 10) {
        canvas.drawPath(metric.extractPath(d, d + 6), paint);
      }
    }
  }

  @override
  bool shouldRepaint(_DashedPill old) => false;
}

/// A square `surface` tile: the name on top, then a count "to check" or a status in words.
class HomeTile extends StatelessWidget {
  const HomeTile({super.key, required this.project, required this.onTap});
  final Project project;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final colors = CalmColors.of(context);
    final text = Theme.of(context).textTheme;
    final status = homeStatus(l, project);
    return _HomeBlock(color: Theme.of(context).cardTheme.color!, radius: CalmRadius.lg,
      label: '${project.name}, ${status.text}', onTap: onTap,
      child: ConstrainedBox(constraints: const BoxConstraints(minHeight: 148),
        child: Padding(padding: const EdgeInsets.all(18), child: Column(
          crossAxisAlignment: CrossAxisAlignment.start, mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text(project.name, style: text.titleSmall),
            const SizedBox(height: 20),
            if (project.changed) Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('${project.latest!.toCheck}', style: text.headlineLarge),
              Text(l.homeToCheckUnit, style: text.bodySmall?.copyWith(color: text.titleSmall?.color)),
            ]) else Row(children: [
              Icon(CalmIcons.progress, size: 18, color: colors.muted),
              const SizedBox(width: 8),
              Expanded(child: Text(status.text, style: text.bodySmall)),
            ]),
          ]))));
  }
}

/// A plain `surface` row: the name, the client label when there is one, and the status at the end.
class HomeRow extends StatelessWidget {
  const HomeRow({super.key, required this.project, required this.onTap});
  final Project project;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final text = Theme.of(context).textTheme;
    final status = homeStatus(l, project);
    final client = project.clientLabel;
    return _HomeBlock(color: Theme.of(context).cardTheme.color!, radius: CalmRadius.md,
      label: [project.name, ?client, status.text].join(', '), onTap: onTap,
      child: ConstrainedBox(constraints: const BoxConstraints(minHeight: 56),
        child: Padding(padding: const EdgeInsets.symmetric(vertical: 14, horizontal: 18),
          child: Wrap(alignment: WrapAlignment.spaceBetween, crossAxisAlignment: WrapCrossAlignment.center,
            spacing: 14, runSpacing: 4, children: [
              Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisSize: MainAxisSize.min, children: [
                Text(project.name, style: text.titleSmall),
                if (client != null) Text(client, style: text.bodySmall),
              ]),
              // A failure is `error` text and says so in words; everything else is `muted`.
              Text(status.text, style: status.error
                ? text.bodySmall?.copyWith(color: Theme.of(context).colorScheme.error) : text.bodySmall),
            ]))));
  }
}
