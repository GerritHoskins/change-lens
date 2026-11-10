import 'dart:convert';
import 'dart:typed_data';

import 'package:changelens/api.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

void main() {
  test('one request carries explicit ordered slots and the same key on retry', () async {
    final requests = <http.Request>[];
    final api = Api('http://local.test', 'test-token', client: MockClient((request) async {
      requests.add(request);
      return http.Response('{"id":"c1","status":"waiting_for_versions"}', 202);
    }));
    const earlier = ComparisonInput.paste('First', 'Budget: EUR 100');
    const later = ComparisonInput.existing('existing-later');
    for (var attempt = 0; attempt < 2; attempt++) {
      final result = await api.createComparison('p1', earlier, later, Scope.partial,
          idempotencyKey: 'stable-submission-key');
      expect(result.id, 'c1');
      expect(result.finished, isFalse);
    }
    expect(requests.length, 2);
    expect(requests.map((r) => r.url.path), everyElement('/projects/p1/comparisons'));
    expect(requests.map((r) => r.headers['Idempotency-Key']), everyElement('stable-submission-key'));
    expect(requests.first.body, requests.last.body);
    expect(jsonDecode(requests.first.body), {
      'earlier': {'label': 'First', 'text': 'Budget: EUR 100'},
      'later': {'version_id': 'existing-later'},
      'scope': 'partial',
    });
  });

  test('two PDFs are copied into memory and sent in a single ordered multipart request', () async {
    late http.Request captured;
    final api = Api('http://local.test', 'test-token', client: MockClient((request) async {
      captured = request;
      return http.Response('{"id":"c2","status":"waiting_for_versions"}', 202);
    }));
    final bytes = Uint8List.fromList(utf8.encode('%PDF-1.7 earlier'));
    final earlier = ComparisonInput.pdf('Before', bytes, filename: 'before.pdf');
    bytes.fillRange(0, bytes.length, 0); // a retry retains the confirmed input, not a caller's mutated buffer
    await api.createComparison('p1', earlier,
        ComparisonInput.pdf('After', Uint8List.fromList(utf8.encode('%PDF-1.7 later'))), Scope.unknown,
        idempotencyKey: 'same-pdf-submission-key');
    expect(captured.headers['content-type'], startsWith('multipart/form-data;'));
    expect(captured.body, contains('name="earlier_file"'));
    expect(captured.body, contains('name="later_file"'));
    expect(captured.body, contains('%PDF-1.7 earlier'));
    expect(captured.body, contains('%PDF-1.7 later'));
    expect(captured.body, contains('"scope":"unknown"'));
  });

  test('conflicting reuse is reported without silently creating another comparison', () async {
    var calls = 0;
    final api = Api('http://local.test', 'test-token', client: MockClient((request) async {
      calls++;
      return http.Response('{"code":"idempotency_conflict"}', 409);
    }));
    await expectLater(api.createComparison('p1', const ComparisonInput.existing('a'),
        const ComparisonInput.existing('b'), Scope.complete, idempotencyKey: 'conflicting-key-123'),
        throwsA(isA<ApiException>().having((e) => e.code, 'code', 'idempotency_conflict')));
    expect(calls, 1);
  });
}
