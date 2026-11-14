"""GUARD (03a P0; I-8 S1): every authenticated route resolves a `Principal` here.

1. The bearer token becomes a subject: a Logto access token verified offline against the configured
   JWKS (`logto` mode), or a dev token matched to its fixed subject (`dev` mode, local and tests only).
2. The subject must belong to a user that isn't deleted, checked on every request (D-8 side finding).
3. The user must have an active membership; the tenant comes from it, never from the request.
4. Any failure is `401 unauthenticated` with `WWW-Authenticate: Bearer`, and the body never says which
   step failed. Nothing here logs the token or the subject.
"""
from __future__ import annotations

import hmac
import uuid

from fastapi import Depends, Request

from changelens.api.errors import ApiError
from changelens.auth.jwt_verifier import AccessTokenRejected
from changelens.domain.identity import Principal

MAX_TOKEN_CHARS = 16384


def _unauthenticated() -> ApiError:
    return ApiError(401, "unauthenticated")


def _subject(request: Request) -> str:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    token = token.strip()
    if scheme.lower() != "bearer" or not token or len(token) > MAX_TOKEN_CHARS:
        raise _unauthenticated()
    settings = request.app.state.settings
    if settings.auth_mode == "dev":
        subject = None
        for known, candidate in settings.dev_tokens.items():
            # Compare against every token so timing does not reveal which prefix matched.
            if hmac.compare_digest(known.encode(), token.encode()):
                subject = candidate
        if subject is None:
            raise _unauthenticated()
        return subject
    try:
        return request.app.state.keys.verify(token).subject
    except AccessTokenRejected:
        raise _unauthenticated() from None


def current_principal(request: Request) -> Principal:
    subject = _subject(request)
    with request.app.state.db.identity_scope() as identities:
        principal = identities.principal(subject)
    if principal is None:
        raise _unauthenticated()
    return principal


def current_tenant(principal: Principal = Depends(current_principal)) -> uuid.UUID:
    """The routes' tenant, from the active membership only."""
    return principal.tenant_id
