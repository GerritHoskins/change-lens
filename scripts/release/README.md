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

After inspection, validate the receipt against the retained artifact:

```text
python scripts/release/check_acceptance.py --platform android --artifact <release.apk> --receipt <receipt.json>
python scripts/release/check_acceptance.py --platform ios --artifact <release.ipa> --receipt <receipt.json>
```

`--commit` selects the artifact's source commit when it differs from current HEAD. Rebuilding changes
the artifact hash and requires a matching receipt. Keep the inspected artifact for any later upload.
