// One finding (02 §4-5, I-10): evidence, review actions and the separate client-approval record.
// Review (confirm, correct, dismiss, note) and client approval are different calls and different
// sections; nothing here turns a review into an approval (AC-12). A correction is saved as a new
// revision and the original stays in the history (AC-15).
import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart';
import 'package:intl/intl.dart';

import '../api.dart';
import '../design/calm_widgets.dart';
import '../l10n/app_localizations.dart';
import '../services.dart';
import 'evidence_screen.dart';
import 'evidence_resolution.dart';
import 'report_widgets.dart';

const changeTypes = ['added', 'changed', 'removed', 'not_addressed', 'uncertain', 'equivalent'];
const categories = ['deliverable', 'quantity', 'date_deadline', 'responsibility_owner', 'approval_wording',
                    'budget', 'other_material', 'structure'];

class FindingScreen extends StatefulWidget {
  const FindingScreen({super.key, required this.comparisonId, required this.findingId,
    required this.report, this.versions = const [],
    this.resolve = resolveEvidence});

  final String comparisonId, findingId;
  final Report report;
  final List<Version> versions;
  final EvidenceResolver resolve;

  @override
  State<FindingScreen> createState() => _FindingScreenState();
}

class _FindingScreenState extends State<FindingScreen> {
  late String id = widget.findingId;
  late int reportIndex = widget.report.findings.indexWhere((finding) => finding.id == widget.findingId);
  FindingDetail? detail;
  String? error;
  bool busy = false, loading = false, checking = false, pageOpened = false, opened = false;
  bool reviewJustSaved = false;
  String? evidenceError;
  final presentations = <Evidence, EvidencePresentation>{};
  final sourceVersions = <String, Version>{};

  bool get canReview => !busy && !loading && !checking && error == null && evidenceError == null && presentations.isNotEmpty;

  int get nextPendingIndex {
    if (detail?.finding.group == 'needs_review' || reportIndex < 0) return reportIndex;
    for (var index = reportIndex + 1; index < widget.report.findings.length; index++) {
      if (!const {'confirmed', 'corrected', 'dismissed'}.contains(widget.report.findings[index].review?.action)) {
        return index;
      }
    }
    return reportIndex;
  }

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (!loading && detail == null && error == null) _load();
  }

  Future<void> _load() async {
    if (loading) return;
    setState(() { loading = true; error = null; });
    try {
      final api = ServicesScope.of(context).api;
      // One explicit screen opening; review reloads and Confirm-next do not renew retention.
      if (!opened) {
        await api.comparisonOpened(widget.comparisonId);
        opened = true;
      }
      if (!mounted) return;
      final d = await api.finding(id);
      if (!mounted) return;
      setState(() {
        if (id != d.finding.id || (detail != null && detail!.finding.revision != d.finding.revision)) {
          pageOpened = false;
        }
        id = d.finding.id;
        detail = d;
        error = null;
      });
      await _checkEvidence();
    } on Exception catch (e) {
      if (mounted) setState(() => error = '$e');
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> _checkEvidence() async {
    setState(() { checking = true; evidenceError = null; presentations.clear(); });
    try {
      final api = ServicesScope.of(context).api;
      final resolved = <Evidence, EvidencePresentation>{};
      for (final e in detail!.finding.evidence) {
        final vid = e.earlier ? widget.report.earlierId : widget.report.laterId;
        final version = _version(e) ?? await api.version(vid);
        sourceVersions[vid] = version;
        resolved[e] = await widget.resolve(api, version, e);
      }
      if (resolved.isEmpty) throw const FormatException('missing evidence');
      if (mounted) setState(() => presentations.addAll(resolved));
    } on Exception catch (e) {
      if (mounted) setState(() => evidenceError = '$e');
    } finally {
      if (mounted) setState(() => checking = false);
    }
  }

  Future<void> _save(Future<void> Function() call) async {
    final l = AppLocalizations.of(context);
    setState(() => busy = true);
    try {
      await call();
      if (!mounted) return;
      await _load();
    } on Exception catch (e) {
      if (!mounted) return;
      if (e is ApiException && e.status == 409 && e.code == 'finding_superseded') {
        // GET resolves the current chain revision. Never retry the rejected mutation automatically.
        setState(() { detail = null; presentations.clear(); pageOpened = false; });
        await _load();
        if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(l.findingChanged)));
      } else {
        ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text(l.saveFailed('$e'))));
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> _review(String action, {String? note, Map<String, String>? correction}) async {
    if (!canReview) return;
    await _save(() async {
      final f = await ServicesScope.of(context).api.review(id, action, note: note, correction: correction,
          evidenceMode: evidenceModes(presentations), pageOpened: pageOpened);
      // Follow the report's order, retaining this position when a correction creates a revision.
      final nextIndex = action == 'confirmed' ? nextPendingIndex : reportIndex;
      final nextId = nextIndex != reportIndex ? widget.report.findings[nextIndex].id : f.id;
      if (!mounted) return;
      setState(() {
        reviewJustSaved = id == nextId && action != 'note';
        if (id != nextId) {
          pageOpened = false;
          detail = null;
          presentations.clear();
          evidenceError = null;
        }
        reportIndex = nextIndex;
        id = nextId;
      });
    });
  }

  Future<String?> _askNote({required bool required}) async {
    final l = AppLocalizations.of(context);
    final field = TextEditingController();
    return showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        scrollable: true,
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
    return sourceVersions[vid] ?? widget.versions.where((v) => v.id == vid).firstOrNull;
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final d = detail;
    final date = DateFormat.yMMMd(Localizations.localeOf(context).toLanguageTag());
    if (d == null) {
      return Scaffold(appBar: AppBar(title: Text(l.findingTitle)),
          body: error == null ? const Center(child: CircularProgressIndicator()) :
            CalmLoadError(onRetry: loading ? null : _load));
    }
    final f = d.finding;
    final reviewed = reviewLabel(l, f.review);
    return Scaffold(
      appBar: AppBar(title: Text(l.findingTitle)),
      bottomNavigationBar: SafeArea(
        child: ConstrainedBox(constraints: BoxConstraints(maxHeight: MediaQuery.sizeOf(context).height * 0.6),
          child: SingleChildScrollView(primary: false,
          child: Padding(padding: const EdgeInsets.fromLTRB(16, 8, 16, 12),
          child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            if (busy) Semantics(liveRegion: true, child: Text(l.saving)),
            if (error != null) CalmWarning(text: l.contentLoadFailed,
              child: TextButton(onPressed: busy || loading ? null : _load, child: Text(l.retry))),
            if (checking) Text(l.evidenceChecking),
            if (evidenceError != null) ...[
              Text(l.evidenceCheckFailed),
              Align(alignment: AlignmentDirectional.centerStart,
                child: TextButton(onPressed: checking ? null : _checkEvidence, child: Text(l.retry))),
            ],
            if (evidenceModes(presentations).containsValue('text_fallback'))
              Semantics(sortKey: const OrdinalSortKey(0), liveRegion: true,
                child: Padding(padding: const EdgeInsets.only(bottom: 8),
                  child: CalmWarning(key: const Key('review-fallback'), text: l.evidenceFallbackReview))),
            Semantics(sortKey: const OrdinalSortKey(1), child:
              SizedBox(width: double.infinity, child:
                FilledButton(key: const Key('review-confirm'), onPressed: canReview ? () => _review('confirmed') : null,
                  child: Text(nextPendingIndex == reportIndex ? l.actionConfirm : l.confirmAndNext)))),
          ])))),
      ),
      body: AbsorbPointer(
        absorbing: busy,
        child: ListView(key: ValueKey(id), padding: const EdgeInsets.fromLTRB(20, 8, 20, 28), children: [
          CalmPageHeader(title: topicLabel(l, f.topic), subtitle: reportIndex < 0 ? null :
            l.findingPosition(reportIndex + 1, widget.report.findings.length)),
          Text('${typeLabel(l, f.changeType)} · ${categoryLabel(l, f.category)}',
              style: Theme.of(context).textTheme.titleMedium),
          if (f.explanation != null) Padding(padding: const EdgeInsets.only(top: 12),
            child: Text(f.explanation!, style: Theme.of(context).textTheme.titleLarge)),
          if (f.group == 'needs_review') Padding(padding: const EdgeInsets.only(top: 16),
            child: Row(children: [
              const CalmReviewDisc(),
              const SizedBox(width: 10),
              Expanded(child: Text(l.groupNeedsReview, style: Theme.of(context).textTheme.titleSmall)),
            ])),
          SectionHeader(l.evidenceTitle),
          for (final e in f.evidence)
            CalmArrival(key: ValueKey('$id-${e.side}-${e.charStart}'), child: QuoteCard(
              evidence: e,
              versionLabel: _version(e)?.label,
              evidenceLabel: switch (presentations[e]?.mode) {
                'pdf_highlight' => l.evidenceModePdf,
                'text_fallback' => l.evidenceModeFallback,
                'text_only' => l.evidenceModeText,
                _ => null,
              },
              onTap: _version(e) == null || !presentations.containsKey(e)
                  ? null
                  : () => Navigator.of(context).push(
                      MaterialPageRoute(builder: (_) => EvidenceScreen(version: _version(e)!, evidence: e,
                        presentation: presentations[e], onPageOpened: () {
                          if (mounted && id == f.id) setState(() => pageOpened = true);
                        }))),
            )),
          SectionHeader(l.yourReview),
          Align(alignment: AlignmentDirectional.centerStart,
            child: CalmReviewMark(key: ValueKey('$id-${f.review?.at}'),
              text: reviewed ?? l.notReviewed, active: reviewed != null, animate: reviewJustSaved)),
          Wrap(spacing: 8, runSpacing: 8, children: [
            OutlinedButton(onPressed: canReview ? () => _correct(f) : null, child: Text(l.actionCorrect)),
            OutlinedButton(onPressed: canReview ? () async {
              final note = await _askNote(required: false);
              if (note != null) await _review('dismissed', note: note.isEmpty ? null : note);
            } : null, child: Text(l.actionDismiss)),
            TextButton(onPressed: canReview ? () async {
              final note = await _askNote(required: true);
              if (note != null && note.isNotEmpty) await _review('note', note: note);
            } : null, child: Text(l.actionNote)),
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
          const Divider(),
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
            child: TextButton.icon(onPressed: busy || loading || error != null ? null : _recordApproval, icon: const Icon(Icons.add),
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
  late String type = widget.finding.changeType,
    category = widget.finding.category == 'approval' ? 'approval_wording' : widget.finding.category;
  late final explanation = TextEditingController(text: widget.finding.explanation ?? '');

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final f = widget.finding;
    return AlertDialog(
      scrollable: true,
      title: Text(l.correctTitle),
      content: SingleChildScrollView(
        child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.start, children: [
          Text(l.correctHint, style: Theme.of(context).textTheme.bodySmall),
          DropdownButtonFormField<String>(
            key: const Key('type-field'),
            isExpanded: true, itemHeight: null,
            initialValue: type,
            decoration: InputDecoration(labelText: l.changeTypeLabel),
            items: [for (final t in changeTypes) DropdownMenuItem(value: t, child: Text(typeLabel(l, t)))],
            onChanged: (v) => setState(() => type = v ?? type),
          ),
          DropdownButtonFormField<String>(
            key: const Key('category-field'),
            isExpanded: true, itemHeight: null,
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
      scrollable: true,
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
