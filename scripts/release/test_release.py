"""Offline release gates: incomplete/wrong-app evidence must never become acceptance."""
from copy import deepcopy
from datetime import datetime, timezone
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

import check_acceptance as acceptance
import check_config


class AcceptanceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.artifact = Path(self.temp.name) / "release.apk"
        self.artifact.write_bytes(b"synthetic artifact, not an installable app")
        self.commit = "a" * 40
        self.receipt = {
            "schema_version": 1, "app_id": "dev.changelens.app", "platform": "android",
            "build_mode": "release", "physical_device": True, "commit": self.commit,
            "artifact_sha256": acceptance.digest(self.artifact),
            "checked_at": datetime.now(timezone.utc).isoformat(),
            "checks": {key: {"result": "pass", "evidence": "Synthetic gate-test observation."}
                       for key in acceptance.CHECKS | acceptance.PLATFORM_CHECKS["android"]},
        }

    def errors(self, receipt=None):
        return acceptance.validate(receipt or self.receipt, self.artifact, "android", self.commit)

    def test_complete_receipt_matches_exact_artifact(self):
        self.assertEqual(self.errors(), [])

    def test_each_missing_device_check_fails(self):
        for key in self.receipt["checks"]:
            with self.subTest(key=key):
                receipt = deepcopy(self.receipt)
                del receipt["checks"][key]
                self.assertIn("missing passing device evidence: " + key, self.errors(receipt))

    def test_pending_or_empty_observation_is_not_a_pass(self):
        for value in ({"result": "pending", "evidence": "Not inspected"},
                      {"result": "pass", "evidence": " "}, True):
            with self.subTest(value=value):
                receipt = deepcopy(self.receipt)
                receipt["checks"]["privacy_cover"] = value
                self.assertTrue(self.errors(receipt))

    def test_poc_debug_other_commit_or_simulator_evidence_is_rejected(self):
        for field, value in (("app_id", "dev.changelens.changelensPoc"), ("build_mode", "debug"),
                             ("commit", "b" * 40), ("physical_device", False), ("platform", "ios")):
            with self.subTest(field=field):
                receipt = dict(self.receipt, **{field: value})
                self.assertTrue(self.errors(receipt))

    def test_modified_artifact_invalidates_prior_receipt(self):
        self.artifact.write_bytes(b"rebuilt artifact")
        self.assertIn("receipt does not match the exact artifact", self.errors())

    def test_invalid_or_future_inspection_date_is_rejected(self):
        for date in ("", "not-a-date", "2026-01-01", "2999-01-01T00:00:00Z"):
            with self.subTest(date=date):
                self.assertTrue(self.errors(dict(self.receipt, checked_at=date)))

    def test_cli_fails_closed_without_receipt_and_on_pending_check(self):
        path = Path(self.temp.name) / "receipt.json"
        command = [sys.executable, str(Path(acceptance.__file__)), "--platform", "android",
                   "--artifact", str(self.artifact), "--receipt", str(path), "--commit", self.commit]
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 1)
        self.receipt["checks"]["privacy_cover"]["result"] = "pending"
        path.write_text(json.dumps(self.receipt), encoding="utf-8")
        self.assertEqual(subprocess.run(command, capture_output=True).returncode, 1)

    def test_ios_requires_its_own_device_checks(self):
        self.artifact = self.artifact.with_suffix(".ipa")
        self.artifact.write_bytes(b"synthetic iOS artifact")
        self.receipt.update(platform="ios", artifact_sha256=acceptance.digest(self.artifact))
        errors = acceptance.validate(self.receipt, self.artifact, "ios", self.commit)
        for key in acceptance.PLATFORM_CHECKS["ios"]:
            self.assertIn("missing passing device evidence: " + key, errors)


class ConfigurationTests(unittest.TestCase):
    def test_current_config_has_real_app_release_boundaries(self):
        self.assertEqual(check_config.check(check_config.ROOT), [])

    def test_historical_release_regressions_are_rejected(self):
        files = ("codemagic.yaml", "app/android/app/build.gradle.kts",
                 "app/android/app/src/main/AndroidManifest.xml",
                 "app/android/app/src/main/res/xml/data_extraction_rules.xml")
        mutations = (
            (files[2], '<uses-permission android:name="android.permission.INTERNET" />', ""),
            (files[1], 'signingConfig = signingConfigs.getByName("release")',
             'signingConfig = signingConfigs.getByName("debug")'),
            (files[0], "bundle_identifier: dev.changelens.app\n",
             "bundle_identifier: dev.changelens.changelensPoc\n"),
            (files[0], "name: App signed IPA for TestFlight (prepare only)\n    <<: *real_app",
             "name: App signed IPA for TestFlight (prepare only)\n    <<: *app"),
        )
        for relative, before, after in mutations:
            with self.subTest(relative=relative, before=before), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                for source in files:
                    target = root / source
                    target.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(check_config.ROOT / source, target)
                target = root / relative
                original = target.read_text(encoding="utf-8")
                self.assertIn(before, original)
                target.write_text(original.replace(before, after), encoding="utf-8")
                self.assertTrue(check_config.check(root))


if __name__ == "__main__":
    unittest.main()
