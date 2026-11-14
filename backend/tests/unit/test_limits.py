"""Rate limiter, client IP and telemetry pins (I-8 S6, §6 items 4, 5 and 7). No database."""
import importlib.util
import io
import logging
import uuid
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from changelens.api.app import create_app
from changelens.api.errors import ApiError
from changelens.api.limits import DAY, MINUTE, MemoryCounters, RateLimiter, client_ip
from changelens.config import Settings
from changelens.domain import Database
from changelens.logs import ScrubFilter, configure_logging
from changelens.storage import MemoryObjectStore
from helpers import DEV_TOKENS, SUBJECT_A, TOKEN_A, auth
from identity_fixture import SqliteIdentity

KEY = "k" * 32
REQUIREMENTS = Path(__file__).resolve().parents[2] / "requirements.txt"


def _request(peer, forwarded=None, trusted=()):
    headers = {"x-forwarded-for": forwarded} if forwarded is not None else {}
    app = SimpleNamespace(state=SimpleNamespace(settings=SimpleNamespace(trusted_proxies=tuple(trusted))))
    return SimpleNamespace(app=app, client=SimpleNamespace(host=peer), headers=headers)


# 5. Client IP --------------------------------------------------------------------------------------
@pytest.mark.parametrize("peer, forwarded, trusted, expected", [
    ("203.0.113.9", "198.51.100.1", (), "203.0.113.9"),                       # no proxy trusted: header ignored
    ("203.0.113.9", "198.51.100.1", ("10.0.0.1",), "203.0.113.9"),            # untrusted peer spoofing
    ("10.0.0.1", "198.51.100.1", ("10.0.0.1",), "198.51.100.1"),              # through the proxy
    ("10.0.0.1", "6.6.6.6, 198.51.100.1", ("10.0.0.1",), "198.51.100.1"),     # client-supplied left entry ignored
    ("10.0.0.1", "198.51.100.1, 10.0.0.2", ("10.0.0.1", "10.0.0.2"), "198.51.100.1"),  # two proxy hops
    ("10.0.0.1", "not-an-ip", ("10.0.0.1",), "10.0.0.1"),                     # malformed chain: key on the proxy
    ("10.0.0.1", None, ("10.0.0.1",), "10.0.0.1"),                            # no header
    ("10.0.0.1", "2001:DB8::1", ("10.0.0.1",), "2001:db8::1"),                # normalised
])
def test_client_ip(peer, forwarded, trusted, expected):
    assert client_ip(_request(peer, forwarded, trusted)) == expected


def test_trusted_proxies_are_normalised_and_validated():
    settings = Settings(database_url="postgresql+psycopg://x@h/d", s3_endpoint="http://u", s3_access_key="x",
                        s3_secret_key="x", s3_bucket="x", trusted_proxies=("2001:DB8::0001",))
    assert settings.trusted_proxies == ("2001:db8::1",)
    with pytest.raises(Exception):
        Settings(database_url="postgresql+psycopg://x@h/d", s3_endpoint="http://u", s3_access_key="x",
                 s3_secret_key="x", s3_bucket="x", trusted_proxies=("proxy.example",))


# 4. Rate limiter -----------------------------------------------------------------------------------
def test_the_limiter_counts_per_window_and_gives_retry_after():
    now = {"t": 1_800_000_000 + 12.5}  # 12.5 s into a minute
    limiter = RateLimiter(MemoryCounters(), KEY, clock=lambda: now["t"])
    for _ in range(3):
        limiter.check("account", "a", 3, MINUTE)
    with pytest.raises(ApiError) as e:
        limiter.check("account", "a", 3, MINUTE)
    assert e.value.status == 429 and e.value.code == "rate_limited"
    assert e.value.headers == {"Retry-After": "48"}
    limiter.check("account", "b", 3, MINUTE)  # another key is unaffected
    now["t"] += 48  # the next window starts
    limiter.check("account", "a", 3, MINUTE)


def test_day_windows_are_utc_days():
    seen = []
    limiter = RateLimiter(lambda k, w: seen.append(w) or 1, KEY, clock=lambda: 1_800_000_000.0)
    limiter.check("signup", "ip", 5, DAY)
    assert seen[0].utcoffset().total_seconds() == 0 and (seen[0].hour, seen[0].minute) == (0, 0)


def test_keys_are_hmacs_that_depend_on_scope_and_secret():
    a, b = RateLimiter(MemoryCounters(), KEY), RateLimiter(MemoryCounters(), "z" * 32)
    h = a.key_hash("ip", "203.0.113.9")
    assert len(h) == 64 and int(h, 16) >= 0 and "203" not in h
    assert h != a.key_hash("signup", "203.0.113.9") and h != b.key_hash("ip", "203.0.113.9")


# 7. Telemetry pins ---------------------------------------------------------------------------------
def test_no_telemetry_sdk_or_exporter_is_installed_or_required():
    for module in ("opentelemetry.sdk", "opentelemetry.exporter", "opentelemetry.instrumentation"):
        try:
            assert importlib.util.find_spec(module) is None, module
        except ModuleNotFoundError:
            pass
    pinned = [line.split("==")[0].strip().lower() for line in REQUIREMENTS.read_text().splitlines()
              if "==" in line and not line.startswith(" ")]
    assert not [p for p in pinned if p.startswith("opentelemetry") and p != "opentelemetry-api"]
    assert not [p for p in pinned if p in ("sentry-sdk", "datadog", "ddtrace", "newrelic", "posthog")]


def _app():
    settings = Settings(database_url="postgresql+psycopg://nobody@127.0.0.1:1/none", s3_endpoint="http://unused",
                        s3_access_key="x", s3_secret_key="x", s3_bucket="x", dev_tokens=DEV_TOKENS,
                        rate_limit_ip_per_minute=1)
    db = Database(settings.database_url)
    identity = SqliteIdentity()
    identity.seed(SUBJECT_A, uuid.uuid4())
    db.identity_scope = identity.identity_scope
    db.rate_limit_hit = MemoryCounters()
    return TestClient(create_app(settings, db, MemoryObjectStore()), raise_server_exceptions=False,
                      client=("203.0.113.77", 1))


def test_access_and_rate_limit_logs_hold_no_ip_token_or_query():
    stream = io.StringIO()
    root = logging.getLogger()
    saved = list(root.handlers), root.level
    try:
        configure_logging(stream=stream)
        client = _app()
        pid = uuid.uuid4()
        client.get("/projects/%s?q=MARKER" % pid, headers=auth("wrong-token-0123456789"))
        r = client.get("/projects/%s" % pid, headers=auth("wrong-token-0123456789"))
        assert r.status_code == 429
        client.post("/projects", json={}, headers=auth(TOKEN_A))  # 422 before any database access
    finally:
        root.handlers[:] = saved[0]
        root.setLevel(saved[1])
    out = stream.getvalue()
    assert "GET /projects/{project_id} 401" in out and "GET /projects/{project_id} 429" in out
    for leak in ("203.0.113.77", "wrong-token", TOKEN_A, "MARKER", str(pid)):
        assert leak not in out


def test_the_scrubber_drops_library_parameters():
    record = logging.LogRecord("sqlalchemy.engine.Engine", logging.INFO, __file__, 1,
                               "SELECT %s", ("203.0.113.9",), None)
    assert ScrubFilter().filter(record) is False
    record = logging.LogRecord("psycopg", logging.ERROR, __file__, 1, "key=%s", ("Bearer abc",), None)
    assert ScrubFilter().filter(record) is True and record.getMessage() == "(message scrubbed)"
