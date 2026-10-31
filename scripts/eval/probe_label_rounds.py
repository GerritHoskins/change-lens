"""Run mutation probes in a disposable copy; only synthetic unittest inputs are used.

    python scripts/eval/probe_label_rounds.py

Each deliberate regression must fail the full evaluation suite. No source file in the
worktree is mutated; the unmodified copy must pass before any probe is run.
"""
import os
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile

PROBES = [
    ("freeze overwrite", "label_rounds.py", [
        ('if path.exists():\n        raise SystemExit("%s already exists; refusing to overwrite"',
         'if False:\n        raise SystemExit("%s already exists; refusing to overwrite"'),
        ('path.open("x",', 'path.open("w",')]),
    ("sample rerun", "label_rounds.py", [
        ('if path.exists():\n        raise SystemExit("%s already exists; refusing a second sample"',
         'if False:\n        raise SystemExit("%s already exists; refusing a second sample"'),
        ('path.open("x",', 'path.open("w",')]),
    ("frozen R1 hash", "label_rounds.py", [('digest(path) != entry["sha256"]', 'False')]),
    ("seed ignored", "label_rounds.py", [('random.Random(seed)', 'random.Random(0)')]),
    ("case-type stratum ignored", "label_rounds.py", [
        ('(entry["case_type"], entry["tier"])', '("all", entry["tier"])')]),
    ("tier stratum ignored", "label_rounds.py", [
        ('(entry["case_type"], entry["tier"])', '(entry["case_type"], "all")')]),
    ("third rounded down", "label_rounds.py", [('math.ceil(len(entries) / 3)', 'len(entries) // 3')]),
    ("sample binding", "label_rounds.py", [
        ('or doc.get("pairs") != stratified(frozen["pairs"], doc["seed"])', 'or False')]),
    ("14-day guard", "label_rounds.py", [('if exported < earliest:', 'if False:')]),
    ("14-day boundary", "label_rounds.py", [('if exported < earliest:', 'if exported <= earliest:')]),
    ("future R2 date", "label_rounds.py", [('if exported > utcnow():', 'if False:')]),
    ("R2 membership", "label_kit.py", [('if set(pairs) - set(sampled):', 'if False:')]),
    ("R2 label leak", "label_kit.py", [('    tpl = TEMPLATE.read_text',
        '    payload["findings"] = [{"id": "R1-1", "note": "SECRET-R1-LABEL"}]\n    tpl = TEMPLATE.read_text')]),
    ("round storage isolation", "label_kit.html", [("+ ':' + d.round + ':'", "+ ':' + 'R1' + ':'")]),
    ("cross-round import", "label_kit.html", [('incoming.round === d.round', 'true')]),
    ("required case type in loader", "label_exports.py", [
        ('if doc.get("case_type") not in label_kit.case_types():', 'if False:')]),
    ("required case type in page", "label_kit.html", [("if (d.case_types.indexOf(caseType) < 0)", "if (false)")]),
    ("P-015 exclusion", "label_kit.py", [('EXCLUDED = {"P-015"}', 'EXCLUDED = set()')]),
    ("resolved-label precedence", "reconcile.py", [('if res.exists():', 'if False:')]),
    ("resolution stratum", "reconcile.py", [('if resolution.get("case_type") != a["case_type"]:', 'if False:')]),
    ("real/constructed reporting", "reconcile.py", [
        ('"Constructed pairs" if tier == "constructed" else "Real pairs (non-gating)"', '"Constructed pairs"')]),
]


def run_suite(root):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    result = subprocess.run([sys.executable, "-B", "-m", "unittest", "discover", "-s", "scripts/eval"],
                            cwd=root, env=env, capture_output=True, text=True, encoding="utf-8", errors="replace")
    text = result.stdout + result.stderr
    ran = re.search(r"^Ran (\d+) tests?", text, re.M)
    return result.returncode, int(ran[1]) if ran else 0, text


def copy_suite(repo, root):
    shutil.copytree(repo / "scripts/eval", root / "scripts/eval", ignore=shutil.ignore_patterns("__pycache__"))
    (root / "docs").mkdir()
    shutil.copy2(repo / "docs/eval-schema.json", root / "docs/eval-schema.json")
    (root / ".git").mkdir()  # preserves the suites' inside-Git refusal tests


def probe(repo, spec, count):
    name, file, replacements = spec
    with tempfile.TemporaryDirectory(prefix="changelens-round-probe-") as tmp:
        root = Path(tmp)
        copy_suite(repo, root)
        path = root / "scripts/eval" / file
        mutated = path.read_text(encoding="utf-8")
        for old, new in replacements:
            if old not in mutated:
                return False, "missing mutation target: %s" % name
            mutated = mutated.replace(old, new)
        path.write_text(mutated, encoding="utf-8", newline="\n")
        code, got, output = run_suite(root)
    # A syntax/import crash is not evidence that the behavioral guard is tested.
    failures = re.search(r"^FAILED \((.*)\)", output, re.M)
    if code == 0 or got != count or "SyntaxError" in output or "ImportError" in output or not failures:
        return False, "PROBE FAIL: %s (exit %s, %s tests)\n%s" % (name, code, got, output)
    return True, "KILLED: %s - %s tests; %s" % (name, got, failures[0])


def main():
    repo = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="changelens-round-baseline-") as tmp:
        root = Path(tmp)
        copy_suite(repo, root)
        code, count, output = run_suite(root)
    if code or not count:
        print("BASELINE FAIL\n" + output)
        return 1
    print("BASELINE: Ran %d tests; OK" % count, flush=True)
    passed = 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        jobs = [pool.submit(probe, repo, spec, count) for spec in PROBES]
        for job in as_completed(jobs):
            ok, result = job.result()
            passed += int(ok)
            print(result, flush=True)
    print("MUTATION %s: %d/%d probes failed the full suite" % (
        "PASS" if passed == len(PROBES) else "FAIL", passed, len(PROBES)))
    return 0 if passed == len(PROBES) else 1


if __name__ == "__main__":
    sys.exit(main())
