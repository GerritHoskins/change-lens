"""The SMTP sender for the `mail` port: standard library only, STARTTLS with certificate checks, a timeout.

One connection per message to the configured host; there is no fallback to an unencrypted session (a
server without STARTTLS is a failed send). Failures become `MailError` carrying the exception's class
name only, and nothing is logged here.

How long one message can take: every socket operation has `timeout` seconds (10), and between the steps
(connect, STARTTLS, login, send) the sender checks an overall `deadline` (30 s) and gives up once it has
passed. That is not a hard limit, because `smtplib` has none: a step that began before the deadline runs to
its end, a step is several socket operations of up to `timeout` each (sending is four commands and the
message), and the timeout applies per read, so a server that trickles a reply can stretch one read. In
practice the worst case is the deadline plus one step. Sends run on the mail queue's two workers
(`changelens/mail/queue.py`), never on the request threads.
"""
from __future__ import annotations

import smtplib
import ssl
import time
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid

from changelens.mail import MailError

SENDER_NAME = "ChangeLens"


class SmtpMailer:
    def __init__(self, host: str, port: int, user: str, password: str, sender: str, timeout: float = 10.0,
                 deadline: float = 30.0, clock=time.monotonic):
        self._host, self._port, self._user, self._password = host, port, user, password
        self._sender, self._timeout, self._deadline, self._clock = sender, timeout, deadline, clock

    def __repr__(self) -> str:  # never the password
        return "SmtpMailer(%s:%d)" % (self._host, self._port)

    def message(self, to: str, subject: str, body: str) -> EmailMessage:
        message = EmailMessage()
        message["From"] = formataddr((SENDER_NAME, self._sender))
        message["To"] = to
        message["Subject"] = subject
        message["Date"] = formatdate(localtime=False)
        message["Message-ID"] = make_msgid(domain=self._sender.rsplit("@", 1)[-1])
        message["Auto-Submitted"] = "auto-generated"  # RFC 3834: no out-of-office replies
        message.set_content(body)
        return message

    def send(self, to: str, subject: str, body: str) -> None:
        give_up_at = self._clock() + self._deadline

        def in_time() -> None:
            if self._clock() > give_up_at:
                raise TimeoutError("deadline")  # an OSError: becomes MailError("TimeoutError") below

        try:
            message = self.message(to, subject, body)
            with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as smtp:
                in_time()
                smtp.starttls(context=ssl.create_default_context())
                in_time()
                smtp.login(self._user, self._password)
                in_time()
                smtp.send_message(message, from_addr=self._sender, to_addrs=[to])
        except (smtplib.SMTPException, OSError, ValueError) as exc:
            raise MailError(type(exc).__name__) from None
