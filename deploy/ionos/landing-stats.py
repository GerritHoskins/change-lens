#!/usr/bin/env python3
"""Daily totals from the landing page's access log (docs/landing-page-handoff.md, Measurement).

Run by root's cron once a day (README step D4). Caddy writes one JSON line per request for
one of the two pages of changelens.pixeltronic.dev, without the client address or any header (Caddyfile):
the path, the status, `ref_host`, the `utm_*` parameters and `bot`. This script:

1. counts yesterday's page views (and any earlier day not counted yet) per language, referrer host and
   campaign, leaving out the requests Caddy marked as a bot;
2. appends them to TOTALS (CSV: day, language, referrer, campaign, views), one day never twice;
3. empties the active log file once its oldest line is older than KEEP_DAYS, so no raw line outlives the
   retention period. Rolled files are deleted by Caddy itself (roll_keep_for).

No unique visitors: that would need the client address, which is never written.
Standard library only. `--dry-run` prints the rows and changes nothing; `--dry-run --through-today` also
shows today's lines so far.
"""
import csv
import glob
import gzip
import json
import os
import re
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

LOG_DIR = os.environ.get("LANDING_LOG_DIR", "/var/log/changelens-caddy")
TOTALS = os.environ.get("LANDING_TOTALS", "/var/lib/changelens/landing-daily.csv")
KEEP_DAYS = 30
PAGES = {"/": "en", "/index.html": "en", "/de/": "de", "/de/index.html": "de"}
OWN_HOST = "changelens.pixeltronic.dev"
SAFE = re.compile(r"[^a-z0-9._-]")


def _label(value: str) -> str:
    """A short, plain label: lower case, at most 60 characters, nothing but letters, digits, '.', '_', '-'."""
    return SAFE.sub("", value.lower())[:60]


def page_view(entry: dict):
    """(day, language, referrer host, campaign) for a counted page view, else None."""
    request = entry.get("request") or {}
    if entry.get("status") != 200 or request.get("method") != "GET":
        return None
    language = PAGES.get(urlsplit(request.get("uri") or "").path)
    if language is None or entry.get("bot"):
        return None
    try:
        day = datetime.fromtimestamp(float(entry["ts"]), timezone.utc).date().isoformat()
    except (KeyError, TypeError, ValueError):
        return None
    referrer = _label(str(entry.get("ref_host") or ""))
    if referrer == OWN_HOST:
        referrer = ""  # a language switch or a reload, not a source
    return day, language, referrer, _label(str(entry.get("utm_source") or ""))


def read_lines(path: str):
    opener = gzip.open if path.endswith(".gz") else open
    with opener(path, "rt", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            if isinstance(entry, dict):
                yield entry


def counted_days(path: str) -> set:
    if not os.path.exists(path):
        return set()
    with open(path, newline="", encoding="utf-8") as handle:
        return {row[0] for row in csv.reader(handle) if row and row[0] != "day"}


def main(argv) -> int:
    dry = "--dry-run" in argv
    today = datetime.now(timezone.utc).date()
    if "--through-today" in argv:  # for a check by hand: count today's lines so far as well
        today += timedelta(days=1)
    files = sorted(glob.glob(os.path.join(LOG_DIR, "landing-access*.log*")))
    done, totals, oldest = counted_days(TOTALS), Counter(), None
    for path in files:
        for entry in read_lines(path):
            view = page_view(entry)
            if view is None:
                continue
            if view[0] < today.isoformat() and view[0] not in done:  # whole days only, each day once
                totals[view] += 1
    active = os.path.join(LOG_DIR, "landing-access.log")
    if os.path.exists(active):
        for entry in read_lines(active):
            try:
                oldest = datetime.fromtimestamp(float(entry["ts"]), timezone.utc).date()
            except (KeyError, TypeError, ValueError):
                continue
            break
    rows = [[*key, count] for key, count in sorted(totals.items())]
    if dry:
        csv.writer(sys.stdout).writerows(rows)
        return 0
    if rows:
        os.makedirs(os.path.dirname(TOTALS), exist_ok=True)
        new = not os.path.exists(TOTALS)
        with open(TOTALS, "a", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            if new:
                writer.writerow(["day", "language", "referrer", "campaign", "views"])
            writer.writerows(rows)
    if oldest is not None and oldest < today - timedelta(days=KEEP_DAYS):
        # Caddy appends to this file, so emptying it in place is safe; its days are in TOTALS by now,
        # except today's lines so far, which are lost to the totals.
        with open(active, "w", encoding="utf-8"):
            pass
    print(f"landing-stats: {len(rows)} rows for {len({r[0] for r in rows})} day(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
