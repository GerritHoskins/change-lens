// I-9 widget tests against a mocked API: AC-14 (confirmation gate), AC-15 (immutable versions),
// AC-24 (paste and PDF import) and AC-25 (picker copies purged after every import).
import 'dart:convert';
import 'dart:typed_data';

import 'package:changelens/api.dart';
import 'package:changelens/main.dart';
import 'package:changelens/screens/confirm_screen.dart';
import 'package:changelens/screens/project_screen.dart';
import 'package:changelens/services.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

class MemoryStore implements SettingsStore {
  final values = <String, String>{};

  @override
  Future<String?> read(String key) async => values[key];

  @override
  Future<void> write(String key, String value) async => values[key] = value;
}

class FakePicker implements DocumentPicker {
  FakePicker(this.doc);

  final PickedDocument? doc;
  int purges = 0;

  @override
  Future<PickedDocument?> pickPdf() async => doc;

  @override
  Future<void> purge() async => purges++;
}

Map<String, dynamic> version(String id, String label, {String status = 'parsed'}) =>
    {'id': id, 'label': label, 'kind': 'text', 'status': status, 'parse_warnings': []};

/// A tiny in-memory backend; records every request.
class Backend {
  final requests = <http.Request>[];
  final versions = [version('v1', 'Brief v1'), version('v2', 'Brief v2')];
  bool failUploads = false;

  Future<http.Response> handle(http.Request r) async {
    requests.add(r);
    final p = r.url.path;
    if (r.headers['authorization'] != 'Bearer dev-token-0123456789') return http.Response('{"code":"unauthorized"}', 401);
    if (r.method == 'GET' && p == '/projects') {
      return http.Response(jsonEncode({'projects': [{'id': 'p1', 'name': 'Relaunch', 'client_label': null}]}), 200);
    }
    if (r.method == 'GET' && p == '/projects/p1/versions') return http.Response(jsonEncode({'versions': versions}), 200);
    if (r.method == 'GET' && p == '/projects/p1/comparisons') return http.Response('{"comparisons": []}', 200);
    if (r.method == 'POST' && p == '/projects/p1/versions') {
      if (failUploads) return http.Response('{"code":"limit_exceeded","detail":"bytes"}', 413);
      final v = version('v${versions.length + 1}', 'new', status: 'uploaded');
      versions.add(v);
      return http.Response(jsonEncode(v), 201);
    }
    if (r.method == 'POST' && p == '/projects/p1/comparisons') return http.Response('{"id":"c1","status":"queued"}', 202);
    if (r.method == 'GET' && p == '/comparisons/c1') {
      return http.Response(jsonEncode({'id': 'c1', 'earlier_id': 'v1', 'later_id': 'v2', 'scope': 'partial', 'status': 'queued'}), 200);
    }
    return http.Response('{"code":"not_found"}', 404);
  }
}

Future<(Services, Backend, FakePicker)> pumpApp(WidgetTester tester, Widget Function() home,
    {PickedDocument? pick}) async {
  final backend = Backend();
  final picker = FakePicker(pick);
  final store = MemoryStore()
    ..values['api_base_url'] = 'http://dev.test'
    ..values['dev_token'] = 'dev-token-0123456789';
  final services = Services(store, picker,
      apiFactory: (base, token) => Api(base, token, client: MockClient(backend.handle)));
  await services.load();
  await tester.pumpWidget(ChangeLensApp(services: services, home: home()));
  await tester.pumpAndSettle();
  return (services, backend, picker);
}

final project = Project({'id': 'p1', 'name': 'Relaunch', 'client_label': null});
final ready = [Version(version('v1', 'Brief v1')), Version(version('v2', 'Brief v2'))];

Future<void> choose(WidgetTester tester, String key, String label) async {
  await tester.tap(find.byKey(Key(key)));
  await tester.pumpAndSettle();
  await tester.tap(find.text(label).last);
  await tester.pumpAndSettle();
}

bool startEnabled(WidgetTester tester) => tester.widget<FilledButton>(find.byKey(const Key('start'))).onPressed != null;

void main() {
  testWidgets('AC-14: nothing preselected, and processing is blocked until order and scope are confirmed',
      (tester) async {
    final (_, backend, _) = await pumpApp(tester, () => ConfirmScreen(project: project, versions: ready));
    expect(find.text('Choose a version'), findsNWidgets(2));
    expect(startEnabled(tester), isFalse);

    await choose(tester, 'earlier', 'Brief v2');
    await choose(tester, 'newer', 'Brief v2');
    await tester.tap(find.byKey(const Key('scope-partial')));
    await tester.pumpAndSettle();
    expect(find.text('Choose two different versions.'), findsOneWidget);
    expect(startEnabled(tester), isFalse);

    await choose(tester, 'newer', 'Brief v1');
    expect(startEnabled(tester), isTrue);
    expect(backend.requests.where((r) => r.method == 'POST'), isEmpty);

    await tester.tap(find.byKey(const Key('start')));
    await tester.pump();
    final post = backend.requests.singleWhere((r) => r.method == 'POST');
    // The user's choice, not upload order: v2 is earlier here.
    expect(jsonDecode(post.body), {'earlier_id': 'v2', 'later_id': 'v1', 'scope': 'partial'});
    await tester.pump(const Duration(seconds: 3));
  });

  testWidgets('AC-14: scope alone is not enough', (tester) async {
    await pumpApp(tester, () => ConfirmScreen(project: project, versions: ready));
    await tester.tap(find.byKey(const Key('scope-unknown')));
    await tester.pumpAndSettle();
    expect(startEnabled(tester), isFalse);
    await choose(tester, 'earlier', 'Brief v1');
    expect(startEnabled(tester), isFalse);
  });

  testWidgets('AC-15: versions can only be added, never edited or deleted', (tester) async {
    await pumpApp(tester, () => ProjectScreen(project: project));
    expect(find.byKey(const Key('version-v1')), findsOneWidget);
    expect(find.byType(Dismissible), findsNothing);
    for (final icon in [Icons.delete, Icons.delete_outline, Icons.edit, Icons.edit_outlined]) {
      expect(find.byIcon(icon), findsNothing);
    }
    expect(find.textContaining('cannot be edited'), findsOneWidget);
  });

  testWidgets('AC-24/25: a picked PDF is uploaded from memory and the picker copy is purged', (tester) async {
    final pdf = Uint8List.fromList(utf8.encode('%PDF-1.7 test'));
    final (_, backend, picker) =
        await pumpApp(tester, () => ProjectScreen(project: project), pick: PickedDocument('brief.pdf', pdf));
    await tester.tap(find.byKey(const Key('pick-pdf')));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const Key('label')), 'Brief v3');
    await tester.tap(find.byKey(const Key('confirm-import')));
    await tester.pumpAndSettle();
    final upload = backend.requests.singleWhere((r) => r.method == 'POST');
    expect(upload.url.path, '/projects/p1/versions');
    expect(upload.bodyBytes.length, greaterThan(pdf.length)); // multipart body carrying the bytes
    expect(picker.purges, 1);
  });

  testWidgets('AC-25: the picker copy is purged even when the upload fails', (tester) async {
    final (_, backend, picker) = await pumpApp(tester, () => ProjectScreen(project: project),
        pick: PickedDocument('big.pdf', Uint8List(10)));
    backend.failUploads = true;
    await tester.tap(find.byKey(const Key('pick-pdf')));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const Key('label')), 'Too big');
    await tester.tap(find.byKey(const Key('confirm-import')));
    await tester.pumpAndSettle();
    expect(picker.purges, 1);
    expect(find.textContaining('limit_exceeded'), findsOneWidget);
  });

  testWidgets('AC-24: pasted text is imported with its label', (tester) async {
    final (_, backend, _) = await pumpApp(tester, () => ProjectScreen(project: project));
    await tester.tap(find.byKey(const Key('paste')));
    await tester.pumpAndSettle();
    await tester.enterText(find.byKey(const Key('label')), 'Email update');
    await tester.enterText(find.byKey(const Key('pasted')), 'Budget is now EUR 15,000.');
    await tester.tap(find.byKey(const Key('confirm-import')));
    await tester.pumpAndSettle();
    final body = utf8.decode(backend.requests.singleWhere((r) => r.method == 'POST').bodyBytes);
    expect(body, contains('Email update'));
    expect(body, contains('Budget is now EUR 15,000.'));
  });

  testWidgets('The app asks for the dev connection before anything else', (tester) async {
    final services = Services(MemoryStore(), FakePicker(null));
    await services.load();
    await tester.pumpWidget(ChangeLensApp(services: services));
    await tester.pumpAndSettle();
    expect(find.textContaining('developer settings'), findsOneWidget);
    expect(find.byKey(const Key('new-project')), findsNothing);
  });
}
