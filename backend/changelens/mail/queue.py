"""The api's mail queue: confirmation mails go out on two threads of their own, never on the request threads.

An SMTP send can take tens of seconds (`changelens/mail/smtp.py` says how long). On the shared request
thread pool a slow or stuck mail server would hold the threads every route needs. Here at most `workers`
sends run at once and at most `waiting` more wait; one beyond that is refused (`submit` returns False) and
the caller logs `early_bird_mail_failed reason=queue_full`. Nothing is retried and nothing is stored: a
dropped mail means the person asks again.

`shutdown` runs with the app (its lifespan): sends that have not started are dropped, the ones running are
waited for. Threads start with the first mail, so an app that never sends has none.
"""
from __future__ import annotations

import threading
from concurrent.futures import ThreadPoolExecutor

WORKERS, WAITING = 2, 50


class MailQueue:
    def __init__(self, workers: int = WORKERS, waiting: int = WAITING):
        self._executor = ThreadPoolExecutor(max_workers=workers, thread_name_prefix="changelens-mail")
        self._slots = threading.BoundedSemaphore(workers + waiting)  # running plus waiting

    def submit(self, task, *args) -> bool:
        """Queue one send. False when the queue is full or shut down: the task will not run."""
        if not self._slots.acquire(blocking=False):
            return False
        try:
            future = self._executor.submit(task, *args)
        except RuntimeError:  # shut down
            self._slots.release()
            return False
        future.add_done_callback(lambda _: self._slots.release())  # also when cancelled at shutdown
        return True

    def shutdown(self) -> None:
        self._executor.shutdown(wait=True, cancel_futures=True)


class InlineMailQueue:
    """Tests: the send runs in the caller's thread before `submit` returns, so nothing is left running."""

    def submit(self, task, *args) -> bool:
        task(*args)
        return True

    def shutdown(self) -> None:
        pass
