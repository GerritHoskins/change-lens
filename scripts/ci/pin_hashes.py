"""Rewrite the `--hash` lines of a pinned requirements file from the PyPI JSON API.

    python scripts/ci/pin_hashes.py --python 3.13 backend/requirements.txt backend/requirements-test.txt
    python scripts/ci/pin_hashes.py --python 3.13 --all-wheels scripts/eval/requirements-render.txt
    python scripts/ci/pin_hashes.py --python 3.13 --check backend/requirements.txt   # exit 1 if it would change

Names, versions, comments and order stay as they are; only each pin's hashes are replaced. By default a pin
gets the wheels one CPython version can install on win_amd64, manylinux x86_64/aarch64 and macOS, plus
pure-Python wheels. `--all-wheels` keeps every published wheel of the pinned version. Source archives are
never hashed (`--only-binary=:all:`). A pin with no wheel for Windows or Linux x86_64 is an error.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.request

PIN = re.compile(r"^([A-Za-z0-9_.-]+)(\[[^\]]+\])?==([^\s\\]+)\s*\\?\s*$")
HASH = re.compile(r"^\s+--hash=sha256:[0-9a-f]{64}\s*\\?\s*$")
WHEEL = re.compile(r"^.+?-[^-]+?(?:-\d[^-]*)?-(?P<py>[^-]+)-(?P<abi>[^-]+)-(?P<plat>[^-]+)\.whl$")
PLATFORMS = (r"^any$", r"^win_amd64$", r"manylinux\S*_(x86_64|aarch64)", r"^macosx_\S+_(x86_64|arm64|universal2)$")
REQUIRED = {"Windows x64": r"^(any|win_amd64)$", "Linux x64": r"^any$|manylinux\S*_x86_64"}


def installable(filename: str, minor: int) -> bool:
    """True when CPython 3.<minor> can install this wheel on one of the supported platforms."""
    match = WHEEL.match(filename)
    if not match or not any(re.search(p, part) for part in match["plat"].split(".") for p in PLATFORMS):
        return False
    abi, tags = match["abi"], match["py"].split(".")
    for tag in tags:
        if tag in ("py3", f"py3{minor}") and abi == "none":
            return True
        if tag == f"cp3{minor}" and abi in (f"cp3{minor}", "abi3", "none"):
            return True
        if abi == "abi3" and re.fullmatch(r"cp3\d+", tag) and int(tag[3:]) <= minor:
            return True
    return False


def fetch(name: str, version: str) -> list[dict]:
    with urllib.request.urlopen(f"https://pypi.org/pypi/{name}/{version}/json", timeout=30) as response:
        return [f for f in json.load(response)["urls"] if f["filename"].endswith(".whl") and not f.get("yanked")]


def hashes_for(name: str, version: str, minor: int, all_wheels: bool, wheels=fetch) -> list[str]:
    files = wheels(name, version)
    chosen = files if all_wheels else [f for f in files if installable(f["filename"], minor)]
    for label, pattern in REQUIRED.items():
        usable = [f for f in files if installable(f["filename"], minor)]
        if not any(re.search(pattern, part) for f in usable for part in WHEEL.match(f["filename"])["plat"].split(".")):
            raise SystemExit(f"{name}=={version}: no wheel for CPython 3.{minor} on {label}")
    return [f["digests"]["sha256"] for f in chosen]


def rewrite(text: str, minor: int, all_wheels: bool, wheels=fetch) -> str:
    out, lines, i = [], text.splitlines(), 0
    while i < len(lines):
        match = PIN.match(lines[i])
        if not match:
            out.append(lines[i])
            i += 1
            continue
        start = i
        i += 1
        while i < len(lines) and HASH.match(lines[i]):
            i += 1
        digests = hashes_for(match[1], match[3], minor, all_wheels, wheels)
        if {re.search(r"[0-9a-f]{64}", line)[0] for line in lines[start + 1:i]} == set(digests):
            out += lines[start:i]  # same hashes: keep the pin's lines as they are
            continue
        out.append(f"{match[1]}{match[2] or ''}=={match[3]} \\")
        out += [f"    --hash=sha256:{d}" + (" \\" if n < len(digests) - 1 else "") for n, d in enumerate(digests)]
    return "\n".join(out) + "\n"


def hash_sets(text: str) -> dict[str, frozenset]:
    """Pin -> its set of hashes; the order of hash lines carries no meaning."""
    result, current = {}, None
    for line in text.splitlines():
        match = PIN.match(line)
        if match:
            current = f"{match[1]}=={match[3]}"
            result[current] = set()
        elif current and HASH.match(line):
            result[current].add(re.search(r"[0-9a-f]{64}", line)[0])
        elif line.strip() and not line.startswith("#"):
            current = None
    return {k: frozenset(v) for k, v in result.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--python", required=True, help="target CPython, for example 3.13")
    parser.add_argument("--all-wheels", action="store_true", help="hash every published wheel of each pin")
    parser.add_argument("--check", action="store_true", help="write nothing; exit 1 when a file would change")
    parser.add_argument("files", nargs="+")
    args = parser.parse_args()
    major, minor = (int(part) for part in args.python.split(".")[:2])
    if major != 3:
        parser.error("only CPython 3.x is supported")
    stale = 0
    for path in args.files:
        with open(path, encoding="utf-8") as handle:
            before = handle.read()
        after = rewrite(before, minor, args.all_wheels)
        old, new = hash_sets(before), hash_sets(after)
        changed = sorted(pin for pin in new if old.get(pin) != new[pin])
        print(f"{path}: {len(new)} pins, {len(changed)} with different hashes" + (": " + ", ".join(changed) if changed else ""))
        stale += bool(changed)
        if changed and not args.check:
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(after)
    return 1 if stale and args.check else 0


if __name__ == "__main__":
    sys.exit(main())
