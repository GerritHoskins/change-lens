"""Job payload rules and log scrubbing (AC-23), without Docker."""
import io
import logging
import uuid

import pytest

from changelens.jobs import build_payload, idempotency_key
from changelens.logs import ScrubFilter, configure_logging


def test_payload_is_kind_plus_uuid_ids_only():
    vid = uuid.uuid4()
    assert build_payload("parse", {"version_id": vid}) == {"kind": "parse", "ids": {"version_id": str(vid)}}
    for bad in ({"version_id": "some document text"}, {"text": uuid.uuid4()}, {"Version_ID": uuid.uuid4()}, {}):
        with pytest.raises(ValueError):
            build_payload("parse", bad)
    with pytest.raises(ValueError):
        build_payload("summarise", {"version_id": vid})


def test_idempotency_key_covers_tenant_kind_ids_and_versions():
    t1, t2, vid = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    k = idempotency_key(t1, "parse", {"version_id": vid})
    assert k == idempotency_key(t1, "parse", {"version_id": vid}) and len(k) == 64
    assert k != idempotency_key(t2, "parse", {"version_id": vid})
    assert k != idempotency_key(t1, "compare", {"version_id": vid})
    assert k != idempotency_key(t1, "parse", {"version_id": vid}, pipeline_version="placeholder-1")
    assert k != idempotency_key(t1, "parse", {"version_id": vid}, model_config_id="other")


def _emit(logger_name, level, msg, *args, exc=None):
    stream = io.StringIO()
    handler = logging.StreamHandler(stream)
    handler.addFilter(ScrubFilter())
    logger = logging.getLogger(logger_name)
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    try:
        if exc:
            try:
                raise exc
            except Exception:
                logger.exception(msg, *args)
        else:
            logger.log(level, msg, *args)
    finally:
        logger.removeHandler(handler)
    return stream.getvalue()


def test_scrub_filter_rules():
    leak = "MARKER-CLIENT-TEXT"
    assert _emit("uvicorn.access", logging.INFO, '%s "%s %s"', "1.2.3.4", "GET", "/x?q=" + leak) == ""
    assert _emit("sqlalchemy.engine.Engine", logging.INFO, "params %s", leak) == ""
    out = _emit("botocore.parsers", logging.WARNING, "body %s", leak)
    assert leak not in out and "scrubbed" in out
    out = _emit("changelens.worker", logging.ERROR, "job %s failed", "abc", exc=ValueError(leak))
    assert leak not in out and "exc=ValueError" in out and "job abc failed" in out
    out = _emit("psycopg", logging.ERROR, "oops", exc=RuntimeError(leak))
    assert leak not in out and "exc=RuntimeError" in out
    assert "job 42 done" in _emit("changelens.worker", logging.INFO, "job %s done", 42)


def test_configure_logging_installs_filter_on_root():
    stream = io.StringIO()
    handler = configure_logging(logging.DEBUG, stream)
    try:
        assert any(isinstance(f, ScrubFilter) for f in handler.filters)
        logging.getLogger("some.library").warning("leak %s", "MARKER-X")
        logging.getLogger("changelens.test").info("kept %s", "id-1")
        out = stream.getvalue()
        assert "MARKER-X" not in out and "kept id-1" in out
        assert logging.getLogger("sqlalchemy.engine").level == logging.WARNING
    finally:
        logging.getLogger().removeHandler(handler)
