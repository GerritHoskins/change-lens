// The report (02 §4, I-10): material changes first, then "Needs your review", with the
// "Selected summary" line linking to every difference (AC-10, AC-13). Withheld findings are only
// counted, never shown (AC-10). Text no finding explains is listed under all differences (AC-18).
import 'package:flutter/material.dart';

import '../api.dart';
import '../design/calm_theme.dart';
import '../design/calm_widgets.dart';
import '../l10n/app_localizations.dart';
import '../services.dart';
import 'definition_sheets.dart';
import 'evidence_screen.dart';
import 'finding_screen.dart';
import 'report_widgets.dart';

class ReportScreen extends StatefulWidget {
  const ReportScreen({super.key, required this.comparisonId, this.versions = const [], this.scope});

  final String comparisonId;
  final String? scope;
  final List<Version> versions;

  @override
  State<ReportScreen> createState() => _ReportScreenState();
}

class _ReportScreenState extends State<ReportScreen> {
  Report? report;
  String? error;
  String? topic;
  bool loading = false, opened = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!loading && report == null && error == null) _load();
  }

  Future<void> _load() async {
    if (loading) return;
    setState(() { loading = true; error = null; });
    try {
      final api = ServicesScope.of(context).api;
      if (!opened) {
        await api.comparisonOpened(widget.comparisonId);
        opened = true;
      }
      if (!mounted) return;
      final r = await api.report(widget.comparisonId);
      if (!mounted) return;
      setState(() {
        report = r;
        error = null;
      });
    } on Exception catch (e) {
      if (mounted) setState(() => error = '$e');
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> _open(Finding f) async {
    await Navigator.of(context).push(MaterialPageRoute(
        builder: (_) => FindingScreen(comparisonId: widget.comparisonId,
            findingId: f.id, report: report!, versions: widget.versions)));
    if (mounted) await _load(); // a review or correction changes the list, but is not another opening
  }

  String _label(String id, AppLocalizations l) =>
      widget.versions.where((v) => v.id == id).firstOrNull?.label ?? l.sourceUnavailable;

  Future<void> _allDifferences() => Navigator.of(context).push(MaterialPageRoute<void>(
      builder: (_) => AllDifferencesScreen(report: report!, versions: widget.versions,
        initialTopic: topic, scope: report!.scope ?? widget.scope, onOpen: _open, latestReport: () => report!)));

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final r = report;
    final colors = CalmColors.of(context);
    final needsReview = r?.inGroup('needs_review') ?? <Finding>[];
    final reviewed = r?.findings.where((f) =>
      const {'confirmed', 'corrected', 'dismissed'}.contains(f.review?.action)).length ?? 0;
    return Scaffold(
      appBar: AppBar(title: r == null ? Text(l.reportTitle) : null),
      body: r == null
          ? error == null ? Center(child: CircularProgressIndicator(semanticsLabel: l.loading)) :
              CalmLoadError(onRetry: loading ? null : _load)
          : RefreshIndicator.adaptive(
              onRefresh: _load,
              child: ListView(
                key: PageStorageKey('report-${widget.comparisonId}'),
                physics: const AlwaysScrollableScrollPhysics(),
                padding: EdgeInsets.fromLTRB(20, 8, 20, 32 + MediaQuery.viewPaddingOf(context).bottom), children: [
                // The result leads: "6 things moved".
                // Only what this screen lists is counted; the rest is under "more differences".
                CalmPageHeader(title: l.reportCount(needsReview.length + r.inGroup('prioritised').length)),
                SourcePairSummary(earlier: _label(r.earlierId, l), newer: _label(r.laterId, l), scope: r.scope ?? widget.scope),
                Padding(padding: const EdgeInsets.only(bottom: 4),
                  child: Text(l.reviewProgress(reviewed, r.findings.length),
                    style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: colors.muted))),
                // The review bar of the report artboard: `action` on `disabled`; the line above says it.
                if (r.findings.isNotEmpty) ExcludeSemantics(child: Padding(
                  padding: const EdgeInsets.only(top: 4, bottom: 14),
                  child: LinearProgressIndicator(value: reviewed / r.findings.length, minHeight: 8,
                    borderRadius: BorderRadius.circular(CalmRadius.sheet), backgroundColor: colors.soft))),
                if (loading) LinearProgressIndicator(semanticsLabel: l.loading),
                if (error != null) CalmWarning(text: l.contentLoadFailed,
                  child: TextButton(onPressed: loading ? null : _load, child: Text(l.retry))),
                ...warnings(l, r),
                TopicFilters(counts: r.topicCounts, selected: topic, onSelected: (value) => setState(() => topic = value)),
                Row(children: [
                  Expanded(child: TextButton(onPressed: _allDifferences,
                    style: TextButton.styleFrom(alignment: AlignmentDirectional.centerStart,
                      padding: const EdgeInsets.symmetric(vertical: 12)),
                    child: Text(l.selectedSummary(r.otherDifferences)))),
                  CalmInfoButton(key: const Key('info-summary'), term: l.defSummaryTitle,
                    sheet: (_) => SummaryDefinitionSheet(otherDifferences: r.otherDifferences,
                      onShowAll: _allDifferences)),
                ]),
                // What needs the user's judgement leads; topic selection never hides it (P-rule: uncertainty
                // stays as reachable as the headline findings).
                if (needsReview.isNotEmpty) ...[
                  SectionHeader('${l.groupNeedsReview} · ${needsReview.length}', hint: l.reviewAcrossTopics),
                  ...topicFindings(l, needsReview, null, _open),
                ],
                SectionHeader(l.groupPrioritised),
                if (!r.inGroup('prioritised').any((f) => topic == null || f.topic == topic))
                  Text(topic == null ? l.noPrioritised : l.noTopicChanges),
                ...topicFindings(l, r.inGroup('prioritised'), topic, _open),
              ]),
            ),
    );
  }
}

List<Widget> warnings(AppLocalizations l, Report r) {
  final messages = [
    if (r.status == 'partial' || r.warnings.contains('unextracted')) l.warningPartial,
    if (r.warnings.contains('hidden_text')) l.warningHidden,
    if (r.warnings.contains('cost_ceiling')) l.warningCeiling,
    if (r.withheld > 0) l.withheld(r.withheld),
  ];
  return [if (messages.isNotEmpty) CalmWarning(kind: CalmMessageKind.warning, text: messages.join('\n\n'))];
}

/// Every finding, then text no finding explains, then moved or reformatted text (AC-5, AC-13, AC-18).
class AllDifferencesScreen extends StatefulWidget {
  const AllDifferencesScreen({super.key, required this.report, required this.versions, required this.onOpen,
    this.initialTopic, this.latestReport, this.scope});

  final Report report;
  final List<Version> versions;
  final Future<void> Function(Finding) onOpen;
  final String? initialTopic;
  final String? scope;
  /// Read the refreshed report after returning from a finding without discarding this route.
  final Report Function()? latestReport;

  @override
  State<AllDifferencesScreen> createState() => _AllDifferencesScreenState();
}

class _AllDifferencesScreenState extends State<AllDifferencesScreen> {
  late String? topic = widget.initialTopic;
  late Report report = widget.report;

  Future<void> _open(Finding finding) async {
    await widget.onOpen(finding);
    if (mounted) setState(() => report = widget.latestReport?.call() ?? report);
  }

  Version? _version(Evidence e) {
    final id = e.earlier ? report.earlierId : report.laterId;
    return widget.versions.where((v) => v.id == id).firstOrNull;
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    Widget quote(Evidence e) => QuoteCard(
          evidence: e,
          versionLabel: _version(e)?.label,
          onTap: _version(e) == null
              ? null
              : () => Navigator.of(context).push(MaterialPageRoute(
                  builder: (_) => EvidenceScreen(version: _version(e)!, evidence: e))),
        );
    return Scaffold(
      appBar: AppBar(),
      body: ListView(
        key: PageStorageKey('all-differences-${report.earlierId}-${report.laterId}'),
        padding: EdgeInsets.fromLTRB(20, 8, 20, 32 + MediaQuery.viewPaddingOf(context).bottom), children: [
        CalmPageHeader(title: l.allDifferencesTitle),
        SourcePairSummary(
          earlier: widget.versions.where((v) => v.id == report.earlierId).firstOrNull?.label ?? l.sourceUnavailable,
          newer: widget.versions.where((v) => v.id == report.laterId).firstOrNull?.label ?? l.sourceUnavailable,
          scope: report.scope ?? widget.scope),
        ...warnings(l, report),
        TopicFilters(counts: report.topicCounts, selected: topic, onSelected: (value) => setState(() => topic = value)),
        for (final (group, title) in [('needs_review', l.groupNeedsReview), ('prioritised', l.groupPrioritised),
                                      ('other', l.groupOther)])
          if (report.inGroup(group).any((f) => topic == null || f.topic == topic)) ...[
            SectionHeader(title),
            ...topicFindings(l, report.inGroup(group), topic, _open),
          ],
        if (report.unexplained.isNotEmpty)
          ExpansionTile(
            key: const PageStorageKey('unexplained-differences'),
            tilePadding: EdgeInsets.zero,
            title: Text('${l.unexplainedTitle} (${report.unexplained.length})'),
            subtitle: Text(l.unexplainedHint),
            children: [for (final e in report.unexplained) quote(e)],
          ),
        if (report.presentationOnly.isNotEmpty)
          ExpansionTile(
            key: const PageStorageKey('presentation-differences'),
            tilePadding: EdgeInsets.zero,
            title: Text('${l.presentationTitle} (${report.presentationOnly.length})'),
            children: [for (final e in report.presentationOnly) quote(e)],
          ),
      ]),
    );
  }
}
