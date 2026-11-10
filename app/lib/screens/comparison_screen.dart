// Comparison status, polled until it finishes, then a link to the report (I-10).
import 'dart:async';

import 'package:flutter/material.dart';

import '../api.dart';
import '../design/calm_widgets.dart';
import '../l10n/app_localizations.dart';
import '../services.dart';
import 'report_screen.dart';

String comparisonStatusLabel(AppLocalizations l, String? status) => switch (status) {
  'waiting_for_versions' => l.comparisonReading,
  'queued' => l.comparisonQueued,
  'running' => l.comparisonRunning,
  'complete' => l.comparisonComplete,
  'partial' => l.comparisonPartial,
  'failed' => l.comparisonFailed,
  _ => l.loadingComparison,
};

String rejectionReasonLabel(AppLocalizations l, String? reason) => switch (reason) {
  'no_text_layer' => l.parseNoTextLayer,
  'malformed_pdf' => l.parseMalformedPdf,
  'limit_exceeded_pages' => l.parseTooManyPages,
  'limit_exceeded_words' => l.parseTooManyWords,
  'limit_exceeded_bytes' => l.parseTooManyBytes,
  'limit_exceeded_text' => l.parseTooMuchText,
  'not_utf8' => l.parseNotUtf8,
  'unsupported_type' => l.parseUnsupported,
  'parse_timeout' || 'parse_cpu_limit' => l.parseTimeout,
  'parse_memory_limit' => l.parseMemoryLimit,
  _ => l.parseFailed, // includes parse_failed/parse_crashed; never expose unknown error text
};

class ComparisonScreen extends StatefulWidget {
  const ComparisonScreen({super.key, required this.comparisonId, this.versions = const []});

  final String comparisonId;
  final List<Version> versions;

  @override
  State<ComparisonScreen> createState() => _ComparisonScreenState();
}

class _ComparisonScreenState extends State<ComparisonScreen> {
  Comparison? comparison;
  String? error;
  Timer? timer;
  bool fetching = false;
  List<Version> versions = [];

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (timer == null) {
      versions = List.of(widget.versions);
      _poll();
      timer = Timer.periodic(const Duration(seconds: 2), (_) => _poll());
    }
  }

  Future<void> _poll() async {
    if (fetching) return;
    fetching = true;
    try {
      final api = ServicesScope.of(context).api;
      final c = await api.comparison(widget.comparisonId);
      if (!mounted) return;
      setState(() { comparison = c; error = null; });
      if (c.finished) timer?.cancel();
      final known = {for (final version in versions) version.id: version};
      final missing = [for (final id in [c.earlierId, c.laterId])
        if (id.isNotEmpty && (!known.containsKey(id) || (c.finished && known[id]!.status == 'uploaded'))) id];
      final loaded = await Future.wait([for (final id in missing) api.version(id)]);
      if (!mounted) return;
      setState(() {
        versions = [for (final version in versions) if (!missing.contains(version.id)) version, ...loaded];
        error = null;
      });
    } on Exception {
      if (mounted) setState(() => error = AppLocalizations.of(context).comparisonLoadFailed);
    } finally { fetching = false; }
  }

  @override
  void dispose() {
    timer?.cancel();
    super.dispose();
  }

  String _label(String id) => versions.where((v) => v.id == id).map((v) => v.label).firstOrNull ?? '…';

  List<String> _failureMessages(AppLocalizations l, Comparison c) {
    final messages = <String>[];
    for (final warning in c.warnings) {
      if (warning.code == 'cost_ceiling') {
        messages.add(l.comparisonCostStopped);
      } else if (warning.code == 'version_rejected' &&
          [c.earlierId, c.laterId].contains(warning.versionId)) {
        final version = versions.where((version) => version.id == warning.versionId).firstOrNull;
        final label = version?.label ?? (warning.versionId == c.earlierId ? l.sideEarlier : l.sideNewer);
        messages.add(l.comparisonInputRejected(label, rejectionReasonLabel(l, warning.reason ?? version?.rejectReason)));
      }
    }
    if (c.status == 'failed' && messages.isEmpty) messages.add(l.comparisonFailedDetails);
    return messages.toSet().toList();
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final c = comparison;
    final status = comparisonStatusLabel(l, c?.status);
    return Scaffold(
      appBar: AppBar(title: Text(l.comparisonTitle)),
      body: SafeArea(top: false, child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 8, 20, 24),
        child: ListView(children: [
          Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Expanded(child: CalmPageHeader(title: status, liveRegion: true)),
            if (error == null && (c == null || !c.finished)) const Padding(
                padding: EdgeInsets.only(left: 12, top: 20),
                child: SizedBox(width: 22, height: 22, child: CircularProgressIndicator(strokeWidth: 2.5))),
          ]),
          if (c != null) SourcePairSummary(earlier: _label(c.earlierId),
            newer: _label(c.laterId), scope: c.scope),
          if (c != null)
            for (final message in _failureMessages(l, c))
              Padding(padding: const EdgeInsets.only(top: 12),
                child: Semantics(liveRegion: true, child: CalmWarning(text: message))),
          if (error != null) ...[
            Padding(padding: const EdgeInsets.only(top: 12), child: CalmWarning(text: error!)),
            Align(alignment: AlignmentDirectional.centerStart,
              child: TextButton(onPressed: fetching ? null : _poll, child: Text(l.retry))),
          ],
          if (c != null && c.finished && c.status != 'failed')
            Padding(
              padding: const EdgeInsets.only(top: 24),
              child: FilledButton.icon(
                icon: const Icon(Icons.article_outlined),
                label: Text(l.openReport),
                onPressed: () => Navigator.of(context).push(MaterialPageRoute(
                    builder: (_) => ReportScreen(comparisonId: c.id, versions: versions, scope: c.scope))),
              ),
            ),
          if (c != null && !c.finished) ...[
            const SizedBox(height: 24),
            Text(l.comparisonReturnHint, style: Theme.of(context).textTheme.bodySmall),
            const SizedBox(height: 12),
            OutlinedButton(onPressed: () => Navigator.of(context).popUntil((route) => route.isFirst),
              child: Text(l.returnToProjects)),
          ],
        ]),
      )),
    );
  }
}
