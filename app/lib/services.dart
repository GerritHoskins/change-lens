// App-wide services: dev connection settings, the API client and document import.
// Document bytes stay in memory; picker temp copies are purged after every import and on start (AC-25).
import 'dart:typed_data';

import 'package:file_picker/file_picker.dart';
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

/// The PDF picker, behind an interface so tests can check that temp copies are purged.
abstract class DocumentPicker {
  Future<PickedDocument?> pickPdf();

  /// Deletes the picker's cached copies of picked files.
  Future<void> purge();
}

class PlatformDocumentPicker implements DocumentPicker {
  @override
  Future<PickedDocument?> pickPdf() async {
    final file = await FilePicker.pickFile(type: FileType.custom, allowedExtensions: ['pdf']);
    if (file == null) return null;
    return PickedDocument(file.name, await file.xFile.readAsBytes());
  }

  @override
  Future<void> purge() => FilePicker.clearTemporaryFiles();
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

  bool get configured => baseUrl.isNotEmpty && token.isNotEmpty;

  Api get api => _api ??= apiFactory(baseUrl, token);

  Future<void> load() async {
    baseUrl = await store.read(_baseKey) ?? '';
    token = await store.read(_tokenKey) ?? '';
    _api = null;
    notifyListeners();
  }

  Future<void> save(String newBase, String newToken) async {
    await store.write(_baseKey, newBase.trim());
    await store.write(_tokenKey, newToken.trim());
    await load();
  }

  /// Uploads a picked PDF, then purges the picker cache whether or not the upload worked (AC-25).
  Future<Version?> importPdf(String projectId, String label) async {
    final doc = await picker.pickPdf();
    if (doc == null) {
      await picker.purge();
      return null;
    }
    try {
      return await api.upload(projectId, label, bytes: doc.bytes, filename: doc.name);
    } finally {
      await picker.purge();
    }
  }

  Future<Version> importText(String projectId, String label, String text) =>
      api.upload(projectId, label, text: text);
}

/// Makes [Services] available to the widget tree.
class ServicesScope extends InheritedNotifier<Services> {
  const ServicesScope({super.key, required Services services, required super.child}) : super(notifier: services);

  static Services of(BuildContext context) =>
      context.dependOnInheritedWidgetOfExactType<ServicesScope>()!.notifier!;
}
