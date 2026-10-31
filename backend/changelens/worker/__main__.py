"""Run the dev worker: `python -m changelens.worker`."""
from pathlib import Path

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
    llm = None
    if settings.llm_provider == "ionos":
        from changelens.llm.ionos import IonosConfig, IonosLlm, read_token
        token = read_token(Path(settings.ionos_env_file) if settings.ionos_env_file else None)
        llm = IonosLlm(IonosConfig(settings.llm_model, token, reasoning_effort="none"))
    elif settings.llm_provider != "fake":
        raise SystemExit("CHANGELENS_LLM must be fake or ionos")
    Worker(settings, db, store, llm).run_forever()


if __name__ == "__main__":
    main()
