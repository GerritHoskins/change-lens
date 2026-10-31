// The report (02 §4, I-10): material changes first, then "Needs your review", with the
// "Selected summary" line linking to every difference (AC-10, AC-13). Withheld findings are only
// counted, never shown (AC-10). Text no finding explains is listed under all differences (AC-18).
import 'package:flutter/material.dart';

import '../api.dart';
import '../l10n/app_localizations.dart';
import '../services.dart';
import 'evidence_screen.dart';
import 'finding_screen.dart';
import 'report_widgets.dart';

class ReportScreen extends StatefulWidget {
  const ReportScreen({super.key, required this.comparisonId, this.versions = const []});

  final String comparisonId;
  final List<Version> versions;

  @override
  State<ReportScreen> createState() => _ReportScreenState();
}

class _ReportScreenState extends State<ReportScreen> {
  Report? report;
  String? error;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (report == null && error == null) _load();
  }

  Future<void> _load() async {
    try {
      final r = await ServicesScope.of(context).api.report(widget.comparisonId);
      if (!mounted) return;
      setState(() {
        report = r;
        error = null;
      });
    } on Exception catch (e) {
      if (mounted) setState(() => error = '$e');
    }
  }

  Future<void> _open(Finding f) async {
    await Navigator.of(context).push(MaterialPageRoute(
        builder: (_) => FindingScreen(findingId: f.id, report: report!, versions: widget.versions)));
    await _load(); // a review or correction changes the list
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final r = report;
    return Scaffold(
      appBar: AppBar(title: Text(l.reportTitle)),
      body: r == null
          ? Center(child: error == null ? const CircularProgressIndicator() : Text(l.loadFailed(error!)))
          : RefreshIndicator(
              onRefresh: _load,
              child: ListView(padding: const EdgeInsets.all(16), children: [
                ...warnings(l, r),
                Card(
                  child: ListTile(
                    leading: const Icon(Icons.filter_list),
                    title: Text(l.selectedSummary(r.otherDifferences)),
                    subtitle: Text(l.showAllDifferences),
                    onTap: () => Navigator.of(context).push(MaterialPageRoute(
                        builder: (_) => AllDifferencesScreen(report: r, versions: widget.versions, onOpen: _open))),
                  ),
                ),
                SectionHeader(l.groupPrioritised),
                if (r.inGroup('prioritised').isEmpty) Text(l.noPrioritised),
                for (final f in r.inGroup('prioritised')) FindingTile(finding: f, onTap: () => _open(f)),
                if (r.inGroup('needs_review').isNotEmpty) ...[
                  SectionHeader(l.groupNeedsReview),
                  for (final f in r.inGroup('needs_review')) FindingTile(finding: f, onTap: () => _open(f)),
                ],
              ]),
            ),
    );
  }
}

List<Widget> warnings(AppLocalizations l, Report r) => [
      if (r.status == 'partial' || r.warnings.contains('unextracted')) _Banner(l.warningPartial),
      if (r.warnings.contains('hidden_text')) _Banner(l.warningHidden),
      if (r.warnings.contains('cost_ceiling')) _Banner(l.warningCeiling),
      if (r.withheld > 0) _Banner(l.withheld(r.withheld)),
    ];

class _Banner extends StatelessWidget {
  const _Banner(this.text);

  final String text;

  @override
  Widget build(BuildContext context) => Card(
        color: Theme.of(context).colorScheme.tertiaryContainer,
        child: ListTile(leading: const Icon(Icons.info_outline), title: Text(text)),
      );
}

/// Every finding, then text no finding explains, then moved or reformatted text (AC-5, AC-13, AC-18).
class AllDifferencesScreen extends StatelessWidget {
  const AllDifferencesScreen({super.key, required this.report, required this.versions, required this.onOpen});

  final Report report;
  final List<Version> versions;
  final Future<void> Function(Finding) onOpen;

  Version? _version(Evidence e) {
    final id = e.earlier ? report.earlierId : report.laterId;
    return versions.where((v) => v.id == id).firstOrNull;
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    Widget quote(Evidence e) => QuoteCard(
          evidence: e,
          onTap: _version(e) == null
              ? null
              : () => Navigator.of(context).push(MaterialPageRoute(
                  builder: (_) => EvidenceScreen(version: _version(e)!, evidence: e))),
        );
    return Scaffold(
      appBar: AppBar(title: Text(l.allDifferencesTitle)),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        for (final (group, title) in [('prioritised', l.groupPrioritised), ('needs_review', l.groupNeedsReview),
                                      ('other', l.groupOther)])
          if (report.inGroup(group).isNotEmpty) ...[
            SectionHeader(title),
            for (final f in report.inGroup(group))
              FindingTile(finding: f, onTap: () async {
                Navigator.of(context).pop();
                await onOpen(f);
              }),
          ],
        if (report.unexplained.isNotEmpty)
          ExpansionTile(
            tilePadding: EdgeInsets.zero,
            title: Text('${l.unexplainedTitle} (${report.unexplained.length})'),
            subtitle: Text(l.unexplainedHint),
            children: [for (final e in report.unexplained) quote(e)],
          ),
        if (report.presentationOnly.isNotEmpty)
          ExpansionTile(
            tilePadding: EdgeInsets.zero,
            title: Text('${l.presentationTitle} (${report.presentationOnly.length})'),
            children: [for (final e in report.presentationOnly) quote(e)],
          ),
      ]),
    );
  }
}
