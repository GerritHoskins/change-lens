import 'dart:async';
import 'dart:convert';

import 'package:changelens/api.dart';
import 'package:changelens/main.dart';
import 'package:changelens/screens/projects_screen.dart';
import 'package:changelens/services.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';

import 'app_test.dart' show FakePicker, MemoryStore;

class DeletionBackend {
  bool exists = true;
  int deletes = 0;
  int status = 204;
  bool loseReplyOnce = false;
  Completer<void>? hold;
  final requests = <http.Request>[];

  Future<http.Response> handle(http.Request request) async {
    requests.add(request);
    if (request.method == 'DELETE') {
      deletes++;
      exists = false;
      if (hold != null) await hold!.future;
      if (loseReplyOnce) {
        loseReplyOnce = false;
        throw http.ClientException('Transport failed');
      }
      return http.Response(status == 202 ? '{"status":"deleting"}' : '', status);
    }
    return switch (request.url.path) {
      '/projects' => http.Response(jsonEncode({'projects': exists ? [
        {'id': 'p1', 'name': 'Relaunch'},
      ] : []}), 200),
      '/projects/p1/versions' => http.Response('{"versions":[]}', 200),
      '/projects/p1/comparisons' => http.Response('{"comparisons":[]}', 200),
      _ => http.Response('{"code":"not_found"}', 404),
    };
  }
}

Future<Services> openProject(WidgetTester tester, DeletionBackend backend) async {
  final store = MemoryStore()
    ..values['api_base_url'] = 'https://api.test'
    ..values['dev_token'] = 'test-token';
  final services = Services(store, FakePicker(null), apiFactory: (base, token) =>
    Api(base, token, client: MockClient(backend.handle)));
  await services.load();
  services.pendingComparison = ComparisonSubmission(Project({'id': 'p1', 'name': 'Relaunch'}),
    const ComparisonInput.paste('earlier', 'before'), const ComparisonInput.paste('later', 'after'), Scope.complete);
  await tester.pumpWidget(ChangeLensApp(services: services, home: const ProjectsScreen()));
  await tester.pumpAndSettle();
  await tester.scrollUntilVisible(find.text('Relaunch'), 120);
  await tester.pumpAndSettle();
  await tester.tap(find.text('Relaunch'));
  await tester.pumpAndSettle();
  return services;
}

Future<void> confirmDialog(WidgetTester tester) async {
  await tester.tap(find.byKey(const Key('project-menu')));
  await tester.pumpAndSettle();
  await tester.tap(find.text('Delete project'));
  await tester.pumpAndSettle();
}

void main() {
  testWidgets('German large-text delete confirmation can scroll without hiding actions', (tester) async {
    tester.view.physicalSize = const Size(320, 568);
    tester.view.devicePixelRatio = 1;
    tester.platformDispatcher.textScaleFactorTestValue = 2;
    tester.platformDispatcher.localesTestValue = const [Locale('de')];
    addTearDown(tester.view.resetPhysicalSize);
    addTearDown(tester.view.resetDevicePixelRatio);
    addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
    addTearDown(tester.platformDispatcher.clearLocalesTestValue);
    final backend = DeletionBackend();
    await openProject(tester, backend);
    await tester.tap(find.byKey(const Key('project-menu')));
    await tester.pumpAndSettle();
    await tester.tap(find.text('Projekt löschen'));
    await tester.pumpAndSettle();
    final content = find.textContaining('Dies kann nicht rückgängig gemacht werden.');
    expect(content, findsOneWidget);
    final scroll = find.ancestor(of: content, matching: find.byType(Scrollable));
    expect(scroll, findsOneWidget);
    expect(find.byKey(const Key('confirm-delete-project')).hitTestable(), findsOneWidget);
    expect(find.text('Abbrechen').hitTestable(), findsOneWidget);
    await tester.drag(scroll, const Offset(0, -350));
    await tester.pumpAndSettle();
    expect(tester.takeException(), isNull);
    expect(backend.deletes, 0);
    await tester.pumpWidget(const SizedBox());
  });

  testWidgets('cancel never requests deletion or clears a pending comparison', (tester) async {
    final backend = DeletionBackend();
    final services = await openProject(tester, backend);
    await confirmDialog(tester);
    expect(find.textContaining('documents, comparisons and reviews'), findsOneWidget);
    await tester.tap(find.text('Cancel'));
    await tester.pumpAndSettle();
    expect(backend.deletes, 0);
    expect(services.pendingComparison, isNotNull);
    expect(find.byKey(const Key('compare')), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
  });

  for (final status in [204, 202]) {
    testWidgets('delete $status hides the project with an accurate outcome', (tester) async {
      final backend = DeletionBackend()..status = status;
      final services = await openProject(tester, backend);
      await confirmDialog(tester);
      await tester.tap(find.byKey(const Key('confirm-delete-project')));
      await tester.pumpAndSettle();
      expect(backend.deletes, 1);
      expect(services.pendingComparison, isNull);
      expect(find.text('Relaunch'), findsNothing);
      expect(find.text(status == 204 ? 'Project deleted.' : 'Project hidden. Its data is being deleted.'), findsOneWidget);
      expect(backend.requests.singleWhere((r) => r.method == 'DELETE').headers['authorization'], 'Bearer test-token');
      await tester.pumpWidget(const SizedBox());
    });
  }

  testWidgets('lost delete response stops content polling and retry is safe', (tester) async {
    final backend = DeletionBackend()..loseReplyOnce = true;
    await openProject(tester, backend);
    await confirmDialog(tester);
    await tester.tap(find.byKey(const Key('confirm-delete-project')));
    await tester.pumpAndSettle();
    expect(find.byKey(const Key('compare')), findsNothing);
    expect(find.byKey(const Key('paste')), findsNothing);
    expect(find.byKey(const Key('retry-delete-project')), findsOneWidget);
    final before = backend.requests.length;
    await tester.pump(const Duration(seconds: 10));
    expect(backend.requests.length, before);
    await tester.tap(find.byKey(const Key('retry-delete-project')));
    await tester.pumpAndSettle();
    expect(backend.deletes, 2);
    expect(find.text('Project deleted.'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
  });

  testWidgets('in-flight deletion cannot be submitted again or navigated away', (tester) async {
    final backend = DeletionBackend()..hold = Completer<void>();
    await openProject(tester, backend);
    await confirmDialog(tester);
    await tester.tap(find.byKey(const Key('confirm-delete-project')));
    await tester.pump();
    await tester.pump(const Duration(milliseconds: 400));
    expect(find.text('Deleting project…'), findsOneWidget);
    expect(find.byKey(const Key('project-menu')), findsNothing);
    await tester.pageBack();
    await tester.pump();
    expect(find.text('Deleting project…'), findsOneWidget);
    expect(backend.deletes, 1);
    backend.hold!.complete();
    await tester.pumpAndSettle();
    expect(find.text('Project deleted.'), findsOneWidget);
    await tester.pumpWidget(const SizedBox());
  });

  test('unexpected success response does not claim completed deletion', () async {
    final backend = DeletionBackend()..status = 200;
    final api = Api('https://api.test', 'test-token', client: MockClient(backend.handle));
    await expectLater(api.deleteProject('p1'), throwsA(isA<ApiException>()));
  });
}
