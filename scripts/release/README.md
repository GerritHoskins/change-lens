# Real-app release preparation (I-17 / O-18)

These tools prepare the real app, `dev.changelens.app`. They do not verify native behavior by
themselves. The D-15 PoC is a different application and cannot satisfy these checks.

## Configuration and signing

Run `python scripts/release/check_config.py` and
`python -m unittest discover -s scripts/release -p "test_*.py"` offline.

Android release tasks require `CM_KEYSTORE_PATH`, `CM_KEYSTORE_PASSWORD`, `CM_KEY_ALIAS`, and
`CM_KEY_PASSWORD` in the process environment. The keystore must exist outside source control;
keep passwords in the local secret manager or Codemagic signing identities. No `key.properties`
or development signing fallback is used. Debug builds do not need release credentials.
Codemagic's manual `app-android-release` uses the externally configured identity
`changelens_release` and produces a signed APK and AAB.

The manual `ios-testflight` workflow builds the real app using App Store signing profiles for
`dev.changelens.app` and the `ChangeLens App Store Connect` integration. `poc-ios-testflight`
preserves the separate PoC build. These are artifact-preparation workflows: **none publishes**.
Signing identities, integration access, and a physical-device run are still required.

Both store workflows build a **signed-in** app: they pass the Logto native app ID (`logto_app` in
`codemagic.yaml`, a public identifier) as `--dart-define=CHANGELENS_LOGTO_APP_ID` to every
`flutter build` and stop when it is empty. Without that define the app is a development build with
no sign-in and the developer settings in the menu; `check_config.py` fails a store workflow that
could produce one. Only `ios-device-check` may be built without it, for a check against a local backend.

Configuration follows [Codemagic Android signing](https://docs.codemagic.io/yaml-code-signing/signing-android/),
[iOS signing](https://docs.codemagic.io/yaml-code-signing/signing-ios/), and
[Android Gradle signing](https://developer.android.com/build/building-cmdline).

## Inspect the exact signed release

I-17 and O-18 require `docs/03a-pipeline-logic.md` P10 DEVICE_STORAGE and CLIENT_TELEMETRY checks
on **both physical platforms**, after the final import and account implementations are present.
Use only synthetic document markers; retain content-free observations outside Git. Keep signing
credentials, device identifiers, customer documents, and captured tokens out of receipts and logs.

Record a JSON receipt for each platform with `schema_version: 1`, `app_id: "dev.changelens.app"`,
`platform: "android"` or `"ios"`, `build_mode: "release"`, `physical_device: true`, the full source
`commit`, the exact file's `artifact_sha256`, an ISO-8601 `checked_at` with timezone, and `checks`.
Each check is an object with `result: "pass"` and a short, content-free `evidence` description.
Missing or pending observations fail acceptance; do not fill passes from source inspection.

| Check ID | Required observation on the signed build |
|---|---|
| `signed_release_identity` | Inspect bundle/application ID and release signing identity; no debug signature. |
| `paste_pdf_compare_review` | Paste and PDF import, explicit order/scope, compare, report and review work against the intended authenticated backend. |
| `evidence_and_text_fallback` | Evidence highlights match; fallback is clear; review and client approval stay separate. |
| `import_cleanup_all_outcomes` | Success, failure and cancellation leave no document files in app/picker/hand-off storage. |
| `restart_cleanup` | Interrupted imports followed by relaunch remove document leftovers. |
| `tokens_secure_and_logout` | Tokens use Keychain/Keystore only; logout clears them; no document persistence. |
| `privacy_cover` | Background/app-switcher snapshots conceal document content. |
| `content_free_telemetry` | HTTP bodies/headers, document markers, token values, exception messages and breadcrumbs do not enter release logs, crash reports or analytics. |
| `inventory_and_store_declarations` | Actual stores/processors match the data inventory, privacy policy and store declarations. |
| `backup_and_transfer_excluded` (Android) | Merged release manifest and a backup/transfer check exclude app data. |
| `keystore_backed_tokens` (Android) | Inspect secure storage and verify Keystore-backed keys on the device. |
| `keychain_this_device_only` (iOS) | Inspect effective accessibility; after first unlock, this device only, no sync. |
| `fresh_install_keychain_cleanup` (iOS) | Reinstall clears tokens surviving the previous installation. |
| `handoff_file_protection` (iOS) | Share-extension hand-off files have complete file protection and are purged. |

For an AAB, inspect the package installed from that same bundle; for TestFlight, use the same
uploaded IPA/build number and retain its hash. Upload to an owner-only testing channel, if needed
to inspect a build, is a separate authorized action. Acceptance gates distribution to external
testers; this script cannot replace the backend security/quality gates or grant publication approval.

## Observing the iOS-only checks

Worked out on 2026-11-18 from the app source, the pinned `flutter_secure_storage` plugin source (11.2.0,
darwin 0.4.3) and Apple's developer forums. None of the three can be recorded as a pass today.

| Check | Status | How to observe it on the signed build |
|---|---|---|
| `fresh_install_keychain_cleanup` | Expected to fail today: the code is missing (task L29) | Sign in, delete the app, install the same IPA again and open it. Pass: the sign-in screen. Fail: you are still signed in. |
| `keychain_this_device_only` | Needs a readback in the app (task L29) | The app asks the Keychain for the attributes of its own items and shows them. Pass: every item reports "after first unlock, this device only" and "not synchronised". |
| `handoff_file_protection` | Does not apply at launch | The app has no share extension and no app group; both come with I-16. The owner decides whether this check leaves the iOS launch set until I-16 or keeps blocking. |

Why these methods:

- iOS keeps an app's Keychain items when the app is deleted. Apple's engineers confirm it in the developer
  forums ([thread 72271](https://developer.apple.com/forums/thread/72271), still so with iOS 17.5 in June
  2024) and call it undocumented behaviour. Neither the app nor the plugin clears the items, although 03a P10
  (`ON_APP_START`) asks for it. So an app that was signed in when it was deleted should start signed in
  after a reinstall. That is read from the code; `docs/device-sitting-1.md` asks for the observation.
- The app sets `first_unlock_this_device` (`app/lib/services.dart`), which the plugin maps to
  `kSecAttrAccessibleAfterFirstUnlockThisDeviceOnly`, with `synchronizable` off by default. That is the
  intent, not the observation: the plugin updates an existing item without changing its protection, and it
  reads items of every protection level. An item keeps the class it was first written with.
- From outside the app there is no dependable way on an unmodified phone. A transfer to another phone is
  not conclusive: a report on Apple's forums says "this device only" items survived a direct transfer
  ([thread 802526](https://developer.apple.com/forums/thread/802526), September 2025, unexplained). Whether
  a release build's log lines show on a connected Mac is not settled in the sources found, so the method
  doesn't rely on it. The app has to read the attributes back itself.
- The readback must be part of the inspected artefact, because the receipt binds to its hash.

After inspection, validate the receipt against the retained artifact:

```text
python scripts/release/check_acceptance.py --platform android --artifact <release.apk> --receipt <receipt.json>
python scripts/release/check_acceptance.py --platform ios --artifact <release.ipa> --receipt <receipt.json>
```

`--commit` selects the artifact's source commit when it differs from current HEAD. Rebuilding changes
the artifact hash and requires a matching receipt. Keep the inspected artifact for any later upload.
