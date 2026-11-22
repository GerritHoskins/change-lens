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
  ThemeData? _onMarker; // the newer slot's light colours, built once

  bool get locked => busy || submission != null;
  bool get distinct => earlier?.versionId == null || later?.versionId == null ||
      earlier!.versionId != later!.versionId;
  bool get complete => project != null && earlier != null && later != null && scope != null && distinct;

  /// What Start still waits for, first thing first; null once nothing is missing. The same version on
  /// both sides is not listed: it has its own warning above the button.
  String? _missing(AppLocalizations l) =>
      project == null ? l.compareNeedsProject
      : earlier == null ? l.compareNeedsEarlier
      : later == null ? l.compareNeedsNewer
      : scope == null ? l.compareNeedsScope : null;

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

  /// The earlier slot is a `surface` card whose fields sit on `ground`. The newer slot is filled with
  /// `marker` (marker means new): like `on-marker`, its content keeps the light theme's colours in
  /// both themes, so the text is ink and the field white.
  Widget _slot(bool before) {
    if (before) return CalmCard(child: CalmSurfaceScope(child: Builder(builder: (context) => _slotContent(context, true))));
    return Theme(data: _onMarker ??= calmTheme(Brightness.light, platform: Theme.of(context).platform),
      child: Builder(builder: (context) => CalmCard(color: CalmColors.of(context).marker,
        child: _slotContent(context, false))));
  }

  Widget _slotContent(BuildContext context, bool before) {
    final l = AppLocalizations.of(context);
    final colors = CalmColors.of(context);
    final text = Theme.of(context).textTheme;
    final value = before ? earlier : later;
    final label = before ? l.earlierVersion : l.newerVersion;
    final key = before ? 'earlier' : 'newer';
    final currentExists = versions.any((v) => v.id == value?.versionId);
    // On the lime block, secondary text stays ink: grey on a colour reads as washed out.
    final quiet = before ? colors.muted : colors.onMarker;
    return Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [
      Semantics(header: true, child: Text(label, style: text.titleMedium)),
      const SizedBox(height: 12),
      if (value != null && value.versionId == null)
        Padding(padding: const EdgeInsets.only(bottom: 12), child: Row(crossAxisAlignment: CrossAxisAlignment.start, children: [
          Icon(value.bytes == null ? CalmIcons.text : CalmIcons.document, color: quiet),
          const SizedBox(width: 10),
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(value.label!, style: text.titleMedium),
            const SizedBox(height: 4),
            Text(l.readyToSubmit, style: text.bodyMedium?.copyWith(color: quiet)),
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
      CalmTextEdge(child: Wrap(spacing: 8, children: [
        TextButton.icon(key: Key('$key-paste'), onPressed: locked ? null : () => _input(before, paste: true),
            icon: const Icon(CalmIcons.paste), label: Text(l.importPaste)),
        TextButton.icon(key: Key('$key-pdf'), onPressed: locked ? null : () => _input(before, paste: false),
            icon: const Icon(CalmIcons.pickPdf), label: Text(l.importPdf)),
      ])),
    ]);
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final text = Theme.of(context).textTheme;
    final colors = CalmColors.of(context);
    final scopes = {Scope.complete: (l.scopeComplete, l.scopeCompleteHint),
      Scope.partial: (l.scopePartial, l.scopePartialHint), Scope.unknown: (l.scopeUnknown, l.scopeUnknownHint)};
    return Scaffold(appBar: AppBar(),
      // The main action is pinned in the thumb zone, as on every other screen; what blocks or follows
      // it sits directly above. The bar scrolls if an error at large text makes it taller than half
      // the screen.
      bottomNavigationBar: CalmPinnedBar(child: ConstrainedBox(
        constraints: BoxConstraints(maxHeight: MediaQuery.sizeOf(context).height * .5),
        child: SingleChildScrollView(
          child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            if (error != null) Semantics(liveRegion: true, child: Padding(
                padding: const EdgeInsets.only(bottom: 12), child: CalmWarning(text: error!))),
            // A choice that can't proceed sits directly above Start, where it can't scroll out of view.
            if (!distinct) Semantics(liveRegion: true, child: Padding(padding: const EdgeInsets.only(bottom: 12),
              child: CalmWarning(key: const Key('same-version'), kind: CalmMessageKind.warning, text: l.sameVersion))),
            if (error == l.compareLoadFailed) TextButton(onPressed: loading ? null : _load, child: Text(l.retry)),
            if (submission != null && !busy && error == null) Padding(
                padding: const EdgeInsets.only(bottom: 12), child: Text(l.compareRetrySame)),
            FilledButton(key: const Key('start'), onPressed: complete && !busy ? _start : null,
                child: Text(busy ? l.submittingComparison : submission != null ? l.retry : l.startComparison)),
            const SizedBox(height: 8),
            // Disabled: the line says what is missing. Ready: what Start does.
            if (_missing(l) != null || distinct) Text(_missing(l) ?? l.compareSubmitHint,
              key: const Key('start-hint'), style: text.bodySmall?.copyWith(color: colors.muted)),
          ])))),
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
        if (loading) LinearProgressIndicator(semanticsLabel: l.loading),
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
  final form = GlobalKey<FormState>();
  final label = TextEditingController(), text = TextEditingController();
  bool busy = false;
  String? error;

  @override
  void dispose() { label.dispose(); text.dispose(); super.dispose(); }

  Future<void> _choose() async {
    if (!form.currentState!.validate()) return;
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
    return Form(key: form, child: CalmSheet(
      title: widget.paste ? l.importPaste : l.importPdf,
      action: widget.paste ? l.useText : l.importPdf, actionKey: const Key('confirm-import'),
      onAction: busy ? null : _choose,
      children: [
        TextFormField(key: const Key('label'), controller: label, maxLength: 100, autofocus: true,
            validator: calmRequired(l.requiredVersionLabel), autovalidateMode: AutovalidateMode.onUserInteraction,
            decoration: InputDecoration(labelText: l.versionLabel, hintText: l.versionLabelHint)),
        if (widget.paste) TextFormField(key: const Key('pasted'), controller: text, minLines: 4, maxLines: 10,
            validator: calmRequired(l.requiredPastedText), autovalidateMode: AutovalidateMode.onUserInteraction,
            decoration: InputDecoration(hintText: l.pasteHint)),
        if (error != null) Semantics(liveRegion: true, child: CalmWarning(text: error!)),
      ],
    ));
  }
}
