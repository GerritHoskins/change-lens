"""Run the dev API: `python -m changelens.api [--port 8000] [--lan]`.

Binds to localhost only, unless `--lan` is given for a phone on the same trusted home network
(owner decision 2026-10-31). Never use `--lan` on a public or shared network: the dev token is the
only protection and traffic is plain HTTP. The schema is not migrated on start: run
`python -m alembic upgrade head` first (backend/README.md).
"""
import argparse

import uvicorn

from changelens.api.app import create_app
from changelens.config import Settings
from changelens.logs import configure_logging


def bind_host(lan: bool) -> str:
    return "0.0.0.0" if lan else "127.0.0.1"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--lan", action="store_true",
                        help="listen on all interfaces, for a device on a trusted home network")
    args = parser.parse_args()
    configure_logging()
    settings = Settings.from_env()
    app = create_app(settings)
    host = bind_host(args.lan)
    if args.lan:
        print("WARNING: the dev API is reachable from the local network (plain HTTP, dev token only).")
    # log_config=None keeps uvicorn on our scrubbed root handler; its access log is replaced by ours.
    uvicorn.run(app, host=host, port=args.port, log_config=None, access_log=False)


if __name__ == "__main__":
    main()
