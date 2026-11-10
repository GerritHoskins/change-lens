// Picker recovery metadata is discarded, never restored as an upload or read from disk.
import 'package:changelens/services.dart';
import 'package:file_picker/file_picker.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter_test/flutter_test.dart';

const channel = MethodChannel('miguelruivo.flutter.plugins.filepicker');

class ChannelPicker extends FilePickerPlatform {
  @override
  Future<void> clearTemporaryFiles() => channel.invokeMethod<void>('clear');
}

class MemorySettings implements SettingsStore {
  @override
  Future<String?> read(String key) async => null;
  @override
  Future<void> write(String key, String value) async {}
}

class InterruptedPicker implements DocumentPicker {
  InterruptedPicker({this.cancelled = false});
  final bool cancelled;
  int purges = 0;
  @override
  Future<PickedDocument?> pickPdf() async {
    if (cancelled) return null;
    throw const FormatException('synthetic picker/read failure');
  }
  @override
  Future<void> purge() async { purges++; }
}

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();
  late FilePickerPlatform previous;
  final messenger = TestDefaultBinaryMessengerBinding.instance.defaultBinaryMessenger;

  setUp(() {
    previous = FilePickerPlatform.instance;
    FilePickerPlatform.instance = ChannelPicker();
    debugDefaultTargetPlatformOverride = TargetPlatform.android;
  });
  tearDown(() {
    FilePickerPlatform.instance = previous;
    debugDefaultTargetPlatformOverride = null;
    messenger.setMockMethodCallHandler(channel, null);
  });

  test('startup purge discards recovered metadata before clearing files and never resumes upload', () async {
    final calls = <String>[];
    Object? savedRecovery = {'files': [{'path': '/nonexistent/synthetic-private.pdf',
      'name': 'synthetic-private.pdf', 'identifier': 'content://synthetic/private', 'size': 42}]};
    messenger.setMockMethodCallHandler(channel, (call) async {
      calls.add(call.method);
      if (call.method == 'retrieveLostData') {
        final result = savedRecovery;
        savedRecovery = null; // the native method's consume-once contract
        return result;
      }
      expect(call.method, 'clear');
      expect(savedRecovery, isNull);
      return null;
    });
    final services = Services(MemorySettings(), PlatformDocumentPicker(),
      apiFactory: (_, _) => throw StateError('recovered data must never reach the API'));
    await services.picker.purge(); // same call used before services.load() at startup
    await services.load();
    expect(services.pendingComparison, isNull);
    expect(calls, ['retrieveLostData', 'clear']);
    await services.picker.purge(); // already-consumed recovery remains harmless
    expect(calls, ['retrieveLostData', 'clear', 'retrieveLostData', 'clear']);
  });

  test('an in-flight native restore drains before cached copies are removed', () async {
    final calls = <String>[];
    messenger.setMockMethodCallHandler(channel, (call) async {
      calls.add(call.method);
      if (call.method == 'retrieveLostData') {
        await Future<void>.delayed(Duration.zero);
        calls.add('restore-finished');
        return {'files': []};
      }
      return null;
    });
    await PlatformDocumentPicker().purge();
    expect(calls, ['retrieveLostData', 'restore-finished', 'clear']);
  });

  test('native recovery error metadata is discarded without parsing it', () async {
    messenger.setMockMethodCallHandler(channel, (call) async => call.method == 'retrieveLostData'
      ? {'errorCode': 'synthetic', 'errorMessage': 'synthetic private file path'} : null);
    await PlatformDocumentPicker().purge();
  });

  test('file cleanup is still attempted if the recovery channel fails', () async {
    final calls = <String>[];
    messenger.setMockMethodCallHandler(channel, (call) async {
      calls.add(call.method);
      if (call.method == 'retrieveLostData') throw PlatformException(code: 'synthetic');
      return null;
    });
    await expectLater(PlatformDocumentPicker().purge(), throwsA(isA<PlatformException>()));
    expect(calls, ['retrieveLostData', 'clear']);
  });

  test('non-Android purge never invokes the Android recovery API', () async {
    debugDefaultTargetPlatformOverride = TargetPlatform.iOS;
    final calls = <String>[];
    messenger.setMockMethodCallHandler(channel, (call) async { calls.add(call.method); return null; });
    await PlatformDocumentPicker().purge();
    expect(calls, ['clear']);
  });

  test('legacy import purges when picking or reading bytes fails', () async {
    final picker = InterruptedPicker();
    final services = Services(MemorySettings(), picker,
      apiFactory: (_, _) => throw StateError('failed pick must never upload'));
    await expectLater(services.importPdf('synthetic-project', 'Synthetic'), throwsFormatException);
    expect(picker.purges, 1);
  });

  test('legacy import purges cancellation once without uploading', () async {
    final picker = InterruptedPicker(cancelled: true);
    final services = Services(MemorySettings(), picker,
      apiFactory: (_, _) => throw StateError('cancelled pick must never upload'));
    expect(await services.importPdf('synthetic-project', 'Synthetic'), isNull);
    expect(picker.purges, 1);
  });
}
