"""Removal from the early-bird list with no services: the link's token, the two public routes on the
in-memory list, the key setting and the owner's export command. The Postgres function and the owner's read
path are checked in tests/integration/test_early_bird_unsubscribe_db.py."""
import csv
import hashlib
import hmac
import io
import re
import uuid
from datetime import datetime, timezone

import pytest

from changelens import early_bird_export
from changelens.api.early_bird_unsubscribe import MAX_BODY, PAGE_HEADERS
from changelens.config import EARLY_BIRD_REQUIRED, NOT_FOR_THE_WORKER, Settings
from changelens.mail import unsubscribe as tokens
from changelens.mail.unsubscribe import list_headers, unsubscribe_token, unsubscribe_url, verify_unsubscribe_token
from helpers import EARLY_BIRD_ENV
from test_early_bird import ADDRESS, API, LANDING, Env, _cors, _logged
from test_guard_logto import LOGTO, _env

PATH = "/early-bird/unsubscribe"
KEY = "k" * 40
ID = uuid.UUID("3f2b8c1e-5a47-4d09-9e6b-0c1d2e3f4a5b")
GONE, FAILED = LANDING + "/#unsubscribed", LANDING + "/#unsubscribe-failed"
FORM = {"Content-Type": "application/x-www-form-urlencoded"}
BASE = dict(database_url="unused", s3_endpoint="unused", s3_access_key="x", s3_secret_key="x", s3_bucket="x")


def _joined(env, email=ADDRESS, locale="en", confirm=True):
    """One address on the list; returns its removal token."""
    env.join(email=email, locale=locale, client=env.at("203.0.113.%d" % (len(env.list.rows) + 10)))
    if confirm:
        env.confirm(env.token())
    return unsubscribe_token(env.settings.early_bird_unsubscribe_key, env.list.rows[email]["id"])


def _post_form(env, token):
    return env.client.post(PATH, content="token=" + token, headers=FORM)


@pytest.fixture()
def env():
    return Env()


# The token -----------------------------------------------------------------------------------------
def test_a_token_is_the_id_and_a_mac_over_it_with_a_prefix():
    token = unsubscribe_token(KEY, ID)
    assert re.fullmatch(r"%s\.[0-9a-f]{64}" % ID, token)
    assert verify_unsubscribe_token(KEY, token) == ID
    mac = token.split(".")[1]
    assert mac == hmac.new(KEY.encode(), b"early-bird-unsubscribe:" + str(ID).encode(), hashlib.sha256).hexdigest()
    assert mac != hmac.new(KEY.encode(), str(ID).encode(), hashlib.sha256).hexdigest()  # the prefix is in the MAC
    assert unsubscribe_token(KEY, ID) == token  # nothing random, nothing stored
    with pytest.raises(TypeError):
        unsubscribe_token(KEY, str(ID))


def test_a_tampered_mac_another_id_and_another_key_are_refused():
    token = unsubscribe_token(KEY, ID)
    other = uuid.uuid4()
    mac = token.split(".")[1]
    flipped = mac[:-1] + ("0" if mac[-1] != "0" else "1")
    assert verify_unsubscribe_token(KEY, "%s.%s" % (ID, flipped)) is None
    assert verify_unsubscribe_token(KEY, "%s.%s" % (other, mac)) is None  # this MAC belongs to another row
    assert verify_unsubscribe_token(KEY, "%s.%s" % (ID, "0" * 64)) is None
    assert verify_unsubscribe_token("j" * 40, token) is None
    assert verify_unsubscribe_token(KEY, unsubscribe_token(KEY, other)) == other


@pytest.mark.parametrize("change", [
    lambda t: "", lambda t: t.upper(), lambda t: t + "\n", lambda t: " " + t, lambda t: t + "0", lambda t: t[:-1],
    lambda t: t.replace(".", ""), lambda t: t.replace(".", ".."), lambda t: t.replace("-", ""),
    lambda t: t.split(".")[0], lambda t: "." + t.split(".")[1], lambda t: t.replace(".", "%2E"),
    lambda t: "{%s}.%s" % tuple(t.split(".")), lambda t: t.encode(), lambda t: None, lambda t: [t], lambda t: 7,
    lambda t: t + "&token=" + t, lambda t: "x" * 5000,
])
def test_anything_but_the_exact_format_is_refused_before_the_mac_is_computed(monkeypatch, change):
    token = unsubscribe_token(KEY, ID)
    monkeypatch.setattr(tokens, "_mac", lambda *args: pytest.fail("the MAC was computed for a malformed token"))
    assert verify_unsubscribe_token(KEY, change(token)) is None


def test_the_mac_is_compared_in_constant_time(monkeypatch):
    seen, real = [], hmac.compare_digest

    def compare(a, b):
        seen.append((a, b))
        return real(a, b)

    monkeypatch.setattr(tokens.hmac, "compare_digest", compare)
    token = unsubscribe_token(KEY, ID)
    mac = token.split(".")[1]
    assert verify_unsubscribe_token(KEY, token) == ID
    assert verify_unsubscribe_token(KEY, "%s.%s" % (ID, "a" * 64)) is None
    assert seen == [(mac, mac), ("a" * 64, mac)]


def test_the_link_and_the_two_list_headers():
    url = unsubscribe_url(API + "/", KEY, ID)
    assert url == API + PATH + "?token=" + unsubscribe_token(KEY, ID)
    assert list_headers(url) == {"List-Unsubscribe": "<%s>" % url,
                                 "List-Unsubscribe-Post": "List-Unsubscribe=One-Click"}


# GET: the page, and nothing else -------------------------------------------------------------------
@pytest.mark.parametrize("confirm", [True, False])
def test_get_shows_a_page_and_never_removes(env, confirm):
    token = _joined(env, confirm=confirm)
    before = dict(env.list.rows[ADDRESS])
    for _ in range(3):  # a mail scanner opening the link, more than once
        r = env.client.get(PATH, params={"token": token})
        assert r.status_code == 200 and r.headers["content-type"] == "text/html; charset=utf-8"
    assert env.list.rows[ADDRESS] == before
    for name, value in PAGE_HEADERS.items():
        assert r.headers[name] == value, name
    assert r.headers["content-security-policy"] == (
        "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'; base-uri 'none'; frame-ancestors 'none'")
    assert (r.headers["referrer-policy"], r.headers["cache-control"], r.headers["x-content-type-options"]) == (
        "no-referrer", "no-store", "nosniff")


def test_the_page_has_one_post_form_no_address_no_script_and_loads_nothing(env):
    token = _joined(env, locale="de")
    page = env.client.get(PATH, params={"token": token}).text
    assert page.startswith("<!doctype html>\n<html lang=\"en\">") and 'lang="de"' in page
    assert '<meta name="robots" content="noindex">' in page and "prefers-color-scheme: dark" in page
    assert page.count("<form") == 1 and '<form method="post">' in page and page.count("<button") == 1
    assert page.count(token) == 1 and '<input type="hidden" name="token" value="%s">' % token in page
    lowered = page.lower()
    for absent in (ADDRESS, "ada", "example.test", "<script", "javascript:", "http:", "https:", "//", "url(",
                   "@import", "<link", "<img", "<iframe", "roboto", " src=", " href=", " action="):
        assert absent not in lowered, absent
    assert not re.search(r"\son[a-z]+\s*=", lowered)  # no inline event handler
    assert "system-ui" in page and "min-height: 60px" in page and "border-radius: 999px" in page


def test_the_page_is_the_same_whether_or_not_the_address_is_still_on_the_list(env):
    token = _joined(env)
    on_the_list = env.client.get(PATH, params={"token": token})
    assert _post_form(env, token).headers["location"] == GONE and not env.list.rows
    removed = env.client.get(PATH, params={"token": token})
    never = env.client.get(PATH, params={"token": unsubscribe_token(env.settings.early_bird_unsubscribe_key, ID)})
    assert on_the_list.status_code == removed.status_code == never.status_code == 200
    assert on_the_list.text == removed.text and len(never.text) == len(removed.text)
    assert dict(on_the_list.headers) == dict(removed.headers) == dict(never.headers)


# POST: removal -------------------------------------------------------------------------------------
@pytest.mark.parametrize("locale, target", [("en", "/#unsubscribed"), ("de", "/de/#unsubscribed")])
@pytest.mark.parametrize("confirm", [True, False])
def test_the_form_post_removes_the_row_and_redirects_by_language(env, locale, target, confirm):
    token = _joined(env, locale=locale, confirm=confirm)
    _joined(env, email="eve@example.test")
    r = _post_form(env, token)
    assert r.status_code == 303 and r.headers["location"] == LANDING + target and r.text == ""
    assert r.headers["referrer-policy"] == "no-referrer" and r.headers["cache-control"] == "no-store"
    assert token not in r.headers["location"]
    assert list(env.list.rows) == ["eve@example.test"]  # that row and no other


@pytest.mark.parametrize("kwargs", [
    dict(content="List-Unsubscribe=One-Click", headers=FORM),               # RFC 8058, urlencoded
    dict(files={"List-Unsubscribe": (None, "One-Click")}),                  # RFC 8058, multipart
    dict(),                                                                 # no body at all
    dict(content="token=not-the-token", headers=FORM),                      # the query string decides
])
def test_one_click_posts_to_the_link_itself_and_the_token_comes_from_the_query(env, kwargs):
    token = _joined(env, locale="de")
    r = env.client.post(PATH + "?token=" + token, **kwargs)
    assert r.status_code == 303 and r.headers["location"] == LANDING + "/de/#unsubscribed" and not env.list.rows


def test_an_address_already_removed_gets_the_same_answer_and_can_join_again(env):
    token = _joined(env, locale="de")
    assert _post_form(env, token).headers["location"] == LANDING + "/de/#unsubscribed"
    again = _post_form(env, token)
    assert again.status_code == 303 and again.headers["location"] == GONE  # the language went with the row
    newer = _joined(env)  # the same address, a new row and a new link
    assert newer != token and _post_form(env, token).headers["location"] == GONE
    assert env.list.rows[ADDRESS]["status"] == "confirmed"  # the old link doesn't reach the new row
    assert _post_form(env, newer).headers["location"] == GONE and not env.list.rows


BAD = ["", "short", "a" * 101, "%3Cscript%3E", str(ID), str(ID) + "." + "0" * 64, str(ID).upper() + "." + "a" * 64]


@pytest.mark.parametrize("bad", BAD)
def test_an_invalid_token_redirects_on_both_routes_and_removes_nothing(env, bad):
    _joined(env)
    answers = [env.client.get(PATH + "?token=" + bad), env.client.get(PATH), env.client.get(PATH + "?other=1"),
               env.client.post(PATH + "?token=" + bad), env.client.post(PATH),
               env.client.post(PATH, content="token=" + bad, headers=FORM)]
    for r in answers:
        assert r.status_code == 303 and r.headers["location"] == FAILED and r.text == ""
        assert "json" not in r.headers.get("content-type", "") and r.headers["referrer-policy"] == "no-referrer"
    assert env.list.rows[ADDRESS]["status"] == "confirmed"


def test_a_token_from_another_key_or_with_a_changed_mac_removes_nothing(env):
    token = _joined(env)
    signup_id = env.list.rows[ADDRESS]["id"]
    flipped = token[:-1] + ("0" if token[-1] != "0" else "1")
    as_counter_key = env.app.state.limiter.key_hash("early-bird-unsubscribe", str(signup_id))  # the other HMAC key
    for forged in (unsubscribe_token("another-key-" + "0" * 32, signup_id), flipped,
                   "%s.%s" % (signup_id, as_counter_key)):
        assert env.client.get(PATH, params={"token": forged}).headers["location"] == FAILED
        assert _post_form(env, forged).headers["location"] == FAILED
        assert env.client.post(PATH, params={"token": forged}).headers["location"] == FAILED
    assert ADDRESS in env.list.rows


def test_the_form_field_is_read_strictly(env):
    token = _joined(env)
    for kwargs in (dict(content="token=" + token, headers={"Content-Type": "text/plain"}),
                   dict(json={"token": token}),
                   dict(files={"token": (None, token)}),                               # multipart: not the form
                   dict(content="token=%s&token=%s" % (token, token), headers=FORM),   # the field twice
                   dict(content="token=" + token.replace(".", "%2E"), headers=FORM),   # nothing is decoded
                   dict(content="token=" + token + "&pad=" + "x" * MAX_BODY, headers=FORM),
                   dict(content=b"token=\xff\xfe", headers=FORM),
                   dict(content="Token=" + token, headers=FORM)):
        r = env.client.post(PATH, **kwargs)
        assert r.status_code == 303 and r.headers["location"] == FAILED, kwargs
    assert ADDRESS in env.list.rows
    oversized = env.client.post(PATH + "?token=" + token, content="x" * (MAX_BODY + 1), headers=FORM)
    assert oversized.headers["location"] == FAILED and ADDRESS in env.list.rows  # the cap holds for one-click too
    ok = env.client.post(PATH, content="other=1&token=" + token,
                         headers={"Content-Type": "application/x-www-form-urlencoded; charset=UTF-8"})
    assert ok.headers["location"] == GONE and not env.list.rows


def test_a_failing_list_redirects_and_logs_only_the_error_class(env):
    token = _joined(env)

    def broken(signup_id):
        raise RuntimeError("could not delete %s for %s" % (signup_id, ADDRESS))

    env.list.early_bird_unsubscribe = broken
    out = _logged(lambda: env.__setattr__("answer", _post_form(env, token)))
    assert env.answer.status_code == 303 and env.answer.headers["location"] == FAILED
    assert "early_bird_unsubscribe_error reason=RuntimeError" in out and "early_bird_unsubscribed" not in out
    assert ADDRESS not in out and "could not delete" not in out and str(env.list.rows[ADDRESS]["id"]) not in out


# Limits, CORS, logs --------------------------------------------------------------------------------
def test_both_routes_are_limited_per_ip_with_a_redirect_and_retry_after():
    env = Env(rate_limit_ip_per_minute=3)
    token = _joined(env)
    assert env.confirm("b" * 43).status_code == 303  # the confirm route shares the per-minute counter
    assert env.client.get(PATH, params={"token": token}).status_code == 200
    for limited in (env.client.get(PATH, params={"token": token}), _post_form(env, token),
                    env.client.post(PATH, params={"token": token})):
        assert limited.status_code == 303 and limited.headers["location"] == FAILED
        assert int(limited.headers["retry-after"]) > 0 and limited.headers["referrer-policy"] == "no-referrer"
    assert ADDRESS in env.list.rows
    env.now += 60  # the next minute: the link still works
    assert _post_form(env, token).headers["location"] == GONE and not env.list.rows
    other = Env(rate_limit_ip_per_minute=1)
    token = _joined(other)
    other.now += 60
    assert _post_form(other, token).headers["location"] == GONE  # another address has its own counter
    assert other.at("203.0.113.77").get(PATH, params={"token": token}).status_code == 200


def test_the_removal_routes_have_no_cors_headers(env):
    token = _joined(env)
    origin = {"Origin": LANDING, "Access-Control-Request-Method": "POST"}
    preflight = env.client.options(PATH, headers=origin)
    assert preflight.status_code == 405 and _cors(preflight) == {}
    for r in (env.client.get(PATH, params={"token": token}, headers=origin),
              env.client.get(PATH, headers=origin),
              env.client.post(PATH, headers=origin),
              env.client.post(PATH, content="token=" + token, headers={**FORM, **origin})):
        assert _cors(r) == {} and "origin" not in r.headers.get("vary", "").lower()
    assert not env.list.rows


def test_logs_hold_event_codes_and_the_language_and_never_an_id_address_or_token(env):
    tokens_seen, ids = [], []

    def run():
        for locale in ("de", "en"):
            tokens_seen.append(_joined(env, email="%s@example.test" % locale, locale=locale))
            ids.append(str(env.list.rows["%s@example.test" % locale]["id"]))
        env.client.get(PATH, params={"token": tokens_seen[0]})
        env.client.post(PATH, params={"token": tokens_seen[0]})
        _post_form(env, tokens_seen[1])
        _post_form(env, tokens_seen[1])  # already removed
        env.client.get(PATH, params={"token": "MARKER"})
        env.client.post(PATH, content="token=MARKER", headers=FORM)

    out = _logged(run)
    for event in ("early_bird_unsubscribed locale=de", "early_bird_unsubscribed locale=en",
                  "early_bird_unsubscribed locale=none", "early_bird_unsubscribe_failed",
                  "GET /early-bird/unsubscribe 200", "GET /early-bird/unsubscribe 303",
                  "POST /early-bird/unsubscribe 303"):
        assert event in out, event
    assert out.count("early_bird_unsubscribe_failed") == 2
    for leak in (*tokens_seen, *ids, *(t.split(".")[1] for t in tokens_seen), "example.test", "token=", "MARKER",
                 "203.0.113"):
        assert leak not in out, leak


def test_without_a_mail_sender_the_removal_routes_are_not_served():
    from test_early_bird import MemoryCounters, MemoryEarlyBird, MemoryObjectStore, RateLimiter, SimpleNamespace
    from test_early_bird import DEV_TOKENS, TestClient, create_app
    settings = Settings(**BASE, dev_tokens=DEV_TOKENS, landing_url=LANDING)
    app = create_app(settings, SimpleNamespace(), MemoryObjectStore(), limiter=RateLimiter(MemoryCounters(), "k" * 32),
                     mailer=None, early_bird=MemoryEarlyBird())
    client = TestClient(app, raise_server_exceptions=False, follow_redirects=False)
    token = unsubscribe_token(settings.early_bird_unsubscribe_key, ID)
    assert client.get(PATH, params={"token": token}).status_code == 404
    assert client.post(PATH, params={"token": token}).status_code == 404


# The key -------------------------------------------------------------------------------------------
def test_the_key_is_its_own_required_setting_never_printed_and_not_for_the_worker(monkeypatch):
    name = "CHANGELENS_EARLY_BIRD_UNSUBSCRIBE_KEY"
    assert name in EARLY_BIRD_REQUIRED and name in NOT_FOR_THE_WORKER
    _env(monkeypatch, LOGTO)
    settings = Settings.from_env()
    assert settings.early_bird_unsubscribe_key == EARLY_BIRD_ENV[name] != settings.rate_limit_key
    assert EARLY_BIRD_ENV[name] not in repr(settings)
    _env(monkeypatch, {**LOGTO, name: "x" * 31})
    with pytest.raises(RuntimeError) as raised:
        Settings.from_env()
    assert "unsubscribe key" in str(raised.value) and "x" * 31 not in str(raised.value)
    with pytest.raises(ValueError):
        Settings(**BASE, early_bird_unsubscribe_key="short")
    dev = Settings(**BASE)
    assert len(dev.early_bird_unsubscribe_key) >= 32 and dev.early_bird_unsubscribe_key != dev.rate_limit_key


# The owner's export --------------------------------------------------------------------------------
EXPORT_ENV = {"CHANGELENS_MIGRATION_DATABASE_URL": "postgresql+psycopg://changelens_owner:owner-pw-0123@db/changelens",
              "CHANGELENS_PUBLIC_API_URL": API, "CHANGELENS_EARLY_BIRD_UNSUBSCRIBE_KEY": KEY}
WHEN = datetime(2026, 11, 22, 9, 30, tzinfo=timezone.utc)


def test_the_export_writes_confirmed_rows_with_their_links_as_csv():
    other = uuid.uuid4()
    rows = [(ID, "ada@example.test", "en", WHEN), (other, "=sum+1@example.test", "de", WHEN)]
    out = io.StringIO()
    assert early_bird_export.write_csv(rows, API, KEY, out) == (2, 1)
    read = list(csv.reader(io.StringIO(out.getvalue())))
    assert read[0] == ["email", "locale", "confirmed_at", "unsubscribe_url"]
    assert read[1] == ["ada@example.test", "en", "2026-11-22T09:30:00+00:00", unsubscribe_url(API, KEY, ID)]
    assert read[2] == ["=sum+1@example.test", "de", "2026-11-22T09:30:00+00:00", unsubscribe_url(API, KEY, other)]
    token = read[1][3].split("token=")[1]
    assert verify_unsubscribe_token(KEY, token) == ID  # the api accepts what the export wrote
    assert str(ID) not in out.getvalue().replace(read[1][3], "")  # the id appears in the link only


def test_the_export_command_prints_the_list_to_stdout_and_only_a_count_to_stderr(monkeypatch):
    seen = []
    monkeypatch.setattr(early_bird_export, "confirmed_rows",
                        lambda url: seen.append(url) or [(ID, ADDRESS, "en", WHEN)])
    out, err = io.StringIO(), io.StringIO()
    assert early_bird_export.main([], EXPORT_ENV, out, err) == 0
    assert seen == [EXPORT_ENV["CHANGELENS_MIGRATION_DATABASE_URL"]]
    assert out.getvalue().splitlines()[1].startswith(ADDRESS + ",en,") and len(out.getvalue().splitlines()) == 2
    assert err.getvalue() == "early_bird_export rows=1 formula_start=0\n"
    assert early_bird_export.main(["--all"], EXPORT_ENV, out, err) == 2


@pytest.mark.parametrize("change, named", [
    ({"CHANGELENS_MIGRATION_DATABASE_URL": None}, "CHANGELENS_MIGRATION_DATABASE_URL"),
    ({"CHANGELENS_MIGRATION_DATABASE_URL": "  "}, "CHANGELENS_MIGRATION_DATABASE_URL"),
    ({"CHANGELENS_PUBLIC_API_URL": None}, "CHANGELENS_PUBLIC_API_URL"),
    ({"CHANGELENS_PUBLIC_API_URL": "http://api.example.test"}, "CHANGELENS_PUBLIC_API_URL"),
    ({"CHANGELENS_PUBLIC_API_URL": API + "/v1"}, "CHANGELENS_PUBLIC_API_URL"),
    ({"CHANGELENS_EARLY_BIRD_UNSUBSCRIBE_KEY": None}, "CHANGELENS_EARLY_BIRD_UNSUBSCRIBE_KEY"),
    ({"CHANGELENS_EARLY_BIRD_UNSUBSCRIBE_KEY": "s" * 31}, "CHANGELENS_EARLY_BIRD_UNSUBSCRIBE_KEY"),
])
def test_the_export_refuses_to_run_without_what_it_needs_and_names_no_value(monkeypatch, change, named):
    monkeypatch.setattr(early_bird_export, "confirmed_rows", lambda url: pytest.fail("the list was read"))
    env = {k: v for k, v in {**EXPORT_ENV, **change}.items() if v is not None}
    out, err = io.StringIO(), io.StringIO()
    assert early_bird_export.main([], env, out, err) == 1
    assert out.getvalue() == "" and err.getvalue().startswith("Not exported: ") and named in err.getvalue()
    for value in ("owner-pw-0123", KEY, "s" * 31):
        assert value not in err.getvalue()


def test_the_export_has_local_defaults_only_with_the_local_marker():
    with pytest.raises(early_bird_export.Refused):
        early_bird_export.settings_from_env({"CHANGELENS_PUBLIC_API_URL": API})
    url, base, key = early_bird_export.settings_from_env({"CHANGELENS_ENV": "local",
                                                          "CHANGELENS_PUBLIC_API_URL": "http://127.0.0.1:8000/"})
    assert "changelens_owner" in url and base == "http://127.0.0.1:8000"
    assert key == Settings(**BASE).early_bird_unsubscribe_key


def test_a_failed_database_read_prints_only_the_error_class(monkeypatch):
    def broken(url):
        raise RuntimeError("could not connect with " + url)

    monkeypatch.setattr(early_bird_export, "confirmed_rows", broken)
    out, err = io.StringIO(), io.StringIO()
    assert early_bird_export.main([], EXPORT_ENV, out, err) == 1
    assert out.getvalue() == "" and err.getvalue() == "Not exported: RuntimeError\n"
