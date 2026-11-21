// Closes an iOS keyboard that no field owns.
//
// From iOS 26, when the app leaves the foreground while a field has focus (an app switch, or a system
// sheet over the app: the PDF picker, a sign-in sheet), UIKit gives the keyboard back on return. Flutter
// was only told that the field lost focus, so no field is focused, the keyboard is up, and nothing in
// the app can close it: it stays over Projects and every screen after it (flutter/flutter#189051; the
// engine fix is not in this stable release). This is what the iPhone showed on 2026-11-21.
//
// For two seconds after a resume, a keyboard that appears while no text field has focus is hidden. At
// any other time the fields decide about the keyboard themselves.
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter/widgets.dart';

class KeyboardGuard extends StatefulWidget {
  const KeyboardGuard({super.key, required this.child});

  /// How long after a resume a keyboard without a focused field is taken to be the restored one.
  static const window = Duration(seconds: 2);

  final Widget child;

  @override
  State<KeyboardGuard> createState() => _KeyboardGuardState();
}

class _KeyboardGuardState extends State<KeyboardGuard> with WidgetsBindingObserver {
  final _sinceResume = Stopwatch();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    super.dispose();
  }

  bool get _watching => _sinceResume.isRunning && _sinceResume.elapsed < KeyboardGuard.window;

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    _sinceResume..stop()..reset();
    if (state != AppLifecycleState.resumed || defaultTargetPlatform != TargetPlatform.iOS) return;
    _sinceResume.start();
    _hideIfUnowned();
  }

  /// The keyboard's inset can arrive just before or just after the resume.
  @override
  void didChangeMetrics() {
    if (_watching) _hideIfUnowned();
  }

  void _hideIfUnowned() {
    if (!mounted || View.of(context).viewInsets.bottom <= 0) return;
    final owned = FocusManager.instance.primaryFocus?.context?.findAncestorStateOfType<EditableTextState>() != null;
    if (!owned) SystemChannels.textInput.invokeMethod<void>('TextInput.hide');
  }

  @override
  Widget build(BuildContext context) => widget.child;
}
