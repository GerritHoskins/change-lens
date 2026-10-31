"""Run the dev API: `python -m changelens.api [--port 8000]`. Binds to localhost only."""
import argparse

import uvicorn

from changelens.api.app import create_app
from changelens.config import Settings
from changelens.logs import configure_logging


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    configure_logging()
    settings = Settings.from_env()
    app = create_app(settings)
    app.state.db.create_schema()
    # log_config=None keeps uvicorn on our scrubbed root handler; its access log is replaced by ours.
    uvicorn.run(app, host="127.0.0.1", port=args.port, log_config=None, access_log=False)


if __name__ == "__main__":
    main()
