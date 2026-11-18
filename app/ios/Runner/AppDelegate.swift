import Flutter
import Security
import UIKit

@main
@objc class AppDelegate: FlutterAppDelegate, FlutterImplicitEngineDelegate {
  override func application(
    _ application: UIApplication,
    didFinishLaunchingWithOptions launchOptions: [UIApplication.LaunchOptionsKey: Any]?
  ) -> Bool {
    // Before the engine starts, so no Dart code reads a session an earlier install left (03a P10).
    KeychainGuard.clearLeftoversOnFirstLaunch(application)
    return super.application(application, didFinishLaunchingWithOptions: launchOptions)
  }

  func didInitializeImplicitFlutterEngine(_ engineBridge: FlutterImplicitEngineBridge) {
    GeneratedPluginRegistrant.register(with: engineBridge.pluginRegistry)
    KeychainGuard.register(with: engineBridge.applicationRegistrar.messenger())
  }
}

/// Keychain housekeeping (task L29; 03a P10, SA-11).
enum KeychainGuard {
  /// An empty file in Application Support. Not UserDefaults: that is a required-reason API, and the
  /// app has no privacy manifest of its own to declare it in.
  private static var installedMarker: URL? {
    FileManager.default.urls(for: .applicationSupportDirectory, in: .userDomainMask).first?
      .appendingPathComponent("installed.marker")
  }

  /// iOS keeps an app's Keychain items when the app is deleted, but it deletes the app's files.
  /// A missing marker therefore means the first launch after an install, and whatever the Keychain
  /// holds then is left from an earlier install.
  ///
  /// A launch while protected data is unavailable decides nothing, so a launch before the first
  /// unlock never deletes a valid session; the next launch decides.
  static func clearLeftoversOnFirstLaunch(_ application: UIApplication) {
    let files = FileManager.default
    guard let marker = installedMarker else { return }
    if files.fileExists(atPath: marker.path) { return }
    guard application.isProtectedDataAvailable else { return }

    let itemClasses = [
      kSecClassGenericPassword, kSecClassInternetPassword, kSecClassCertificate, kSecClassKey,
      kSecClassIdentity,
    ]
    var cleared = true
    for itemClass in itemClasses {
      let query: [String: Any] = [
        kSecClass as String: itemClass,
        kSecAttrSynchronizable as String: kSecAttrSynchronizableAny,
      ]
      let status = SecItemDelete(query as CFDictionary)
      if status != errSecSuccess && status != errSecItemNotFound { cleared = false }
    }
    // A failed delete leaves the marker unwritten, so the next launch tries again.
    guard cleared else { return }
    try? files.createDirectory(
      at: marker.deletingLastPathComponent(), withIntermediateDirectories: true, attributes: nil)
    _ = files.createFile(atPath: marker.path, contents: nil, attributes: nil)
  }

  static func register(with messenger: FlutterBinaryMessenger) {
    let channel = FlutterMethodChannel(name: "changelens/keychain", binaryMessenger: messenger)
    channel.setMethodCallHandler { call, result in
      if call.method == "protection" {
        result(protection())
      } else {
        result(FlutterMethodNotImplemented)
      }
    }
  }

  /// The protection class and the sync setting iOS reports for every item the app stores.
  /// Never a value and never a key name.
  private static func protection() -> Any {
    let query: [String: Any] = [
      kSecClass as String: kSecClassGenericPassword,
      kSecAttrSynchronizable as String: kSecAttrSynchronizableAny,
      kSecMatchLimit as String: kSecMatchLimitAll,
      kSecReturnAttributes as String: true,
    ]
    var found: CFTypeRef?
    let status = SecItemCopyMatching(query as CFDictionary, &found)
    if status == errSecItemNotFound { return [[String: Any]]() }
    guard status == errSecSuccess, let items = found as? [[String: Any]] else {
      return FlutterError(code: "keychain", message: "Keychain query failed (\(status))", details: nil)
    }
    return items.map { item -> [String: Any] in
      let synchronizable = (item[kSecAttrSynchronizable as String] as? NSNumber)?.boolValue ?? false
      return [
        "accessible": accessibleName(item[kSecAttrAccessible as String] as? String),
        "synchronizable": synchronizable,
      ]
    }
  }

  private static func accessibleName(_ value: String?) -> String {
    let names: [(CFString, String)] = [
      (kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly, "after_first_unlock_this_device"),
      (kSecAttrAccessibleAfterFirstUnlock, "after_first_unlock"),
      (kSecAttrAccessibleWhenUnlockedThisDeviceOnly, "when_unlocked_this_device"),
      (kSecAttrAccessibleWhenUnlocked, "when_unlocked"),
      (kSecAttrAccessibleWhenPasscodeSetThisDeviceOnly, "when_passcode_set_this_device"),
    ]
    for (constant, name) in names where (constant as String) == value {
      return name
    }
    return "other"
  }
}
