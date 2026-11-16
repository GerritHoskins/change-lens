// Client for the ChangeLens API (backend/README.md; I-22, I-8). Bodies are never logged (03a P10).
import 'dart:convert';
import 'dart:math';
import 'dart:typed_data';

import 'package:http/http.dart' as http;

class ApiException implements Exception {
  ApiException(this.status, this.code, [this.detail]);

  final int status;
  final String code;
  final String? detail;

  @override
  String toString() => detail == null ? code : '$code ($detail)';
}

class Project {
  Project(Map<String, dynamic> j)
      : id = j['id'] as String,
        name = j['name'] as String,
        clientLabel = j['client_label'] as String?,
        comparisonCounts = Map<String, int>.from(j['comparison_counts'] as Map? ?? const {});

  final String id, name;
  final String? clientLabel;
  final Map<String, int> comparisonCounts;
}

class Version {
  Version(Map<String, dynamic> j)
      : id = j['id'] as String,
        label = j['label'] as String,
        kind = j['kind'] as String,
        status = j['status'] as String,
        rejectReason = j['reject_reason'] as String?,
        warnings = (j['parse_warnings'] as List?)?.length ?? 0;

  final String id, label, kind, status;
  final String? rejectReason;
  final int warnings;

  bool get ready => status == 'parsed';
}

/// Only allowlisted status fields; provider details and document content are not status copy.
class ComparisonWarning {
  ComparisonWarning(Map<String, dynamic> json)
      : code = json['code'] as String? ?? '',
        versionId = json['version_id'] as String?,
        reason = json['reason'] as String?;

  final String code;
  final String? versionId, reason;
}

class Comparison {
  Comparison(Map<String, dynamic> j)
      : id = j['id'] as String,
        earlierId = j['earlier_id'] as String? ?? '',
        laterId = j['later_id'] as String? ?? '',
        scope = j['scope'] as String? ?? '',
        status = j['status'] as String,
        warnings = [for (final warning in j['warnings'] as List? ?? [])
          if (warning is Map<String, dynamic>) ComparisonWarning(warning)];

  final String id, earlierId, laterId, scope, status;
  final List<ComparisonWarning> warnings;

  bool get finished => const {'complete', 'partial', 'failed'}.contains(status);
}

/// Scope of the newer version, as confirmed by the user (AC-14). No default exists.
enum Scope { complete, partial, unknown }

/// Create once per user-confirmed submission and retain for any transport retry.
String comparisonRequestKey() {
  final random = Random.secure();
  return List.generate(16, (_) => random.nextInt(256).toRadixString(16).padLeft(2, '0')).join();
}

/// One explicitly selected input. New content is retained only in memory until submission.
class ComparisonInput {
  const ComparisonInput.existing(this.versionId)
      : label = null, text = null, bytes = null, filename = null;
  const ComparisonInput.paste(this.label, this.text)
      : versionId = null, bytes = null, filename = null;
  ComparisonInput.pdf(this.label, Uint8List data, {this.filename})
      : bytes = Uint8List.fromList(data), versionId = null, text = null;

  final String? versionId, label, text, filename;
  final Uint8List? bytes;

  Map<String, dynamic> get descriptor => versionId != null
      ? {'version_id': versionId}
      : {'label': label, if (bytes != null) 'file': true else 'text': text};
}

/// The decoded JSON body of a 2xx response, or an [ApiException] with the problem code.
dynamic decodeApiResponse(http.Response res) {
  dynamic body;
  try {
    body = res.body.isEmpty ? null : jsonDecode(res.body);
  } on FormatException {
    body = null; // not JSON (a proxy error page, say): report the status only
  }
  if (res.statusCode >= 300) {
    // Problem details (backend/changelens/api/errors.py): {"code": ..., "detail"?: ...}
    final err = body is Map ? body : const {};
    throw ApiException(res.statusCode, '${err['code'] ?? 'http_${res.statusCode}'}', err['detail'] as String?);
  }
  return body;
}

/// The account's onboarding state (O-23): `GET /me/onboarding` and the `onboarding` of `POST /session`.
class OnboardingState {
  const OnboardingState({required this.completed, this.step});

  OnboardingState.fromJson(Map<String, dynamic> j)
      : completed = j['completed'] == true,
        step = j['step'] is int ? j['step'] as int : null;

  static const notStarted = OnboardingState(completed: false);

  final bool completed;

  /// The last step reached, 1-based; null when not started or completed.
  final int? step;
}

/// The usage-events consent (D-18 tier B): `GET`/`PUT /me/consent`. [granted] is null when the account
/// hasn't answered for the current [policyVersion].
class ConsentState {
  const ConsentState({required this.granted, required this.policyVersion});

  ConsentState.fromJson(Map<String, dynamic> j)
      : granted = (j['usage_events'] as Map<String, dynamic>)['granted'] as bool?,
        policyVersion = (j['usage_events'] as Map<String, dynamic>)['policy_version'] as String;

  final bool? granted;
  final String policyVersion;
}

class Api {
  Api(this.baseUrl, this.token, {http.Client? client}) : _client = client ?? http.Client();

  final String baseUrl, token;
  final http.Client _client;

  /// With signed-in accounts the client adds the bearer itself and [token] is empty.
  Map<String, String> get _auth => token.isEmpty ? {} : {'Authorization': 'Bearer $token'};

  Uri _u(String path) => Uri.parse(baseUrl.replaceAll(RegExp(r'/+$'), '') + path);

  Future<dynamic> _json(Future<http.Response> call) async => decodeApiResponse(await call);

  Future<OnboardingState> onboarding() async =>
      OnboardingState.fromJson(await _json(_client.get(_u('/me/onboarding'), headers: _auth)));

  /// Saves the last onboarding step reached (1-based) or completion; exactly one of the two (O-23).
  Future<OnboardingState> saveOnboarding({int? step, bool completed = false}) async {
    assert((step != null) != completed, 'send exactly one of step or completed');
    return OnboardingState.fromJson(await _json(_client.put(_u('/me/onboarding'),
        headers: {..._auth, 'Content-Type': 'application/json'},
        body: jsonEncode(completed ? {'completed': true} : {'step': step}))));
  }

  Future<ConsentState> consent() async =>
      ConsentState.fromJson(await _json(_client.get(_u('/me/consent'), headers: _auth)));

  /// Answers for [policyVersion], which must be the server's current one (else `policy_version_stale`).
  Future<ConsentState> saveConsent({required bool granted, required String policyVersion}) async =>
      ConsentState.fromJson(await _json(_client.put(_u('/me/consent'),
          headers: {..._auth, 'Content-Type': 'application/json'},
          body: jsonEncode({'usage_events': {'granted': granted, 'policy_version': policyVersion}}))));

  /// `DELETE /me` (I-8 S5): true when every step finished, false when the rest is pending. Both mean the
  /// account is gone for the app: every later call is rejected.
  Future<bool> deleteAccount() async {
    final response = await _client.delete(_u('/me'), headers: _auth);
    decodeApiResponse(response);
    if (response.statusCode == 204) return true;
    if (response.statusCode == 202) return false;
    throw ApiException(response.statusCode, 'unexpected_response');
  }

  Future<List<Project>> projects() async {
    final j = await _json(_client.get(_u('/projects'), headers: _auth));
    return [for (final p in j['projects'] as List) Project(p as Map<String, dynamic>)];
  }

  Future<Project> createProject(String name, {String? clientLabel}) async => Project(await _json(_client.post(
      _u('/projects'),
      headers: {..._auth, 'Content-Type': 'application/json'},
      body: jsonEncode({'name': name, 'client_label': clientLabel}))));

  /// Idempotent deletion: true means primary storage is purged; false means durable cleanup is pending.
  Future<bool> deleteProject(String id) async {
    final response = await _client.delete(_u('/projects/$id'), headers: _auth);
    await _json(Future.value(response));
    if (response.statusCode == 204) return true;
    if (response.statusCode == 202) return false;
    throw ApiException(response.statusCode, 'unexpected_response');
  }

  Future<List<Version>> versions(String projectId) async {
    final j = await _json(_client.get(_u('/projects/$projectId/versions'), headers: _auth));
    return [for (final v in j['versions'] as List) Version(v as Map<String, dynamic>)];
  }

  Future<Version> version(String id) async =>
      Version(await _json(_client.get(_u('/versions/$id'), headers: _auth)));

  /// Explicit foreground use only. Metadata polls and evidence prefetch never call this.
  Future<void> versionOpened(String id) =>
      _json(_client.post(_u('/versions/$id/opened'), headers: _auth));

  /// Called once when a report or finding screen opens, not by automatic refreshes.
  Future<void> comparisonOpened(String id) =>
      _json(_client.post(_u('/comparisons/$id/opened'), headers: _auth));

  Future<List<Comparison>> comparisons(String projectId) async {
    final j = await _json(_client.get(_u('/projects/$projectId/comparisons'), headers: _auth));
    return [for (final c in j['comparisons'] as List) Comparison(c as Map<String, dynamic>)];
  }

  /// Uploads pasted text or a file's bytes, held in memory only (AC-25).
  Future<Version> upload(String projectId, String label, {String? text, Uint8List? bytes, String? filename}) async {
    final req = http.MultipartRequest('POST', _u('/projects/$projectId/versions'))
      ..headers.addAll(_auth)
      ..fields['label'] = label;
    if (text != null) {
      req.fields['text'] = text;
    } else {
      req.files.add(http.MultipartFile.fromBytes('file', bytes!, filename: filename ?? 'document'));
    }
    final streamed = await _client.send(req);
    return Version(await _json(http.Response.fromStream(streamed)));
  }

  /// The only call that starts processing: it carries the user's order and scope (AC-14).
  Future<String> startComparison(String projectId, String earlierId, String laterId, Scope scope,
      {String? idempotencyKey}) async {
    final j = await _json(_client.post(_u('/projects/$projectId/comparisons'),
        headers: {..._auth, 'Content-Type': 'application/json',
          'Idempotency-Key': idempotencyKey ?? comparisonRequestKey()},
        body: jsonEncode({'earlier_id': earlierId, 'later_id': laterId, 'scope': scope.name})));
    return j['id'] as String;
  }

  /// Atomically imports both slots and creates the waiting/queued comparison. Keep the
  /// supplied key and exact inputs unchanged for a transport retry of this submission.
  Future<Comparison> createComparison(String projectId, ComparisonInput earlier, ComparisonInput later,
      Scope scope, {required String idempotencyKey}) async {
    final payload = {'earlier': earlier.descriptor, 'later': later.descriptor, 'scope': scope.name};
    final headers = {..._auth, 'Idempotency-Key': idempotencyKey};
    if (earlier.bytes == null && later.bytes == null) {
      return Comparison(await _json(_client.post(_u('/projects/$projectId/comparisons'),
          headers: {...headers, 'Content-Type': 'application/json'}, body: jsonEncode(payload))));
    }
    final request = http.MultipartRequest('POST', _u('/projects/$projectId/comparisons'))
      ..headers.addAll(headers)
      ..fields['comparison'] = jsonEncode(payload);
    for (final entry in {'earlier': earlier, 'later': later}.entries) {
      if (entry.value.bytes != null) {
        request.files.add(http.MultipartFile.fromBytes('${entry.key}_file', entry.value.bytes!,
            filename: entry.value.filename ?? 'document.pdf'));
      }
    }
    return Comparison(await _json(http.Response.fromStream(await _client.send(request))));
  }

  Future<Comparison> comparison(String id) async =>
      Comparison(await _json(_client.get(_u('/comparisons/$id'), headers: _auth)));
}

/// A quoted passage at its locator (03 §3). `quote` equals the parsed text there (AC-9).
class Evidence {
  Evidence(Map<String, dynamic> j)
      : side = j['side'] as String,
        quote = j['quote'] as String,
        page = (j['locator'] as Map)['page'] as int?,
        charStart = (j['locator'] as Map)['char_start'] as int,
        charEnd = (j['locator'] as Map)['char_end'] as int;

  final String side, quote;
  final int? page;
  final int charStart, charEnd;

  bool get earlier => side == 'earlier';
}

class Review {
  Review(Map<String, dynamic> j)
      : action = j['action'] as String,
        note = j['note'] as String?,
        evidenceModeBefore = (j['evidence_mode'] as Map?)?['before'] as String?,
        evidenceModeAfter = (j['evidence_mode'] as Map?)?['after'] as String?,
        pageOpened = j['page_opened'] as bool?,
        dismissalReason = j['dismissal_reason'] as String?,
        at = DateTime.parse(j['at'] as String);

  final String action;
  final String? note;
  /// Why a dismissal was made (WP-C): reworded | wrong_passage | irrelevant | other. Null on other
  /// actions and on dismissals recorded before the field existed.
  final String? dismissalReason;
  // Historical reviews have unknown observations; never infer them from the action.
  final String? evidenceModeBefore, evidenceModeAfter;
  final bool? pageOpened;
  final DateTime at;
}

const findingTopics = ['deadlines', 'deliverables', 'responsibilities', 'approval_wording', 'budget', 'other'];

String topicForCategory(String category) => switch (category) {
  'date_deadline' => 'deadlines',
  'deliverable' || 'quantity' => 'deliverables',
  'responsibility_owner' => 'responsibilities',
  'approval' || 'approval_wording' => 'approval_wording',
  'budget' => 'budget',
  _ => 'other',
};

class Finding {
  Finding(Map<String, dynamic> j)
      : id = j['id'] as String,
        changeType = j['change_type'] as String,
        category = j['category'] as String,
        topic = j['topic'] as String? ?? topicForCategory(j['category'] as String),
        evidence = [for (final e in j['evidence'] as List) Evidence(e as Map<String, dynamic>)],
        explanation = j['explanation'] as String?,
        uncertainty = j['uncertainty'] as String?,
        note = j['note'] as String?,
        group = j['group'] as String? ?? 'other',
        revision = j['revision'] as int? ?? 1,
        review = j['review'] == null ? null : Review(j['review'] as Map<String, dynamic>),
        clientApprovalRecorded = j['client_approval_recorded'] as bool? ?? false;

  final String id, changeType, category, topic, group;
  final List<Evidence> evidence;
  final String? explanation, uncertainty, note;
  final int revision;
  final Review? review;
  final bool clientApprovalRecorded;

  Iterable<Evidence> side(String s) => evidence.where((e) => e.side == s);
}

class Report {
  Report(Map<String, dynamic> j)
      : status = j['status'] as String,
        scope = j['scope'] as String?,
        earlierId = j['earlier_id'] as String? ?? '',
        laterId = j['later_id'] as String? ?? '',
        findings = [for (final f in j['findings'] as List) Finding(f as Map<String, dynamic>)],
        topicCounts = {for (final topic in findingTopics) topic:
          (j['topic_counts'] as Map?)?[topic] as int? ?? (j['findings'] as List).where((f) =>
            (f['topic'] ?? topicForCategory(f['category'] as String)) == topic).length},
        otherDifferences = (j['summary'] as Map?)?['other_differences'] as int? ?? 0,
        withheld = j['withheld_count'] as int? ?? 0,
        unexplained = [for (final e in j['unexplained_differences'] as List? ?? []) Evidence(e as Map<String, dynamic>)],
        presentationOnly = [for (final e in j['presentation_only'] as List? ?? []) Evidence(e as Map<String, dynamic>)],
        warnings = [for (final w in j['warnings'] as List? ?? []) (w as Map)['code'] as String];

  final String status, earlierId, laterId;
  final String? scope;
  final List<Finding> findings;
  final Map<String, int> topicCounts;
  final int otherDifferences, withheld;
  final List<Evidence> unexplained, presentationOnly;
  final List<String> warnings;

  List<Finding> inGroup(String g) => [for (final f in findings) if (f.group == g) f];
}

/// "Client approval recorded (not verified by ChangeLens)": a separate record, never a review (AC-12).
class ApprovalRecord {
  ApprovalRecord(Map<String, dynamic> j)
      : evidenceText = j['evidence_text'] as String,
        statedBy = j['stated_by'] as String,
        statedAt = DateTime.parse(j['stated_at'] as String);

  final String evidenceText, statedBy;
  final DateTime statedAt;
}

class FindingDetail {
  FindingDetail(Map<String, dynamic> j)
      : finding = Finding(j),
        revisions = [for (final r in j['revisions'] as List) Finding(r as Map<String, dynamic>)],
        reviews = [for (final r in j['reviews'] as List) Review(r as Map<String, dynamic>)],
        approvals = [for (final a in j['client_approvals'] as List) ApprovalRecord(a as Map<String, dynamic>)];

  final Finding finding;
  final List<Finding> revisions;
  final List<Review> reviews;
  final List<ApprovalRecord> approvals;
}

extension ReportApi on Api {
  Future<Report> report(String comparisonId) async =>
      Report(await _json(_client.get(_u('/comparisons/$comparisonId/findings'), headers: _auth)));

  Future<FindingDetail> finding(String id) async =>
      FindingDetail(await _json(_client.get(_u('/findings/$id'), headers: _auth)));

  /// confirmed | corrected | dismissed | note. A correction returns the new revision (AC-15). A
  /// dismissal needs its [dismissalReason], and only a dismissal takes one (WP-C).
  Future<Finding> review(String findingId, String action, {required Map<String, String?> evidenceMode,
      required bool pageOpened, String? note, Map<String, String>? correction, String? dismissalReason}) async {
    assert((action == 'dismissed') == (dismissalReason != null), 'a dismissal needs a reason, and only a dismissal');
    final j = await _json(_client.post(_u('/findings/$findingId/reviews'),
        headers: {..._auth, 'Content-Type': 'application/json'},
        body: jsonEncode({'action': action, 'note': note, 'correction': correction,
          'dismissal_reason': ?dismissalReason,
          'evidence_mode': evidenceMode, 'page_opened': pageOpened})));
    return Finding(j['finding'] as Map<String, dynamic>);
  }

  Future<void> recordApproval(String findingId, String evidenceText, String statedBy, DateTime statedAt) =>
      _json(_client.post(_u('/findings/$findingId/client-approvals'),
          headers: {..._auth, 'Content-Type': 'application/json'},
          body: jsonEncode({'evidence_text': evidenceText, 'stated_by': statedBy,
                            'stated_at': statedAt.toUtc().toIso8601String()})));

  /// Parsed page texts: the evidence fallback (03 §9.4).
  Future<List<String>> versionText(String versionId) async {
    final j = await _json(_client.get(_u('/versions/$versionId/text'), headers: _auth));
    return [for (final p in j['pages'] as List) p as String];
  }

  /// The original document, held in memory only (AC-25).
  Future<Uint8List> original(String versionId) async {
    final res = await _client.get(_u('/versions/$versionId/original'), headers: _auth);
    if (res.statusCode != 200) throw ApiException(res.statusCode, 'http_${res.statusCode}');
    return res.bodyBytes;
  }
}
