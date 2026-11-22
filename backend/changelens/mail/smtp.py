"""The SMTP sender for the `mail` port: standard library only, STARTTLS with certificate checks, a timeout.

One connection per message to the configured host; there is no fallback to an unencrypted session (a
server without STARTTLS is a failed send). Failures become `MailError` carrying the exception's class
name only, and nothing is logged here.
"""
from __future__ import annotations

import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr, formatdate, make_msgid

from changelens.mail import MailError

SENDER_NAME = "ChangeLens"


class SmtpMailer:
    def __init__(self, host: str, port: int, user: str, password: str, sender: str, timeout: float = 10.0):
        self._host, self._port, self._user, self._password = host, port, user, password
        self._sender, self._timeout = sender, timeout

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
        try:
            message = self.message(to, subject, body)
            with smtplib.SMTP(self._host, self._port, timeout=self._timeout) as smtp:
                smtp.starttls(context=ssl.create_default_context())
                smtp.login(self._user, self._password)
                smtp.send_message(message, from_addr=self._sender, to_addrs=[to])
        except (smtplib.SMTPException, OSError, ValueError) as exc:
            raise MailError(type(exc).__name__) from None
