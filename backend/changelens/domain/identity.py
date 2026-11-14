"""Pre-tenant identity for GUARD and `POST /session` (03a P0 and P1; I-8 S1 to S3).

These run before a tenant is known, so they live outside `TenantRepo`. In Postgres the app role has no
rights on `users` and sees only the current tenant's memberships, so `IdentityRepo` goes through the
`SECURITY DEFINER` functions `session_lookup` and `session_bootstrap` (migration 0003, 03 §6), which
return IDs and the role only. Keep every pre-tenant identity query here and nowhere else.

`ensure_member` is for `changelens.db seed-dev` and test fixtures, on an owner-role session.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from changelens.domain.models import Membership, User

log = logging.getLogger("changelens.identity")

ROLES = ("owner", "member")
MAX_SUBJECT = 200  # users.idp_subject


@dataclass(frozen=True)
class Principal:
    """The authenticated caller. The tenant always comes from the active membership, never the request."""
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    role: str


def _valid_subject(subject) -> bool:
    return isinstance(subject, str) and 0 < len(subject) <= MAX_SUBJECT


class IdentityRepo:
    def __init__(self, session: Session):
        self.s = session

    def principal(self, subject: str) -> Optional[Principal]:
        """GUARD steps 2-3: a live user and its active membership, or None. Runs on every request,
        because a deleted user can still hold valid cached tokens (D-8 side finding)."""
        if not _valid_subject(subject):
            return None
        row = self.s.execute(text("SELECT user_id, tenant_id, member_role FROM session_lookup(:subject)"),
                             {"subject": subject}).one_or_none()
        return Principal(row.user_id, row.tenant_id, row.member_role) if row else None

    def _bootstrap(self, subject: str, create: bool):
        return self.s.execute(text("SELECT outcome, user_id, tenant_id, member_role "
                                   "FROM session_bootstrap(:subject, :create)"),
                              {"subject": subject, "create": create}).one()

    def bootstrap(self, subject: str, before_create=None) -> Optional[Principal]:
        """03a P1 ON_SIGN_IN for email sign-in (I-8 S2): the existing account, or on the first call a new
        user, a new tenant and an active owner membership. Concurrent first calls end with one user (the
        function's insert waits on the unique subject and re-reads the winner).
        `before_create()` runs only on the first-sign-in branch (S6's sign-up cap hooks in there)."""
        if not _valid_subject(subject):
            return None
        row = self._bootstrap(subject, False)
        if row.outcome == "missing":
            if before_create is not None:
                before_create()
            row = self._bootstrap(subject, True)
        return self._principal_for(row.outcome, row)

    @staticmethod
    def _principal_for(outcome: str, row) -> Optional[Principal]:
        if outcome == "no_membership":
            log.warning("session rejected: no_active_membership")  # event code only, never the subject
            return None
        if outcome not in ("existing", "created"):
            return None  # deleted: no re-registration under a tombstone
        return Principal(row.user_id, row.tenant_id, row.member_role)

    def bind_tenant(self, tenant_id: uuid.UUID):
        """Once the tenant is known, continue in this transaction as `tenant_scope` would."""
        from changelens.domain import TenantRepo  # domain imports this module
        if self.s.get_bind().dialect.name == "postgresql":
            self.s.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_id)})
        return TenantRepo(self.s, tenant_id)


def user_by_subject(session: Session, subject: str) -> Optional[User]:
    return session.scalars(select(User).where(User.idp_subject == subject)).one_or_none()


def active_membership(session: Session, user_id: uuid.UUID) -> Optional[Membership]:
    return session.scalars(select(Membership).where(Membership.user_id == user_id,
                                                    Membership.status == "active")).one_or_none()


def ensure_member(session: Session, subject: str, tenant_id: uuid.UUID, role: str = "owner") -> User:
    """Create the user and an active membership if missing. Owner-role sessions only (dev seed and test
    fixtures; sign-up is `POST /session`). Refuses a user already active in another tenant."""
    if role not in ROLES or not isinstance(tenant_id, uuid.UUID):
        raise ValueError("invalid role or tenant")
    user = user_by_subject(session, subject)
    if user is None:
        user = User(idp_subject=subject)
        session.add(user)
        session.flush()
    active = active_membership(session, user.id)
    if active is not None and active.tenant_id != tenant_id:
        raise ValueError("the user is already active in another tenant")
    if active is None:
        row = session.get(Membership, (user.id, tenant_id))
        if row is None:
            session.add(Membership(user_id=user.id, tenant_id=tenant_id, role=role, status="active"))
        else:
            row.status, row.role = "active", role
        session.flush()
    return user
