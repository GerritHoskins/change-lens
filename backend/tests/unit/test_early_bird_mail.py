"""The early-bird confirmation mail: its wording per language, the SMTP sender against a fake server class,
and the settings that stop a deployment at start when the mail can't be sent."""
import smtplib

import pytest

from changelens.config import EARLY_BIRD_REQUIRED, NOT_FOR_THE_WORKER, Settings
from changelens.mail import MailError, RecordingMailer, mailer_for
from changelens.mail import smtp as smtp_module
from changelens.mail.confirmation import LOCALES, confirmation_mail
from changelens.mail.smtp import SmtpMailer
from helpers import EARLY_BIRD_ENV
from test_guard_logto import LOGTO, WORKER, _env

LINK = "https://api.example.test/early-bird/confirm?token=" + "t" * 43
ADDRESS = "ada@example.test"
BASE = dict(database_url="unused", s3_endpoint="unused", s3_access_key="x", s3_secret_key="x", s3_bucket="x")
SMTP = {"smtp_host": "smtp.example.test", "smtp_user": "noreply@example.test",
        "smtp_password": "smtp-password-0123", "mail_from": "noreply@example.test"}


# Wording -------------------------------------------------------------------------------------------
@pytest.mark.parametrize("locale, why, ignore, imprint", [
    ("en", "You are receiving this email because", "is deleted after 7 days", "[Placeholder:"),
    ("de", "Du erhältst diese E-Mail, weil", "wird nach 7 Tagen gelöscht", "[Platzhalter:"),
])
def test_the_mail_says_why_carries_the_link_and_what_ignoring_means(locale, why, ignore, imprint):
    subject, body = confirmation_mail(locale, LINK, 7)
    assert "ChangeLens" in subject and "\n" not in subject
    assert body.startswith(why) and body.count(LINK) == 1 and ignore in body and imprint in body
    assert "\n" + LINK + "\n" in body  # the link on a line of its own, so mail clients keep it whole
    text = (subject + body.replace(LINK, "")).lower()
    for marketing in ("%", "€", "eur", "discount", "rabatt", "price", "preis", "offer", "angebot", "http"):
        assert marketing not in text, marketing
    assert ADDRESS not in body  # the text never holds the recipient


def test_both_page_languages_have_a_mail_and_no_other():
    assert LOCALES == ("en", "de")
    assert confirmation_mail("en", LINK, 7) != confirmation_mail("de", LINK, 7)
    with pytest.raises(KeyError):
        confirmation_mail("fr", LINK, 7)


# The SMTP sender -----------------------------------------------------------------------------------
class FakeSmtp:
    calls: list = []
    fail_at = None

    def __init__(self, host, port, timeout=None):
        self.calls.append(("connect", host, port, timeout))

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.calls.append(("quit",))
        return False

    def _step(self, name, *detail):
        if self.fail_at == name:
            raise smtplib.SMTPException("550 no such user <%s>" % ADDRESS)
        self.calls.append((name, *detail))

    def starttls(self, context=None):
        self._step("starttls", context is not None and context.check_hostname)

    def login(self, user, password):
        self._step("login", user, password)

    def send_message(self, message, from_addr=None, to_addrs=None):
        self._step("send", from_addr, to_addrs, message)


@pytest.fixture()
def server(monkeypatch):
    FakeSmtp.calls, FakeSmtp.fail_at = [], None
    monkeypatch.setattr(smtp_module.smtplib, "SMTP", FakeSmtp)
    return FakeSmtp


def test_the_smtp_sender_encrypts_before_it_logs_in_and_sends_plain_text(server):
    mailer = SmtpMailer("smtp.example.test", 587, "user", "secret-password", "noreply@example.test")
    subject, body = confirmation_mail("de", LINK, 7)
    mailer.send(ADDRESS, subject, body)
    names = [call[0] for call in server.calls]
    assert names == ["connect", "starttls", "login", "send", "quit"]
    assert server.calls[0] == ("connect", "smtp.example.test", 587, 10.0)  # a timeout, always
    assert server.calls[1] == ("starttls", True)  # certificate and host name are checked
    assert server.calls[2] == ("login", "user", "secret-password")
    _, sender, recipients, message = server.calls[3]
    assert sender == "noreply@example.test" and recipients == [ADDRESS]
    assert message["To"] == ADDRESS and message["From"] == "ChangeLens <noreply@example.test>"
    assert message["Subject"] == subject and message["Auto-Submitted"] == "auto-generated"
    assert message.get_content_type() == "text/plain" and not message.is_multipart()
    assert message.get_content() == body
    assert "secret-password" not in repr(mailer)


@pytest.mark.parametrize("step", ["starttls", "login", "send"])
def test_a_failed_step_is_a_mail_error_that_names_only_the_exception_class(server, step):
    server.fail_at = step
    mailer = SmtpMailer("smtp.example.test", 587, "user", "secret-password", "noreply@example.test")
    with pytest.raises(MailError) as error:
        mailer.send(ADDRESS, "s", "b")
    assert error.value.reason == "SMTPException" and ADDRESS not in str(error.value)
    assert error.value.__cause__ is None and error.value.__suppress_context__  # the server's text is not chained
    assert "send" not in [call[0] for call in server.calls]  # nothing went out unencrypted or unauthenticated


def test_a_connection_failure_is_a_mail_error(monkeypatch):
    def refuse(*args, **kwargs):
        raise ConnectionRefusedError("refused")
    monkeypatch.setattr(smtp_module.smtplib, "SMTP", refuse)
    with pytest.raises(MailError) as error:
        SmtpMailer("smtp.example.test", 587, "u", "p", "noreply@example.test").send(ADDRESS, "s", "b")
    assert error.value.reason == "ConnectionRefusedError"


# Which sender a process gets -----------------------------------------------------------------------
def test_dev_mode_records_and_never_sends_even_with_smtp_settings():
    for settings in (Settings(**BASE), Settings(**BASE, **SMTP)):
        mailer = mailer_for(settings)
        assert isinstance(mailer, RecordingMailer)
        mailer.send(ADDRESS, "s", "b")
        assert [m.to for m in mailer.sent] == [ADDRESS]
    keeps = RecordingMailer(keep=2)
    for i in range(5):
        keeps.send("p%d@example.test" % i, "s", "b")
    assert [m.to for m in keeps.sent] == ["p3@example.test", "p4@example.test"]  # bounded


def test_logto_mode_sends_through_smtp_and_has_no_sender_without_settings():
    logto = dict(BASE, auth_mode="logto", logto_issuer="https://auth.example.test/oidc", logto_audience="a",
                 logto_jwks_url="https://auth.example.test/oidc/jwks")
    assert mailer_for(Settings(**logto)) is None
    configured = Settings(**logto, **SMTP, public_api_url="https://api.example.test",
                          landing_url="https://landing.example.test")
    assert isinstance(mailer_for(configured), SmtpMailer) and "smtp-password" not in repr(configured)
    with pytest.raises(ValueError):  # a sender without the URLs its mail and redirect need
        Settings(**logto, **SMTP)


# Settings ------------------------------------------------------------------------------------------
@pytest.mark.parametrize("value", [None, "   "])
@pytest.mark.parametrize("name", EARLY_BIRD_REQUIRED)
def test_a_deployment_without_a_mail_or_link_setting_does_not_start(monkeypatch, name, value):
    _env(monkeypatch, {**LOGTO, name: value})
    with pytest.raises(RuntimeError) as raised:
        Settings.from_env()
    message = str(raised.value)
    assert name in message
    assert not any(secret in message for secret in EARLY_BIRD_ENV.values())  # names only, never a value


def test_a_complete_deployment_loads_the_mail_settings_and_the_defaults(monkeypatch):
    assert set(EARLY_BIRD_REQUIRED) == set(EARLY_BIRD_ENV)
    _env(monkeypatch, {**LOGTO, "CHANGELENS_LANDING_URL": "https://landing.example.test/"})
    settings = Settings.from_env()
    assert (settings.smtp_host, settings.smtp_port, settings.smtp_user, settings.mail_from) == (
        "smtp.example.test", 587, "noreply@example.test", "noreply@example.test")
    assert settings.smtp_password == EARLY_BIRD_ENV["CHANGELENS_SMTP_PASSWORD"]
    assert settings.smtp_password not in repr(settings)
    assert (settings.public_api_url, settings.landing_url) == ("https://api.example.test",
                                                               "https://landing.example.test")
    assert (settings.early_bird_per_ip_per_day, settings.early_bird_mails_per_address_per_day,
            settings.early_bird_mails_per_hour, settings.early_bird_mails_per_day,
            settings.early_bird_mails_per_row) == (5, 3, 30, 200, 5)
    _env(monkeypatch, {**LOGTO, "CHANGELENS_SMTP_PORT": "2525", "CHANGELENS_EARLY_BIRD_PER_IP_PER_DAY": "9",
                       "CHANGELENS_EARLY_BIRD_MAILS_PER_ADDRESS_PER_DAY": "2",
                       "CHANGELENS_EARLY_BIRD_MAILS_PER_HOUR": "12", "CHANGELENS_EARLY_BIRD_MAILS_PER_DAY": "90",
                       "CHANGELENS_EARLY_BIRD_MAILS_PER_ROW": "4",
                       "CHANGELENS_EARLY_BIRD_PENDING_DAYS": "14"})  # no longer a setting: ignored
    settings = Settings.from_env()
    assert (settings.smtp_port, settings.early_bird_per_ip_per_day, settings.early_bird_mails_per_address_per_day,
            settings.early_bird_mails_per_hour, settings.early_bird_mails_per_day,
            settings.early_bird_mails_per_row) == (2525, 9, 2, 12, 90, 4)
    assert not hasattr(settings, "early_bird_pending_days")  # the period is fixed in the database


@pytest.mark.parametrize("values", [
    {"CHANGELENS_LANDING_URL": "http://landing.example.test"},          # not https
    {"CHANGELENS_LANDING_URL": "https://landing.example.test/de"},      # a path: not an origin
    {"CHANGELENS_LANDING_URL": "https://user@landing.example.test"},
    {"CHANGELENS_PUBLIC_API_URL": "api.example.test"},
    {"CHANGELENS_PUBLIC_API_URL": "https://api.example.test?x=1"},
    {"CHANGELENS_MAIL_FROM": "ChangeLens <noreply@example.test>"},      # the bare address only
    {"CHANGELENS_MAIL_FROM": "noreply"},
    {"CHANGELENS_SMTP_HOST": "smtp.example.test X"},
    {"CHANGELENS_SMTP_PORT": "0"}, {"CHANGELENS_SMTP_PORT": "smtp"},
    {"CHANGELENS_EARLY_BIRD_PER_IP_PER_DAY": "0"}, {"CHANGELENS_EARLY_BIRD_MAILS_PER_ADDRESS_PER_DAY": "-1"},
    {"CHANGELENS_EARLY_BIRD_MAILS_PER_HOUR": "0"}, {"CHANGELENS_EARLY_BIRD_MAILS_PER_DAY": "many"},
    {"CHANGELENS_EARLY_BIRD_MAILS_PER_ROW": "0"}, {"CHANGELENS_EARLY_BIRD_MAILS_PER_ROW": "101"},
])
def test_malformed_mail_and_link_settings_do_not_start(monkeypatch, values):
    _env(monkeypatch, {**LOGTO, **values})
    with pytest.raises(RuntimeError):
        Settings.from_env()


def test_dev_mode_needs_no_mail_setting_and_the_worker_holds_none(monkeypatch):
    _env(monkeypatch, {"CHANGELENS_ENV": "local", "CHANGELENS_DEV_TOKEN": "local-dev-token-0123456789"})
    dev = Settings.from_env()
    assert (dev.smtp_host, dev.landing_url, dev.public_api_url) == (None, "", "")
    assert "CHANGELENS_SMTP_PASSWORD" in NOT_FOR_THE_WORKER
    _env(monkeypatch, WORKER)
    worker = Settings.from_env(worker=True)  # starts without any of them
    assert (worker.smtp_host, worker.smtp_password, worker.mail_from) == (None, None, None)
    with pytest.raises(ValueError):
        Settings(**BASE, auth_mode="logto", worker=True, **SMTP)
