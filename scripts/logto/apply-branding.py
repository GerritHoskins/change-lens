#!/usr/bin/env python3
"""Apply the ChangeLens branding to Logto's hosted sign-in pages (docs/logto-branding-plan.md §4.3-4.5).

The desired state is deploy/ionos/logto/sign-in-experience.json plus the files it names (custom.css,
custom-phrases.<lang>.json). This script only applies that state through the Management API, with the
machine-to-machine app the backend already uses. Nothing is set by hand in the Console: a value set
there (a brand colour, pasted CSS) shows up here as a difference and is overwritten by --apply.

  python scripts/logto/apply-branding.py --check    # no network: the files parse and are well-formed
  python scripts/logto/apply-branding.py            # dry run: what differs on the server; changes nothing
  python scripts/logto/apply-branding.py --apply    # write, then read back and compare

Environment (the names in /etc/changelens/changelens.env):
  CHANGELENS_LOGTO_MANAGEMENT_ENDPOINT   e.g. https://auth.pixeltronic.dev, or http://localhost:3001 (d8-logto)
  CHANGELENS_LOGTO_M2M_APP_ID, CHANGELENS_LOGTO_M2M_APP_SECRET
  CHANGELENS_LOGTO_MANAGEMENT_RESOURCE   optional, default https://default.logto.app/api (Logto OSS)

PUT /api/custom-phrases/<lang> replaces that language's custom phrases as a whole. Stdlib only.
Exit codes: 0 in sync or applied, 1 differences found by a dry run, 2 bad input or a failed request.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

CONFIG = Path(__file__).resolve().parents[2] / "deploy" / "ionos" / "logto" / "sign-in-experience.json"
HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")
# Left to the owner and the lawyer (plan §2 row 5): this script must not set them by accident.
ALLOWED = {"color", "branding", "customCss", "customPhrases"}


class Failure(Exception):
    pass


def load(config: Path, endpoint: str) -> tuple[dict, dict[str, dict]]:
    """The PATCH body for /api/sign-in-exp and the custom phrases per language."""
    raw = json.loads(config.read_text(encoding="utf-8"))
    unknown = set(raw) - ALLOWED
    if unknown:
        raise Failure(f"{config.name}: unexpected keys {sorted(unknown)}")
    color = raw["color"]
    if set(color) != {"primaryColor", "isDarkModeEnabled", "darkPrimaryColor"}:
        raise Failure("color needs primaryColor, isDarkModeEnabled and darkPrimaryColor (Logto takes it whole)")
    for key in ("primaryColor", "darkPrimaryColor"):
        if not HEX.match(color[key]):
            raise Failure(f"color.{key}: {color[key]!r} is not #RRGGBB")
    branding = {k: v.replace("{endpoint}", endpoint) for k, v in raw["branding"].items()}
    css = (config.parent / raw["customCss"]["file"]).read_text(encoding="utf-8")
    if "fonts.googleapis.com" in css or "fonts.gstatic.com" in css or re.search(r"url\(\s*['\"]?https?:", css):
        raise Failure("custom.css loads from another origin; fonts and images must come from /changelens-brand/")
    phrases = {}
    for lang, ref in raw.get("customPhrases", {}).items():
        phrases[lang] = json.loads((config.parent / ref["file"]).read_text(encoding="utf-8"))
        if not isinstance(phrases[lang], dict):
            raise Failure(f"{ref['file']}: not an object")
    return {"color": color, "branding": branding, "customCss": css}, phrases


def request(method: str, url: str, token: str | None = None, body: dict | None = None,
            form: dict | None = None, basic: tuple[str, str] | None = None) -> tuple[int, object]:
    headers = {"Accept": "application/json"}
    data = None
    if body is not None:
        data, headers["Content-Type"] = json.dumps(body).encode(), "application/json"
    if form is not None:
        data, headers["Content-Type"] = urllib.parse.urlencode(form).encode(), "application/x-www-form-urlencoded"
    if token:
        headers["Authorization"] = "Bearer " + token
    if basic:
        headers["Authorization"] = "Basic " + base64.b64encode(":".join(basic).encode()).decode()
    try:
        with urllib.request.urlopen(urllib.request.Request(url, data=data, headers=headers, method=method),
                                    timeout=20) as r:
            text = r.read().decode()
            return r.status, json.loads(text) if text else None
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return 404, None
        # The response body can echo the request; print the status and Logto's error code only.
        try:
            code = json.loads(e.read().decode()).get("code", "")
        except Exception:
            code = ""
        raise Failure(f"{method} {urllib.parse.urlsplit(url).path}: HTTP {e.code} {code}".rstrip()) from None
    except urllib.error.URLError as e:
        raise Failure(f"{method} {urllib.parse.urlsplit(url).path}: {e.reason}") from None


def summary(value: object) -> str:
    if isinstance(value, str) and len(value) > 80:
        return f"<{len(value)} chars, sha256 {hashlib.sha256(value.encode()).hexdigest()[:12]}>"
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def differences(endpoint: str, token: str, patch: dict, phrases: dict[str, dict]) -> list[str]:
    _, current = request("GET", endpoint + "/api/sign-in-exp", token)
    lines = []
    for key, want in patch.items():
        have = current.get(key)
        # Logto stores extra branding keys untouched; compare only the ones this file owns.
        if key == "branding":
            have = {k: (have or {}).get(k) for k in want}
        if have != want:
            lines.append(f"sign-in-exp.{key}: {summary(have)} -> {summary(want)}")
    for lang, want in phrases.items():
        status, have = request("GET", f"{endpoint}/api/custom-phrases/{lang}", token)
        have = have.get("translation") if status == 200 and isinstance(have, dict) else None
        if have != want:
            lines.append(f"custom-phrases.{lang}: {summary(have)} -> {summary(want)}")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--check", action="store_true", help="validate the files only, no network")
    mode.add_argument("--apply", action="store_true", help="write the differences to Logto")
    parser.add_argument("--config", type=Path, default=CONFIG)
    args = parser.parse_args()

    endpoint = os.environ.get("CHANGELENS_LOGTO_MANAGEMENT_ENDPOINT", "").rstrip("/")
    try:
        if args.check:
            patch, phrases = load(args.config, endpoint or "https://auth.pixeltronic.dev")
            print(f"ok: color {patch['color']['primaryColor']} / {patch['color']['darkPrimaryColor']}, "
                  f"css {summary(patch['customCss'])}, phrases {', '.join(sorted(phrases))}")
            return 0
        app_id = os.environ.get("CHANGELENS_LOGTO_M2M_APP_ID", "")
        secret = os.environ.get("CHANGELENS_LOGTO_M2M_APP_SECRET", "")
        if not (endpoint and app_id and secret):
            raise Failure("set CHANGELENS_LOGTO_MANAGEMENT_ENDPOINT, CHANGELENS_LOGTO_M2M_APP_ID and "
                          "CHANGELENS_LOGTO_M2M_APP_SECRET")
        patch, phrases = load(args.config, endpoint)
        resource = os.environ.get("CHANGELENS_LOGTO_MANAGEMENT_RESOURCE", "https://default.logto.app/api")
        _, grant = request("POST", endpoint + "/oidc/token", basic=(app_id, secret),
                           form={"grant_type": "client_credentials", "resource": resource, "scope": "all"})
        token = grant["access_token"]

        lines = differences(endpoint, token, patch, phrases)
        if not lines:
            print(f"in sync: {endpoint}")
            return 0
        print(("applying to " if args.apply else "differs on ") + endpoint + ":")
        for line in lines:
            print("  " + line)
        if not args.apply:
            print("dry run: nothing changed. Re-run with --apply.")
            return 1
        request("PATCH", endpoint + "/api/sign-in-exp", token, body=patch)
        for lang, translation in phrases.items():
            request("PUT", f"{endpoint}/api/custom-phrases/{lang}", token, body=translation)
        left = differences(endpoint, token, patch, phrases)
        if left:
            raise Failure("still differs after applying: " + "; ".join(left))
        print("applied and read back: in sync")
        return 0
    except (Failure, OSError, KeyError, json.JSONDecodeError) as e:
        print(f"error: {e}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
