import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

import 'finding_progression_test.dart' show ProgressBackend, pumpProgress, reviewPosts;

void main() {
  testWidgets('failed reload after saving retains evidence but blocks duplicate review until retry', (tester) async {
    final backend = ProgressBackend();
    // The final finding stays open after Confirm, so a failed reload retains its old detail.
    await pumpProgress(tester, backend, findingId: 'second');
    backend.failNextLoad = true;

    await tester.tap(find.byKey(const Key('review-confirm')));
    await tester.pumpAndSettle();

    expect(reviewPosts(backend), hasLength(1));
    expect(find.text('Second source'), findsOneWidget);
    expect(find.text('This content could not be opened. Check your connection and retry.'), findsOneWidget);
    expect(find.text('Retry'), findsOneWidget);
    expect(tester.widget<FilledButton>(find.byKey(const Key('review-confirm'))).onPressed, isNull);
    for (final label in ['Correct', 'Dismiss', 'Add note']) {
      final button = find.ancestor(of: find.text(label),
        matching: find.byWidgetPredicate((widget) => widget is ButtonStyleButton));
      expect(tester.widget<ButtonStyleButton>(button).onPressed, isNull);
    }

    // A second tap must not turn a successful save with a failed GET into a duplicate POST.
    await tester.tap(find.byKey(const Key('review-confirm')));
    await tester.pumpAndSettle();
    expect(reviewPosts(backend), hasLength(1));

    backend.failNextLoad = false;
    await tester.tap(find.text('Retry'));
    await tester.pumpAndSettle();

    expect(find.text('Retry'), findsNothing);
    expect(find.text('Confirmed by you'), findsWidgets);
    expect(tester.widget<FilledButton>(find.byKey(const Key('review-confirm'))).onPressed, isNotNull);
    expect(reviewPosts(backend), hasLength(1));
    expect(backend.requests.where((request) => request.url.path == '/comparisons/c1/opened'), hasLength(1));
    expect(tester.takeException(), isNull);
  });
}
