// Client for the dev comparison API (backend/README.md, I-22). Bodies are never logged (03a P10).
import 'dart:convert';
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
        clientLabel = j['client_label'] as String?;

  final String id, name;
  final String? clientLabel;
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

class Comparison {
  Comparison(Map<String, dynamic> j)
      : id = j['id'] as String,
        earlierId = j['earlier_id'] as String? ?? '',
        laterId = j['later_id'] as String? ?? '',
        scope = j['scope'] as String? ?? '',
        status = j['status'] as String;

  final String id, earlierId, laterId, scope, status;

  bool get finished => const {'complete', 'partial', 'failed'}.contains(status);
}

/// Scope of the newer version, as confirmed by the user (AC-14). No default exists.
enum Scope { complete, partial, unknown }

class Api {
  Api(this.baseUrl, this.token, {http.Client? client}) : _client = client ?? http.Client();

  final String baseUrl, token;
  final http.Client _client;

  Map<String, String> get _auth => {'Authorization': 'Bearer $token'};

  Uri _u(String path) => Uri.parse(baseUrl.replaceAll(RegExp(r'/+$'), '') + path);

  Future<dynamic> _json(Future<http.Response> call) async {
    final res = await call;
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

  Future<List<Project>> projects() async {
    final j = await _json(_client.get(_u('/projects'), headers: _auth));
    return [for (final p in j['projects'] as List) Project(p as Map<String, dynamic>)];
  }

  Future<Project> createProject(String name, {String? clientLabel}) async => Project(await _json(_client.post(
      _u('/projects'),
      headers: {..._auth, 'Content-Type': 'application/json'},
      body: jsonEncode({'name': name, 'client_label': clientLabel}))));

  Future<List<Version>> versions(String projectId) async {
    final j = await _json(_client.get(_u('/projects/$projectId/versions'), headers: _auth));
    return [for (final v in j['versions'] as List) Version(v as Map<String, dynamic>)];
  }

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
  Future<String> startComparison(String projectId, String earlierId, String laterId, Scope scope) async {
    final j = await _json(_client.post(_u('/projects/$projectId/comparisons'),
        headers: {..._auth, 'Content-Type': 'application/json'},
        body: jsonEncode({'earlier_id': earlierId, 'later_id': laterId, 'scope': scope.name})));
    return j['id'] as String;
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
        at = DateTime.parse(j['at'] as String);

  final String action;
  final String? note;
  final DateTime at;
}

class Finding {
  Finding(Map<String, dynamic> j)
      : id = j['id'] as String,
        changeType = j['change_type'] as String,
        category = j['category'] as String,
        evidence = [for (final e in j['evidence'] as List) Evidence(e as Map<String, dynamic>)],
        explanation = j['explanation'] as String?,
        uncertainty = j['uncertainty'] as String?,
        note = j['note'] as String?,
        group = j['group'] as String? ?? 'other',
        revision = j['revision'] as int? ?? 1,
        review = j['review'] == null ? null : Review(j['review'] as Map<String, dynamic>),
        clientApprovalRecorded = j['client_approval_recorded'] as bool? ?? false;

  final String id, changeType, category, group;
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
        earlierId = j['earlier_id'] as String? ?? '',
        laterId = j['later_id'] as String? ?? '',
        findings = [for (final f in j['findings'] as List) Finding(f as Map<String, dynamic>)],
        otherDifferences = (j['summary'] as Map?)?['other_differences'] as int? ?? 0,
        withheld = j['withheld_count'] as int? ?? 0,
        unexplained = [for (final e in j['unexplained_differences'] as List? ?? []) Evidence(e as Map<String, dynamic>)],
        presentationOnly = [for (final e in j['presentation_only'] as List? ?? []) Evidence(e as Map<String, dynamic>)],
        warnings = [for (final w in j['warnings'] as List? ?? []) (w as Map)['code'] as String];

  final String status, earlierId, laterId;
  final List<Finding> findings;
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

  /// confirmed | corrected | dismissed | note. A correction returns the new revision (AC-15).
  Future<Finding> review(String findingId, String action, {String? note, Map<String, String>? correction}) async {
    final j = await _json(_client.post(_u('/findings/$findingId/reviews'),
        headers: {..._auth, 'Content-Type': 'application/json'},
        body: jsonEncode({'action': action, 'note': note, 'correction': correction})));
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
