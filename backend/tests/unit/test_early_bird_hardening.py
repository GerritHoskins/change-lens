"""The fixes of the early-bird security review of 2026-11-22 (docs/security-review.md, EB-1 to EB-13) with no
services: mail caps and how clients and addresses are counted, the confirm page, the mail queue and the SMTP
deadline, link tokens, the fixed pending period, retention's settings and the log fields. The Postgres side
is in tests/integration/test_early_bird_hardening_db.py."""
import importlib.util
import json
import threading
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from changelens.api.app import create_app
from changelens.api.early_bird import ACCEPTED, MAX_BODY, counter_address
from changelens.api.early_bird_memory import MemoryEarlyBird
from changelens.api.early_bird_pages import PAGE_HEADERS
from changelens.api.limits import MemoryCounters, RateLimiter, network_key
from changelens.config import EARLY_BIRD_REQUIRED, Settings
from changelens.mail import MailError, RecordingMailer
from changelens.mail.confirmation import PENDING_DAYS, confirmation_mail
from changelens.mail.queue import WAITING, WORKERS, InlineMailQueue, MailQueue
from changelens.mail.smtp import SmtpMailer
from changelens.storage import MemoryObjectStore
from helpers import DEV_TOKENS, EARLY_BIRD_ENV
from test_early_bird import ADDRESS, API, DAY, LANDING, Env, _logged
from test_early_bird_mail import FakeSmtp, server  # noqa: F401 (server is a fixture)
from test_guard_logto import LOGTO, _env

OK, FAILED = LANDING + "/#confirmed", LANDING + "/#confirm-failed"
FORM = {"Content-Type": "application/x-www-form-urlencoded"}
VERSIONS = Path(__file__).resolve().parents[2] / "migrations" / "versions"
ROOMY = dict(early_bird_per_ip_per_day=1000, early_bird_mails_per_address_per_day=1000)


def _ip(n):
    return "198.51.100.%d" % n


def _mail_threads():
    return [t for t in threading.enumerate() if t.name.startswith("changelens-mail")]


@pytest.fixture()
def env():
    return Env()


# EB-1 (M1): mail caps and what they count by -------------------------------------------------------
@pytest.mark.parametrize("setting, scope, window", [("early_bird_mails_per_hour", "all_hour", 3600),
                                                    ("early_bird_mails_per_day", "all_day", DAY)])
def test_mails_to_all_addresses_together_are_capped_and_the_answer_stays_the_same(setting, scope, window):
    env = Env(**{setting: 3})

    def run():
        return [env.join(email="person%d@example.test" % i, client=env.at(_ip(i))) for i in range(6)]

    answers = []
    out = _logged(lambda: answers.extend(run()))
    assert {(r.status_code, r.text) for r in answers} == {(202, json.dumps(ACCEPTED, separators=(",", ":")))}
    assert [m.to for m in env.mailer.sent] == ["person%d@example.test" % i for i in range(3)]
    assert sorted(env.list.rows) == ["person%d@example.test" % i for i in range(3)]  # over the cap: nothing changes
    assert out.count("early_bird_mail_capped scope=%s" % scope) == 3 and out.count("early_bird_mail_due") == 3
    assert out.count("early_bird_accepted locale=en") == 6
    env.now += window  # the next hour, or the next UTC day
    assert env.join(email="person9@example.test", client=env.at(_ip(9))).status_code == 202
    assert env.mailer.sent[-1].to == "person9@example.test"


def test_a_request_stopped_by_its_address_limit_does_not_use_up_the_limit_for_all():
    env = Env(early_bird_mails_per_address_per_day=1, early_bird_mails_per_hour=2)
    for i in range(5):
        env.join(client=env.at(_ip(i)))  # one address, five times: one mail, one count against the cap for all
    env.join(email="eve@example.test", client=env.at(_ip(9)))
    assert [m.to for m in env.mailer.sent] == [ADDRESS, "eve@example.test"]


@pytest.mark.parametrize("address, key", [
    ("203.0.113.5", "203.0.113.5"),
    ("2001:db8:1:2:3:4:5:6", "2001:db8:1:2::/64"),
    ("2001:db8:1:2::", "2001:db8:1:2::/64"),
    ("2001:db8:1:3::1", "2001:db8:1:3::/64"),
    ("::ffff:203.0.113.5", "203.0.113.5"),
    ("::1", "::/64"),
    ("", ""), ("testclient", "testclient"),
])
def test_an_ipv6_client_is_counted_by_its_64_network(address, key):
    assert network_key(address) == key


def test_one_ipv6_network_shares_the_daily_limit_and_another_has_its_own(env):
    for i in range(5):
        assert env.join(email="p%d@example.test" % i, client=env.at("2001:db8:aa:bb::%x" % (i + 1))).status_code == 202
    limited = env.join(email="p5@example.test", client=env.at("2001:db8:aa:bb:ffff:ffff:ffff:ffff"))
    assert limited.status_code == 429 and int(limited.headers["retry-after"]) > 0
    assert env.join(email="p6@example.test", client=env.at("2001:db8:aa:bc::1")).status_code == 202  # the next /64
    assert env.join(email="p7@example.test", client=env.at("203.0.113.6")).status_code == 202
    keys = "".join(key for key, _ in env.counters._hits)
    assert "2001" not in keys and "db8" not in keys  # hashes only


def test_the_link_routes_count_an_ipv6_client_by_network_and_the_sign_in_limit_does_not():
    env = Env(rate_limit_ip_per_minute=1)
    env.join()
    token = env.token()
    assert env.at("2001:db8:aa:bb::1").get("/early-bird/confirm", params={"token": token}).status_code == 200
    again = env.at("2001:db8:aa:bb::2").get("/early-bird/confirm", params={"token": token})
    assert again.status_code == 303 and again.headers["location"] == FAILED and "retry-after" in again.headers
    # A request that fails authentication is still counted by its exact address, as before this change.
    assert env.at("2001:db8:cc:dd::1").get("/projects").status_code == 401
    assert env.at("2001:db8:cc:dd::2").get("/projects").status_code == 401
    assert env.at("2001:db8:cc:dd::2").get("/projects").status_code == 429
    assert env.at("2001:db8:aa:bb::1").get("/projects").status_code == 401  # and in a scope of its own


@pytest.mark.parametrize("email, key", [
    ("ada@example.test", "ada@example.test"), ("ada+list@example.test", "ada@example.test"),
    ("ada+a+b@example.test", "ada@example.test"), ("+tag@example.test", "+tag@example.test"),
    ("ada.b@example.test", "ada.b@example.test"),
])
def test_the_address_counter_ignores_a_plus_tag(email, key):
    assert counter_address(email) == key


def test_tagged_addresses_share_one_mail_counter_and_are_stored_as_entered(env):
    for i in range(5):
        assert env.join(email="ada+%d@example.test" % i, client=env.at(_ip(i))).status_code == 202
    assert [m.to for m in env.mailer.sent] == ["ada+0@example.test", "ada+1@example.test", "ada+2@example.test"]
    assert sorted(env.list.rows) == ["ada+0@example.test", "ada+1@example.test", "ada+2@example.test"]
    assert env.join(email="eve+x@example.test", client=env.at(_ip(9))).status_code == 202
    assert env.mailer.sent[-1].to == "eve+x@example.test"


def test_a_pending_sign_up_gets_a_bounded_number_of_mails_and_starts_again_after_it_expired():
    env = Env(early_bird_mails_per_row=5, **ROOMY)
    answers = [env.join(client=env.at(_ip(i))) for i in range(8)]
    assert {(r.status_code, r.text) for r in answers} == {(202, json.dumps(ACCEPTED, separators=(",", ":")))}
    assert len(env.mailer.sent) == 5 and env.list.rows[ADDRESS]["mail_count"] == 5
    last = env.token()
    env.now += 3 * DAY
    env.join(client=env.at(_ip(20)))
    assert len(env.mailer.sent) == 5  # still the same pending sign-up: no sixth mail on another day
    assert env.confirm(last).headers["location"] == OK  # and its last link still works
    other = Env(early_bird_mails_per_row=2, **ROOMY)
    for i in range(4):
        other.join(client=other.at(_ip(i)))
    assert len(other.mailer.sent) == 2
    other.now += PENDING_DAYS * DAY + 1  # the sign-up expired; whether or not maintenance has deleted the row
    other.join(client=other.at(_ip(30)))
    assert len(other.mailer.sent) == 3 and other.list.rows[ADDRESS]["mail_count"] == 1
    assert other.confirm(other.token()).headers["location"] == OK


# EB-2 (M2): opening the link confirms nothing -----------------------------------------------------
def test_opening_the_confirmation_link_changes_nothing_and_shows_the_one_button_page(env):
    env.join(locale="de")
    token = env.token()
    before = dict(env.list.rows[ADDRESS])
    for _ in range(3):  # a mail scanner, more than once
        r = env.open(token)
        assert r.status_code == 200 and r.headers["content-type"] == "text/html; charset=utf-8"
    assert env.list.rows[ADDRESS] == before and before["status"] == "pending"
    for name, value in PAGE_HEADERS.items():
        assert r.headers[name] == value, name
    page = r.text
    assert page.count("<form") == 1 and '<form method="post">' in page and page.count("<button") == 1
    assert page.count(token) == 1 and '<input type="hidden" name="token" value="%s">' % token in page
    assert "Confirm" in page and "Bestätigen" in page and 'lang="de"' in page
    for absent in (ADDRESS, "ada", "example.test", "<script", "http:", "https:", "//", "url(", " src=", " href="):
        assert absent not in page.lower(), absent
    unknown = env.open("z" * 43)
    assert unknown.status_code == 200 and unknown.text == page.replace(token, "z" * 43)  # reveals nothing
    assert dict(unknown.headers) == dict(r.headers)


def test_the_confirm_and_unsubscribe_pages_are_one_page_with_different_words(env):
    from changelens.mail.unsubscribe import unsubscribe_token
    env.join()
    confirm = env.open(env.token())
    removal = env.client.get("/early-bird/unsubscribe", params={"token": unsubscribe_token(
        env.settings.early_bird_unsubscribe_key, env.list.rows[ADDRESS]["id"])})
    style = lambda page: page[page.index("<style>"):page.index("</style>")]
    assert style(confirm.text) == style(removal.text) and "min-height: 60px" in style(confirm.text)
    headers = lambda r: {k: v for k, v in r.headers.items() if k != "content-length"}
    assert headers(confirm) == headers(removal)


def test_the_form_post_confirms_once_and_only_with_the_token_in_the_form(env):
    env.join(locale="de")
    token = env.token()
    for refused in (env.client.post("/early-bird/confirm?token=" + token),                 # the link alone
                    env.client.post("/early-bird/confirm?token=" + token, content="other=1", headers=FORM),
                    env.client.post("/early-bird/confirm", json={"token": token}),
                    env.client.post("/early-bird/confirm", content="token=" + token, headers={"Content-Type": "text/plain"}),
                    env.client.post("/early-bird/confirm", content="token=%s&pad=%s" % (token, "x" * MAX_BODY),
                                    headers=FORM)):
        assert refused.status_code == 303 and refused.headers["location"] == FAILED
    assert env.list.rows[ADDRESS]["status"] == "pending"
    first = env.client.post("/early-bird/confirm", content="token=" + token, headers=FORM)
    assert first.status_code == 303 and first.headers["location"] == LANDING + "/de/#confirmed" and first.text == ""
    assert first.headers["referrer-policy"] == "no-referrer" and token not in first.headers["location"]
    assert env.list.rows[ADDRESS]["status"] == "confirmed"
    again = env.client.post("/early-bird/confirm", content="token=" + token, headers=FORM)
    assert again.headers["location"] == FAILED
    assert env.client.options("/early-bird/confirm", headers={"Origin": LANDING}).status_code == 405  # no CORS


def test_the_mail_says_to_press_the_button():
    for locale, words in (("en", "press the button on the page"), ("de", "drücke auf der Seite den Button")):
        assert words in confirmation_mail(locale, "https://api.example.test/x")[1]


# EB-3 (M3): the mail queue and the time one send can take -------------------------------------------
def test_the_mail_queue_runs_two_at_a_time_holds_a_bounded_number_and_refuses_the_rest():
    assert (WORKERS, WAITING) == (2, 50)
    queue, release, started, done = MailQueue(workers=2, waiting=3), threading.Event(), threading.Semaphore(0), []

    def send(n):
        started.release()
        release.wait(5)
        done.append(n)

    try:
        accepted = [queue.submit(send, n) for n in range(8)]
        assert accepted == [True] * 5 + [False] * 3  # two running, three waiting, the rest refused at once
        assert started.acquire(timeout=5) and started.acquire(timeout=5) and not started.acquire(timeout=0.2)
        assert len(_mail_threads()) == 2
    finally:
        release.set()
        queue.shutdown()
    assert sorted(done) in ([0, 1], [0, 1, 2], [0, 1, 2, 3], [0, 1, 2, 3, 4])  # waiting ones may be dropped at shutdown
    assert {0, 1} <= set(done) and _mail_threads() == []
    assert queue.submit(send, 9) is False and 9 not in done  # shut down: refused, not run


def test_a_full_queue_frees_its_places_as_sends_finish():
    queue, release, started = MailQueue(workers=1, waiting=0), threading.Event(), threading.Event()
    try:
        assert queue.submit(lambda: (started.set(), release.wait(5))) is True
        assert started.wait(5) and queue.submit(lambda: None) is False
        release.set()
        for _ in range(200):
            if queue.submit(lambda: None):
                break
            threading.Event().wait(0.01)
        else:
            pytest.fail("the place of a finished send was not freed")
    finally:
        release.set()
        queue.shutdown()
    assert _mail_threads() == []


class FullQueue:
    def submit(self, task, *args):
        return False

    def shutdown(self):
        pass


def test_a_full_queue_drops_the_mail_logs_it_and_keeps_the_link_mailed_before():
    env = Env(**ROOMY)
    env.join()
    first = env.token()
    env.app.state.mail_queue = FullQueue()
    out = _logged(lambda: env.__setattr__("answer", env.join(client=env.at(_ip(1)))))
    assert env.answer.status_code == 202 and env.answer.json() == ACCEPTED and len(env.mailer.sent) == 1
    assert "early_bird_mail_failed reason=queue_full" in out and "early_bird_mail_sent" not in out
    assert ADDRESS not in out and "token" not in out
    assert env.confirm(first).headers["location"] == OK


def test_the_app_sends_from_the_queue_threads_and_ends_them_with_the_app():
    settings = Settings(database_url="unused", s3_endpoint="unused", s3_access_key="x", s3_secret_key="x",
                        s3_bucket="x", dev_tokens=DEV_TOKENS, landing_url=LANDING, public_api_url=API)
    seen, mailer = [], RecordingMailer()

    class Noting(RecordingMailer):
        def send(self, to, subject, body):
            seen.append(threading.current_thread().name)
            mailer.send(to, subject, body)

    app = create_app(settings, object(), MemoryObjectStore(), limiter=RateLimiter(MemoryCounters(), "k" * 32),
                     mailer=Noting(), early_bird=MemoryEarlyBird())
    assert isinstance(app.state.mail_queue, MailQueue) and _mail_threads() == []  # no thread before the first mail
    with TestClient(app, raise_server_exceptions=False) as client:
        assert client.post("/early-bird", json={"email": ADDRESS, "locale": "en"}).status_code == 202
    assert [m.to for m in mailer.sent] == [ADDRESS]  # leaving the app waits for the running send
    assert len(seen) == 1 and seen[0].startswith("changelens-mail") and _mail_threads() == []
    without = create_app(settings, object(), MemoryObjectStore(), limiter=RateLimiter(MemoryCounters(), "k" * 32),
                         mailer=None, early_bird=MemoryEarlyBird())
    assert without.state.mail_queue is None  # no sender, no queue
    with TestClient(without):
        pass


@pytest.mark.parametrize("late_after, reached", [("connect", ["connect", "quit"]),
                                                 ("starttls", ["connect", "starttls", "quit"]),
                                                 ("login", ["connect", "starttls", "login", "quit"])])
def test_a_send_gives_up_between_steps_once_its_deadline_has_passed(server, late_after, reached):  # noqa: F811
    now = [0.0]
    mailer = SmtpMailer("smtp.example.test", 587, "user", "secret-password", "noreply@example.test",
                        deadline=30.0, clock=lambda: now[0])
    real = server._step

    def slow(self, name, *detail):
        real(self, name, *detail)
        if name == late_after:
            now[0] += 31.0

    server._step = slow
    connect = server.__init__

    def slow_connect(self, host, port, timeout=None):
        connect(self, host, port, timeout)
        if late_after == "connect":
            now[0] += 31.0

    server.__init__ = slow_connect
    try:
        with pytest.raises(MailError) as error:
            mailer.send(ADDRESS, "s", "b")
    finally:
        server._step, server.__init__ = real, connect
    assert error.value.reason == "TimeoutError" and [call[0] for call in server.calls] == reached
    now[0] = 0.0
    mailer.send(ADDRESS, "s", "b")  # in time: every step runs
    assert [call[0] for call in server.calls][len(reached):] == ["connect", "starttls", "login", "send", "quit"]
    assert server.calls[len(reached)][3] == 10.0  # each socket operation has its own timeout


# EB-4 and EB-5 (L1, L2): link tokens ---------------------------------------------------------------
class FailingAfter(RecordingMailer):
    """Sends the first `ok` mails, then fails."""

    def __init__(self, ok):
        super().__init__()
        self.ok = ok

    def send(self, to, subject, body):
        if len(self.sent) >= self.ok:
            raise MailError("SMTPException")
        super().send(to, subject, body)


def test_a_new_token_whose_mail_was_not_sent_does_not_end_the_link_mailed_before():
    env = Env(mailer=FailingAfter(1), **ROOMY)
    env.join()
    first = env.token()
    env.join(client=env.at(_ip(1)))  # this mail fails
    row = env.list.rows[ADDRESS]
    assert len(env.mailer.sent) == 1 and row["token_hash"] is not None and row["next_token_hash"] is not None
    assert env.confirm(first).headers["location"] == OK
    assert env.list.rows[ADDRESS]["next_token_hash"] is None  # confirmation clears both


def test_a_mailed_token_replaces_the_one_before_only_when_its_mail_is_out(env):
    env.join()
    env.join()
    first, second = env.token(0), env.token(1)
    assert env.list.rows[ADDRESS]["next_token_hash"] is None  # promoted when the second mail went out
    assert env.confirm(first).headers["location"] == FAILED and env.confirm(second).headers["location"] == OK


def test_a_sent_mail_whose_record_failed_still_has_a_working_link(env):
    def broken(hashed):
        raise RuntimeError("database down for %s" % ADDRESS)

    env.list.early_bird_mark_sent = broken
    out = _logged(env.join)
    assert len(env.mailer.sent) == 1 and "early_bird_mail_failed reason=RuntimeError" in out
    assert env.list.rows[ADDRESS]["token_hash"] is None  # never promoted
    assert env.confirm(env.token()).headers["location"] == OK


def test_a_link_lives_for_the_period_from_when_it_was_issued_not_from_the_first_request():
    env = Env(**ROOMY)
    env.join()
    first = env.token()
    env.now += 6 * DAY
    env.join(client=env.at(_ip(1)))
    second = env.token()
    env.now += 6 * DAY  # day 12 of the sign-up, day 6 of the second link
    assert env.list.early_bird_prune() == 0  # the last mail said "deleted after 7 days"
    assert env.open(second).status_code == 200 and env.confirm(first).headers["location"] == FAILED
    assert env.confirm(second).headers["location"] == OK
    late = Env(**ROOMY)
    late.join()
    late.now += 6 * DAY
    late.join(client=late.at(_ip(1)))
    late.now += PENDING_DAYS * DAY + 1  # the second link's own period is over
    assert late.confirm(late.token()).headers["location"] == FAILED
    assert late.list.early_bird_prune() == 1 and not late.list.rows


# EB-6 (L3): the pending period is not a setting -----------------------------------------------------
def test_the_pending_period_is_one_constant_that_the_migration_and_the_mail_share(monkeypatch):
    spec = importlib.util.spec_from_file_location("hardening", VERSIONS / "0011_early_bird_hardening.py")
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    assert migration.PENDING_DAYS == PENDING_DAYS == MemoryEarlyBird().early_bird_pending_days() == 7
    for signature, body in migration.FUNCTIONS.items():  # no function takes the period as an argument
        assert "p_pending_days" not in body and "days" not in signature.split("(", 1)[1], signature
    assert "is deleted after %d days" % PENDING_DAYS in confirmation_mail("en", "https://api.example.test/x")[1]
    assert "early_bird_pending_days" not in Settings.__dataclass_fields__
    with pytest.raises(TypeError):
        Settings(database_url="u", s3_endpoint="u", s3_access_key="x", s3_secret_key="x", s3_bucket="x",
                 early_bird_pending_days=30)
    _env(monkeypatch, {**LOGTO, "CHANGELENS_EARLY_BIRD_PENDING_DAYS": "365"})
    Settings.from_env()  # the old variable is not read: no error and no effect


# EB-7 (L4): retention holds no mail setting --------------------------------------------------------
def test_retention_starts_without_any_mail_setting_and_the_api_does_not(monkeypatch):
    _env(monkeypatch, {**LOGTO, **dict.fromkeys(EARLY_BIRD_ENV)})
    with pytest.raises(RuntimeError) as raised:
        Settings.from_env()
    assert all(name in str(raised.value) for name in EARLY_BIRD_REQUIRED)
    retention = Settings.from_env(mail=False)
    assert (retention.auth_mode, retention.smtp_host, retention.smtp_password, retention.mail_from) == (
        "logto", None, None, None)
    assert retention.logto_m2m_app_id == "m2m-app"  # it still deletes Logto users: those settings stay required
    _env(monkeypatch, LOGTO)  # one env file for both, as deployed: retention does not read the mail lines
    retention = Settings.from_env(mail=False)
    assert (retention.smtp_host, retention.smtp_password, retention.public_api_url) == (None, None, "")
    assert retention.early_bird_unsubscribe_key != EARLY_BIRD_ENV["CHANGELENS_EARLY_BIRD_UNSUBSCRIBE_KEY"]
    assert Settings.from_env().smtp_password == EARLY_BIRD_ENV["CHANGELENS_SMTP_PASSWORD"]


# EB-9, EB-10, EB-11 (L6, N1, N2): logs and the order of counting ------------------------------------
class Leaky(Exception):
    reason = "could not deliver to ada@example.test"


@pytest.mark.parametrize("error, logged", [(MailError("SMTPException"), "reason=SMTPException"),
                                           (Leaky("ada@example.test"), "reason=Leaky"),
                                           (OSError("ada@example.test"), "reason=OSError")])
def test_only_a_mail_error_has_its_reason_logged(error, logged):
    class Failing:
        def send(self, to, subject, body):
            raise error

    env = Env(mailer=Failing())
    out = _logged(env.join)
    assert "early_bird_mail_failed " + logged in out
    assert ADDRESS not in out and "could not deliver" not in out


def test_a_request_is_counted_before_its_body_is_read():
    env = Env(early_bird_per_ip_per_day=2)
    big = json.dumps({"email": ADDRESS, "locale": "en", "pad": "x" * MAX_BODY})
    for _ in range(2):
        assert env.client.post("/early-bird", content=big, headers={"Content-Type": "application/json"}).status_code == 413
    limited = env.join()
    assert limited.status_code == 429 and not env.list.rows and not env.mailer.sent
    over = env.client.post("/early-bird", content=big, headers={"Content-Type": "application/json"})
    assert over.status_code == 429  # the limit answers before the size does
    link = Env(rate_limit_ip_per_minute=1)
    link.join()
    assert link.client.post("/early-bird/confirm", content="x" * (MAX_BODY + 1), headers=FORM).status_code == 303
    limited = link.confirm(link.token())
    assert limited.headers["location"] == FAILED and "retry-after" in limited.headers


def test_accepted_counts_every_valid_request_and_mail_due_only_the_ones_that_issue_a_link():
    env = Env(early_bird_mails_per_address_per_day=2, early_bird_per_ip_per_day=1000)

    def run():
        env.join(locale="de")                    # new: a mail is due
        env.join(locale="de")                    # pending: due again
        env.join(locale="de")                    # over the address limit
        env.confirm(env.token())
        env.now += DAY
        env.join(locale="de")                    # confirmed: accepted, nothing due
        env.join(email="MARKER-bad")             # invalid: not accepted

    out = _logged(run)
    assert out.count("early_bird_accepted locale=de") == 4 and out.count("early_bird_mail_due locale=de") == 2
    assert out.count("early_bird_mail_sent locale=de") == 2 and out.count("early_bird_mail_capped scope=address") == 1
    assert out.count("early_bird_confirmed locale=de") == 1 and "MARKER" not in out and ADDRESS not in out


def test_the_inline_queue_runs_the_send_before_it_returns():
    ran = []
    assert InlineMailQueue().submit(ran.append, 1) is True and ran == [1]
