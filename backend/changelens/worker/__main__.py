"""Run the dev worker: `python -m changelens.worker`."""
from changelens.config import Settings
from changelens.domain import Database
from changelens.logs import configure_logging
from changelens.storage import S3ObjectStore
from changelens.worker import Worker


def main() -> None:
    configure_logging()
    settings = Settings.from_env()
    db = Database(settings.database_url)
    db.create_schema()
    store = S3ObjectStore(settings.s3_endpoint, settings.s3_access_key, settings.s3_secret_key, settings.s3_bucket)
    store.ensure_bucket()
    Worker(settings, db, store).run_forever()


if __name__ == "__main__":
    main()
