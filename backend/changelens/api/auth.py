"""Dev-token authentication (I-22 only; never deployed publicly).

The tenant comes from the token, never from the request body. I-8 replaces this dependency with
Logto JWT verification and the GUARD membership lookup (03a P0); routes keep receiving a tenant ID.
"""
from __future__ import annotations

import hmac
import uuid

from fastapi import Request

from changelens.api.errors import ApiError


def current_tenant(request: Request) -> uuid.UUID:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise ApiError(401, "unauthenticated")
    tenant = None
    for known, tid in request.app.state.settings.dev_tokens.items():
        # Compare against every token so timing does not reveal which prefix matched.
        if hmac.compare_digest(known.encode(), token.strip().encode()):
            tenant = tid
    if tenant is None:
        raise ApiError(401, "unauthenticated")
    return tenant
