"""Reject missing, empty, skipped, failed or inconsistent pytest JUnit integration reports."""
from __future__ import annotations

import argparse
from pathlib import Path
import sys
import xml.etree.ElementTree as ET


def counts(element: ET.Element) -> dict[str, int]:
    cases = list(element.iter("testcase"))
    return {
        "tests": len(cases),
        "skipped": sum(case.find("skipped") is not None for case in cases),
        "failures": sum(case.find("failure") is not None for case in cases),
        "errors": sum(case.find("error") is not None for case in cases),
    }


def inspect(path: Path) -> tuple[dict[str, int], list[str]]:
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        return {}, ["integration report is missing or unreadable"]
    if root.tag not in ("testsuite", "testsuites"):
        return {}, ["integration report has an unsupported root element"]
    result = counts(root)
    errors = []
    if not result["tests"]:
        errors.append("no integration tests executed")
    for kind in ("skipped", "failures", "errors"):
        if result[kind]:
            errors.append(f"integration report contains {result[kind]} {kind}")
    for suite in root.iter():
        if suite.tag not in ("testsuite", "testsuites"):
            continue
        actual = counts(suite)
        for key, value in actual.items():
            recorded = suite.get(key)
            if recorded is None:
                continue  # pytest's outer testsuites element has no aggregate attributes
            if not recorded.isdecimal() or int(recorded) != value:
                errors.append("integration report has inconsistent " + key + " count")
    return result, errors


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("report", type=Path)
    args = parser.parse_args(argv)
    result, errors = inspect(args.report)
    for error in errors:
        print("FAIL " + error)
    if not errors:
        print(f"PASS integration evidence: {result['tests']} executed; zero skipped, failures or errors")
    return int(bool(errors))


if __name__ == "__main__":
    sys.exit(main())
