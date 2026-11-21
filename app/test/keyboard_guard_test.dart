// The iOS 26 keyboard that comes back after an app switch with no field focused is hidden
// (flutter/flutter#189051). Widget test with simulated lifecycle and keyboard inset; the real
// keyboard is not exercised, so this is not device evidence.
import 'package:changelens/design/keyboard_guard.dart';
import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('a keyboard restored after a resume is hidden only when no field has focus', (tester) async {
    addTearDown(tester.view.reset);
    final focus = FocusNode();
    addTearDown(focus.dispose);
    await tester.pumpWidget(MaterialApp(
      builder: (context, child) => KeyboardGuard(child: child!),
      home: Scaffold(body: TextField(focusNode: focus))));

    int hides() => tester.testTextInput.log.where((call) => call.method == 'TextInput.hide').length;

    Future<void> leave() async {
      for (final s in [AppLifecycleState.inactive, AppLifecycleState.hidden, AppLifecycleState.paused]) {
        tester.binding.handleAppLifecycleStateChanged(s);
      }
      tester.view.viewInsets = FakeViewPadding.zero;
      await tester.pump();
    }

    Future<void> comeBack({required bool insetFirst}) async {
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.hidden);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
      if (insetFirst) tester.view.viewInsets = const FakeViewPadding(bottom: 900);
      tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
      if (!insetFirst) tester.view.viewInsets = const FakeViewPadding(bottom: 900);
      await tester.pump();
    }

    // A focused field keeps its keyboard across the switch.
    focus.requestFocus();
    await tester.pump();
    await leave();
    tester.testTextInput.log.clear();
    await comeBack(insetFirst: true);
    expect(hides(), 0);

    // No field focused, the keyboard is back: hidden, whether its inset arrives before or after resume.
    for (final insetFirst in [true, false]) {
      focus.unfocus();
      await tester.pump();
      await leave();
      tester.testTextInput.log.clear();
      await comeBack(insetFirst: insetFirst);
      expect(hides(), greaterThanOrEqualTo(1), reason: 'insetFirst=$insetFirst');
    }

    // Away from a resume, the guard leaves the keyboard alone.
    await leave();
    tester.testTextInput.log.clear();
    tester.view.viewInsets = const FakeViewPadding(bottom: 900);
    await tester.pump();
    expect(hides(), 0);
  }, variant: TargetPlatformVariant.only(TargetPlatform.iOS));

  testWidgets('on Android the guard does nothing', (tester) async {
    addTearDown(tester.view.reset);
    await tester.pumpWidget(MaterialApp(
      builder: (context, child) => KeyboardGuard(child: child!), home: const Scaffold()));
    tester.testTextInput.log.clear();
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.inactive);
    tester.view.viewInsets = const FakeViewPadding(bottom: 900);
    tester.binding.handleAppLifecycleStateChanged(AppLifecycleState.resumed);
    await tester.pump();
    expect(tester.testTextInput.log.where((call) => call.method == 'TextInput.hide'), isEmpty);
  }, variant: TargetPlatformVariant.only(TargetPlatform.android));
}
