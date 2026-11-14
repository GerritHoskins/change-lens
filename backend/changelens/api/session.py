"""`POST /session` (03 §9.4, 03a P1; I-8 S2): the session bootstrap for email one-time-code sign-in.

The only authenticated route outside GUARD, because the user may not exist yet. The token is verified
exactly as GUARD's step 1 does. The first call for a subject creates the user, a new tenant and an
active owner membership; later calls return the same account. The response carries the onboarding
state read in the same transaction (O-23), and never an ID, subject, email or tenant.
Google, Apple and `link_required` are S4; invites are never built in v1.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Request

from changelens.api.auth import token_subject
from changelens.api.errors import ApiError
from changelens.api.limits import limit_ip, limit_signup
from changelens.api.onboarding import _state

router = APIRouter()


def _before_first_sign_in(request: Request):
    """Runs only when a new account is about to be created: the sign-up cap per IP (I-8 S6).
    Returning users never reach it."""
    limit_signup(request)


@router.post("/session")
def create_session(request: Request, body: Optional[dict] = Body(default=None)):
    limit_ip(request)
    if body:
        raise ApiError(422, "invalid_request", "send no body or {}")
    subject = token_subject(request)
    with request.app.state.db.identity_scope() as identities:
        principal = identities.bootstrap(subject, before_create=lambda: _before_first_sign_in(request))
        if principal is None:
            raise ApiError(401, "unauthenticated")
        repo = identities.bind_tenant(principal.tenant_id)
        onboarding = _state(repo.onboarding(principal.user_id))
    return {"status": "active", "onboarding": onboarding}
