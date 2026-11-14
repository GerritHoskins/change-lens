"""Spend caps, rate limits and the sign-up cap in Postgres (I-8 S6, §6 items 1-6)."""
import time
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi.testclient import TestClient

from changelens.api.app import create_app
from changelens.api.limits import RateLimiter
from conftest import TENANT_A, TENANT_B
from helpers import DEV_TOKENS, TOKEN_A, TOKEN_B, auth

LIMITS = dict(rate_limit_account_per_minute=60, rate_limit_ip_per_minute=20, signups_per_ip_per_day=5)


def _spend(env, tenant, amount, when=None, status=None):
    """Recorded cost: a cost tombstone (a deleted comparison), or a failed comparison's actual cost."""
    when = when or datetime.now(timezone.utc)
    env.sql("INSERT INTO comparison_cost_tombstones (id, tenant_id, cost_actual, cost_reservations, created_at) "
            "VALUES (gen_random_uuid(), :t, :a, '{}', :w) RETURNING id", t=tenant, a=amount, w=when)


def _pair(env, token=TOKEN_A):
    pid = env.project(token)
    a = env.upload(pid, token, label="v1", text="one\ntwo").json()["id"]
    b = env.upload(pid, token, label="v2", text="one\nthree").json()["id"]
    env.worker.run_until_idle()
    return pid, a, b


def _counts(env):
    return env.sql("SELECT (SELECT count(*) FROM comparisons), (SELECT count(*) FROM source_versions), "
                   "(SELECT count(*) FROM jobs)")


# 1-3. Spend caps -----------------------------------------------------------------------------------
def test_the_tenant_cap_counts_failed_runs_and_deleted_projects(env):
    pid, a, b = _pair(env)
    _spend(env, TENANT_A, Decimal("3"))  # a deleted project's comparison
    failed = env.compare(pid, a, b).json()["id"]
    env.sql("UPDATE comparisons SET status = 'failed', cost_actual = 1.99 WHERE id = :c RETURNING id", c=failed)
    r = env.compare(pid, a, b)  # 4.99 + the first comparison's own 0: just under the cap
    assert r.status_code == 202, r.text
    env.sql("UPDATE comparisons SET cost_reservations = '{\"t\": \"0.01\"}' WHERE id = :c RETURNING id",
            c=r.json()["id"])  # an open reservation counts too: 5.00
    before = _counts(env)
    r = env.compare(pid, a, b)
    assert r.status_code == 429 and r.json()["code"] == "spend_cap_reached"
    assert _counts(env) == before  # nothing created or charged
    assert env.compare(*_pair(env, TOKEN_B), token=TOKEN_B).status_code == 202  # another tenant is fine


def test_spend_from_the_previous_utc_month_does_not_count(env):
    pid, a, b = _pair(env)
    start = datetime.now(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    _spend(env, TENANT_A, Decimal("100"), when=start - timedelta(seconds=1))
    _spend(env, TENANT_B, Decimal("100"), when=start - timedelta(days=3))
    assert env.compare(pid, a, b).status_code == 202


def test_the_global_cap_rejects_every_tenant_and_stops_a_running_comparison(env):
    pid, a, b = _pair(env)
    cid = env.compare(pid, a, b).json()["id"]  # created before the cap, not yet run
    _spend(env, TENANT_B, Decimal("50"))
    for token in (TOKEN_A, TOKEN_B):
        r = env.compare(*_pair(env, token), token=token)
        assert r.status_code == 429 and r.json()["code"] == "spend_cap_reached"
    env.worker.run_until_idle()
    c = env.get("/comparisons/" + cid).json()
    assert c["status"] == "failed" and {"code": "spend_cap_reached"} in c["warnings"]
    assert env.sql("SELECT cost_actual, cost_reservations FROM comparisons WHERE id = :c", c=cid) == [(0, {})]


# 4. Rate limits ------------------------------------------------------------------------------------
def _app(env, clock, **overrides):
    settings = env.settings.__class__(**{**env.settings.__dict__, **LIMITS, **overrides})
    limiter = RateLimiter(env.db.rate_limit_hit, settings.rate_limit_key, clock=clock)
    return TestClient(create_app(settings, env.db, env.store, limiter=limiter), raise_server_exceptions=False)


def _fixed_clock():
    start = time.time() // 60 * 60 + 5  # 5 s into the current minute, for every request
    return lambda: start


def test_the_61st_request_from_one_account_is_rate_limited_across_two_instances(env):
    clock = _fixed_clock()
    one, two = _app(env, clock), _app(env, clock)
    for i in range(60):
        assert (one if i % 2 else two).get("/projects", headers=auth(TOKEN_A)).status_code == 200, i
    r = one.get("/projects", headers=auth(TOKEN_A))
    assert r.status_code == 429 and r.json()["code"] == "rate_limited"
    assert r.headers["retry-after"] == "55"
    assert two.get("/projects", headers=auth(TOKEN_B)).status_code == 200  # another account isn't affected
    keys = env.sql("SELECT key_hash FROM rate_limit_counters")
    assert all(len(k) == 64 and int(k, 16) >= 0 for (k,) in keys)


def test_failed_authentication_and_session_calls_are_limited_per_ip(env):
    client = _app(env, _fixed_clock())
    for _ in range(20):
        assert client.get("/projects", headers=auth("wrong-token-0123456789")).status_code == 401
    r = client.get("/projects", headers=auth("wrong-token-0123456789"))
    assert r.status_code == 429 and "retry-after" in r.headers
    assert client.post("/session", headers=auth(TOKEN_A)).status_code == 429  # same IP, same window
    assert client.get("/projects", headers=auth(TOKEN_A)).status_code == 200  # a valid account still works


# 5. Client IP --------------------------------------------------------------------------------------
def test_forwarded_for_is_believed_only_from_a_trusted_proxy_and_ips_are_stored_hashed(env):
    clock = _fixed_clock()
    settings = dict(trusted_proxies=("10.0.0.1",))
    spoofer = _app(env, clock, **settings)
    spoofer_client = TestClient(spoofer.app, raise_server_exceptions=False, client=("203.0.113.9", 1))
    proxied = TestClient(spoofer.app, raise_server_exceptions=False, client=("10.0.0.1", 1))
    for i in range(20):  # a spoofed header from an untrusted peer: every request counts against the peer
        r = spoofer_client.get("/projects", headers={**auth("bad-token-0123456789"),
                                                     "X-Forwarded-For": "198.51.100.%d" % i})
        assert r.status_code == 401
    assert spoofer_client.get("/projects", headers=auth("bad-token-0123456789")).status_code == 429
    # Through the trusted proxy, each forwarded client has its own window.
    for i in range(3):
        r = proxied.get("/projects", headers={**auth("bad-token-0123456789"), "X-Forwarded-For": "198.51.100.%d" % i})
        assert r.status_code == 401
    stored = str(env.sql("SELECT * FROM rate_limit_counters"))
    assert "203.0.113.9" not in stored and "198.51.100" not in stored and "10.0.0.1" not in stored
    limiter = spoofer.app.state.limiter
    assert (limiter.key_hash("ip", "203.0.113.9"),) in env.sql("SELECT key_hash FROM rate_limit_counters")


# 6. Sign-up cap ------------------------------------------------------------------------------------
def test_the_sixth_new_account_from_one_ip_in_a_day_is_rejected_but_returning_users_are_not(env):
    tokens = {"dev-token-signup-%02d-0123456789" % i: "dev:signup-%d" % i for i in range(7)}
    client = _app(env, _fixed_clock(), dev_tokens={**DEV_TOKENS, **tokens})
    new = list(tokens)
    for token in new[:5]:
        assert client.post("/session", headers=auth(token)).status_code == 200
    r = client.post("/session", headers=auth(new[5]))
    assert r.status_code == 429 and r.json()["code"] == "rate_limited" and int(r.headers["retry-after"]) > 0
    assert env.sql("SELECT count(*) FROM users WHERE idp_subject = 'dev:signup-5'") == [(0,)]
    for token in (new[0], TOKEN_A):  # returning users from the same IP
        assert client.post("/session", headers=auth(token)).status_code == 200
    other_ip = TestClient(client.app, raise_server_exceptions=False, client=("192.0.2.7", 1))
    assert other_ip.post("/session", headers=auth(new[6])).status_code == 200
    assert uuid.UUID(str(env.sql("SELECT id FROM users WHERE idp_subject = 'dev:signup-6'")[0][0]))
