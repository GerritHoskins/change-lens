// A project's history (P6 timeline: versions linked by the comparisons the user ran), plus import
// by paste or PDF picker (AC-24).
// Versions are immutable (AC-15): there is no edit or delete action, only "import a new version".
import 'dart:async';
import 'package:flutter/material.dart';

import '../api.dart';
import '../design/calm_controls.dart';
import '../design/calm_icons.dart';
import '../design/calm_theme.dart';
import '../design/calm_widgets.dart';
import '../l10n/app_localizations.dart';
import '../services.dart';
import 'compare_screen.dart';
import 'comparison_screen.dart' show comparisonStatusLabel, rejectionReasonLabel;
import 'project_timeline.dart';

class ProjectScreen extends StatefulWidget {
  const ProjectScreen({super.key, required this.project});

  /// Names this screen's route, so the review summary can return here ("Back to the project").
  static const routeName = 'project';

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
        if (appInForeground() && ModalRoute.of(context)?.isCurrent == true) _load();
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
      // A comparison that finishes while this screen is open is announced once (cards update silently).
      final l = AppLocalizations.of(context);
      final before = {for (final old in comparisons) old.id: old.finished};
      String label(String id) => v.where((x) => x.id == id).firstOrNull?.label ?? l.sourceUnavailable;
      for (final now in c) {
        if (now.finished && before[now.id] == false) {
          calmAnnounce(context, l.historyComparisonDone(label(now.earlierId), label(now.laterId),
            comparisonStatusLabel(l, now.status)));
        }
      }
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
        error = userErrorMessage(AppLocalizations.of(context), e);
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

  /// Asks for a label (and the text, when pasting), starting from [draft] and showing why the last
  /// attempt failed. Returns null if cancelled.
  Future<(String, String?)?> _askLabel({required bool paste, (String, String?)? draft, String? failure}) {
    final l = AppLocalizations.of(context);
    final form = GlobalKey<FormState>();
    final label = TextEditingController(text: draft?.$1), text = TextEditingController(text: draft?.$2);
    return showCalmSheet<(String, String?)>(context, builder: (context) => Form(key: form, child: CalmSheet(
      title: paste ? l.importPaste : l.importPdf,
      action: l.upload, actionKey: const Key('confirm-import'),
      onAction: () {
        if (!form.currentState!.validate()) return;
        Navigator.pop(context, (label.text.trim(), paste ? text.text : null));
      },
      children: [
        if (failure != null) Semantics(liveRegion: true, child: CalmWarning(text: failure)),
        TextFormField(key: const Key('label'), controller: label, maxLength: 100, autofocus: true,
          validator: calmRequired(l.requiredVersionLabel), autovalidateMode: AutovalidateMode.onUserInteraction,
          decoration: InputDecoration(labelText: l.versionLabel, hintText: l.versionLabelHint)),
        if (paste) TextFormField(key: const Key('pasted'), controller: text, minLines: 4, maxLines: 10,
          validator: calmRequired(l.requiredPastedText), autovalidateMode: AutovalidateMode.onUserInteraction,
          decoration: InputDecoration(hintText: l.pasteHint)),
      ],
    )));
  }

  /// A failed upload reopens the sheet with what the user typed. The draft lives in this call only:
  /// Cancel or a success drops it, and nothing is written to the device (AC-25).
  Future<void> _import({required bool paste}) async {
    final l = AppLocalizations.of(context);
    final services = ServicesScope.of(context);
    (String, String?)? draft;
    String? failure;
    while (mounted) {
      final answer = await _askLabel(paste: paste, draft: draft, failure: failure);
      if (answer == null || !mounted) return;
      setState(() => importing = true);
      try {
        if (paste) {
          await services.importText(widget.project.id, answer.$1, answer.$2!);
        } else {
          await services.importPdf(widget.project.id, answer.$1);
        }
        await _load();
        return;
      } on Exception catch (e) {
        draft = answer;
        // A limit the server enforces names the limit and the way out, like any rejected input.
        failure = l.importFailed(e is ApiException && e.code == 'limit_exceeded' && e.detail != null
            ? rejectionReasonLabel(l, 'limit_exceeded_${e.detail}') : userErrorMessage(l, e));
      } finally {
        if (mounted) setState(() => importing = false);
      }
    }
  }

  Future<void> _compare({String? earlierId, String? laterId}) async {
    await Navigator.of(context).push(MaterialPageRoute(builder: (_) =>
        CompareScreen(project: widget.project, versions: versions, earlierId: earlierId, laterId: laterId)));
    if (mounted) await _load();
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final colors = CalmColors.of(context);
    final text = Theme.of(context).textTheme;
    return PopScope(
      canPop: !_deleting,
      child: Scaffold(
      appBar: AppBar(actions: [
        if (!_deleteStarted) Padding(padding: const EdgeInsetsDirectional.only(end: 12), child: PopupMenuButton<String>(
          key: const Key('project-menu'),
          enabled: !importing,
          icon: Icon(Theme.of(context).platform == TargetPlatform.iOS ? CalmIcons.moreIOS : CalmIcons.more),
          onSelected: (_) => _confirmDelete(),
          itemBuilder: (_) => [PopupMenuItem(value: 'delete', child: Text(l.deleteProject,
            style: text.labelLarge?.copyWith(color: Theme.of(context).colorScheme.error)))],
        )),
      ]),
      // The main action sits in the thumb zone, as on Finding and the review summary.
      bottomNavigationBar: _deleteStarted ? null : SafeArea(child: Padding(
        padding: const EdgeInsets.fromLTRB(20, 8, 20, 16),
        child: FilledButton.icon(key: const Key('compare'), onPressed: _compare,
          icon: const Icon(CalmIcons.compare), label: Text(l.compareBriefs)))),
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
          Wrap(spacing: 8, runSpacing: 8, children: [
            TextButton.icon(
                key: const Key('paste'),
                onPressed: importing ? null : () => _import(paste: true),
                icon: const Icon(CalmIcons.paste),
                label: Text(l.importPaste)),
            TextButton.icon(
                key: const Key('pick-pdf'),
                onPressed: importing ? null : () => _import(paste: false),
                icon: const Icon(CalmIcons.pickPdf),
                label: Text(l.importPdf)),
          ]),
          if (importing) Padding(padding: const EdgeInsets.only(top: 12),
            child: Semantics(liveRegion: true, child: Text(l.uploading))),
          const SizedBox(height: 32),
          ProjectTimeline(versions: versions, comparisons: comparisons, loading: loading,
            onCompareFrom: (version) => _compare(earlierId: version.id),
            onCompareAgain: (c) => _compare(earlierId: c.earlierId, laterId: c.laterId)),
          const SizedBox(height: 16),
          Text(l.originalsNote, style: text.bodySmall?.copyWith(color: colors.muted)),
        ]),
      )),
      ),
    );
  }
}
