import 'dart:convert';

import 'package:changelens/api.dart';
import 'package:changelens/l10n/app_localizations_de.dart';
import 'package:changelens/l10n/app_localizations_en.dart';
import 'package:changelens/main.dart';
import 'package:changelens/screens/comparison_screen.dart';
import 'package:changelens/services.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'app_test.dart' show MemoryStore, FakePicker;

class StatusBackend {
  String status = 'waiting_for_versions';
  List<Map<String, dynamic>> warnings = [];
  bool unavailable = false, metadataUnavailable = false;
  final requests = <http.Request>[];

  Future<http.Response> handle(http.Request request) async {
    requests.add(request);
    if (unavailable || (metadataUnavailable && request.url.path.startsWith('/versions/'))) {
      return http.Response('{"code":"provider_failed","detail":"PRIVATE_PROVIDER_CONTENT"}', 503);
    }
    if (request.url.path == '/comparisons/c1') {
      return http.Response(jsonEncode({'id': 'c1', 'earlier_id': 'v1', 'later_id': 'v2',
        'status': status, 'warnings': warnings}), 200);
    }
    final earlier = request.url.path == '/versions/v1';
    return http.Response(jsonEncode({'id': earlier ? 'v1' : 'v2', 'label': earlier ? 'First brief' : 'Updated brief',
      'kind': 'pdf', 'status': status == 'waiting_for_versions' ? 'uploaded' : earlier ? 'parsed' : 'rejected',
      'reject_reason': earlier ? null : 'no_text_layer'}), 200);
  }
}

Future<void> pumpStatus(WidgetTester tester, StatusBackend backend) async {
  final store = MemoryStore()..values['api_base_url'] = 'http://dev.test'
    ..values['dev_token'] = 'dev-token-0123456789';
  final services = Services(store, FakePicker(null), apiFactory: (base, token) =>
    Api(base, token, client: MockClient(backend.handle)));
  await services.load();
  await tester.pumpWidget(ChangeLensApp(services: services, home: const ComparisonScreen(comparisonId: 'c1')));
  await tester.pump();
  await tester.pump(const Duration(milliseconds: 1));
}

void main() {
  test('Comparison keeps only typed warning metadata and supports older responses', () {
    final comparison = Comparison({'id': 'c', 'status': 'failed', 'warnings': [
      {'code': 'version_rejected', 'version_id': 'v2', 'reason': 'malformed_pdf', 'detail': 'PRIVATE_CONTENT'},
    ]});
    expect(comparison.warnings.single.code, 'version_rejected');
    expect(comparison.warnings.single.versionId, 'v2');
    expect(comparison.warnings.single.reason, 'malformed_pdf');
    expect(Comparison({'id': 'c', 'status': 'queued'}).warnings, isEmpty);
  });

  testWidgets('waiting becomes failed with the rejected version and readable reason; no POST', (tester) async {
    final backend = StatusBackend();
    await pumpStatus(tester, backend);
    expect(find.text('Status: Reading versions'), findsOneWidget);
    backend.status = 'failed';
    backend.warnings = [{'code': 'version_rejected', 'version_id': 'v2', 'reason': 'no_text_layer'}];
    await tester.pump(const Duration(seconds: 2));
    await tester.pumpAndSettle();
    expect(find.text('Status: Failed'), findsOneWidget);
    expect(find.textContaining('“Updated brief” could not be read'), findsOneWidget);
    expect(find.textContaining('no selectable text'), findsOneWidget);
    expect(find.text('Open report'), findsNothing);
    expect(backend.requests.where((r) => r.method != 'GET'), isEmpty);
    final count = backend.requests.length;
    await tester.pump(const Duration(seconds: 5));
    expect(backend.requests.length, count); // terminal status stops polling
  });

  for (final status in ['failed', 'partial']) {
    testWidgets('$status cost ceiling shows stopped processing without provider details', (tester) async {
      final backend = StatusBackend()..status = status..warnings = [
        {'code': 'cost_ceiling', 'reason': 'PRIVATE_PROVIDER_CONTENT', 'detail': 'PRIVATE_DOCUMENT_CONTENT'},
      ];
      await pumpStatus(tester, backend);
      await tester.pumpAndSettle();
      expect(find.text('The cost limit was reached, so processing has stopped.'), findsOneWidget);
      expect(find.textContaining('standard wording'), findsNothing);
      expect(find.textContaining('PRIVATE_'), findsNothing);
      expect(find.text('Open report'), status == 'partial' ? findsOneWidget : findsNothing);
      expect(backend.requests.where((r) => r.method != 'GET'), isEmpty);
    });
  }

  testWidgets('unknown rejection reason stays generic and never renders raw contents', (tester) async {
    final backend = StatusBackend()..status = 'failed'..warnings = [
      {'code': 'version_rejected', 'version_id': 'v2', 'reason': 'PRIVATE_DOCUMENT_CONTENT'},
    ];
    await pumpStatus(tester, backend);
    await tester.pumpAndSettle();
    expect(find.textContaining('“Updated brief” could not be read'), findsOneWidget);
    expect(find.textContaining('Export it again or paste the text'), findsOneWidget);
    expect(find.textContaining('PRIVATE_'), findsNothing);
  });

  testWidgets('other failures show generic recovery and metadata failures retain terminal status', (tester) async {
    final backend = StatusBackend()..status = 'failed'..metadataUnavailable = true..warnings = [
      {'code': 'PRIVATE_PROVIDER_CONTENT'},
    ];
    await pumpStatus(tester, backend);
    await tester.pumpAndSettle();
    expect(find.text('Status: Failed'), findsOneWidget);
    expect(find.textContaining('This comparison could not be completed'), findsOneWidget);
    expect(find.textContaining('Check your connection and retry'), findsOneWidget);
    expect(find.textContaining('PRIVATE_'), findsNothing);
    backend.metadataUnavailable = false;
    await tester.tap(find.text('Retry'));
    await tester.pumpAndSettle();
    expect(find.text('Earlier · First brief'), findsOneWidget);
    expect(find.text('Newer · Updated brief'), findsOneWidget);
    expect(find.text('Retry'), findsNothing);
    expect(backend.requests.where((r) => r.method != 'GET'), isEmpty);
  });

  test('all parser rejection codes have safe EN/DE wording, unknown codes stay generic', () {
    for (final locale in [AppLocalizationsEn(), AppLocalizationsDe()]) {
      for (final code in ['no_text_layer', 'malformed_pdf', 'limit_exceeded_pages', 'limit_exceeded_words',
        'limit_exceeded_bytes', 'limit_exceeded_text', 'not_utf8', 'unsupported_type', 'parse_timeout',
        'parse_cpu_limit', 'parse_memory_limit']) {
        final message = rejectionReasonLabel(locale, code);
        expect(message, isNot(locale.parseFailed), reason: code);
        expect(message, isNot(contains(code)), reason: code);
      }
      for (final code in ['parse_failed', 'parse_crashed', 'PRIVATE_PROVIDER_CONTENT']) {
        expect(rejectionReasonLabel(locale, code), locale.parseFailed);
      }
    }
  });
}
