// One confirmed submission: selected order, project and scope, with originals in memory only.
import 'package:flutter/material.dart';

import '../api.dart';
import '../design/calm_theme.dart';
import '../design/calm_widgets.dart';
import '../l10n/app_localizations.dart';
import '../services.dart';
import 'comparison_screen.dart';

class CompareScreen extends StatefulWidget {
  const CompareScreen({super.key, this.project, this.versions = const []});

  final Project? project;
  final List<Version> versions;

  @override
  State<CompareScreen> createState() => _CompareScreenState();
}

class _CompareScreenState extends State<CompareScreen> {
  Project? project;
  List<Project> projects = [];
  List<Version> versions = [];
  ComparisonInput? earlier, later;
  Scope? scope;
  Services? services;
  bool busy = false, loading = false, initialized = false;
  String? error;
  ComparisonSubmission? submission;

  bool get locked => busy || submission != null;
  bool get distinct => earlier?.versionId == null || later?.versionId == null ||
      earlier!.versionId != later!.versionId;
  bool get complete => project != null && earlier != null && later != null && scope != null && distinct;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    services = ServicesScope.of(context);
    if (initialized) return;
    initialized = true;
    final pending = services!.pendingComparison;
    project = pending?.project ?? widget.project;
    versions = List.of(widget.versions);
    if (pending != null) {
      submission = pending;
      earlier = pending.earlier;
      later = pending.later;
      scope = pending.scope;
    }
    _load();
  }

  Future<void> _load() async {
    setState(() => loading = true);
    final selected = project;
    try {
      final p = await services!.api.projects();
      final v = selected == null ? <Version>[] : await services!.api.versions(selected.id);
      if (!mounted || project?.id != selected?.id) return;
      setState(() { projects = p; versions = v; loading = false; error = null; });
    } on Exception {
      if (mounted && project?.id == selected?.id) {
        setState(() { loading = false; error = AppLocalizations.of(context).compareLoadFailed; });
      }
    }
  }

  Future<void> _input(bool before, {required bool paste}) async {
    final input = await showDialog<ComparisonInput>(context: context,
        builder: (_) => _InputDialog(paste: paste, services: services!));
    if (input == null || !mounted) return;
    setState(() { if (before) { earlier = input; } else { later = input; } error = null; });
  }

  Future<void> _start() async {
    if (!complete || busy) return;
    final s = submission ?? ComparisonSubmission(project!, earlier!, later!, scope!);
    submission = s;
    services!.pendingComparison = s; // transport retry survives navigation, never written to disk
    setState(() { busy = true; error = null; });
    try {
      final c = await services!.api.createComparison(s.project.id, s.earlier, s.later, s.scope,
          idempotencyKey: s.key);
      if (identical(services!.pendingComparison, s)) services!.pendingComparison = null;
      if (!mounted) return;
      await Navigator.of(context).pushReplacement(MaterialPageRoute(
          builder: (_) => ComparisonScreen(comparisonId: c.id, versions: versions)));
    } on Exception catch (e) {
      // A definitive validation rejection permits editing. Ambiguous transport/server failures
      // retain the exact key and body, even if the user leaves and comes back to this screen.
      final rejected = e is ApiException && e.status >= 400 && e.status < 500 &&
          !const {408, 409, 429}.contains(e.status);
      if (rejected) {
        if (identical(services!.pendingComparison, s)) services!.pendingComparison = null;
        submission = null;
      }
      if (!mounted) return;
      setState(() {
        busy = false;
        error = rejected ? AppLocalizations.of(context).compareRejected :
            AppLocalizations.of(context).compareRetrySame;
      });
    }
  }

  Widget _slot(bool before) {
    final l = AppLocalizations.of(context);
    final colors = CalmColors.of(context);
    final text = Theme.of(context).textTheme;
    final value = before ? earlier : later;
    final label = before ? l.earlierVersion : l.newerVersion;
    final key = before ? 'earlier' : 'newer';
    final currentExists = versions.any((v) => v.id == value?.versionId);
    return DecoratedBox(
      position: DecorationPosition.foreground,
      decoration: BoxDecoration(
        borderRadius: BorderRadius.circular(CalmRadius.lg),
        border: before ? null : Border.all(color: colors.marker, width: 2)),
      child: CalmCard(child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Semantics(header: true, child: Text(label, style: text.titleMedium)),
      const SizedBox(height: 12),
      if (value != null && value.versionId == null)
        Padding(padding: const EdgeInsets.only(bottom: 12), child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Icon(value.bytes == null ? Icons.notes : Icons.picture_as_pdf_outlined, color: colors.muted),
          const SizedBox(width: 10),
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(value.label!, style: text.titleMedium),
            const SizedBox(height: 4),
            Text(l.readyToSubmit, style: text.bodyMedium?.copyWith(color: colors.muted)),
          ])),
        ])),
      if (versions.isNotEmpty)
        DropdownButtonFormField<String>(
          key: ValueKey('$key-${value?.versionId ?? "new"}'),
          initialValue: currentExists ? value?.versionId : null,
          isExpanded: true,
          itemHeight: null,
          decoration: InputDecoration(labelText: l.chooseVersion, border: const OutlineInputBorder()),
          items: [for (final v in versions) DropdownMenuItem(value: v.id, enabled: v.status != 'rejected',
              child: Padding(padding: const EdgeInsets.symmetric(vertical: 8), child: Text(v.label)))],
          onChanged: locked ? null : (id) => setState(() {
            final input = id == null ? null : ComparisonInput.existing(id);
            if (before) { earlier = input; } else { later = input; }
          }),
        ),
      const SizedBox(height: 12),
      Wrap(spacing: 8, runSpacing: 8, children: [
        OutlinedButton.icon(key: Key('$key-paste'), onPressed: locked ? null : () => _input(before, paste: true),
            icon: const Icon(Icons.content_paste), label: Text(l.importPaste)),
        OutlinedButton.icon(key: Key('$key-pdf'), onPressed: locked ? null : () => _input(before, paste: false),
            icon: const Icon(Icons.upload_file), label: Text(l.importPdf)),
      ]),
    ])));
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final text = Theme.of(context).textTheme;
    final colors = CalmColors.of(context);
    final scopes = {Scope.complete: (l.scopeComplete, l.scopeCompleteHint),
      Scope.partial: (l.scopePartial, l.scopePartialHint), Scope.unknown: (l.scopeUnknown, l.scopeUnknownHint)};
    return Scaffold(appBar: AppBar(),
      body: SafeArea(top: false, child: SingleChildScrollView(padding: const EdgeInsets.fromLTRB(20, 8, 20, 32),
        child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
        CalmPageHeader(title: l.compareBriefs,
          subtitle: widget.project != null || submission != null ? project!.name : null),
        if (widget.project == null && submission == null) ...[
          DropdownButtonFormField<String>(key: const Key('comparison-project'),
            initialValue: project?.id, isExpanded: true, itemHeight: null,
            decoration: InputDecoration(labelText: l.projectName, border: const OutlineInputBorder()),
            items: [for (final p in projects) DropdownMenuItem(value: p.id, child: Text(p.name))],
            onChanged: locked ? null : (id) {
              setState(() { project = projects.firstWhere((p) => p.id == id); earlier = later = null; versions = []; });
              _load();
            }),
          const SizedBox(height: 16),
        ],
        Text(l.confirmIntro, style: text.bodyMedium?.copyWith(color: colors.muted)),
        if (loading) const LinearProgressIndicator(),
        const SizedBox(height: 20),
        _slot(true),
        Padding(padding: const EdgeInsets.symmetric(vertical: 4),
          child: Align(alignment: AlignmentDirectional.centerEnd, child: TextButton.icon(
            key: const Key('swap-versions'),
            onPressed: locked || (earlier == null && later == null) ? null : () => setState(() {
              final previousEarlier = earlier;
              earlier = later;
              later = previousEarlier;
              scope = null;
              error = null;
            }),
            icon: const Icon(Icons.swap_vert), label: Text(l.swapVersions)))),
        _slot(false),
        if (!distinct) Padding(padding: const EdgeInsets.only(top: 12), child: CalmWarning(text: l.sameVersion)),
        const SizedBox(height: 28),
        Semantics(header: true, child: Text(l.scopeQuestion, style: text.titleLarge)),
        const SizedBox(height: 8),
        RadioGroup<Scope>(groupValue: scope,
          onChanged: (s) { if (!locked) setState(() => scope = s); },
          child: Column(children: [for (final e in scopes.entries) RadioListTile<Scope>(
            key: Key('scope-${e.key.name}'), value: e.key, enabled: !locked,
            contentPadding: EdgeInsets.zero,
            title: Text(e.value.$1, style: text.titleMedium),
            subtitle: Padding(padding: const EdgeInsets.only(top: 4, bottom: 8),
              child: Text(e.value.$2, style: text.bodyMedium?.copyWith(color: colors.muted))))])),
        const SizedBox(height: 16),
        if (error != null) Semantics(liveRegion: true, child: Padding(
            padding: const EdgeInsets.only(bottom: 12), child: CalmWarning(text: error!))),
        if (error == l.compareLoadFailed) TextButton(onPressed: loading ? null : _load, child: Text(l.retry)),
        if (submission != null && !busy && error == null) Text(l.compareRetrySame),
        FilledButton(key: const Key('start'), onPressed: complete && !busy ? _start : null,
            child: Text(busy ? l.submittingComparison : submission != null ? l.retry : l.startComparison)),
        const SizedBox(height: 8),
        Text(l.compareSubmitHint, style: text.bodySmall?.copyWith(color: colors.muted)),
      ]))));
  }
}

class _InputDialog extends StatefulWidget {
  const _InputDialog({required this.paste, required this.services});
  final bool paste;
  final Services services;
  @override
  State<_InputDialog> createState() => _InputDialogState();
}

class _InputDialogState extends State<_InputDialog> {
  final label = TextEditingController(), text = TextEditingController();
  bool busy = false;
  String? error;

  @override
  void dispose() { label.dispose(); text.dispose(); super.dispose(); }

  Future<void> _choose() async {
    if (label.text.trim().isEmpty || (widget.paste && text.text.trim().isEmpty)) return;
    if (widget.paste) {
      Navigator.pop(context, ComparisonInput.paste(label.text.trim(), text.text));
      return;
    }
    setState(() => busy = true);
    try {
      PickedDocument? doc;
      try { doc = await widget.services.picker.pickPdf(); }
      finally { await widget.services.picker.purge(); }
      if (doc != null && mounted) {
        Navigator.pop(context, ComparisonInput.pdf(label.text.trim(), doc.bytes, filename: doc.name));
      }
    } on Exception {
      if (mounted) setState(() => error = AppLocalizations.of(context).comparePickFailed);
    } finally { if (mounted) setState(() => busy = false); }
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    return AlertDialog(title: Text(widget.paste ? l.importPaste : l.importPdf),
      content: SingleChildScrollView(child: Column(mainAxisSize: MainAxisSize.min, children: [
        TextField(key: const Key('label'), controller: label, maxLength: 100,
            decoration: InputDecoration(labelText: l.versionLabel, hintText: l.versionLabelHint)),
        if (widget.paste) TextField(key: const Key('pasted'), controller: text, minLines: 4, maxLines: 10,
            decoration: InputDecoration(hintText: l.pasteHint, border: const OutlineInputBorder())),
        if (error != null) Text(error!),
      ])), actions: [TextButton(onPressed: busy ? null : () => Navigator.pop(context), child: Text(l.cancel)),
        FilledButton(key: const Key('confirm-import'), onPressed: busy ? null : _choose,
            child: Text(widget.paste ? l.useText : l.importPdf))]);
  }
}
