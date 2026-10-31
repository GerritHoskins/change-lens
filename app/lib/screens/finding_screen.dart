// One finding (02 §4-5, I-10): evidence, review actions and the separate client-approval record.
// Review (confirm, correct, dismiss, note) and client approval are different calls and different
// sections; nothing here turns a review into an approval (AC-12). A correction is saved as a new
// revision and the original stays in the history (AC-15).
import 'package:flutter/material.dart';
import 'package:intl/intl.dart';

import '../api.dart';
import '../l10n/app_localizations.dart';
import '../services.dart';
import 'evidence_screen.dart';
import 'report_widgets.dart';

const changeTypes = ['added', 'changed', 'removed', 'not_addressed', 'uncertain', 'equivalent'];
const categories = ['deliverable', 'quantity', 'date_deadline', 'responsibility_owner', 'approval',
                    'other_material', 'structure'];

class FindingScreen extends StatefulWidget {
  const FindingScreen({super.key, required this.findingId, required this.report, this.versions = const []});

  final String findingId;
  final Report report;
  final List<Version> versions;

  @override
  State<FindingScreen> createState() => _FindingScreenState();
}

class _FindingScreenState extends State<FindingScreen> {
  late String id = widget.findingId;
  FindingDetail? detail;
  String? error;
  bool busy = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (detail == null && error == null) _load();
  }

  Future<void> _load() async {
    try {
      final d = await ServicesScope.of(context).api.finding(id);
      if (!mounted) return;
      setState(() {
        detail = d;
        error = null;
      });
    } on Exception catch (e) {
      if (mounted) setState(() => error = '$e');
    }
  }

  Future<void> _save(Future<void> Function() call) async {
    final l = AppLocalizations.of(context);
    setState(() => busy = true);
    try {
      await call();
      await _load();
    } on Exception catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(l.saveFailed('$e'))));
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> _review(String action, {String? note, Map<String, String>? correction}) => _save(() async {
        final f = await ServicesScope.of(context).api.review(id, action, note: note, correction: correction);
        id = f.id; // a correction returns the new revision
      });

  Future<String?> _askNote({required bool required}) async {
    final l = AppLocalizations.of(context);
    final field = TextEditingController();
    return showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(l.noteLabel),
        content: TextField(key: const Key('note-field'), controller: field, maxLines: 4, autofocus: true),
        actions: [
          TextButton(onPressed: () => Navigator.pop(context), child: Text(l.cancel)),
          TextButton(
              onPressed: () {
                if (required && field.text.trim().isEmpty) return;
                Navigator.pop(context, field.text.trim());
              },
              child: Text(l.save)),
        ],
      ),
    );
  }

  Future<void> _correct(Finding f) async {
    final result = await showDialog<Map<String, String>>(
        context: context, builder: (_) => CorrectionDialog(finding: f));
    if (result != null && result.isNotEmpty) await _review('corrected', correction: result);
  }

  Future<void> _recordApproval() async {
    final result = await showDialog<(String, String, DateTime)>(context: context, builder: (_) => const ApprovalDialog());
    if (result == null) return;
    await _save(() => ServicesScope.of(context).api.recordApproval(id, result.$1, result.$2, result.$3));
  }

  Version? _version(Evidence e) {
    final vid = e.earlier ? widget.report.earlierId : widget.report.laterId;
    return widget.versions.where((v) => v.id == vid).firstOrNull;
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final d = detail;
    final date = DateFormat.yMMMd(Localizations.localeOf(context).toLanguageTag());
    if (d == null) {
      return Scaffold(appBar: AppBar(title: Text(l.findingTitle)),
          body: Center(child: error == null ? const CircularProgressIndicator() : Text(l.loadFailed(error!))));
    }
    final f = d.finding;
    final reviewed = reviewLabel(l, f.review);
    return Scaffold(
      appBar: AppBar(title: Text(l.findingTitle)),
      body: AbsorbPointer(
        absorbing: busy,
        child: ListView(padding: const EdgeInsets.all(16), children: [
          Text('${typeLabel(l, f.changeType)} · ${categoryLabel(l, f.category)}',
              style: Theme.of(context).textTheme.titleLarge),
          if (f.explanation != null) Padding(padding: const EdgeInsets.only(top: 8), child: Text(f.explanation!)),
          SectionHeader(l.evidenceTitle),
          for (final e in f.evidence)
            QuoteCard(
              evidence: e,
              onTap: _version(e) == null
                  ? null
                  : () => Navigator.of(context).push(
                      MaterialPageRoute(builder: (_) => EvidenceScreen(version: _version(e)!, evidence: e))),
            ),
          SectionHeader(reviewed ?? l.notReviewed),
          Wrap(spacing: 8, runSpacing: 8, children: [
            FilledButton.tonal(onPressed: () => _review('confirmed'), child: Text(l.actionConfirm)),
            OutlinedButton(onPressed: () => _correct(f), child: Text(l.actionCorrect)),
            OutlinedButton(
                onPressed: () async {
                  final note = await _askNote(required: false);
                  if (note != null) await _review('dismissed', note: note.isEmpty ? null : note);
                },
                child: Text(l.actionDismiss)),
            TextButton(
                onPressed: () async {
                  final note = await _askNote(required: true);
                  if (note != null && note.isNotEmpty) await _review('note', note: note);
                },
                child: Text(l.actionNote)),
          ]),
          if (d.reviews.isNotEmpty || d.revisions.length > 1) ...[
            SectionHeader(l.historyTitle),
            for (final r in d.revisions.length > 1 ? d.revisions : <Finding>[])
              ListTile(dense: true, contentPadding: EdgeInsets.zero, title: Text(l.revisionLabel(r.revision)),
                  subtitle: Text('${typeLabel(l, r.changeType)} · ${categoryLabel(l, r.category)}')),
            for (final r in d.reviews)
              ListTile(dense: true, contentPadding: EdgeInsets.zero,
                  title: Text(reviewLabel(l, r) ?? l.noteLabel),
                  subtitle: Text([date.format(r.at.toLocal()), if (r.note != null) r.note!].join(' · '))),
          ],
          // Separate record, separate wording (AC-12).
          SectionHeader(l.approvalTitle, hint: l.approvalHint),
          if (d.approvals.isEmpty) Text(l.approvalNone),
          for (final a in d.approvals)
            Card(
              child: ListTile(
                leading: const Icon(Icons.mark_email_read_outlined),
                title: Text(l.approvalRecorded),
                subtitle: Text('${l.approvalLine(a.statedBy, date.format(a.statedAt.toLocal()))}\n${a.evidenceText}'),
                isThreeLine: true,
              ),
            ),
          Align(
            alignment: Alignment.centerLeft,
            child: TextButton.icon(onPressed: _recordApproval, icon: const Icon(Icons.add),
                label: Text(l.recordApproval)),
          ),
        ]),
      ),
    );
  }
}

class CorrectionDialog extends StatefulWidget {
  const CorrectionDialog({super.key, required this.finding});

  final Finding finding;

  @override
  State<CorrectionDialog> createState() => _CorrectionDialogState();
}

class _CorrectionDialogState extends State<CorrectionDialog> {
  late String type = widget.finding.changeType, category = widget.finding.category;
  late final explanation = TextEditingController(text: widget.finding.explanation ?? '');

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final f = widget.finding;
    return AlertDialog(
      title: Text(l.correctTitle),
      content: SingleChildScrollView(
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(l.correctHint, style: Theme.of(context).textTheme.bodySmall),
          DropdownButtonFormField<String>(
            key: const Key('type-field'),
            initialValue: type,
            decoration: InputDecoration(labelText: l.changeTypeLabel),
            items: [for (final t in changeTypes) DropdownMenuItem(value: t, child: Text(typeLabel(l, t)))],
            onChanged: (v) => setState(() => type = v ?? type),
          ),
          DropdownButtonFormField<String>(
            key: const Key('category-field'),
            initialValue: category,
            decoration: InputDecoration(labelText: l.categoryLabel),
            items: [for (final c in categories) DropdownMenuItem(value: c, child: Text(categoryLabel(l, c)))],
            onChanged: (v) => setState(() => category = v ?? category),
          ),
          TextField(controller: explanation, maxLines: 3, decoration: InputDecoration(labelText: l.explanationLabel)),
        ]),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: Text(l.cancel)),
        TextButton(
          onPressed: () => Navigator.pop(context, {
            if (type != f.changeType) 'change_type': type,
            if (category != f.category) 'category': category,
            if (explanation.text.trim() != (f.explanation ?? '') && explanation.text.trim().isNotEmpty)
              'explanation': explanation.text.trim(),
          }),
          child: Text(l.save),
        ),
      ],
    );
  }
}

class ApprovalDialog extends StatefulWidget {
  const ApprovalDialog({super.key});

  @override
  State<ApprovalDialog> createState() => _ApprovalDialogState();
}

class _ApprovalDialogState extends State<ApprovalDialog> {
  final evidence = TextEditingController(), statedBy = TextEditingController();
  DateTime statedAt = DateTime.now();

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final date = DateFormat.yMMMd(Localizations.localeOf(context).toLanguageTag());
    return AlertDialog(
      title: Text(l.recordApproval),
      content: SingleChildScrollView(
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(l.approvalHint, style: Theme.of(context).textTheme.bodySmall),
          TextField(key: const Key('approval-evidence'), controller: evidence, maxLines: 4,
              decoration: InputDecoration(labelText: l.approvalEvidence)),
          TextField(key: const Key('approval-by'), controller: statedBy,
              decoration: InputDecoration(labelText: l.approvalStatedBy)),
          TextButton.icon(
            icon: const Icon(Icons.event),
            label: Text(l.approvalStatedOn(date.format(statedAt))),
            onPressed: () async {
              final picked = await showDatePicker(context: context, initialDate: statedAt,
                  firstDate: DateTime(2000), lastDate: DateTime.now());
              if (picked != null) setState(() => statedAt = picked);
            },
          ),
        ]),
      ),
      actions: [
        TextButton(onPressed: () => Navigator.pop(context), child: Text(l.cancel)),
        TextButton(
          onPressed: () {
            if (evidence.text.trim().isEmpty || statedBy.text.trim().isEmpty) return;
            Navigator.pop(context, (evidence.text.trim(), statedBy.text.trim(), statedAt));
          },
          child: Text(l.save),
        ),
      ],
    );
  }
}
