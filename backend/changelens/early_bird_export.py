"""The owner's export of the early-bird list, for a mail to it. Run from backend/.

    python -m changelens.early_bird_export > list.csv

CSV on stdout, confirmed addresses only: `email,locale,confirmed_at,unsubscribe_url`. Every mail to the list
must carry that row's link, visibly in the body and in two headers (`changelens.mail.unsubscribe.list_headers`):

    List-Unsubscribe: <unsubscribe_url>
    List-Unsubscribe-Post: List-Unsubscribe=One-Click

This is the only code that reads addresses, and no route reaches it. It connects as the owner role
(`CHANGELENS_MIGRATION_DATABASE_URL`, like migrations), which owns the table and bypasses its row-level
security; the app role has no rights on the table and no function that returns an address, and this command
refuses to run as a role that row-level security applies to. The transaction is read-only.

It needs three settings and has a default for none of them outside `CHANGELENS_ENV=local`:
`CHANGELENS_MIGRATION_DATABASE_URL`, `CHANGELENS_PUBLIC_API_URL` (the origin the links point at) and
`CHANGELENS_EARLY_BIRD_UNSUBSCRIBE_KEY` (the same value the api has, or its links are refused there).

stderr gets a count and nothing else: no address, no link. The file on stdout holds personal data and working
removal links: keep it off shared disks and delete it after the mail. It is a file for a mail tool, not a
spreadsheet: an address may begin with `=`, `+`, `-` or `@`, which a spreadsheet reads as a formula.
"""
from __future__ import annotations

import csv
import os
import sys
from typing import Iterable, Optional

from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from changelens.config import DEFAULT_MIGRATION_DATABASE_URL, UNSUBSCRIBE_KEY_MIN, Settings, _origin
from changelens.mail.unsubscribe import unsubscribe_url

COLUMNS = ("email", "locale", "confirmed_at", "unsubscribe_url")
_FORMULA = ("=", "+", "-", "@")
_ROWS = text("SELECT id, email, locale, confirmed_at FROM early_bird_signups "
             "WHERE status = 'confirmed' ORDER BY confirmed_at, id")
_BYPASSES = text("SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname = current_user")


class Refused(Exception):
    """The command won't run. The message names settings, never their values."""


def settings_from_env(env=None) -> tuple[str, str, str]:
    """(owner database URL, public API origin, unsubscribe key), or `Refused` naming what is missing."""
    env = os.environ if env is None else env
    local = env.get("CHANGELENS_ENV") == "local"
    url = env.get("CHANGELENS_MIGRATION_DATABASE_URL", "").strip() or (DEFAULT_MIGRATION_DATABASE_URL if local else "")
    key = env.get("CHANGELENS_EARLY_BIRD_UNSUBSCRIBE_KEY", "")
    if not key and local:
        key = Settings.__dataclass_fields__["early_bird_unsubscribe_key"].default
    base = env.get("CHANGELENS_PUBLIC_API_URL", "").strip().rstrip("/")
    missing = [name for name, value in (("CHANGELENS_MIGRATION_DATABASE_URL", url),
                                        ("CHANGELENS_PUBLIC_API_URL", base),
                                        ("CHANGELENS_EARLY_BIRD_UNSUBSCRIBE_KEY", key)) if not value]
    if missing:
        raise Refused("set " + ", ".join(missing))
    if len(key) < UNSUBSCRIBE_KEY_MIN:
        raise Refused("CHANGELENS_EARLY_BIRD_UNSUBSCRIBE_KEY needs at least %d characters" % UNSUBSCRIBE_KEY_MIN)
    if not _origin(base, https_only=not local):
        raise Refused("CHANGELENS_PUBLIC_API_URL must be an https origin (scheme and host, no path)")
    return url, base, key


def confirmed_rows(url: str) -> list:
    """(id, email, locale, confirmed_at) of every confirmed address, read as the owner role."""
    engine = create_engine(url, echo=False, hide_parameters=True, poolclass=NullPool)
    try:
        with engine.connect() as conn:
            conn.execute(text("SET TRANSACTION READ ONLY"))
            if not conn.execute(_BYPASSES).scalar_one():
                raise Refused("CHANGELENS_MIGRATION_DATABASE_URL must use the owner role (changelens_owner), "
                              "never the app role")
            return [tuple(row) for row in conn.execute(_ROWS)]
    finally:
        engine.dispose()


def write_csv(rows: Iterable, public_api_url: str, key: str, out) -> tuple[int, int]:
    """Write the list; returns (rows written, addresses that begin with a spreadsheet formula character)."""
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(COLUMNS)
    count = risky = 0
    for signup_id, email, locale, confirmed_at in rows:
        writer.writerow((email, locale, confirmed_at.isoformat() if confirmed_at else "",
                         unsubscribe_url(public_api_url, key, signup_id)))
        count += 1
        risky += email.startswith(_FORMULA)
    return count, risky


def main(argv: Optional[list] = None, env=None, out=None, err=None) -> int:
    out, err = out or sys.stdout, err or sys.stderr
    if argv:
        print("usage: python -m changelens.early_bird_export > list.csv", file=err)
        return 2
    try:
        url, base, key = settings_from_env(env)
        rows = confirmed_rows(url)
    except Refused as refused:
        print("Not exported: %s" % refused, file=err)
        return 1
    except Exception as exc:  # the class name only: a driver message can quote the URL
        print("Not exported: %s" % type(exc).__name__, file=err)
        return 1
    count, risky = write_csv(rows, base, key, out)
    print("early_bird_export rows=%d formula_start=%d" % (count, risky), file=err)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
