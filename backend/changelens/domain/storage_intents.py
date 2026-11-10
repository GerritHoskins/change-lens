"""Durable object-write compensation, including unknown PUT/commit outcomes.

The uploader holds its request advisory lock from before prepare through the source transaction.
An independent transaction commits the intent before PUT. Reconciliation takes the same lock,
checks tenant-owned source references, then removes either only the intent or the exact orphan.
There is no attempt limit: a failed purge remains durable for the next worker run.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import logging
import uuid

from changelens.domain import comparison_lock_id
from changelens.domain.models import ObjectWriteIntent
from changelens.storage import original_key

log = logging.getLogger("changelens.storage.reconciliation")
# A lost DB connection releases the advisory lock even if a PUT is still in flight.
# This exceeds the write adapter's normal 5s connect/30s read timeouts and single HTTP attempt.
# It is not a server-side completion fence: unknown writes keep a recurring tombstone even
# after a successful purge, so a delayed PUT cannot become an untracked orphan.
UNKNOWN_WRITE_GRACE = timedelta(minutes=15)


def _now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class WriteTicket:
    id: uuid.UUID
    tenant_id: uuid.UUID
    object_key: str


def prepare_write(db, tenant_id: uuid.UUID, project_id: uuid.UUID, request_key: str) -> WriteTicket:
    ticket = WriteTicket(uuid.uuid4(), tenant_id, original_key(tenant_id, project_id))
    # Intentionally separate from the transaction that will reference the object. Rollback
    # or a process crash must not erase the only durable record of a possibly stored upload.
    with db.write_intent_scope(tenant_id) as repo:
        repo.add(ObjectWriteIntent(id=ticket.id, object_key=ticket.object_key,
            request_lock_id=comparison_lock_id(tenant_id, request_key),
            next_attempt_at=_now() + UNKNOWN_WRITE_GRACE, attempts=0, write_acknowledged=False))
    return ticket


def write_prepared(db, store, ticket: WriteTicket, data: bytes) -> None:
    store.put(ticket.object_key, data)
    with db.write_intent_scope(ticket.tenant_id) as repo:
        intent = repo.object_write_intent(ticket.id, lock=True)
        if intent is None:
            raise RuntimeError("object_write_intent_missing")
        intent.next_attempt_at = _now()
        intent.write_acknowledged = True


def _exact_tenant_leaf(key: str, tenant_id: uuid.UUID) -> bool:
    if not isinstance(key, str):
        return False
    parts = key.split("/")
    try:
        return (len(parts) == 3 and parts[0] == str(tenant_id)
                and all(str(uuid.UUID(part)) == part for part in parts))
    except (ValueError, AttributeError):
        return False


def reconcile_write(db, store, tenant_id: uuid.UUID, intent_id: uuid.UUID, *, now=None) -> bool:
    """Return True only when resolved. Errors, live writers and future retries keep the intent."""
    now = now or _now()
    try:
        with db.tenant_scope(tenant_id) as repo:
            intent = repo.object_write_intent(intent_id)
            if intent is None:
                return True
            if not repo.try_object_write_lock(intent.request_lock_id):
                return False
            # Refresh after acquiring the request lock: another reconciler may have changed
            # or removed this row while we waited between its first read and lock attempt.
            intent = repo.object_write_intent(intent_id, lock=True)
            if intent is None:
                return True
            if not _exact_tenant_leaf(intent.object_key, tenant_id):
                raise ValueError("invalid_object_write_scope")
            if repo.object_key_is_referenced(intent.object_key):
                repo.remove_object_write_intent(intent)
            elif intent.next_attempt_at > now:
                return False
            else:
                try:
                    store.delete_prefix(intent.object_key)
                except Exception:
                    intent.attempts += 1
                    intent.next_attempt_at = now + timedelta(seconds=min(3600, 30 * 2 ** min(intent.attempts - 1, 7)))
                    log.warning("object write cleanup deferred")
                    return False
                if intent.write_acknowledged:
                    repo.remove_object_write_intent(intent)
                else:
                    # A successful delete does not prove an unacknowledged PUT can no
                    # longer arrive. Keep checking this exact leaf, including all versions.
                    intent.attempts += 1
                    intent.next_attempt_at = now + timedelta(hours=1)
                    return False
        return True
    except Exception:
        # Never lose an intent on an unavailable DB or an uncertain deletion acknowledgement.
        # No object key, provider message or document content enters logs.
        log.warning("object write reconciliation deferred")
        return False


def reconcile_pending_writes(db, store, *, limit: int = 100, now=None) -> int:
    now = now or _now()
    try:
        pending = db.pending_object_writes(now, limit)
    except Exception:
        log.warning("object write reconciliation scan deferred")
        return 0
    return sum(reconcile_write(db, store, tenant, identifier, now=now) for tenant, identifier in pending)
