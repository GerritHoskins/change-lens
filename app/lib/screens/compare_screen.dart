// One confirmed submission: selected order, project and scope, with originals in memory only.
import 'package:flutter/material.dart';

import '../api.dart';
import '../design/calm_controls.dart';
import '../design/calm_icons.dart';
import '../design/calm_theme.dart';
import '../design/calm_widgets.dart';
import '../l10n/app_localizations.dart';
import '../services.dart';
import 'comparison_screen.dart';
import 'definition_sheets.dart';

class CompareScreen extends StatefulWidget {
  const CompareScreen({super.key, this.project, this.versions = const [], this.earlierId, this.laterId});

  final Project? project;
  final List<Version> versions;

  /// A version the user chose from the project's history: preset as Earlier, nothing else.
  final String? earlierId;

  /// With [earlierId], from a failed comparison's "Compare again": the same pair, scope still unset.
  final String? laterId;

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
    } else if (widget.earlierId != null) {
      earlier = ComparisonInput.existing(widget.earlierId);
      if (widget.laterId != null) later = ComparisonInput.existing(widget.laterId);
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
    final input = await showCalmSheet<ComparisonInput>(context,
        builder: (_) => _InputSheet(paste: paste, services: services!));
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
      child: CalmCard(child: CalmSurfaceScope(child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Semantics(header: true, child: Text(label, style: text.titleMedium)),
      const SizedBox(height: 12),
      if (value != null && value.versionId == null)
        Padding(padding: const EdgeInsets.only(bottom: 12), child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Icon(value.bytes == null ? CalmIcons.text : CalmIcons.document, color: colors.muted),
          const SizedBox(width: 10),
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(value.label!, style: text.titleMedium),
            const SizedBox(height: 4),
            Text(l.readyToSubmit, style: text.bodyMedium?.copyWith(color: colors.muted)),
          ])),
        ])),
      if (versions.isNotEmpty) Padding(padding: const EdgeInsets.only(bottom: 4),
        child: CalmSelectField<String>(
          key: ValueKey('$key-${value?.versionId ?? "new"}'),
          label: l.chooseVersion,
          value: currentExists ? value?.versionId : null,
          options: [for (final v in versions) CalmOption(v.id, v.label, enabled: v.status != 'rejected')],
          onChanged: locked ? null : (id) => setState(() {
            final input = ComparisonInput.existing(id);
            if (before) { earlier = input; } else { later = input; }
          }),
        )),
      // Secondary actions: plain ink text buttons, aligned with the card's text edge.
      Transform.translate(offset: const Offset(-12, 0), child: Wrap(spacing: 4, children: [
        TextButton.icon(key: Key('$key-paste'), onPressed: locked ? null : () => _input(before, paste: true),
            icon: const Icon(CalmIcons.paste), label: Text(l.importPaste)),
        TextButton.icon(key: Key('$key-pdf'), onPressed: locked ? null : () => _input(before, paste: false),
            icon: const Icon(CalmIcons.pickPdf), label: Text(l.importPdf)),
      ])),
    ]))));
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
          CalmSelectField<String>(key: const Key('comparison-project'),
            label: l.projectName, value: project?.id,
            options: [for (final p in projects) CalmOption(p.id, p.name, detail: p.clientLabel)],
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
            icon: const Icon(CalmIcons.swap), label: Text(l.swapVersions)))),
        _slot(false),
        if (!distinct) Padding(padding: const EdgeInsets.only(top: 12), child: CalmWarning(text: l.sameVersion)),
        const SizedBox(height: 28),
        Row(children: [
          Expanded(child: Semantics(header: true, child: Text(l.scopeQuestion, style: text.titleLarge))),
          CalmInfoButton(key: const Key('info-scope'), term: l.scopeQuestion,
            sheet: (_) => const ScopeDefinitionSheet()),
        ]),
        const SizedBox(height: 12),
        RadioGroup<Scope>(groupValue: scope,
          onChanged: (s) { if (!locked) setState(() => scope = s); },
          child: CalmRadioRows(children: [for (final e in scopes.entries) CalmRadioRow<Scope>(
            key: Key('scope-${e.key.name}'), value: e.key, enabled: !locked,
            title: e.value.$1, subtitle: e.value.$2)])),
        const SizedBox(height: 24),
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

class _InputSheet extends StatefulWidget {
  const _InputSheet({required this.paste, required this.services});
  final bool paste;
  final Services services;
  @override
  State<_InputSheet> createState() => _InputSheetState();
}

class _InputSheetState extends State<_InputSheet> {
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
    return CalmSheet(
      title: widget.paste ? l.importPaste : l.importPdf,
      action: widget.paste ? l.useText : l.importPdf, actionKey: const Key('confirm-import'),
      onAction: busy ? null : _choose,
      children: [
        TextField(key: const Key('label'), controller: label, maxLength: 100, autofocus: true,
            decoration: InputDecoration(labelText: l.versionLabel, hintText: l.versionLabelHint)),
        if (widget.paste) TextField(key: const Key('pasted'), controller: text, minLines: 4, maxLines: 10,
            decoration: InputDecoration(hintText: l.pasteHint)),
        if (error != null) Semantics(liveRegion: true, child: CalmWarning(text: error!)),
      ],
    );
  }
}
