// Task L29: the Keychain readback and its line in Settings. The native side (AppDelegate.swift) is
// faked here. The cleanup on a fresh install has no Dart part; it is checked on the iPhone.
import 'package:changelens/l10n/app_localizations.dart';
import 'package:changelens/screens/settings_screen.dart';
import 'package:changelens/services.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

import 'account_screens_test.dart' show pumpGate;
import 'session_settings_test.dart' show pumpLocalized;

const channel = MethodChannel('changelens/keychain');
const intended = {'accessible': 'after_first_unlock_this_device', 'synchronizable': false};

/// Runs [readKeychainProtection] as on an iPhone, with [reply] as the native answer.
Future<KeychainProtection?> readOnIos(Future<Object?> Function(MethodCall call) reply) async {
  final messenger = TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
  messenger.setMockMethodCallHandler(channel, reply);
  debugDefaultTargetPlatformOverride = TargetPlatform.iOS;
  try {
    return await readKeychainProtection();
  } finally {
    debugDefaultTargetPlatformOverride = null;
    messenger.setMockMethodCallHandler(channel, null);
  }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('Keychain readback', () {
    test('every item this device only and not synchronised: as intended', () async {
      final calls = <String>[];
      final found = await readOnIos((call) async {
        calls.add(call.method);
        return [intended, intended];
      });
      expect(calls, ['protection']);
      expect(found!.asIntended, isTrue);
      expect(found.classes, {KeychainProtection.intended});
    });

    test('one item in another class: not as intended, and the classes are named', () async {
      final found = await readOnIos((_) async => [
        intended,
        {'accessible': 'after_first_unlock', 'synchronizable': false},
      ]);
      expect(found!.asIntended, isFalse);
      expect(found.found, 'after_first_unlock, after_first_unlock_this_device');
    });

    test('a synchronised item: not as intended', () async {
      final found = await readOnIos((_) async => [
        {'accessible': 'after_first_unlock_this_device', 'synchronizable': true},
      ]);
      expect(found!.asIntended, isFalse);
      expect(found.found, 'after_first_unlock_this_device, synchronised');
    });

    test('nothing stored, a native error or no native side: nothing is claimed', () async {
      expect(await readOnIos((_) async => <Object?>[]), isNull);
      expect(await readOnIos((_) async => throw PlatformException(code: 'keychain')), isNull);
      expect(await readOnIos((_) async => throw MissingPluginException()), isNull);
    });

    test('off iOS the native side is not asked', () async {
      final messenger = TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;
      var asked = false;
      messenger.setMockMethodCallHandler(channel, (_) async {
        asked = true;
        return [intended];
      });
      addTearDown(() => messenger.setMockMethodCallHandler(channel, null));
      expect(await readKeychainProtection(), isNull);
      expect(asked, isFalse);
    });
  });

  group('Settings line', () {
    Future<void> pumpSettings(WidgetTester tester, KeychainProtection? found,
        {Locale locale = const Locale('en')}) async {
      final h = await pumpGate(tester, stored: true, onboarding: {'completed': true, 'step': null});
      await pumpLocalized(tester,
        SettingsScreen(session: h.session, keychainProtection: () async => found), locale: locale);
    }

    for (final locale in ['en', 'de']) {
      testWidgets('as intended: the plain sentence, above Sign out ($locale)', (tester) async {
        await pumpSettings(tester, const KeychainProtection({KeychainProtection.intended}, synchronised: false),
          locale: Locale(locale));
        final l = lookupAppLocalizations(Locale(locale));
        final line = find.byKey(const Key('keychain-protection'));
        expect(tester.widget<Text>(line).data, l.settingsKeychainOk);
        expect(tester.getBottomLeft(line).dy, lessThan(tester.getTopLeft(find.byKey(const Key('sign-out'))).dy));
      });
    }

    testWidgets('a difference is said, with what was found', (tester) async {
      await pumpSettings(tester, const KeychainProtection({'after_first_unlock'}, synchronised: true));
      expect(tester.widget<Text>(find.byKey(const Key('keychain-protection'))).data,
        "The sign-in stored on this iPhone isn't protected as intended (after_first_unlock, synchronised).");
    });

    testWidgets('no readback: no line', (tester) async {
      await pumpSettings(tester, null);
      expect(find.byKey(const Key('keychain-protection')), findsNothing);
      expect(find.byKey(const Key('sign-out')), findsOneWidget);
    });
  });
}
