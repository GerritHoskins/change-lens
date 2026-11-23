"""The early-bird list in one process, for tests without services: the same calls and rules as the
`early_bird_*` functions of migrations 0009 to 0011 (`Database` has them as methods)."""
from __future__ import annotations

import threading
import time
import uuid
from typing import Optional

from changelens.api.limits import DAY
from changelens.mail.confirmation import PENDING_DAYS


class MemoryEarlyBird:
    def __init__(self, clock=time.time):
        self.rows: dict = {}
        self._clock, self._lock = clock, threading.Lock()

    def _cutoff(self) -> float:
        return self._clock() - PENDING_DAYS * DAY

    def _expired(self, row: dict) -> bool:
        """A pending row's period runs from its creation or its newest mailed link, whichever is later."""
        return max(row["created_at"], row["token_issued_at"] or row["created_at"]) < self._cutoff()

    def early_bird_request(self, email: str, locale: str, hashed: str, max_mails: int) -> bool:
        with self._lock:
            now, row = self._clock(), self.rows.get(email)
            if row is None:
                self.rows[email] = {"id": uuid.uuid4(), "locale": locale, "status": "pending", "token_hash": None,
                                    "token_issued_at": None, "next_token_hash": hashed, "next_token_issued_at": now,
                                    "created_at": now, "confirmation_sent_at": None, "confirmed_at": None,
                                    "mail_count": 1}
                return True
            if row["status"] != "pending":
                return False
            if self._expired(row):  # maintenance has not deleted it yet: it starts again
                row.update(created_at=now, token_hash=None, token_issued_at=None, confirmation_sent_at=None,
                           mail_count=0)
            elif row["mail_count"] >= max_mails:
                return False
            row.update(locale=locale, next_token_hash=hashed, next_token_issued_at=now,
                       mail_count=row["mail_count"] + 1)
            return True

    def early_bird_mark_sent(self, hashed: str) -> None:
        with self._lock:
            for row in self.rows.values():
                if row["status"] != "pending" or hashed not in (row["token_hash"], row["next_token_hash"]):
                    continue
                if row["next_token_hash"] == hashed:  # its mail is out: it replaces the link mailed before
                    row.update(token_hash=hashed, token_issued_at=row["next_token_issued_at"],
                               next_token_hash=None, next_token_issued_at=None)
                row["confirmation_sent_at"] = self._clock()

    def early_bird_confirm(self, hashed: str) -> Optional[str]:
        with self._lock:
            cutoff = self._cutoff()
            for row in self.rows.values():
                if row["status"] != "pending":
                    continue
                if ((row["token_hash"] == hashed and row["token_issued_at"] >= cutoff)
                        or (row["next_token_hash"] == hashed and row["next_token_issued_at"] >= cutoff)):
                    row.update(status="confirmed", confirmed_at=self._clock(), token_hash=None,
                               token_issued_at=None, next_token_hash=None, next_token_issued_at=None)
                    return row["locale"]
        return None

    def early_bird_prune(self) -> int:
        with self._lock:
            gone = [email for email, row in self.rows.items() if row["status"] == "pending" and self._expired(row)]
            for email in gone:
                del self.rows[email]
            return len(gone)

    def early_bird_unsubscribe(self, signup_id: uuid.UUID) -> Optional[str]:
        with self._lock:
            for email, row in self.rows.items():
                if row["id"] == signup_id:
                    return self.rows.pop(email)["locale"]
        return None

    def early_bird_pending_days(self) -> int:
        return PENDING_DAYS
