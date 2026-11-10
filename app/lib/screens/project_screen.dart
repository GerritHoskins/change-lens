// A project's versions and comparisons, plus import by paste or PDF picker (AC-24).
// Versions are immutable (AC-15): there is no edit or delete action, only "import a new version".
import 'dart:async';
import 'package:flutter/material.dart';

import '../api.dart';
import '../design/calm_theme.dart';
import '../design/calm_widgets.dart';
import '../l10n/app_localizations.dart';
import '../services.dart';
import 'comparison_screen.dart';
import 'compare_screen.dart';

class ProjectScreen extends StatefulWidget {
  const ProjectScreen({super.key, required this.project});

  final Project project;

  @override
  State<ProjectScreen> createState() => _ProjectScreenState();
}

class _ProjectScreenState extends State<ProjectScreen> {
  List<Version> versions = [];
  List<Comparison> comparisons = [];
  String? error;
  bool loading = true, importing = false;
  bool _fetching = false, _initialized = false;
  bool _deleteStarted = false, _deleting = false, _deleteFailed = false;
  Timer? _timer;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!_initialized) {
      _initialized = true;
      _load();
      _timer = Timer.periodic(const Duration(seconds: 3), (_) {
        if (ModalRoute.of(context)?.isCurrent == true) _load();
      });
    }
  }

  @override
  void dispose() { _timer?.cancel(); super.dispose(); }

  Future<void> _load() async {
    if (_fetching || _deleteStarted) return;
    _fetching = true;
    final api = ServicesScope.of(context).api;
    try {
      final v = await api.versions(widget.project.id);
      final c = await api.comparisons(widget.project.id);
      if (!mounted || _deleteStarted) return;
      setState(() {
        versions = v;
        comparisons = c;
        loading = false;
        error = null;
      });
    } on Exception catch (e) {
      if (!mounted || _deleteStarted) return;
      setState(() {
        loading = false;
        error = '$e';
      });
    } finally { _fetching = false; }
  }

  Future<void> _confirmDelete() async {
    final l = AppLocalizations.of(context);
    final confirmed = await showAdaptiveDialog<bool>(
      context: context,
      builder: (context) => AlertDialog.adaptive(
        scrollable: true,
        title: Text(l.deleteProject),
        content: Text(l.deleteProjectConfirmation(widget.project.name)),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context, false), child: Text(l.cancel)),
          TextButton(
            key: const Key('confirm-delete-project'),
            style: TextButton.styleFrom(foregroundColor: Theme.of(context).colorScheme.error),
            onPressed: () => Navigator.pop(context, true),
            child: Text(l.deleteProject),
          ),
        ],
      ),
    );
    if (confirmed == true && mounted) await _delete();
  }

  Future<void> _delete() async {
    if (_deleting) return;
    final services = ServicesScope.of(context);
    _timer?.cancel();
    if (services.pendingComparison?.project.id == widget.project.id) {
      services.pendingComparison = null;
    }
    setState(() {
      _deleteStarted = true;
      _deleting = true;
      _deleteFailed = false;
      versions = [];
      comparisons = [];
      error = null;
    });
    try {
      final complete = await services.api.deleteProject(widget.project.id);
      if (!mounted) return;
      setState(() => _deleting = false);
      Navigator.of(context).pop(complete);
    } on Exception {
      if (mounted) setState(() { _deleting = false; _deleteFailed = true; });
    }
  }

  /// Asks for a label (and the text, when pasting). Returns null if cancelled.
  Future<(String, String?)?> _askLabel({required bool paste}) {
    final l = AppLocalizations.of(context);
    final label = TextEditingController(), text = TextEditingController();
    return showDialog<(String, String?)>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(paste ? l.importPaste : l.importPdf),
        content: SingleChildScrollView(
          child: Column(mainAxisSize: MainAxisSize.min, children: [
            TextField(
                key: const Key('label'),
                controller: label,
                maxLength: 100,
                decoration: InputDecoration(labelText: l.versionLabel, hintText: l.versionLabelHint)),
            if (paste)
              TextField(
                  key: const Key('pasted'),
                  controller: text,
                  minLines: 4,
                  maxLines: 10,
                  decoration: InputDecoration(hintText: l.pasteHint, border: const OutlineInputBorder())),
          ]),
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: Text(l.cancel)),
          FilledButton(
            key: const Key('confirm-import'),
            onPressed: () {
              if (label.text.trim().isEmpty || (paste && text.text.trim().isEmpty)) return;
              Navigator.pop(context, (label.text.trim(), paste ? text.text : null));
            },
            child: Text(l.upload),
          ),
        ],
      ),
    );
  }

  Future<void> _import({required bool paste}) async {
    final l = AppLocalizations.of(context);
    final services = ServicesScope.of(context);
    final messenger = ScaffoldMessenger.of(context);
    final answer = await _askLabel(paste: paste);
    if (answer == null) return;
    setState(() => importing = true);
    try {
      if (paste) {
        await services.importText(widget.project.id, answer.$1, answer.$2!);
      } else {
        await services.importPdf(widget.project.id, answer.$1);
      }
      await _load();
    } on Exception catch (e) {
      messenger.showSnackBar(SnackBar(content: Text(l.importFailed('$e'))));
    } finally {
      if (mounted) setState(() => importing = false);
    }
  }

  String _status(AppLocalizations l, Version v) => switch (v.status) {
        'parsed' => l.statusParsed,
        'rejected' => l.statusRejected(v.rejectReason ?? ''),
        _ => l.statusUploaded,
      };

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final colors = CalmColors.of(context);
    final text = Theme.of(context).textTheme;
    final byId = {for (final v in versions) v.id: v.label};
    return PopScope(
      canPop: !_deleting,
      child: Scaffold(
      appBar: AppBar(actions: [
        if (!_deleteStarted) PopupMenuButton<String>(
          key: const Key('project-menu'),
          enabled: !importing,
          onSelected: (_) => _confirmDelete(),
          itemBuilder: (_) => [PopupMenuItem(value: 'delete', child: Text(l.deleteProject))],
        ),
      ]),
      body: _deleteStarted ? Center(child: Padding(
        padding: const EdgeInsets.all(24),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          if (_deleting) const CircularProgressIndicator(),
          const SizedBox(height: 16),
          Text(_deleteFailed ? l.deleteProjectFailed : l.deletingProject, textAlign: TextAlign.center),
          if (_deleteFailed) Padding(padding: const EdgeInsets.only(top: 16), child: FilledButton(
            key: const Key('retry-delete-project'), onPressed: _delete, child: Text(l.retryDeleteProject),
          )),
        ]),
      )) : SafeArea(top: false, child: RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          physics: const AlwaysScrollableScrollPhysics(),
          padding: const EdgeInsets.fromLTRB(20, 8, 20, 32), children: [
          CalmPageHeader(title: widget.project.name, subtitle: widget.project.clientLabel),
          if (loading) const LinearProgressIndicator(),
          if (error != null) Padding(padding: const EdgeInsets.only(bottom: 16),
            child: CalmWarning(text: error!, child: TextButton(onPressed: _load, child: Text(l.retry)))),
          FilledButton.icon(
            key: const Key('compare'),
            onPressed: () async {
              await Navigator.of(context).push(MaterialPageRoute(
                builder: (_) => CompareScreen(project: widget.project, versions: versions)));
              if (mounted) await _load();
            },
            icon: const Icon(Icons.compare_arrows),
            label: Text(l.compareBriefs),
          ),
          const SizedBox(height: 16),
          Wrap(spacing: 8, runSpacing: 8, children: [
            OutlinedButton.icon(
                key: const Key('paste'),
                onPressed: importing ? null : () => _import(paste: true),
                icon: const Icon(Icons.content_paste),
                label: Text(l.importPaste)),
            OutlinedButton.icon(
                key: const Key('pick-pdf'),
                onPressed: importing ? null : () => _import(paste: false),
                icon: const Icon(Icons.upload_file),
                label: Text(l.importPdf)),
          ]),
          if (importing) Padding(padding: const EdgeInsets.only(top: 12),
            child: Semantics(liveRegion: true, child: Text(l.uploading))),
          const SizedBox(height: 32),
          Semantics(header: true, child: Text(l.comparisonsTitle, style: text.titleLarge)),
          const SizedBox(height: 12),
          if (!loading && comparisons.isEmpty) Padding(padding: const EdgeInsets.symmetric(vertical: 8),
            child: Text(l.comparisonsEmpty, style: text.bodyMedium?.copyWith(color: colors.muted))),
          for (final c in comparisons)
            Material(color: Colors.transparent, child: InkWell(
              borderRadius: BorderRadius.circular(CalmRadius.md),
              onTap: () => Navigator.of(context).push(MaterialPageRoute(
                  builder: (_) => ComparisonScreen(comparisonId: c.id, versions: versions))),
              child: Container(padding: const EdgeInsets.symmetric(vertical: 16),
                decoration: BoxDecoration(border: Border(bottom: BorderSide(color: colors.line))),
                child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
                  SourcePairSummary(framed: false,
                    earlier: byId[c.earlierId] ?? l.sourceUnavailable,
                    newer: byId[c.laterId] ?? l.sourceUnavailable,
                    scope: c.scope),
                  const SizedBox(height: 8),
                  Row(children: [
                    Expanded(child: Text(comparisonStatusLabel(l, c.status), style: text.labelLarge?.copyWith(
                      color: c.status == 'failed' ? Theme.of(context).colorScheme.error
                        : c.status == 'partial' ? colors.warning : colors.muted))),
                    const SizedBox(width: 12),
                    Icon(Icons.chevron_right, color: colors.muted),
                  ]),
                ])),
            )),
          const SizedBox(height: 28),
          Semantics(header: true, child: Text(l.versionsTitle, style: text.titleLarge)),
          const SizedBox(height: 8),
          if (!loading && versions.isEmpty) Padding(padding: const EdgeInsets.symmetric(vertical: 12),
            child: Text(l.versionsEmpty, style: text.bodyMedium?.copyWith(color: colors.muted))),
          for (final v in versions)
            Container(
              key: Key('version-${v.id}'),
              padding: const EdgeInsets.symmetric(vertical: 16),
              decoration: BoxDecoration(border: Border(bottom: BorderSide(color: colors.line))),
              child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
                Padding(padding: const EdgeInsets.only(top: 2),
                  child: Icon(v.kind == 'pdf' ? Icons.picture_as_pdf_outlined : Icons.notes, color: colors.muted)),
                const SizedBox(width: 12),
                Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Text(v.label, style: text.titleMedium),
                  const SizedBox(height: 5),
                  Text([_status(l, v), if (v.warnings > 0) l.warningsCount(v.warnings)].join(' · '),
                    style: text.bodyMedium?.copyWith(color: v.status == 'rejected' ? Theme.of(context).colorScheme.error : colors.muted)),
                ])),
              ]),
            ),
          const SizedBox(height: 16),
          Text(l.originalsNote, style: text.bodySmall?.copyWith(color: colors.muted)),
        ]),
      )),
      ),
    );
  }
}
