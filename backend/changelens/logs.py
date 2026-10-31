"""Log scrubbing (AC-23). Installed on the root handler, so it sees records from every logger.

Rules:
- Only `changelens.*` and uvicorn's lifecycle logger keep their message text. Our code logs IDs,
  route templates, status codes and error class names, never document text, filenames or labels.
- Any other logger is dropped below WARNING and reduced to "<logger> <level> (message scrubbed)"
  above it: SQLAlchemy, psycopg, botocore and multipart can echo parameters or bodies.
- Tracebacks are replaced by the exception class name; exception messages (e.g. Pydantic
  validation errors) can quote input.
- uvicorn's access log is dropped; the API logs `method route-template status` itself.
"""
from __future__ import annotations

import logging
import sys

KEEP_TEXT = ("changelens", "uvicorn.error")


class ScrubFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        name = record.name
        if name == "uvicorn.access":
            return False
        if record.exc_info or record.exc_text or record.stack_info:
            exc = record.exc_info[0].__name__ if record.exc_info and record.exc_info[0] else "exception"
            record.exc_info = None
            record.exc_text = None
            record.stack_info = None
            record.msg, record.args = "%s exc=%s", (_safe_message(record) if _keeps(name) else "(message scrubbed)", exc)
            return True
        if _keeps(name):
            return True
        if record.levelno < logging.WARNING:
            return False
        record.msg, record.args = "(message scrubbed)", ()
        return True


def _keeps(name: str) -> bool:
    return any(name == k or name.startswith(k + ".") for k in KEEP_TEXT)


def _safe_message(record: logging.LogRecord) -> str:
    try:
        return record.getMessage()
    except Exception:
        return "(unformattable message)"


FORMAT = "%(asctime)s %(levelname)s %(name)s %(message)s"


def configure_logging(level: int = logging.INFO, stream=None) -> logging.Handler:
    """Replace root handlers with one scrubbed stream handler; returns it."""
    root = logging.getLogger()
    for h in list(root.handlers):
        root.removeHandler(h)
    handler = logging.StreamHandler(stream or sys.stderr)
    handler.setFormatter(logging.Formatter(FORMAT))
    handler.addFilter(ScrubFilter())
    root.addHandler(handler)
    root.setLevel(level)
    # Belt and braces: keep the chattiest libraries quiet even if a handler is added without the filter.
    for noisy in ("sqlalchemy.engine", "botocore", "boto3", "s3transfer", "urllib3", "multipart",
                  "python_multipart", "psycopg"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    return handler
