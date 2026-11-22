"""The `mail` port and a recording sender (the early-bird list's confirmation mail).

The port is one call: a recipient, a subject and a plain-text body. The SMTP sender is
`changelens.mail.smtp`; `logto` mode uses it and `dev` mode never does: there the recording sender keeps
the last few messages in memory and sends nothing. Nothing here logs a recipient, a subject or a body.
"""
from __future__ import annotations

import threading
from collections import deque
from typing import NamedTuple, Optional, Protocol


class MailError(Exception):
    """A message was not handed to the mail server. `reason` is an exception class name, never text from
    the server: an SMTP reply can quote the recipient."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


class MailPort(Protocol):
    def send(self, to: str, subject: str, body: str) -> None:
        """Hand one plain-text message to the mail server, or raise `MailError`."""
        ...


class Message(NamedTuple):
    to: str
    subject: str
    body: str


class RecordingMailer:
    """Dev mode and tests: keeps the newest messages in memory, sends nothing."""

    def __init__(self, keep: int = 20):
        self.sent: deque = deque(maxlen=keep)
        self._lock = threading.Lock()

    def send(self, to: str, subject: str, body: str) -> None:
        with self._lock:
            self.sent.append(Message(to, subject, body))


def mailer_for(settings) -> Optional[MailPort]:
    """The process's sender: recording in dev mode whatever else is set, SMTP in logto mode. None in logto
    mode without SMTP settings, which `Settings.from_env` refuses, so a deployment always has a sender;
    without one the early-bird routes are not served at all."""
    if settings.auth_mode == "dev":
        return RecordingMailer()
    if not settings.smtp_host:
        return None
    from changelens.mail.smtp import SmtpMailer  # the only module that opens a mail connection
    return SmtpMailer(settings.smtp_host, settings.smtp_port, settings.smtp_user, settings.smtp_password,
                      settings.mail_from)
