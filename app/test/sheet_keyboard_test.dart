// The keyboard in a sheet can always be closed (iPhone report, 2026-11-21: it stayed up over
// Projects after New project). Widget tests against the framework's fake text input; the iOS
// keyboard itself is not exercised here, so this is not device evidence.
import 'package:changelens/design/calm_controls.dart';
import 'package:changelens/screens/projects_screen.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'app_test.dart' show pumpApp;

Future<void> tapAndSettle(WidgetTester tester, Finder finder) async {
  await tester.ensureVisible(finder);
  await tester.tap(finder);
  await tester.pumpAndSettle();
}

Finder inSheet(Finder finder) => find.descendant(of: find.byType(CalmSheet), matching: finder);

void main() {
  testWidgets('New project: a tap on the sheet closes the keyboard and keeps the sheet', (tester) async {
    await pumpApp(tester, () => const ProjectsScreen());
    await tapAndSettle(tester, find.byKey(const Key('new-project')));
    expect(tester.testTextInput.isVisible, isTrue, reason: 'the name field takes focus');

    await tapAndSettle(tester, inSheet(find.text('New project')));
    expect(tester.testTextInput.isVisible, isFalse);
    expect(find.byKey(const Key('create-project')), findsOneWidget);

    // The field takes the keyboard back on a tap, with what was typed still there.
    await tapAndSettle(tester, find.byKey(const Key('project-name')));
    expect(tester.testTextInput.isVisible, isTrue);
    await tester.pumpWidget(const SizedBox());
  });

  testWidgets('New project: Cancel closes the keyboard, and the platform is told to hide it', (tester) async {
    await pumpApp(tester, () => const ProjectsScreen());
    await tapAndSettle(tester, find.byKey(const Key('new-project')));
    expect(tester.testTextInput.isVisible, isTrue);
    tester.testTextInput.log.clear();

    await tapAndSettle(tester, inSheet(find.text('Cancel')));
    expect(find.byType(CalmSheet), findsNothing);
    expect(tester.testTextInput.isVisible, isFalse);
    expect([for (final call in tester.testTextInput.log) call.method], contains('TextInput.hide'));
    await tester.pumpWidget(const SizedBox());
  });

  testWidgets('New project: closing the sheet by its scrim hides the keyboard too', (tester) async {
    await pumpApp(tester, () => const ProjectsScreen());
    await tapAndSettle(tester, find.byKey(const Key('new-project')));
    tester.testTextInput.log.clear();

    await tester.tapAt(const Offset(400, 20)); // the dimmed screen above the sheet
    await tester.pumpAndSettle();
    expect(find.byType(CalmSheet), findsNothing);
    expect(tester.testTextInput.isVisible, isFalse);
    expect([for (final call in tester.testTextInput.log) call.method], contains('TextInput.hide'));
    await tester.pumpWidget(const SizedBox());
  });

  testWidgets('New project: Done on the client field creates the project and closes the keyboard', (tester) async {
    final (_, backend, _) = await pumpApp(tester, () => const ProjectsScreen());
    await tapAndSettle(tester, find.byKey(const Key('new-project')));
    await tester.enterText(find.byKey(const Key('project-name')), 'Sitting 2');
    await tapAndSettle(tester, find.byKey(const Key('project-client')));
    await tester.testTextInput.receiveAction(TextInputAction.done);
    await tester.pumpAndSettle();

    expect(find.byType(CalmSheet), findsNothing);
    expect(tester.testTextInput.isVisible, isFalse);
    expect(backend.requests.where((r) => r.method == 'POST' && r.url.path == '/projects'), hasLength(1));
    await tester.pumpWidget(const SizedBox());
  });

  testWidgets('New project: Done with a blank name keeps the sheet and names the field', (tester) async {
    final (_, backend, _) = await pumpApp(tester, () => const ProjectsScreen());
    await tapAndSettle(tester, find.byKey(const Key('new-project')));
    await tapAndSettle(tester, find.byKey(const Key('project-client')));
    await tester.testTextInput.receiveAction(TextInputAction.done);
    await tester.pumpAndSettle();

    expect(find.byType(CalmSheet), findsOneWidget);
    expect(find.text('Enter a project name.'), findsOneWidget);
    expect(backend.requests.where((r) => r.method == 'POST'), isEmpty);
    await tester.pumpWidget(const SizedBox());
  });
}
