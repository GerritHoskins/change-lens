// One finding (02 §4-5, I-10): evidence, review actions and the separate client-approval record.
// Review (confirm, correct, dismiss, note) and client approval are different calls and different
// sections; nothing here turns a review into an approval (AC-12). A correction is saved as a new
// revision and the original stays in the history (AC-15).
import 'dart:async';

import 'package:flutter/cupertino.dart' show CupertinoDatePicker, CupertinoDatePickerMode, showCupertinoModalPopup;
import 'package:flutter/material.dart';
import 'package:flutter/semantics.dart';
import 'package:flutter/services.dart' show SystemUiOverlayStyle;
import 'package:intl/intl.dart';

import '../api.dart';
import '../design/calm_controls.dart';
import '../design/calm_icons.dart';
import '../design/calm_theme.dart';
import '../design/calm_widgets.dart';
import '../l10n/app_localizations.dart';
import '../services.dart';
import 'definition_sheets.dart';
import 'evidence_screen.dart';
import 'evidence_resolution.dart';
import 'finding_header.dart';
import 'report_widgets.dart';
import 'review_completion.dart';

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
  bool leaving = false; // replaced by the review summary
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
      if (!mounted || leaving) return;
      await _load();
    } on Exception catch (e) {
      if (!mounted) return;
      if (e is ApiException && e.status == 409 && e.code == 'finding_superseded') {
        // GET resolves the current chain revision. Never retry the rejected mutation automatically.
        setState(() { detail = null; presentations.clear(); pageOpened = false; });
        await _load();
        if (mounted) calmSnack(context, l.findingChanged, kind: CalmMessageKind.warning);
      } else {
        calmSnack(context, l.saveFailed(userErrorMessage(l, e)), kind: CalmMessageKind.error);
      }
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }

  Future<void> _review(String action, {String? note, Map<String, String>? correction, String? reason}) async {
    if (!canReview) return;
    // Only a finding that was still open can complete the review; re-reviewing one never jumps away.
    final wasOpen = !const {'confirmed', 'corrected', 'dismissed'}.contains(detail?.finding.review?.action);
    await _save(() async {
      final api = ServicesScope.of(context).api;
      final f = await api.review(id, action, note: note, correction: correction, dismissalReason: reason,
          evidenceMode: evidenceModes(presentations), pageOpened: pageOpened);
      // Follow the report's order, retaining this position when a correction creates a revision.
      final advances = action == 'confirmed' || action == 'dismissed';
      final nextIndex = advances ? nextPendingIndex : reportIndex;
      // The last open finding: the summary (P7), counted from the server's report, not from this screen.
      if (wasOpen && action != 'note' && nextIndex == reportIndex) {
        final report = await _reportIfDone(api);
        if (report != null && mounted) {
          leaving = true;
          // Not awaited: the future only completes when the summary closes.
          unawaited(Navigator.of(context).pushReplacement(MaterialPageRoute<void>(
            builder: (_) => ReviewSummaryScreen(report: report))));
          return;
        }
      }
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
      // "Confirm and next" swaps the finding in place: say which one is on screen now.
      if (f.id != nextId && nextIndex >= 0) {
        calmAnnounce(context, AppLocalizations.of(context).findingPosition(nextIndex + 1, widget.report.findings.length));
      }
    });
  }

  /// The report when every finding has a review; null otherwise, or when it can't be loaded (the
  /// finding screen then simply stays, as before).
  Future<Report?> _reportIfDone(Api api) async {
    try {
      final report = await api.report(widget.comparisonId);
      return everyFindingReviewed(report) ? report : null;
    } on Exception {
      return null;
    }
  }

  Future<void> _dismiss() async {
    final result = await showCalmSheet<(String, String?)>(context,
      builder: (_) => DismissSheet(hasNext: nextPendingIndex != reportIndex));
    if (result != null) await _review('dismissed', note: result.$2, reason: result.$1);
  }

  Future<String?> _askNote({required bool required}) async {
    final l = AppLocalizations.of(context);
    final form = GlobalKey<FormState>();
    final field = TextEditingController();
    return showCalmSheet<String>(context, builder: (context) => Form(key: form, child: CalmSheet(
      title: l.noteLabel,
      action: l.save,
      onAction: () {
        if (!form.currentState!.validate()) return;
        Navigator.pop(context, field.text.trim());
      },
      children: [TextFormField(key: const Key('note-field'), controller: field, minLines: 3, maxLines: 6,
        autofocus: true, validator: required ? calmRequired(l.requiredNote) : null,
        autovalidateMode: AutovalidateMode.onUserInteraction)],
    )));
  }

  Future<void> _correct(Finding f) async {
    final result = await showCalmSheet<Map<String, String>>(context, builder: (_) => CorrectionSheet(finding: f));
    if (result != null && result.isNotEmpty) await _review('corrected', correction: result);
  }

  Future<void> _recordApproval() async {
    final result = await showCalmSheet<(String, String, DateTime)>(context, builder: (_) => const ApprovalSheet());
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
          body: error == null ? Center(child: CircularProgressIndicator(semanticsLabel: l.loading)) :
            CalmLoadError(onRetry: loading ? null : _load));
    }
    final f = d.finding;
    final reviewed = reviewLabel(l, f.review);
    return Scaffold(
      // The app bar continues the topic block: its colour, with `on-topic` ink in both themes.
      appBar: AppBar(title: Text(l.findingTitle), backgroundColor: CalmColors.of(context).topicSurface(f.topic),
        foregroundColor: CalmColors.ink, systemOverlayStyle: SystemUiOverlayStyle.dark,
        titleTextStyle: Theme.of(context).textTheme.titleMedium?.copyWith(color: CalmColors.ink)),
      // The same pinned bar as every other screen: the 20px gutter and a hairline over the content.
      bottomNavigationBar: CalmPinnedBar(
        child: ConstrainedBox(constraints: BoxConstraints(maxHeight: MediaQuery.sizeOf(context).height * 0.6),
          child: SingleChildScrollView(primary: false,
          child: Column(mainAxisSize: MainAxisSize.min, crossAxisAlignment: CrossAxisAlignment.stretch, children: [
            if (busy) Semantics(liveRegion: true, child: Text(l.saving)),
            if (error != null) CalmWarning(text: l.contentLoadFailed,
              child: CalmTextEdge(child: TextButton(onPressed: busy || loading ? null : _load, child: Text(l.retry)))),
            if (checking) Semantics(liveRegion: true, child: Text(l.evidenceChecking)),
            if (evidenceError != null) ...[
              Text(l.evidenceCheckFailed),
              Align(alignment: AlignmentDirectional.centerStart,
                child: CalmTextEdge(child: TextButton(onPressed: checking ? null : _checkEvidence, child: Text(l.retry)))),
            ],
            if (evidenceModes(presentations).containsValue('text_fallback'))
              Semantics(sortKey: const OrdinalSortKey(0), liveRegion: true,
                child: Padding(padding: const EdgeInsets.only(bottom: 8),
                  child: CalmWarning(key: const Key('review-fallback'), kind: CalmMessageKind.warning, text: l.evidenceFallbackReview))),
            Semantics(sortKey: const OrdinalSortKey(1), child:
              SizedBox(width: double.infinity, child:
                FilledButton(key: const Key('review-confirm'), onPressed: canReview ? () => _review('confirmed') : null,
                  child: Text(nextPendingIndex == reportIndex ? l.actionConfirm : l.confirmAndNext)))),
          ]))),
      ),
      body: AbsorbPointer(
        absorbing: busy,
        // The topic block runs edge to edge; everything after it keeps the 20px gutter.
        child: CustomScrollView(key: ValueKey(id), slivers: [
          SliverToBoxAdapter(child: FindingHeader(finding: f, position: reportIndex < 0 ? null :
            l.findingPosition(reportIndex + 1, widget.report.findings.length))),
          SliverPadding(padding: const EdgeInsets.fromLTRB(20, 0, 20, 28), sliver: SliverList.list(children: [
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
              evidenceInfo: CalmInfoButton(key: ValueKey('info-evidence-${e.side}'), term: l.defEvidenceTitle,
                sheet: (_) => const EvidenceDefinitionSheet()),
              onTap: _version(e) == null || !presentations.containsKey(e)
                  ? null
                  : () => Navigator.of(context).push(
                      MaterialPageRoute(builder: (_) => EvidenceScreen(version: _version(e)!, evidence: e,
                        presentation: presentations[e], onPageOpened: () {
                          if (mounted && id == f.id) setState(() => pageOpened = true);
                        }))),
            )),
          SectionHeader(l.yourReview),
          // One text edge for the section: the mark and the buttons move out by their own padding.
          Align(alignment: AlignmentDirectional.centerStart,
            child: CalmTextEdge(inset: 4, child: CalmReviewMark(key: ValueKey('$id-${f.review?.at}'),
              text: reviewed ?? l.notReviewed, active: reviewed != null, animate: reviewJustSaved))),
          CalmTextEdge(child: Wrap(spacing: 8, runSpacing: 8, children: [
            TextButton(onPressed: canReview ? () => _correct(f) : null, child: Text(l.actionCorrect)),
            TextButton(key: const Key('review-dismiss'), onPressed: canReview ? _dismiss : null,
              child: Text(l.actionDismiss)),
            TextButton(onPressed: canReview ? () async {
              final note = await _askNote(required: true);
              if (note != null && note.isNotEmpty) await _review('note', note: note);
            } : null, child: Text(l.actionNote)),
          ])),
          if (d.reviews.isNotEmpty || d.revisions.length > 1) ...[
            SectionHeader(l.historyTitle),
            for (final r in d.revisions.length > 1 ? d.revisions : <Finding>[])
              ListTile(dense: true, contentPadding: EdgeInsets.zero, title: Text(l.revisionLabel(r.revision)),
                  subtitle: Text('${typeLabel(l, r.changeType)} · ${categoryLabel(l, r.category)}')),
            for (final r in d.reviews)
              ListTile(dense: true, contentPadding: EdgeInsets.zero,
                  title: Text(reviewLabel(l, r) ?? l.noteLabel),
                  subtitle: Text([date.format(r.at.toLocal()),
                    if (r.dismissalReason != null) l.dismissReasonLine(dismissalReasonLabel(l, r.dismissalReason!)),
                    if (r.note != null) r.note!].join(' · '))),
          ],
          // Separate record, separate wording (AC-12).
          const Divider(),
          SectionHeader(l.approvalTitle, hint: l.approvalHint),
          if (d.approvals.isEmpty) Text(l.approvalNone),
          for (final a in d.approvals)
            Card(
              child: ListTile(
                leading: const Icon(CalmIcons.approval),
                title: Text(l.approvalRecorded),
                subtitle: Text('${l.approvalLine(a.statedBy, date.format(a.statedAt.toLocal()))}\n${a.evidenceText}'),
                isThreeLine: true,
              ),
            ),
          Align(
            alignment: Alignment.centerLeft,
            child: CalmTextEdge(child: TextButton.icon(onPressed: busy || loading || error != null ? null : _recordApproval,
                icon: const Icon(CalmIcons.add), label: Text(l.recordApproval))),
          ),
          ])),
        ]),
      ),
    );
  }
}

class CorrectionSheet extends StatefulWidget {
  const CorrectionSheet({super.key, required this.finding});

  final Finding finding;

  @override
  State<CorrectionSheet> createState() => _CorrectionSheetState();
}

class _CorrectionSheetState extends State<CorrectionSheet> {
  late String type = widget.finding.changeType,
    category = widget.finding.category == 'approval' ? 'approval_wording' : widget.finding.category;
  late final explanation = TextEditingController(text: widget.finding.explanation ?? '');

  @override
  void dispose() { explanation.dispose(); super.dispose(); }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final f = widget.finding;
    return CalmSheet(
      title: l.correctTitle,
      lead: l.correctHint,
      action: l.save,
      onAction: () => Navigator.pop(context, {
        if (type != f.changeType) 'change_type': type,
        if (category != f.category) 'category': category,
        if (explanation.text.trim() != (f.explanation ?? '') && explanation.text.trim().isNotEmpty)
          'explanation': explanation.text.trim(),
      }),
      children: [
        CalmSelectField<String>(key: const Key('type-field'), label: l.changeTypeLabel, value: type,
          options: [for (final t in changeTypes) CalmOption(t, typeLabel(l, t))],
          onChanged: (v) => setState(() => type = v)),
        CalmSelectField<String>(key: const Key('category-field'), label: l.categoryLabel, value: category,
          options: [for (final c in categories) CalmOption(c, categoryLabel(l, c))],
          onChanged: (v) => setState(() => category = v)),
        TextField(controller: explanation, minLines: 2, maxLines: 4,
          decoration: InputDecoration(labelText: l.explanationLabel)),
      ],
    );
  }
}

class ApprovalSheet extends StatefulWidget {
  const ApprovalSheet({super.key});

  @override
  State<ApprovalSheet> createState() => _ApprovalSheetState();
}

class _ApprovalSheetState extends State<ApprovalSheet> {
  final form = GlobalKey<FormState>();
  final evidence = TextEditingController(), statedBy = TextEditingController();
  DateTime statedAt = DateTime.now();

  @override
  void dispose() { evidence.dispose(); statedBy.dispose(); super.dispose(); }

  /// iOS: the system's date wheels in a bottom popup with Done; elsewhere Material's calendar.
  Future<DateTime?> _pickDate() {
    final first = DateTime(2000), last = DateTime.now();
    if (Theme.of(context).platform != TargetPlatform.iOS) {
      return showDatePicker(context: context, initialDate: statedAt, firstDate: first, lastDate: last);
    }
    var value = statedAt;
    return showCupertinoModalPopup<DateTime>(context: context, builder: (context) => Material(
      color: Theme.of(context).cardTheme.color,
      child: SafeArea(top: false, child: Column(mainAxisSize: MainAxisSize.min, children: [
        Align(alignment: AlignmentDirectional.centerEnd, child: TextButton(key: const Key('approval-date-done'),
          onPressed: () => Navigator.pop(context, value),
          child: Text(MaterialLocalizations.of(context).okButtonLabel))),
        SizedBox(height: 216, child: CupertinoDatePicker(mode: CupertinoDatePickerMode.date,
          initialDateTime: statedAt, minimumDate: first, maximumDate: last,
          onDateTimeChanged: (d) => value = d)),
      ]))));
  }

  @override
  Widget build(BuildContext context) {
    final l = AppLocalizations.of(context);
    final date = DateFormat.yMMMd(Localizations.localeOf(context).toLanguageTag());
    return Form(key: form, child: CalmSheet(
      title: l.recordApproval,
      lead: l.approvalHint,
      action: l.save,
      onAction: () {
        if (!form.currentState!.validate()) return;
        Navigator.pop(context, (evidence.text.trim(), statedBy.text.trim(), statedAt));
      },
      children: [
        TextFormField(key: const Key('approval-evidence'), controller: evidence, minLines: 3, maxLines: 5,
            validator: calmRequired(l.requiredApprovalEvidence), autovalidateMode: AutovalidateMode.onUserInteraction,
            decoration: InputDecoration(labelText: l.approvalEvidence)),
        TextFormField(key: const Key('approval-by'), controller: statedBy,
            validator: calmRequired(l.requiredApprovalBy), autovalidateMode: AutovalidateMode.onUserInteraction,
            decoration: InputDecoration(labelText: l.approvalStatedBy)),
        Align(alignment: AlignmentDirectional.centerStart, child: TextButton.icon(
          icon: const Icon(CalmIcons.calendar),
          label: Text(l.approvalStatedOn(date.format(statedAt))),
          onPressed: () async {
            final picked = await _pickDate();
            if (picked != null) setState(() => statedAt = picked);
          },
        )),
      ],
    ));
  }
}
