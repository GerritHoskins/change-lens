"""Pre-tenant identity lookups for GUARD (03a P0; I-8 S1).

These run before a tenant is known, so they live outside `TenantRepo`. They read through a plain
session for now; S3 replaces this module's queries with narrow `SECURITY DEFINER` functions (03 §6),
so keep every pre-tenant identity query here and nowhere else.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass
from typing import Optional

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from changelens.domain.models import Membership, User

log = logging.getLogger("changelens.identity")

ROLES = ("owner", "member")


@dataclass(frozen=True)
class Principal:
    """The authenticated caller. The tenant always comes from the active membership, never the request."""
    user_id: uuid.UUID
    tenant_id: uuid.UUID
    role: str


class IdentityRepo:
    def __init__(self, session: Session):
        self.s = session

    def user_by_subject(self, subject: str) -> Optional[User]:
        return self.s.scalars(select(User).where(User.idp_subject == subject)).one_or_none()

    def active_membership(self, user_id: uuid.UUID) -> Optional[Membership]:
        return self.s.scalars(select(Membership).where(Membership.user_id == user_id,
                                                       Membership.status == "active")).one_or_none()

    def principal(self, subject: str) -> Optional[Principal]:
        """GUARD steps 2-3: a live user and its active membership, or None. Runs on every request,
        because a deleted user can still hold valid cached tokens (D-8 side finding)."""
        user = self.user_by_subject(subject)
        if user is None or user.deleted_at is not None:
            return None
        membership = self.active_membership(user.id)
        if membership is None:
            return None
        return Principal(user.id, membership.tenant_id, membership.role)

    def bootstrap(self, subject: str, before_create=None) -> Optional[Principal]:
        """03a P1 ON_SIGN_IN for email sign-in (I-8 S2): the existing account, or on the first call a new
        user, a new tenant and an active owner membership. Concurrent first calls end with one user: the
        insert runs in a savepoint and a lost race re-reads the winner's committed rows.
        `before_create()` runs only on the first-sign-in branch (S6's sign-up cap hooks in there)."""
        user = self.user_by_subject(subject)
        if user is None:
            if before_create is not None:
                before_create()
            try:
                with self.s.begin_nested():
                    user = User(idp_subject=subject)
                    self.s.add(user)
                    self.s.flush()
                    self.s.add(Membership(user_id=user.id, tenant_id=uuid.uuid4(), role="owner", status="active"))
                    self.s.flush()
            except IntegrityError:
                self.s.expunge_all()
                user = self.user_by_subject(subject)
                if user is None:
                    return None
        if user.deleted_at is not None:
            return None  # no re-registration under a tombstone
        membership = self.active_membership(user.id)
        if membership is None:
            log.warning("session rejected: no_active_membership")  # event code only, never the subject
            return None
        return Principal(user.id, membership.tenant_id, membership.role)

    def bind_tenant(self, tenant_id: uuid.UUID):
        """Once the tenant is known, continue in this transaction as `tenant_scope` would."""
        from changelens.domain import TenantRepo  # domain imports this module
        if self.s.get_bind().dialect.name == "postgresql":
            self.s.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant_id)})
        return TenantRepo(self.s, tenant_id)

    def ensure_member(self, subject: str, tenant_id: uuid.UUID, role: str = "owner") -> User:
        """Create the user and an active membership if missing (dev seed and test fixtures only;
        sign-up is `POST /session`, S2). Refuses a user already active in another tenant."""
        if role not in ROLES or not isinstance(tenant_id, uuid.UUID):
            raise ValueError("invalid role or tenant")
        user = self.user_by_subject(subject)
        if user is None:
            user = User(idp_subject=subject)
            self.s.add(user)
            self.s.flush()
        active = self.active_membership(user.id)
        if active is not None and active.tenant_id != tenant_id:
            raise ValueError("the user is already active in another tenant")
        if active is None:
            row = self.s.get(Membership, (user.id, tenant_id))
            if row is None:
                self.s.add(Membership(user_id=user.id, tenant_id=tenant_id, role=role, status="active"))
            else:
                row.status, row.role = "active", role
            self.s.flush()
        return user
