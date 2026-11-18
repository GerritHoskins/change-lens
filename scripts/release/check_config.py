"""Offline source checks for the real app's release configuration; no signing or device claim."""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
ANDROID = "{http://schemas.android.com/apk/res/android}"


def workflow(text: str, name: str) -> str:
    """Read one top-level workflow from this repository's two-space YAML layout."""
    match = re.search(r"^  " + re.escape(name) + r":\s*\n(.*?)(?=^  [\w-]+:\s*$|\Z)",
                      text.split("workflows:", 1)[-1], re.M | re.S)
    return match.group(1) if match else ""


def check(root: Path) -> list[str]:
    errors = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    manifest = ET.parse(root / "app/android/app/src/main/AndroidManifest.xml").getroot()
    permissions = {item.get(ANDROID + "name") for item in manifest.findall("uses-permission")}
    require("android.permission.INTERNET" in permissions, "main manifest must permit network access")
    application = manifest.find("application")
    require(application is not None and application.get(ANDROID + "allowBackup") == "false",
            "main manifest must disable app backup")
    require(application is not None and application.get(ANDROID + "dataExtractionRules") ==
            "@xml/data_extraction_rules", "main manifest must bind data-extraction exclusions")
    rules = ET.parse(root / "app/android/app/src/main/res/xml/data_extraction_rules.xml").getroot()
    for target in ("cloud-backup", "device-transfer"):
        excluded = {e.get("domain") for e in rules.findall(target + "/exclude") if e.get("path") == "."}
        require({"root", "file", "database", "sharedpref", "external"} <= excluded,
                target + " must exclude every app data domain")

    gradle = (root / "app/android/app/build.gradle.kts").read_text(encoding="utf-8")
    require('applicationId = "dev.changelens.app"' in gradle, "Android application ID must be the real app")
    require('signingConfig = signingConfigs.getByName("release")' in gradle,
            "release must use the release signing configuration")
    require('signingConfig = signingConfigs.getByName("debug")' not in gradle,
            "debug signing must not be a release fallback")
    require('dependsOn(validateReleaseSigning)' in gradle and 'it.name == "preReleaseBuild"' in gradle,
            "release build must require external signing validation")
    for variable in ("CM_KEYSTORE_PATH", "CM_KEYSTORE_PASSWORD", "CM_KEY_ALIAS", "CM_KEY_PASSWORD"):
        require(variable in gradle, "release signing input missing: " + variable)

    config = (root / "codemagic.yaml").read_text(encoding="utf-8")
    for name in ("app-android-release", "ios-testflight", "ios-device-check"):
        block = workflow(config, name)
        require("<<: *real_app" in block, name + " must build app/, not the PoC")
        require("- *release_config" in block, name + " must run the offline release hook")
        require("triggering:" not in block and "*on_" not in block, name + " must remain manual")
        require("publishing:" not in block, name + " must not publish before artifact acceptance")
    ios = workflow(config, "ios-testflight")
    require("bundle_identifier: dev.changelens.app\n" in ios, "TestFlight must sign the real bundle ID")
    require("$CM_BUILD_DIR/app/build/ios/ipa/*.ipa" in ios, "TestFlight must export the real-app IPA")
    require("--project ios/Runner.xcodeproj" in ios, "signing profiles must target the current app project")
    device = workflow(config, "ios-device-check")
    require("distribution_type: ad_hoc\n" in device and "bundle_identifier: dev.changelens.app\n" in device,
            "device checks must use ad hoc signing for the real bundle ID")
    # The device build shows the consent screen, so the owner can check it on the phone (L13).
    require("--dart-define=CHANGELENS_CONSENT=${CHANGELENS_CONSENT:-true}" in device,
            "device checks must build with the consent screen on")
    android = workflow(config, "app-android-release")
    require("android_signing:" in android and "changelens_release" in android,
            "Android release must request its external signing identity")
    require("flutter build appbundle --release" in android, "Android release must produce a signed bundle")
    require("bundle_identifier: dev.changelens.changelensPoc" in workflow(config, "poc-ios-testflight"),
            "PoC signing must stay in its separately named workflow")

    # Without the Logto app ID the app is a development build: no sign-in, and the developer settings
    # (API address, dev token) are in the menu (app/lib/auth/logto.dart). A store build must never be one.
    require(re.search(r"^  logto_app: &logto_app\n    CHANGELENS_LOGTO_APP_ID: [A-Za-z0-9]+\n", config, re.M)
            is not None, "the sign-in app ID must be defined once and must not be empty")
    define = '--dart-define=CHANGELENS_LOGTO_APP_ID="$CHANGELENS_LOGTO_APP_ID"'
    guard = ': "${CHANGELENS_LOGTO_APP_ID:?'
    for name in ("app-android-release", "ios-testflight"):
        block = workflow(config, name)
        builds = [line for line in block.splitlines() if "flutter build " in line]
        require("      vars: *logto_app\n" in block, name + " must set the sign-in app ID")
        require(bool(builds) and all(define in line for line in builds),
                name + " must pass the sign-in app ID to every flutter build")
        require(-1 < block.find(guard) < block.find("flutter build "),
                name + " must stop before building when the sign-in app ID is empty")
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    try:
        errors = check(args.root)
    except (OSError, ET.ParseError, ValueError):
        errors = ["release configuration could not be read"]
    for error in errors:
        print("FAIL " + error)
    if not errors:
        print("PASS real-app release source configuration (signing and devices not verified)")
    return int(bool(errors))


if __name__ == "__main__":
    sys.exit(main())
