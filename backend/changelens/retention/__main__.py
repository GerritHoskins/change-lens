"""Preview: python -m changelens.retention --once; process: add --apply."""
import argparse
import json
import logging
import time

from changelens.auth.logto_management import idp_for
from changelens.config import Settings
from changelens.domain import Database
from changelens.domain.retention import run_maintenance
from changelens.domain.social import apple_tokens_for
from changelens.logs import configure_logging
from changelens.storage import S3ObjectStore


def positive(value):
    number = int(value)
    if number <= 0:
        raise argparse.ArgumentTypeError("must be positive")
    return number


def main(argv=None):
    parser = argparse.ArgumentParser(description="Primary retention maintenance; dry-run unless --apply is supplied.")
    parser.add_argument("--apply", action="store_true", help="delete expired primary data and retry durable purges")
    parser.add_argument("--once", action="store_true", help="process one bounded batch, then exit")
    parser.add_argument("--interval-seconds", type=positive, default=60)
    parser.add_argument("--limit", type=positive, default=100)
    args = parser.parse_args(argv)
    configure_logging()
    settings = Settings.from_env()
    db = Database(settings.database_url)
    # No schema bootstrap or bucket creation here: even preview must remain read-only.
    store = S3ObjectStore(settings.s3_endpoint, settings.s3_access_key, settings.s3_secret_key, settings.s3_bucket)
    idp = idp_for(settings)
    apple = apple_tokens_for(settings)  # revokes deleted accounts' and expired parked Apple tokens (I-8 S4)
    try:
        db.assert_app_role()  # RLS must apply to this process (I-8 S3)
        while True:
            try:
                summary = run_maintenance(db, store, limit=args.limit, execute=args.apply, idp=idp,
                                          apple=apple)
                print(json.dumps(summary, sort_keys=True), flush=True)
                if args.once:
                    return 0
            except Exception as exc:
                logging.getLogger("changelens.retention").error("maintenance failed: %s", type(exc).__name__)
                if args.once:
                    return 1
            time.sleep(args.interval_seconds)
    finally:
        db.engine.dispose()
        db._intent_engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
