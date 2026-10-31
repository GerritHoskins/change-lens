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
