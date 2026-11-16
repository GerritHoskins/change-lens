"""`POST /session` (03 §9.4, 03a P1; I-8 S2, S4): session bootstrap, the only route outside GUARD.

With a bearer (a Logto access token, verified exactly as GUARD's step 1): body none, `{}` or
`{"link_id": ...}`. The first call for a subject creates the user, a new tenant and an active owner
membership; later calls return the same account. With `link_id`, the Google or Apple identity of that
pending link is linked to this user first, only if this user is the link's target, before expiry and
once (O-19); anything else is `401` and the link is gone. A parked Apple token is then attached to the
user row. The response carries the onboarding state read in the same transaction (O-23).

Without a bearer: native Google or Apple sign-in, body `{"provider": "google" | "apple", "code": ...,
"nonce": ...}` (nonce optional; Apple: the raw value whose SHA-256 the app gave Apple). The backend
exchanges the code, then answers `{"status": "sign_in", "one_time_token", "login_hint", "expires_in"}` for
Logto's normal sign-in (where MFA applies), or `{"status": "link_required", "methods", "link_id"}` when
the identity is new and a Logto user has the same verified email (nothing is signed in or created).

Responses never carry an ID, subject or tenant; the sign-in response carries the account's own email as
`login_hint`, to the holder of a verified provider identity of that account only. Error bodies never echo
the request. Invites are never built in v1.
"""
from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Body, Request

from changelens.api.auth import token_subject
from changelens.api.errors import ApiError
from changelens.api.limits import limit_ip, limit_signup, limit_signup_idp
from changelens.api.onboarding import _state
from changelens.auth.logto_management import IdpUnavailable
from changelens.auth.social import ProviderRejected, ProviderUnavailable, valid_nonce
from changelens.domain.social import (LinkRejected, attach_parked, complete_link, provider_sign_in, take_link)

router = APIRouter()
MAX_FIELD = 4096


def _before_first_sign_in(request: Request):
    """Runs only when a new account is about to be created: the sign-up cap per IP (I-8 S6).
    Returning users never reach it."""
    limit_signup(request)


def _unavailable() -> ApiError:
    return ApiError(503, "provider_unavailable", headers={"Retry-After": "30"})


@router.post("/session")
def create_session(request: Request, body: Optional[dict] = Body(default=None)):
    limit_ip(request)
    if "authorization" not in request.headers and isinstance(body, dict) and "provider" in body:
        return _provider_session(request, body)
    link_id = None
    if body:
        if not isinstance(body, dict) or set(body) != {"link_id"} or not isinstance(body["link_id"], str) \
                or not 1 <= len(body["link_id"]) <= 64:
            raise ApiError(422, "invalid_request", "send no body, {} or {link_id}")
        link_id = body["link_id"]
    subject = token_subject(request)
    state = request.app.state
    link = None
    if link_id is not None:
        try:
            link = take_link(state.db, subject, link_id)
        except LinkRejected:
            raise ApiError(401, "unauthenticated") from None
    with state.db.identity_scope() as identities:
        principal = identities.bootstrap(subject, before_create=lambda: _before_first_sign_in(request))
        if principal is not None:
            repo = identities.bind_tenant(principal.tenant_id)
            onboarding = _state(repo.onboarding(principal.user_id))
    if principal is None:
        if link is not None and link[2] is not None:
            with state.db.social_scope() as social:
                social.expire_park(link[2][0])
        raise ApiError(401, "unauthenticated")
    park = None
    if link is not None:
        provider, provider_subject, park = link
        try:
            complete_link(state.db, state.idp, subject, provider, provider_subject, park)
        except LinkRejected:
            raise ApiError(401, "unauthenticated") from None
        except IdpUnavailable:
            raise _unavailable() from None
    attach_parked(state.db, state.apple, principal.user_id, subject, park)
    return {"status": "active", "onboarding": onboarding}


def _provider_session(request: Request, body: dict) -> dict:
    if (not set(body) <= {"provider", "code", "nonce"} or not {"provider", "code"} <= set(body)
            or not all(isinstance(v, str) and 1 <= len(v) <= MAX_FIELD for v in body.values())
            or ("nonce" in body and not valid_nonce(body["nonce"]))):
        raise ApiError(422, "invalid_request", "send {provider, code} and an optional nonce")
    state = request.app.state
    provider = state.providers.get(body["provider"])
    if provider is None or state.idp is None or not hasattr(state.idp, "one_time_token"):
        raise ApiError(422, "invalid_request", "this sign-in method is not available")
    try:
        return provider_sign_in(state.db, state.idp, provider, state.apple, body["code"], body.get("nonce"),
                                before_create=lambda: limit_signup_idp(request))
    except ProviderRejected:
        raise ApiError(401, "unauthenticated") from None
    except (ProviderUnavailable, IdpUnavailable):
        raise _unavailable() from None
