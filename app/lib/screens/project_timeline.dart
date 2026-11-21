// P6 version timeline (WP-D; owner approved the Calm Bold drafts 2026-11-16). One History list
// replaces the Project screen's separate Versions and Comparisons lists.
//
// Order comes only from comparisons the user ran: each comparison links its earlier version to its
// newer one, as the user set them (AC-14). Upload time, list order and file names never place a
// version. Versions compared with the same earlier version but not with each other are a fork:
// shown together, not ranked. Versions in no comparison are listed apart, in label order.
import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart' show CustomSemanticsAction;

import '../api.dart';
import '../design/calm_icons.dart';
import '../design/calm_theme.dart';
import '../l10n/app_localizations.dart';
import 'comparison_screen.dart';

/// A placed version and the comparisons in which it is the newer side.
class TimelineEntry {
  TimelineEntry(this.version, this.links, {required this.bothWays});

  final Version version;
  final List<Comparison> links;

  /// Compared with another version in both directions (A → B and B → A).
  final bool bothWays;
}

/// Versions at the same distance from the oldest in their group. More than one is a fork.
class TimelineGroup {
  TimelineGroup(this.entries);

  final List<TimelineEntry> entries;

  bool get fork => entries.length > 1;
}

class Timeline {
  Timeline(this.components, this.unplaced, this.unattached);

  /// Each connected set of compared versions, newest group first.
  final List<List<TimelineGroup>> components;

  /// Versions in no comparison: their place is unknown.
  final List<Version> unplaced;

  /// Comparisons whose versions aren't in the list (not expected; kept so nothing disappears).
  final List<Comparison> unattached;

  bool get isEmpty => components.isEmpty && unplaced.isEmpty && unattached.isEmpty;
}

int _byLabel(Version a, Version b) {
  final c = a.label.toLowerCase().compareTo(b.label.toLowerCase());
  return c != 0 ? c : a.id.compareTo(b.id);
}

Timeline buildTimeline(List<Version> versions, List<Comparison> comparisons) {
  final byId = {for (final v in versions) v.id: v};
  final edges = <Comparison>[];
  final unattached = <Comparison>[];
  for (final c in comparisons) {
    if (byId.containsKey(c.earlierId) && byId.containsKey(c.laterId) && c.earlierId != c.laterId) {
      edges.add(c);
    } else {
      unattached.add(c);
    }
  }
  final earlierOf = <String, Set<String>>{}; // version → the versions it was compared against as newer
  final neighbours = <String, Set<String>>{};
  for (final c in edges) {
    earlierOf.putIfAbsent(c.laterId, () => {}).add(c.earlierId);
    neighbours.putIfAbsent(c.earlierId, () => {}).add(c.laterId);
    neighbours.putIfAbsent(c.laterId, () => {}).add(c.earlierId);
  }

  // Depth = the longest chain of comparisons below a version. A cycle (both directions) is cut
  // where it closes, so it can't recurse forever.
  final depth = <String, int>{};
  final visiting = <String>{};
  int depthOf(String id) {
    final known = depth[id];
    if (known != null) return known;
    visiting.add(id);
    var d = 0;
    for (final e in earlierOf[id] ?? const <String>{}) {
      if (visiting.contains(e)) continue;
      final below = depthOf(e) + 1;
      if (below > d) d = below;
    }
    visiting.remove(id);
    return depth[id] = d;
  }

  // Components in the order their first comparison appears in the server's list.
  final seen = <String>{};
  final components = <List<TimelineGroup>>[];
  for (final c in edges) {
    if (seen.contains(c.earlierId)) continue;
    final members = <String>[];
    final queue = [c.earlierId];
    seen.add(c.earlierId);
    while (queue.isNotEmpty) {
      final id = queue.removeLast();
      members.add(id);
      for (final n in neighbours[id] ?? const <String>{}) {
        if (seen.add(n)) queue.add(n);
      }
    }
    final byDepth = <int, List<Version>>{};
    for (final id in members) {
      byDepth.putIfAbsent(depthOf(id), () => []).add(byId[id]!);
    }
    final levels = byDepth.keys.toList()..sort((a, b) => b.compareTo(a));
    components.add([
      for (final level in levels)
        TimelineGroup([
          for (final v in byDepth[level]!..sort(_byLabel))
            TimelineEntry(v, [for (final e in edges) if (e.laterId == v.id) e],
              bothWays: (earlierOf[v.id] ?? const <String>{})
                  .any((e) => earlierOf[e]?.contains(v.id) ?? false)),
        ]),
    ]);
  }
  final unplaced = [for (final v in versions) if (!seen.contains(v.id)) v]..sort(_byLabel);
  return Timeline(components, unplaced, unattached);
}

String scopeLabel(AppLocalizations l, String scope) => switch (scope) {
  'complete' => l.scopeComplete,
  'partial' => l.scopePartial,
  _ => l.scopeUnknown,
};

/// Kind, status and warnings. A rejected version's reason is a full sentence, so the tile shows it on
/// its own line ([rejectedLine]); with [withReason] this string carries it for screen readers.
String versionMeta(AppLocalizations l, Version v, {bool withReason = true}) => [
  v.kind == 'pdf' ? l.kindPdf : l.kindText,
  switch (v.status) {
    'parsed' => l.statusParsed,
    'rejected' => withReason ? rejectedLine(l, v) : null,
    _ => l.statusUploaded,
  },
  if (v.warnings > 0) l.warningsCount(v.warnings),
].nonNulls.join(' · ');

/// "Rejected: " plus why, and what to do. An unknown or missing reason uses the generic parse failure.
String rejectedLine(AppLocalizations l, Version v) => l.statusRejected(rejectionReasonLabel(l, v.rejectReason));

/// Large text (about 1.3× and up) trades the decorative extras (chevron, wide gaps) for words that fit.
bool _largeText(BuildContext context) => MediaQuery.textScalerOf(context).scale(10) >= 13;

/// One item on a component's main rail.
sealed class _Item {}

class _VersionItem extends _Item {
  _VersionItem(this.version);
  final Version version;
}

class _LinkItem extends _Item {
  _LinkItem(this.comparison);
  final Comparison comparison;
}

class _ForkItem extends _Item {
  _ForkItem(this.group);
  final TimelineGroup group;
}

/// The History section of the Project screen.
class ProjectTimeline extends StatelessWidget {
  const ProjectTimeline({super.key, required this.versions, required this.comparisons,
    required this.loading, required this.onCompareFrom, this.onCompareAgain});

  final List<Version> versions;
  final List<Comparison> comparisons;
  final bool loading;

  /// Opens Compare with this version preset as Earlier.
  final void Function(Version version) onCompareFrom;

  /// Opens Compare with a failed comparison's pair preset (both versions readable), scope unset.
  final void Function(Comparison comparison)? onCompareAgain;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final colors = CalmColors.of(context);
    final text = Theme.of(context).textTheme;
    final timeline = buildTimeline(versions, comparisons);
    final byId = {for (final v in versions) v.id: v.label};
    String label(String id) => byId[id] ?? l.sourceUnavailable;

    Widget version(Version v, {required bool top, required bool bottom, bool rail = true}) => _VersionTile(
      version: v, top: top, bottom: bottom, rail: rail,
      onTap: v.status == 'rejected' ? null : () => onCompareFrom(v));
    Widget link(Comparison c, {required bool bottom}) => _LinkTile(comparison: c, bottom: bottom,
      earlier: label(c.earlierId), newer: label(c.laterId), versions: versions,
      onCompareAgain: onCompareAgain == null || c.status != 'failed' ||
          ![c.earlierId, c.laterId].every((id) => versions.any((v) => v.id == id && v.ready))
          ? null : () => onCompareAgain!(c));

    final children = <Widget>[
      Semantics(header: true, child: Text(l.historyTitle, style: text.titleLarge)),
      const SizedBox(height: 4),
    ];
    if (timeline.isEmpty) {
      if (!loading) {
        children.add(Padding(padding: const EdgeInsets.only(top: 8),
        child: Column(key: const Key('history-empty'), crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(l.historyEmptyTitle, style: text.titleMedium),
          const SizedBox(height: 6),
          Text(l.historyEmptyBody, style: text.bodyMedium?.copyWith(color: colors.muted)),
        ])));
      }
      return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: children);
    }
    if (timeline.components.isNotEmpty) {
      children.add(Text(l.historyLead, style: text.bodySmall?.copyWith(color: colors.muted)));
    }
    for (final component in timeline.components) {
      children.add(const SizedBox(height: 16));
      // A note qualifies the whole component, so it sits above the rail instead of cutting it.
      if (component.any((g) => g.entries.any((e) => e.bothWays))) {
        children.add(_Note(text: l.historyBothWays, icon: CalmIcons.compare));
      }
      final items = <_Item>[
        for (final group in component)
          if (group.fork) _ForkItem(group)
          else for (final entry in group.entries) ...[
            _VersionItem(entry.version),
            for (final c in entry.links) _LinkItem(c),
          ],
      ];
      for (var i = 0; i < items.length; i++) {
        final top = i > 0, bottom = i < items.length - 1;
        children.add(switch (items[i]) {
          _VersionItem(version: final v) => version(v, top: top, bottom: bottom),
          _LinkItem(:final comparison) => link(comparison, bottom: bottom),
          _ForkItem(:final group) => _ForkBlock(top: top, bottom: bottom, children: [
            _Note(text: l.historyForkNote, icon: CalmIcons.fork),
            for (final (n, entry) in group.entries.indexed) ...[
              if (n > 0) const SizedBox(height: 8),
              version(entry.version, top: false, bottom: entry.links.isNotEmpty),
              for (final (k, c) in entry.links.indexed) link(c, bottom: k < entry.links.length - 1),
            ],
          ]),
        });
      }
    }
    for (final c in timeline.unattached) {
      children.add(link(c, bottom: false));
    }
    if (timeline.unplaced.isNotEmpty) {
      children.addAll([
        const SizedBox(height: 28),
        Semantics(header: true, child: Text(l.historyNotCompared, style: text.titleMedium)),
        const SizedBox(height: 4),
        Text(l.historyNotComparedLead, style: text.bodySmall?.copyWith(color: colors.muted)),
        const SizedBox(height: 4),
        for (final v in timeline.unplaced) version(v, top: false, bottom: false, rail: false),
      ]);
    }
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: children);
  }
}

class _Note extends StatelessWidget {
  const _Note({required this.text, required this.icon});

  final String text;
  final IconData icon;

  @override
  Widget build(BuildContext context) => Padding(padding: const EdgeInsets.only(bottom: 8),
    child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
      SizedBox(width: 20, child: Icon(icon, size: 20, color: CalmColors.of(context).muted)),
      SizedBox(width: _largeText(context) ? 8 : 12),
      Expanded(child: Text(text, style: Theme.of(context).textTheme.bodySmall)),
    ]));
}

/// A fork: its members side by side in time, none ranked. The main rail runs past them, joining what
/// is above to the version they share below; each member keeps its own short rail to its links.
class _ForkBlock extends StatelessWidget {
  const _ForkBlock({required this.top, required this.bottom, required this.children});

  final bool top, bottom;
  final List<Widget> children;

  @override
  Widget build(BuildContext context) => Stack(children: [
    Padding(padding: const EdgeInsetsDirectional.only(start: 16),
      child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: children)),
    // Aligned with the main rail's centre (x 9 to 11 of its 20-pixel column).
    PositionedDirectional(start: 9, top: top ? 0 : 24, bottom: 0,
      child: ExcludeSemantics(child: Container(width: 2, color: bottom ? CalmColors.of(context).line : null))),
  ]);
}

class _Rail extends StatelessWidget {
  const _Rail({required this.top, required this.bottom, required this.child, this.lead});

  final bool top, bottom;
  final Widget child;

  /// Fixed distance from the row's top to [child]; null centres it.
  final double? lead;

  @override
  Widget build(BuildContext context) {
    final line = CalmColors.of(context).line;
    Color? on(bool v) => v ? line : null;
    return ExcludeSemantics(child: SizedBox(width: 20, child: Column(children: [
      if (lead != null) Container(width: 2, height: lead, color: on(top))
      else Expanded(child: Container(width: 2, color: on(top))),
      child,
      Expanded(child: Container(width: 2, color: on(bottom))),
    ])));
  }
}

class _VersionTile extends StatelessWidget {
  const _VersionTile({required this.version, required this.top, required this.bottom, required this.onTap,
    this.rail = true});

  final Version version;
  final bool top, bottom, rail;

  /// Null for a rejected version: it can't be an input, so it offers no comparison.
  final VoidCallback? onTap;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final colors = CalmColors.of(context);
    final text = Theme.of(context).textTheme;
    final ink = Theme.of(context).colorScheme.onSurface;
    final large = _largeText(context);
    final rejected = version.status == 'rejected';
    Widget compareFrom() => Row(mainAxisSize: MainAxisSize.min, children: [
      Icon(CalmIcons.compare, size: 18, color: ink),
      const SizedBox(width: 6),
      // Quiet on purpose: it repeats on every row and must not outweigh the version names.
      Flexible(child: Text(l.historyCompareFrom, style: text.bodySmall?.copyWith(color: colors.muted))),
    ]);
    // The label replaces the row's text, so the tap is passed on with it: without onTap here the
    // node would say "button" and do nothing for TalkBack and VoiceOver.
    return Semantics(key: Key('version-${version.id}'), button: onTap != null, excludeSemantics: true,
      onTap: onTap,
      label: onTap != null ? l.historyVersionA11y(version.label, versionMeta(l, version))
          : '${version.label}, ${versionMeta(l, version)}',
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(CalmRadius.md),
        // The rail is positioned over the row's own height: no second layout pass to measure it.
        child: Stack(children: [
          if (rail) PositionedDirectional(start: 0, top: 0, bottom: 0,
            // The dot sits on the name's first line, however tall the row's details grow.
            child: _Rail(top: top, bottom: bottom, lead: 8 + (MediaQuery.textScalerOf(context).scale(22) - 12) / 2,
              child: Container(width: 12, height: 12, decoration: BoxDecoration(shape: BoxShape.circle, color: ink)))),
          Padding(padding: EdgeInsetsDirectional.only(start: rail ? (large ? 28 : 32) : 0), child: Container(
            constraints: const BoxConstraints(minHeight: 64),
            padding: const EdgeInsets.symmetric(vertical: 8),
            decoration: rail ? null : BoxDecoration(border: Border(bottom: BorderSide(color: colors.line))),
            child: Column(mainAxisAlignment: MainAxisAlignment.center,
              crossAxisAlignment: CrossAxisAlignment.start, children: [
                Text(version.label, style: text.titleMedium),
                const SizedBox(height: 4),
                Text(versionMeta(l, version, withReason: false), style: text.bodySmall?.copyWith(color: colors.muted)),
                if (rejected) ...[
                  const SizedBox(height: 2),
                  Text(rejectedLine(l, version), style: text.bodySmall?.copyWith(
                    color: Theme.of(context).colorScheme.error)),
                ],
                // Always under the details: one place, whatever the language, width or text size.
                if (onTap != null) ...[const SizedBox(height: 8), compareFrom()],
              ]),
          )),
        ]),
      ));
  }
}

class _LinkTile extends StatelessWidget {
  const _LinkTile({required this.comparison, required this.bottom, required this.earlier,
    required this.newer, required this.versions, this.onCompareAgain});

  final Comparison comparison;
  final bool bottom;
  final String earlier, newer;
  final List<Version> versions;
  final VoidCallback? onCompareAgain;

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final colors = CalmColors.of(context);
    final text = Theme.of(context).textTheme;
    final large = _largeText(context);
    final scope = scopeLabel(l, comparison.scope);
    final status = comparisonStatusLabel(l, comparison.status);
    final failed = comparison.status == 'failed', partial = comparison.status == 'partial';
    final statusColor = failed ? Theme.of(context).colorScheme.error : partial ? colors.caution : colors.muted;
    final cause = failed ? comparisonFailureMessages(l, comparison, versions).firstOrNull : null;
    // With Compare again on the card, the generic "start a new comparison" advice would repeat it.
    final why = cause == l.comparisonFailedDetails && onCompareAgain != null ? l.comparisonFailedShort : cause;
    void open() => Navigator.of(context).push(MaterialPageRoute<void>(
      builder: (_) => ComparisonScreen(comparisonId: comparison.id, versions: versions)));
    return Stack(key: Key('link-${comparison.id}'), children: [
        // A plain rail: the card's own "earlier → newer" carries the direction.
        PositionedDirectional(start: 0, top: 0, bottom: 0,
          child: _Rail(top: true, bottom: bottom, child: const SizedBox.shrink())),
        Padding(padding: EdgeInsetsDirectional.only(start: large ? 28 : 32, top: 4, bottom: 4), child: Semantics(
          // One node for the card: its tap opens the comparison, and "Compare again" (hidden with the
          // card's other text) is offered as a custom action.
          button: true, excludeSemantics: true, onTap: open,
          customSemanticsActions: onCompareAgain == null ? null
              : {CustomSemanticsAction(label: l.historyCompareAgain): onCompareAgain!},
          label: [l.historyLinkA11y(earlier, newer, scope, status), ?why].join(' '),
          child: Material(
            color: Theme.of(context).cardTheme.color,
            shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(CalmRadius.md),
              side: BorderSide(color: colors.line)),
            clipBehavior: Clip.antiAlias,
            child: InkWell(
              onTap: open,
              child: Padding(
                padding: large ? const EdgeInsets.all(12) : const EdgeInsetsDirectional.fromSTEB(16, 12, 14, 12),
                child: Row(children: [
                  Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                    // The arrow is drawn, not a font glyph: the bundled Roboto has no U+2192.
                    Text.rich(TextSpan(style: text.bodyLarge, children: [
                      TextSpan(text: '$earlier '),
                      WidgetSpan(alignment: PlaceholderAlignment.middle, child: Icon(CalmIcons.arrowForward, size: 18, color: colors.muted)),
                      TextSpan(text: ' $newer'),
                    ])),
                    const SizedBox(height: 2),
                    Text(scope, style: text.bodySmall?.copyWith(color: colors.muted)),
                    // Only a status that needs attention is emphasised.
                    Text(status, style: (failed || partial ? text.labelMedium : text.bodySmall)
                        ?.copyWith(color: statusColor)),
                    if (why != null) ...[
                      const SizedBox(height: 4),
                      Text(why, style: text.bodySmall),
                    ],
                    if (onCompareAgain != null) Padding(padding: const EdgeInsets.only(top: 4),
                      child: TextButton.icon(key: Key('compare-again-${comparison.id}'), onPressed: onCompareAgain,
                        style: TextButton.styleFrom(padding: EdgeInsets.zero),
                        icon: const Icon(CalmIcons.compare, size: 18), label: Text(l.historyCompareAgain))),
                  ])),
                  if (!large) ...[
                    const SizedBox(width: 12),
                    Icon(CalmIcons.chevronRight, color: colors.muted),
                  ],
                ])),
            ),
          ),
        )),
      ]);
  }
}
