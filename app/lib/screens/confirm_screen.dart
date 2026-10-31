// Order and scope confirmation (02 §1 step 4, AC-14). Nothing is preselected: no order is inferred
// from upload time or file names, and the scope has no default. Processing starts only here.
import 'package:flutter/material.dart';

import '../api.dart';
import '../l10n/app_localizations.dart';
import '../services.dart';
import 'comparison_screen.dart';

class ConfirmScreen extends StatefulWidget {
  const ConfirmScreen({super.key, required this.project, required this.versions});

  final Project project;
  final List<Version> versions; // parsed versions only

  @override
  State<ConfirmScreen> createState() => _ConfirmScreenState();
}

class _ConfirmScreenState extends State<ConfirmScreen> {
  String? earlierId, laterId;
  Scope? scope;
  bool busy = false;
  String? error;

  bool get _distinct => earlierId == null || laterId == null || earlierId != laterId;
  bool get _complete => earlierId != null && laterId != null && scope != null && _distinct;

  Future<void> _start() async {
    final services = ServicesScope.of(context);
    setState(() => busy = true);
    try {
      final id = await services.api.startComparison(widget.project.id, earlierId!, laterId!, scope!);
      if (!mounted) return;
      await Navigator.of(context).pushReplacement(
          MaterialPageRoute(builder: (_) => ComparisonScreen(comparisonId: id, versions: widget.versions)));
    } on Exception catch (e) {
      setState(() {
        busy = false;
        error = '$e';
      });
    }
  }

  Widget _versionPicker(String label, String? value, ValueChanged<String?> onChanged, Key key) {
    final l = AppLocalizations.of(context);
    return DropdownButtonFormField<String>(
      key: key,
      initialValue: value,
      isExpanded: true,
      decoration: InputDecoration(labelText: label, border: const OutlineInputBorder()),
      hint: Text(l.chooseVersion),
      items: [for (final v in widget.versions) DropdownMenuItem(value: v.id, child: Text(v.label))],
      onChanged: busy ? null : onChanged,
    );
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final scopes = {
      Scope.complete: (l.scopeComplete, l.scopeCompleteHint),
      Scope.partial: (l.scopePartial, l.scopePartialHint),
      Scope.unknown: (l.scopeUnknown, l.scopeUnknownHint),
    };
    return Scaffold(
      appBar: AppBar(title: Text(l.confirmTitle)),
      body: ListView(padding: const EdgeInsets.all(16), children: [
        Text(l.confirmIntro),
        const SizedBox(height: 16),
        _versionPicker(l.earlierVersion, earlierId, (v) => setState(() => earlierId = v), const Key('earlier')),
        const SizedBox(height: 12),
        _versionPicker(l.newerVersion, laterId, (v) => setState(() => laterId = v), const Key('newer')),
        if (!_distinct)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Text(l.sameVersion, style: TextStyle(color: Theme.of(context).colorScheme.error)),
          ),
        const SizedBox(height: 20),
        Text(l.scopeQuestion, style: Theme.of(context).textTheme.titleMedium),
        RadioGroup<Scope>(
          groupValue: scope,
          onChanged: (s) => busy ? null : setState(() => scope = s),
          child: Column(children: [
            for (final e in scopes.entries)
              RadioListTile<Scope>(
                key: Key('scope-${e.key.name}'),
                value: e.key,
                title: Text(e.value.$1),
                subtitle: Text(e.value.$2),
              ),
          ]),
        ),
        const SizedBox(height: 16),
        if (error != null)
          Text(error!, style: TextStyle(color: Theme.of(context).colorScheme.error)),
        FilledButton(
          key: const Key('start'),
          onPressed: _complete && !busy ? _start : null,
          child: Text(l.startComparison),
        ),
        if (!_complete)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Text(l.confirmMissing, textAlign: TextAlign.center),
          ),
      ]),
    );
  }
}
