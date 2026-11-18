// L27 (audit A2): a failed import keeps its draft in memory, and a blank required field says why at
// the field and is announced. Widget tests with a fake API; not device or screen-reader evidence.
import 'dart:convert';
import 'dart:typed_data';

import 'package:changelens/screens/compare_screen.dart';
import 'package:changelens/screens/finding_screen.dart';
import 'package:changelens/screens/project_screen.dart';
import 'package:changelens/screens/projects_screen.dart';
import 'package:changelens/services.dart';
import 'package:flutter/material.dart';
import 'package:flutter/rendering.dart';
import 'package:flutter_test/flutter_test.dart';

import 'app_test.dart' show project, pumpApp, ready;
import 'report_test.dart' as fixture;

const needLabel = 'Enter a label for this version.';
const needText = 'Paste the text first.';

String fieldText(WidgetTester tester, String key) => tester.widget<EditableText>(
    find.descendant(of: find.byKey(Key(key)), matching: find.byType(EditableText))).controller.text;

Future<void> tapAndSettle(WidgetTester tester, Finder finder) async {
  await tester.tap(finder);
  await tester.pumpAndSettle();
}

Future<void> openPaste(WidgetTester tester, {String label = '', String text = ''}) async {
  await tapAndSettle(tester, find.byKey(const Key('paste')));
  await tester.enterText(find.byKey(const Key('label')), label);
  await tester.enterText(find.byKey(const Key('pasted')), text);
}

void main() {
  testWidgets('A failed paste import reopens the sheet with the label and text intact', (tester) async {
    final (_, backend, _) = await pumpApp(tester, () => ProjectScreen(project: project));
    backend.failUploads = true;
    await openPaste(tester, label: 'Email update', text: 'Budget is now EUR 15,000.');
    await tapAndSettle(tester, find.byKey(const Key('confirm-import')));

    expect(find.byKey(const Key('confirm-import')), findsOneWidget);
    expect(find.textContaining('the file exceeds the size limit'), findsOneWidget);
    expect(fieldText(tester, 'label'), 'Email update');
    expect(fieldText(tester, 'pasted'), 'Budget is now EUR 15,000.');

    // The same draft goes out again, and a success clears it.
    backend.failUploads = false;
    await tapAndSettle(tester, find.byKey(const Key('confirm-import')));
    expect(find.byKey(const Key('confirm-import')), findsNothing);
    final posts = backend.requests.where((r) => r.method == 'POST').toList();
    expect(posts, hasLength(2));
    expect(utf8.decode(posts[1].bodyBytes), allOf(contains('Email update'), contains('Budget is now EUR 15,000.')));
    await tapAndSettle(tester, find.byKey(const Key('paste')));
    expect(fieldText(tester, 'label'), isEmpty);
    expect(fieldText(tester, 'pasted'), isEmpty);
    expect(find.textContaining('Import failed'), findsNothing);
  });

  testWidgets('Cancel after a failed import discards the draft', (tester) async {
    final (_, backend, _) = await pumpApp(tester, () => ProjectScreen(project: project));
    backend.failUploads = true;
    await openPaste(tester, label: 'Email update', text: 'Budget is now EUR 15,000.');
    await tapAndSettle(tester, find.byKey(const Key('confirm-import')));
    expect(fieldText(tester, 'label'), 'Email update');
    await tapAndSettle(tester, find.text('Cancel'));
    expect(find.byKey(const Key('confirm-import')), findsNothing);
    await tapAndSettle(tester, find.byKey(const Key('paste')));
    expect(fieldText(tester, 'label'), isEmpty);
    expect(fieldText(tester, 'pasted'), isEmpty);
    expect(find.textContaining('Import failed'), findsNothing);
  });

  testWidgets('A failed PDF import reopens the sheet with the label, and the picker copy is purged', (tester) async {
    final (_, backend, picker) = await pumpApp(tester, () => ProjectScreen(project: project),
        pick: PickedDocument('big.pdf', Uint8List(10)));
    backend.failUploads = true;
    await tapAndSettle(tester, find.byKey(const Key('pick-pdf')));
    await tester.enterText(find.byKey(const Key('label')), 'Too big');
    await tapAndSettle(tester, find.byKey(const Key('confirm-import')));
    expect(picker.purges, 1);
    expect(fieldText(tester, 'label'), 'Too big');
    expect(find.textContaining('the file exceeds the size limit'), findsOneWidget);
  });

  testWidgets('Project import: a blank label or text is named at the field and announced', (tester) async {
    final (_, backend, _) = await pumpApp(tester, () => ProjectScreen(project: project));
    await tapAndSettle(tester, find.byKey(const Key('paste')));
    tester.takeAnnouncements();
    await tapAndSettle(tester, find.byKey(const Key('confirm-import')));
    expect(find.text(needLabel), findsOneWidget);
    expect(find.text(needText), findsOneWidget);
    expect([for (final a in tester.takeAnnouncements()) a.message], [needLabel]);
    expect(backend.requests.where((r) => r.method == 'POST'), isEmpty);

    // Typing clears that field's message; the other one stays until it is filled.
    await tester.enterText(find.byKey(const Key('label')), 'Email update');
    await tester.pumpAndSettle();
    expect(find.text(needLabel), findsNothing);
    expect(find.text(needText), findsOneWidget);
    await tapAndSettle(tester, find.byKey(const Key('confirm-import')));
    expect(find.byKey(const Key('confirm-import')), findsOneWidget);
    expect(backend.requests.where((r) => r.method == 'POST'), isEmpty);
  });

  testWidgets('A field message wraps instead of being cut at 320 wide with 2x text', (tester) async {
    tester.view.physicalSize = const Size(320, 568);
    tester.view.devicePixelRatio = 1;
    tester.platformDispatcher.textScaleFactorTestValue = 2;
    addTearDown(tester.view.reset);
    addTearDown(tester.platformDispatcher.clearTextScaleFactorTestValue);
    await pumpApp(tester, () => const ProjectsScreen());
    await tester.scrollUntilVisible(find.byKey(const Key('new-project')), 150,
        scrollable: find.byType(Scrollable).first);
    await tester.pumpAndSettle();
    await tapAndSettle(tester, find.byKey(const Key('new-project')));
    expect(find.byKey(const Key('create-project')).hitTestable(), findsOneWidget);
    await tapAndSettle(tester, find.byKey(const Key('create-project')));
    // The test font is about twice as wide as the app's, so this is the strict case. The label field
    // also shares the message's row with its character counter; that one needs a look on a phone.
    final message = tester.renderObject<RenderParagraph>(find.text('Enter a project name.'));
    expect(message.didExceedMaxLines, isFalse);
    expect(tester.takeException(), isNull);
    await tester.pumpWidget(const SizedBox());
  });

  testWidgets('Compare input: a blank label or text is named, and no PDF is picked without a label', (tester) async {
    final (_, _, picker) = await pumpApp(tester, () => CompareScreen(project: project, versions: ready),
        pick: PickedDocument('brief.pdf', Uint8List(10)));
    await tapAndSettle(tester, find.byKey(const Key('earlier-paste')));
    tester.takeAnnouncements();
    await tapAndSettle(tester, find.byKey(const Key('confirm-import')));
    expect(find.text(needLabel), findsOneWidget);
    expect(find.text(needText), findsOneWidget);
    expect([for (final a in tester.takeAnnouncements()) a.message], [needLabel]);
    await tapAndSettle(tester, find.text('Cancel'));

    await tester.ensureVisible(find.byKey(const Key('newer-pdf')));
    await tapAndSettle(tester, find.byKey(const Key('newer-pdf')));
    await tapAndSettle(tester, find.byKey(const Key('confirm-import')));
    expect(find.text(needLabel), findsOneWidget);
    expect(find.byKey(const Key('confirm-import')), findsOneWidget);
    expect(picker.purges, 0);
  });

  testWidgets('New project: an empty name keeps the sheet open and says why', (tester) async {
    final (_, backend, _) = await pumpApp(tester, () => const ProjectsScreen());
    await tapAndSettle(tester, find.byKey(const Key('new-project')));
    tester.takeAnnouncements();
    await tester.enterText(find.byKey(const Key('project-name')), '   ');
    await tapAndSettle(tester, find.byKey(const Key('create-project')));
    expect(find.byKey(const Key('create-project')), findsOneWidget);
    expect(find.text('Enter a project name.'), findsOneWidget);
    expect([for (final a in tester.takeAnnouncements()) a.message], ['Enter a project name.']);
    expect(backend.requests.where((r) => r.method == 'POST'), isEmpty);
    await tester.pumpWidget(const SizedBox());
  });

  testWidgets('Finding: a blank note and blank approval fields are named, and nothing is saved', (tester) async {
    final backend = fixture.ReportBackend();
    final report = await fixture.loadReport(backend);
    final b = await fixture.pump(tester,
        FindingScreen(comparisonId: 'c1', findingId: 'f1', report: report, versions: fixture.versions));
    await tapAndSettle(tester, find.text('Add note'));
    tester.takeAnnouncements();
    await tapAndSettle(tester, find.text('Save'));
    expect(find.byKey(const Key('note-field')), findsOneWidget);
    expect(find.text('Write the note first.'), findsOneWidget);
    expect([for (final a in tester.takeAnnouncements()) a.message], ['Write the note first.']);
    await tapAndSettle(tester, find.text('Cancel'));

    await tester.scrollUntilVisible(find.text('Record client approval'), 200,
      scrollable: find.descendant(of: find.byType(ListView), matching: find.byType(Scrollable)));
    await tapAndSettle(tester, find.text('Record client approval'));
    await tapAndSettle(tester, find.text('Save'));
    expect(find.byKey(const Key('approval-evidence')), findsOneWidget);
    expect(find.text('Enter the evidence.'), findsOneWidget);
    expect(find.text('Enter who stated it.'), findsOneWidget);
    expect([for (final a in tester.takeAnnouncements()) a.message], ['Enter the evidence.']);
    expect(b.posts(), ['/comparisons/c1/opened']);
  });
}
