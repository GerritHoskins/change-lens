"""Fail closed unless release-device evidence identifies this exact real-app artifact.

This validates an operator's receipt, not the truth of its manual observations. It does not
authorize publication, run services, read credentials, or mark a milestone complete.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
CHECKS = {
    "signed_release_identity", "paste_pdf_compare_review", "evidence_and_text_fallback",
    "import_cleanup_all_outcomes", "restart_cleanup", "tokens_secure_and_logout",
    "privacy_cover", "content_free_telemetry", "inventory_and_store_declarations",
}
PLATFORM_CHECKS = {
    "android": {"backup_and_transfer_excluded", "keystore_backed_tokens"},
    "ios": {"keychain_this_device_only", "fresh_install_keychain_cleanup", "handoff_file_protection"},
}


def digest(path: Path) -> str:
    sha = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            sha.update(chunk)
    return sha.hexdigest()


def validate(receipt: dict, artifact: Path, platform: str, commit: str) -> list[str]:
    errors = []

    def require(condition: bool, message: str) -> None:
        if not condition:
            errors.append(message)

    require(type(receipt.get("schema_version")) is int and receipt["schema_version"] == 1,
            "unsupported acceptance receipt schema")
    require(receipt.get("app_id") == "dev.changelens.app", "receipt is not for the real app")
    require(receipt.get("platform") == platform, "receipt platform does not match")
    require(receipt.get("build_mode") == "release", "a debug or PoC build cannot satisfy release acceptance")
    require(receipt.get("physical_device") is True, "physical-device inspection is required")
    require(bool(re.fullmatch(r"[0-9a-f]{40}", commit)) and receipt.get("commit") == commit,
            "receipt must bind to the requested source commit")
    suffixes = {"android": {".apk", ".aab"}, "ios": {".ipa"}}
    require(artifact.suffix.lower() in suffixes[platform], "artifact type does not match platform")
    require(receipt.get("artifact_sha256") == digest(artifact), "receipt does not match the exact artifact")
    try:
        checked = datetime.fromisoformat(receipt.get("checked_at", "").replace("Z", "+00:00"))
        require(checked.tzinfo is not None and checked <= datetime.now(timezone.utc),
                "inspection time must include timezone and cannot be in the future")
    except (ValueError, TypeError, AttributeError):
        errors.append("inspection time is missing or invalid")
    checks = receipt.get("checks")
    checks = checks if isinstance(checks, dict) else {}
    for key in sorted(CHECKS | PLATFORM_CHECKS[platform]):
        value = checks.get(key)
        valid = (isinstance(value, dict) and value.get("result") == "pass" and
                 isinstance(value.get("evidence"), str) and bool(value["evidence"].strip()))
        require(valid, "missing passing device evidence: " + key)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--artifact", type=Path, required=True)
    parser.add_argument("--platform", choices=sorted(PLATFORM_CHECKS), required=True)
    parser.add_argument("--commit", help="Source commit of the artifact; defaults to this checkout's HEAD")
    args = parser.parse_args()
    try:
        commit = args.commit or subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True, stderr=subprocess.DEVNULL).strip()
        receipt = json.loads(args.receipt.read_text(encoding="utf-8"))
        if not isinstance(receipt, dict):
            raise ValueError("invalid receipt")
        errors = validate(receipt, args.artifact, args.platform, commit)
    except (OSError, ValueError, subprocess.CalledProcessError):
        errors = ["receipt, artifact, or commit could not be read; acceptance is unverified"]
    for error in errors:
        print("FAIL " + error)
    if not errors:
        print("PASS real-app artifact acceptance receipt; manual evidence is operator-attested")
    return int(bool(errors))


if __name__ == "__main__":
    sys.exit(main())
