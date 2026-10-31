// A project's versions and comparisons, plus import by paste or PDF picker (AC-24).
// Versions are immutable (AC-15): there is no edit or delete action, only "import a new version".
import 'package:flutter/material.dart';

import '../api.dart';
import '../l10n/app_localizations.dart';
import '../services.dart';
import 'comparison_screen.dart';
import 'confirm_screen.dart';

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

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (loading) _load();
  }

  Future<void> _load() async {
    final api = ServicesScope.of(context).api;
    try {
      final v = await api.versions(widget.project.id);
      final c = await api.comparisons(widget.project.id);
      if (!mounted) return;
      setState(() {
        versions = v;
        comparisons = c;
        loading = false;
        error = null;
      });
    } on Exception catch (e) {
      if (!mounted) return;
      setState(() {
        loading = false;
        error = '$e';
      });
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
    final ready = versions.where((v) => v.ready).toList();
    final byId = {for (final v in versions) v.id: v.label};
    return Scaffold(
      appBar: AppBar(title: Text(widget.project.name)),
      body: RefreshIndicator(
        onRefresh: _load,
        child: ListView(padding: const EdgeInsets.all(16), children: [
          if (loading) const LinearProgressIndicator(),
          if (error != null) Text(error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
          Text(l.versionsTitle, style: Theme.of(context).textTheme.titleLarge),
          if (!loading && versions.isEmpty) Padding(padding: const EdgeInsets.all(8), child: Text(l.versionsEmpty)),
          for (final v in versions)
            ListTile(
              key: Key('version-${v.id}'),
              leading: Icon(v.kind == 'pdf' ? Icons.picture_as_pdf : Icons.notes),
              title: Text(v.label),
              subtitle: Text([_status(l, v), if (v.warnings > 0) l.warningsCount(v.warnings)].join(' · ')),
            ),
          Text(l.originalsNote, style: Theme.of(context).textTheme.bodySmall),
          const SizedBox(height: 12),
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
          if (importing) Padding(padding: const EdgeInsets.only(top: 8), child: Text(l.uploading)),
          const SizedBox(height: 16),
          FilledButton.icon(
            key: const Key('compare'),
            onPressed: ready.length < 2
                ? null
                : () async {
                    await Navigator.of(context).push(MaterialPageRoute(
                        builder: (_) => ConfirmScreen(project: widget.project, versions: ready)));
                    await _load();
                  },
            icon: const Icon(Icons.compare_arrows),
            label: Text(l.compare),
          ),
          if (ready.length < 2) Padding(padding: const EdgeInsets.only(top: 4), child: Text(l.compareNeedsTwo)),
          const SizedBox(height: 24),
          Text(l.comparisonsTitle, style: Theme.of(context).textTheme.titleLarge),
          if (!loading && comparisons.isEmpty) Padding(padding: const EdgeInsets.all(8), child: Text(l.comparisonsEmpty)),
          for (final c in comparisons)
            ListTile(
              title: Text(l.earlierToNewer(byId[c.earlierId] ?? '…', byId[c.laterId] ?? '…')),
              subtitle: Text(c.status),
              onTap: () => Navigator.of(context).push(MaterialPageRoute(
                  builder: (_) => ComparisonScreen(comparisonId: c.id, versions: versions))),
            ),
        ]),
      ),
    );
  }
}
