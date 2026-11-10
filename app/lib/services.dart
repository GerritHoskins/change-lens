// App-wide services: dev connection settings, the API client and document import.
// Document bytes stay in memory; picker cleanup is requested after import and on start (AC-25).
import 'package:file_picker/file_picker.dart';
import 'package:flutter/foundation.dart';
import 'package:flutter/services.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_secure_storage/flutter_secure_storage.dart';

import 'api.dart';

/// Key-value store for the dev connection. Production: Keychain / Keystore only (03a P10).
abstract class SettingsStore {
  Future<String?> read(String key);
  Future<void> write(String key, String value);
}

class SecureSettingsStore implements SettingsStore {
  // iOS: this device only, after first unlock, no iCloud sync (SA-11).
  static const _storage = FlutterSecureStorage(
      iOptions: IOSOptions(accessibility: KeychainAccessibility.first_unlock_this_device));

  @override
  Future<String?> read(String key) => _storage.read(key: key);

  @override
  Future<void> write(String key, String value) => _storage.write(key: key, value: value);
}

class PickedDocument {
  PickedDocument(this.name, this.bytes);

  final String name;
  final Uint8List bytes;
}

/// The PDF picker, behind an interface so tests can check that cleanup is requested.
abstract class DocumentPicker {
  Future<PickedDocument?> pickPdf();

  /// Requests deletion of picker copies and discards available recovery metadata.
  Future<void> purge();
}

class PlatformDocumentPicker implements DocumentPicker {
  static const _androidPicker = MethodChannel('miguelruivo.flutter.plugins.filepicker');

  @override
  Future<PickedDocument?> pickPdf() async {
    final file = await FilePicker.pickFile(type: FileType.custom, allowedExtensions: ['pdf']);
    if (file == null) return null;
    return PickedDocument(file.name, await file.xFile.readAsBytes());
  }

  @override
  Future<void> purge() async {
    try {
      if (!kIsWeb && defaultTargetPlatform == TargetPlatform.android) {
        // FilePicker has no cross-platform recovery API. The pinned Android plugin's
        // retrieveLostData wrapper reconstructs file handles from saved metadata; drain
        // its native one-shot result directly instead, without parsing or opening them.
        // It also waits for an already-running restore before we clear its file copies.
        await _androidPicker.invokeMethod<Object?>('retrieveLostData');
      }
    } finally {
      // Native plugins discard their cleanup result: this attempts cleanup, not proof of
      // erasure. A restore arriving after this call still needs device lifecycle testing.
      await FilePicker.clearTemporaryFiles();
    }
  }
}

class Services extends ChangeNotifier {
  Services(this.store, this.picker, {this.apiFactory = Api.new});

  static const _baseKey = 'api_base_url', _tokenKey = 'dev_token';

  final SettingsStore store;
  final DocumentPicker picker;
  final Api Function(String baseUrl, String token) apiFactory;
  String baseUrl = '';
  String token = '';
  Api? _api;
  ComparisonSubmission? pendingComparison;

  bool get configured => baseUrl.isNotEmpty && token.isNotEmpty;

  Api get api => _api ??= apiFactory(baseUrl, token);

  Future<void> load() async {
    final newBase = await store.read(_baseKey) ?? '';
    final newToken = await store.read(_tokenKey) ?? '';
    if (newBase != baseUrl || newToken != token) pendingComparison = null;
    baseUrl = newBase;
    token = newToken;
    _api = null;
    notifyListeners();
  }

  Future<void> save(String newBase, String newToken) async {
    await store.write(_baseKey, newBase.trim());
    await store.write(_tokenKey, newToken.trim());
    await load();
  }

  /// Attempts picker cleanup after selecting, reading or uploading a PDF, including failures.
  Future<Version?> importPdf(String projectId, String label) async {
    try {
      final doc = await picker.pickPdf();
      if (doc == null) return null;
      return await api.upload(projectId, label, bytes: doc.bytes, filename: doc.name);
    } finally {
      await picker.purge();
    }
  }

  Future<Version> importText(String projectId, String label, String text) =>
      api.upload(projectId, label, text: text);
}

/// In-memory recovery only; no source documents or submission bodies go to device storage.
class ComparisonSubmission {
  ComparisonSubmission(this.project, this.earlier, this.later, this.scope) : key = comparisonRequestKey();
  final Project project;
  final ComparisonInput earlier, later;
  final Scope scope;
  final String key;
}

/// Makes [Services] available to the widget tree.
class ServicesScope extends InheritedNotifier<Services> {
  const ServicesScope({super.key, required Services services, required super.child}) : super(notifier: services);

  static Services of(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<ServicesScope>()!.notifier!;
}
