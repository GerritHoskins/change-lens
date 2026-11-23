"""The early-bird list's sign-up and confirmation routes (docs/landing-page-handoff.md) with no services: the
list and the rate-limit counters in memory, the recording mail sender, mails sent inline instead of from the
mail queue's threads. The Postgres functions are checked in tests/integration/test_early_bird_db.py; the
fixes of the 2026-11-22 review (caps, link tokens, the queue) in test_early_bird_hardening.py."""
import io
import json
import logging
import re
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from changelens.api.app import create_app
from changelens.api.early_bird import ACCEPTED, MAX_BODY, MemoryEarlyBird, normalise_email, token_hash
from changelens.api.limits import MemoryCounters, RateLimiter
from changelens.config import Settings
from changelens.logs import configure_logging
from changelens.mail import RecordingMailer
from changelens.mail.queue import InlineMailQueue
from changelens.storage import MemoryObjectStore
from helpers import DEV_TOKENS

LANDING, API = "https://landing.example.test", "https://api.example.test"
ADDRESS = "ada@example.test"
DAY = 86400


class Env:
    def __init__(self, mailer=None, mail_queue=None, **overrides):
        base = dict(database_url="unused", s3_endpoint="unused", s3_access_key="x", s3_secret_key="x",
                    s3_bucket="x", dev_tokens=DEV_TOKENS, landing_url=LANDING, public_api_url=API)
        self.settings = Settings(**{**base, **overrides})
        self.now = 1_800_000_000.0 + 3600  # one hour into a UTC day
        self.list = MemoryEarlyBird(clock=lambda: self.now)
        self.counters = MemoryCounters()
        self.mailer = RecordingMailer() if mailer is None else mailer
        limiter = RateLimiter(self.counters, self.settings.rate_limit_key, clock=lambda: self.now)
        self.app = create_app(self.settings, SimpleNamespace(), MemoryObjectStore(), limiter=limiter,
                              mailer=self.mailer, early_bird=self.list, mail_queue=mail_queue or InlineMailQueue())
        self.client = self.at("203.0.113.5")

    def at(self, ip):
        return TestClient(self.app, raise_server_exceptions=False, client=(ip, 1), follow_redirects=False)

    def join(self, email=ADDRESS, locale="en", client=None, **kwargs):
        return (client or self.client).post("/early-bird", json={"email": email, "locale": locale}, **kwargs)

    def token(self, index=-1):
        return re.search(r"/early-bird/confirm\?token=([A-Za-z0-9_-]+)", self.mailer.sent[index].body).group(1)

    def open(self, token):
        """Open the link in the mail: the page with the button. Changes nothing."""
        return self.client.get("/early-bird/confirm", params={"token": token})

    def confirm(self, token):
        """Press the page's button: the form post that confirms."""
        return self.client.post("/early-bird/confirm?token=" + token, content="token=" + token,
                                headers={"Content-Type": "application/x-www-form-urlencoded"})


@pytest.fixture()
def env():
    return Env()


# Validation ----------------------------------------------------------------------------------------
@pytest.mark.parametrize("given, expected", [
    ("ada@example.test", "ada@example.test"),
    ("  Ada.Lovelace+list@Example.TEST \n", "ada.lovelace+list@example.test"),  # trimmed and lower-cased
    ("a@b.co", "a@b.co"),
    ("x" * 64 + "@" + "d" * 185 + ".com", "x" * 64 + "@" + "d" * 185 + ".com"),  # 254 characters
])
def test_addresses_are_trimmed_and_lower_cased(given, expected):
    assert normalise_email(given) == expected


@pytest.mark.parametrize("given", [
    "", "ada", "@example.test", "ada@", "ada@example", "a@b@example.test", "ada @example.test", "ada@exam ple.test",
    "ada@example..test", "ada@.example.test", "ada@example.test.", "ada\n@example.test", "ada\x00@example.test",
    "ada​@example.test", "ädä@example.test", "ada@exämple.test", "Ada <ada@example.test>",
    "ada@example.test,eve@example.test", '"ada"@example.test', "x" * 65 + "@example.test",
    "x" * 64 + "@" + "d" * 186 + ".com",  # 255 characters
    None, 7, True, ["ada@example.test"], {"a": 1},
])
def test_other_addresses_are_refused(given):
    assert normalise_email(given) is None


@pytest.mark.parametrize("body", [
    {"email": "MARKER-not-an-address", "locale": "en"},
    {"email": ADDRESS, "locale": "fr"},
    {"email": ADDRESS, "locale": "EN"},
    {"email": ADDRESS, "locale": ["en"]},
    {"email": ADDRESS, "locale": None},
    {"email": ["MARKER@example.test"], "locale": "en"},
    {"email": 5, "locale": "en"},
    {"email": ADDRESS},
    {"locale": "en"},
    {"email": ADDRESS, "locale": "en", "MARKER": "extra"},
    {},
    [{"email": ADDRESS, "locale": "en"}],
    "MARKER",
    None,
])
def test_invalid_input_is_422_and_never_echoed(env, body):
    r = env.client.post("/early-bird", json=body)
    assert r.status_code == 422 and r.headers["content-type"] == "application/problem+json"
    assert r.json()["code"] == "invalid_request" and "MARKER" not in r.text and ADDRESS not in r.text
    assert not env.list.rows and not env.mailer.sent


def test_the_body_must_be_json_sent_as_json_and_small(env):
    valid = json.dumps({"email": ADDRESS, "locale": "en"})
    for kwargs in (dict(content=b"{not json", headers={"Content-Type": "application/json"}),
                   dict(content=b"\xff\xfe", headers={"Content-Type": "application/json"}),
                   dict(content=b"", headers={"Content-Type": "application/json"}),
                   dict(content=valid, headers={"Content-Type": "text/plain"}),  # a cross-site "simple" request
                   dict(data={"email": ADDRESS, "locale": "en"})):  # a form post
        r = env.client.post("/early-bird", **kwargs)
        assert r.status_code == 422 and r.json()["code"] == "invalid_request", kwargs
    padded = json.dumps({"email": ADDRESS, "locale": "en", "pad": "x" * MAX_BODY})
    r = env.at("203.0.113.6").post("/early-bird", content=padded, headers={"Content-Type": "application/json"})
    assert r.status_code == 413 and r.json()["code"] == "limit_exceeded"
    assert not env.list.rows and not env.mailer.sent
    assert env.at("203.0.113.7").post("/early-bird", content=valid,
                                      headers={"Content-Type": "application/json; charset=utf-8"}).status_code == 202


# The same answer whatever the list holds -----------------------------------------------------------
def test_new_pending_and_confirmed_addresses_get_the_same_202(env):
    def shape(r):
        return r.status_code, r.json(), sorted(k for k in r.headers if k != "content-length")

    new = env.join()
    assert new.status_code == 202 and new.json() == ACCEPTED and len(env.mailer.sent) == 1
    pending = env.join()
    assert len(env.mailer.sent) == 2 and env.token(0) != env.token(1)  # a fresh link each time
    assert env.confirm(env.token(1)).headers["location"] == LANDING + "/#confirmed"
    confirmed = env.join()
    assert len(env.mailer.sent) == 2  # a confirmed address gets no further mail
    assert shape(new) == shape(pending) == shape(confirmed)
    assert ADDRESS not in new.text + pending.text + confirmed.text
    assert env.list.rows[ADDRESS]["status"] == "confirmed"


def test_the_address_is_stored_normalised_and_the_token_only_as_its_hash(env):
    assert env.join(email="  Ada@Example.TEST ").status_code == 202
    row = env.list.rows[ADDRESS]
    token = env.token()
    assert row["status"] == "pending" and row["locale"] == "en" and row["confirmation_sent_at"] is not None
    assert row["token_hash"] == token_hash(token) and len(row["token_hash"]) == 64
    assert token not in json.dumps(env.list.rows, default=str) and len(token) >= 43
    message = env.mailer.sent[-1]
    assert message.to == ADDRESS and API + "/early-bird/confirm?token=" + token in message.body


# Confirmation --------------------------------------------------------------------------------------
def test_a_token_confirms_once_and_redirects_by_language(env):
    env.join(locale="de")
    token = env.token()
    first = env.confirm(token)
    assert first.status_code == 303 and first.headers["location"] == LANDING + "/de/#confirmed"
    assert first.headers["referrer-policy"] == "no-referrer" and first.headers["cache-control"] == "no-store"
    assert token not in first.headers["location"] and first.text == ""
    row = env.list.rows[ADDRESS]
    assert row["status"] == "confirmed" and row["token_hash"] is None and row["confirmed_at"] is not None
    again = env.confirm(token)
    assert again.status_code == 303 and again.headers["location"] == LANDING + "/#confirm-failed"


def test_a_newer_link_replaces_the_older_one(env):
    env.join()
    env.join()
    assert env.confirm(env.token(0)).headers["location"] == LANDING + "/#confirm-failed"
    assert env.list.rows[ADDRESS]["status"] == "pending"
    assert env.confirm(env.token(1)).headers["location"] == LANDING + "/#confirmed"


@pytest.mark.parametrize("query", ["", "?token=", "?token=short", "?token=" + "a" * 43, "?token=" + "a" * 200,
                                   "?token=%3Cscript%3E", "?other=1"])
def test_a_missing_unknown_or_malformed_token_redirects_and_is_never_json(env, query):
    env.join()
    opened = env.client.get("/early-bird/confirm" + query)
    if query == "?token=" + "a" * 43:  # well-formed: the page, which says nothing about the token
        assert opened.status_code == 200 and opened.text == env.open(env.token()).text.replace(env.token(), "a" * 43)
    else:
        assert opened.status_code == 303 and opened.headers["location"] == LANDING + "/#confirm-failed"
    form = {"Content-Type": "application/x-www-form-urlencoded"}
    for r in (env.client.post("/early-bird/confirm" + query, content=query[1:], headers=form),
              env.client.post("/early-bird/confirm" + query)):
        assert r.status_code == 303 and r.headers["location"] == LANDING + "/#confirm-failed"
        assert "json" not in r.headers.get("content-type", "")
    assert env.list.rows[ADDRESS]["status"] == "pending"


def test_a_token_expires_with_the_pending_period_and_the_row_is_pruned(env):
    env.join()
    token = env.token()
    env.now += 7 * DAY + 1
    assert env.confirm(token).headers["location"] == LANDING + "/#confirm-failed"
    assert env.list.early_bird_prune() == 1 and not env.list.rows
    env.join()  # the same address can sign up again
    env.confirm(env.token())
    env.now += 30 * DAY
    assert env.list.early_bird_prune() == 0 and env.list.rows[ADDRESS]["status"] == "confirmed"


def test_an_expired_pending_row_starts_a_new_period_on_the_next_request(env):
    env.join()
    env.now += 8 * DAY  # maintenance has not run
    env.join()
    assert env.confirm(env.token()).headers["location"] == LANDING + "/#confirmed"


def test_confirmation_is_limited_per_ip_with_a_redirect_not_an_error_page():
    env = Env(rate_limit_ip_per_minute=2)
    env.join()
    for _ in range(2):
        assert env.confirm("b" * 43).status_code == 303
    assert env.open(env.token()).headers["location"] == LANDING + "/#confirm-failed"  # the page is limited too
    limited = env.confirm(env.token())
    assert limited.status_code == 303 and limited.headers["location"] == LANDING + "/#confirm-failed"
    assert int(limited.headers["retry-after"]) > 0 and env.list.rows[ADDRESS]["status"] == "pending"
    env.now += 60  # the next minute: the unused token still works
    assert env.confirm(env.token()).headers["location"] == LANDING + "/#confirmed"


# Limits --------------------------------------------------------------------------------------------
def test_the_sixth_request_from_one_ip_in_a_day_is_rate_limited(env):
    for i in range(5):
        assert env.join(email="person%d@example.test" % i).status_code == 202
    r = env.join(email="person5@example.test")
    assert r.status_code == 429 and r.json()["code"] == "rate_limited" and int(r.headers["retry-after"]) > 0
    assert "person5@example.test" not in env.list.rows and len(env.mailer.sent) == 5
    assert env.client.post("/early-bird", json={"email": "bad"}).status_code == 429  # invalid requests count too
    assert env.join(email="person5@example.test", client=env.at("203.0.113.99")).status_code == 202
    env.now += DAY
    assert env.join(email="person6@example.test").status_code == 202  # the next UTC day


def test_the_fourth_mail_to_one_address_in_a_day_is_not_sent_but_the_answer_is_the_same(env):
    answers = [env.join(client=env.at("203.0.113.%d" % i)) for i in range(1, 6)]
    assert {(r.status_code, r.text) for r in answers} == {(202, json.dumps(ACCEPTED, separators=(",", ":")))}
    assert len(env.mailer.sent) == 3
    assert env.confirm(env.token()).headers["location"] == LANDING + "/#confirmed"  # the third link still works
    env.now += DAY
    other = Env()
    other.join()
    other.now += DAY
    other.join()
    assert len(other.mailer.sent) == 2  # the cap is per UTC day


def test_the_counters_hold_no_address_and_no_ip(env):
    env.join()
    keys = [key for key, _ in env.counters._hits]  # the client, the address, and all mails per hour and day
    assert len(keys) == 4 and all(re.fullmatch(r"[0-9a-f]{64}", key) for key in keys)
    assert "ada" not in "".join(keys) and "203" not in "".join(keys)


# CORS ----------------------------------------------------------------------------------------------
CORS_HEADERS = ("access-control-allow-origin", "access-control-allow-methods", "access-control-allow-headers",
                "access-control-allow-credentials", "access-control-max-age")


def _cors(response):
    return {name: response.headers[name] for name in CORS_HEADERS if name in response.headers}


def test_the_landing_origin_may_post_and_nothing_allows_credentials(env):
    preflight = env.client.options("/early-bird", headers={
        "Origin": LANDING, "Access-Control-Request-Method": "POST", "Access-Control-Request-Headers": "content-type"})
    assert preflight.status_code == 204 and _cors(preflight) == {
        "access-control-allow-origin": LANDING, "access-control-allow-methods": "POST",
        "access-control-allow-headers": "Content-Type", "access-control-max-age": "600"}
    accepted = env.join(headers={"Origin": LANDING})
    assert accepted.status_code == 202 and _cors(accepted) == {"access-control-allow-origin": LANDING}
    assert "Origin" in accepted.headers["vary"]
    refused = env.client.post("/early-bird", json={"email": "bad"}, headers={"Origin": LANDING})
    assert refused.status_code == 422 and _cors(refused) == {"access-control-allow-origin": LANDING}


@pytest.mark.parametrize("origin", ["https://evil.example", LANDING + ".evil.example", "http://landing.example.test",
                                    LANDING + ":8443", "null", None])
def test_any_other_origin_gets_no_cors_header(env, origin):
    headers = {} if origin is None else {"Origin": origin}
    preflight = env.client.options("/early-bird", headers={**headers, "Access-Control-Request-Method": "POST"})
    assert preflight.status_code == 204 and _cors(preflight) == {}
    assert _cors(env.join(headers=headers)) == {}


def test_no_other_route_has_cors_headers(env):
    env.join()
    for method, path in (("GET", "/projects"), ("POST", "/session"), ("OPTIONS", "/session"),
                         ("OPTIONS", "/projects"), ("GET", "/early-bird/confirm?token=" + env.token()),
                         ("OPTIONS", "/early-bird/confirm"), ("OPTIONS", "/early-bird/"), ("GET", "/nothing")):
        r = env.client.request(method, path, headers={"Origin": LANDING, "Access-Control-Request-Method": "POST"})
        assert _cors(r) == {}, (method, path)
        if method == "OPTIONS":
            assert r.status_code in (307, 404, 405), path  # 307: the router's trailing-slash redirect


def test_with_no_landing_origin_configured_no_origin_is_allowed():
    env = Env(landing_url="")
    for origin in ("", "null", "https://landing.example.test"):
        assert _cors(env.client.options("/early-bird", headers={"Origin": origin})) == {}
        assert _cors(env.join(headers={"Origin": origin}, client=env.at("203.0.113.%d" % (len(origin) + 1)))) == {}


# Logs ----------------------------------------------------------------------------------------------
class FailingMailer:
    def send(self, to, subject, body):
        raise RuntimeError("could not deliver to %s: %s" % (to, body))


def _logged(action):
    stream, root = io.StringIO(), logging.getLogger()
    saved = list(root.handlers), root.level
    try:
        configure_logging(stream=stream)
        action()
    finally:
        root.handlers[:] = saved[0]
        root.setLevel(saved[1])
    return stream.getvalue()


def test_logs_hold_event_codes_and_never_the_address_token_or_link(env):
    def run():
        env.join(locale="de")
        env.join(locale="de")
        env.confirm(env.token())
        env.confirm(env.token())
        env.join(email="MARKER-bad")

    out = _logged(run)
    for event in ("early_bird_accepted locale=de", "early_bird_mail_sent locale=de", "early_bird_confirmed locale=de",
                  "early_bird_confirm_failed", "POST /early-bird 202", "POST /early-bird/confirm 303",
                  "POST /early-bird 422"):
        assert event in out, event
    for leak in (ADDRESS, "ada", "example.test", env.token(0), env.token(1), "token=", "MARKER", "203.0.113.5"):
        assert leak not in out, leak


def test_a_failed_send_still_answered_202_and_logs_only_an_event_code():
    env = Env(mailer=FailingMailer())
    out = _logged(lambda: env.__setattr__("answer", env.join()))
    assert env.answer.status_code == 202 and env.answer.json() == ACCEPTED
    assert "early_bird_mail_failed reason=RuntimeError" in out and "early_bird_mail_sent" not in out
    assert ADDRESS not in out and "token=" not in out and "could not deliver" not in out
    assert env.list.rows[ADDRESS]["confirmation_sent_at"] is None  # nothing was handed to a mail server


# No sender, no routes ------------------------------------------------------------------------------
def test_without_a_mail_sender_the_routes_are_not_served():
    settings = Settings(database_url="unused", s3_endpoint="unused", s3_access_key="x", s3_secret_key="x",
                        s3_bucket="x", dev_tokens=DEV_TOKENS, landing_url=LANDING)
    app = create_app(settings, SimpleNamespace(), MemoryObjectStore(), limiter=RateLimiter(MemoryCounters(), "k" * 32),
                     mailer=None, early_bird=MemoryEarlyBird())
    client = TestClient(app, raise_server_exceptions=False, follow_redirects=False)
    assert client.post("/early-bird", json={"email": ADDRESS, "locale": "en"}).status_code == 404
    assert client.get("/early-bird/confirm?token=" + "a" * 43).status_code == 404
    assert _cors(client.options("/early-bird", headers={"Origin": LANDING})) == {}
