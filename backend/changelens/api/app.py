"""FastAPI application factory for the `api` process (03 §9.1). Auth is GUARD (`api.auth`, I-8 S1)."""
from __future__ import annotations

import logging
from typing import Optional

from fastapi import FastAPI
from starlette.datastructures import MutableHeaders
from starlette.formparsers import MultiPartParser

from changelens.api import errors
from changelens.api.errors import ApiError, problem
from changelens.api.reviews import router as review_router
from changelens.api.comparisons import router as comparison_router
from changelens.api.onboarding import router as onboarding_router
from changelens.api.consent import router as consent_router
from changelens.api.retention import router as retention_router
from changelens.api.routes import router
from changelens.api.session import router as session_router
from changelens.api.account import router as account_router
from changelens.api.early_bird import EarlyBirdCors, MemoryEarlyBird, router as early_bird_router
from changelens.auth.jwks import JwksKeyHolder
from changelens.auth.jwt_verifier import JwtPolicy
from changelens.api.limits import MemoryCounters, RateLimiter
from changelens.auth.logto_management import idp_for
from changelens.domain.social import social_for
from changelens.config import Settings
from changelens.domain import Database
from changelens.mail import mailer_for
from changelens.storage import ObjectStore, S3ObjectStore

_DEFAULT = object()

access_log = logging.getLogger("changelens.access")

# Multipart overhead allowed on top of the largest permitted document.
_OVERHEAD = 64 * 1024


class NoStoreMiddleware:
    """Retention covers the primary stores; API responses must not create an HTTP cache."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        async def no_store(message):
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message)["Cache-Control"] = "no-store"
            await send(message)

        await self.app(scope, receive, no_store)


class AccessLogMiddleware:
    """Logs `method route-template status` only: no query string, client address or body."""

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        status = {"code": 500}

        async def _send(message):
            if message["type"] == "http.response.start":
                status["code"] = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, _send)
        finally:
            route = getattr(scope.get("route"), "path", "<unmatched>")
            access_log.info("%s %s %s", scope["method"], route, status["code"])


class BodyLimitMiddleware:
    """Rejects bodies over the cap before or while they are read (AC-20), so nothing large is buffered."""

    def __init__(self, app, max_bytes: int):
        self.app, self.max_bytes = app, max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        # The atomic compare request can contain two inputs. All other uploads retain
        # their original one-document cap; each slot is also validated independently.
        path = scope.get("path", "").strip("/").split("/")
        pair = scope.get("method") == "POST" and len(path) == 3 and path[0] == "projects" and path[2] == "comparisons"
        max_bytes = self.max_bytes * (2 if pair else 1)
        length = dict(scope["headers"]).get(b"content-length")
        if length is not None and (not length.isdigit() or int(length) > max_bytes):
            return await problem(413, "limit_exceeded", "bytes")(scope, receive, send)
        seen = {"n": 0}

        async def _receive():
            message = await receive()
            if message["type"] == "http.request":
                seen["n"] += len(message.get("body", b""))
                if seen["n"] > max_bytes:
                    raise ApiError(413, "limit_exceeded", "bytes")
            return message

        await self.app(scope, _receive, send)


def create_app(settings: Settings, db: Optional[Database] = None, store: Optional[ObjectStore] = None,
               keys: Optional[JwksKeyHolder] = None, idp=_DEFAULT, limiter: Optional[RateLimiter] = None,
               providers=_DEFAULT, apple=_DEFAULT, mailer=_DEFAULT, early_bird=None) -> FastAPI:
    max_body = max(settings.limits.max_pdf_bytes, settings.limits.max_text_bytes) + _OVERHEAD
    # Uploads stay in memory: never spool document bytes to a temp file on disk (03 §9.1 `storage`).
    # The parser sees the full multipart stream before per-slot validation. Even a
    # malformed oversized part within a two-input body must never spill onto disk.
    MultiPartParser.spool_max_size = 2 * max_body
    if settings.auth_mode == "logto":
        # A deployment serves no interactive documentation and no schema: without these three routes the
        # paths answer `not_found` like any other unknown path. `app.openapi()` still works in process.
        app = FastAPI(title="ChangeLens API", version="0.0.1", docs_url=None, redoc_url=None, openapi_url=None)
    else:
        app = FastAPI(title="ChangeLens dev API (I-22)", version="0.0.1-dev")
    app.state.settings = settings
    app.state.db = db or Database(settings.database_url)
    if store is None:
        s3 = S3ObjectStore(settings.s3_endpoint, settings.s3_access_key, settings.s3_secret_key, settings.s3_bucket)
        s3.ensure_bucket()
        store = s3
    app.state.store = store
    app.state.keys = None
    # Rate-limit counters in Postgres, shared by every api process (I-8 S6). Test doubles for the
    # database have no counter function and get the single-process counters instead.
    if limiter is None:
        db_ = app.state.db
        hit = db_.rate_limit_hit if isinstance(db_, Database) else MemoryCounters()
        limiter = RateLimiter(hit, settings.rate_limit_key)
    app.state.limiter = limiter
    # Deletes the IdP user on account deletion (I-8 S5); None leaves that step pending.
    app.state.idp = idp_for(settings) if idp is _DEFAULT else idp
    # Native Google and Apple sign-in (I-8 S4): provider clients by name, and Apple token handling for
    # parking, attaching and revoking. Unconfigured providers are absent; dev mode has none.
    configured_providers, configured_apple = social_for(settings) if _DEFAULT in (providers, apple) else ({}, None)
    app.state.providers = configured_providers if providers is _DEFAULT else providers
    app.state.apple = configured_apple if apple is _DEFAULT else apple
    # The early-bird list (public routes): the sender of its confirmation mail, and the list itself, which
    # lives in Postgres behind functions. Test doubles for the database get the single-process list.
    app.state.mailer = mailer_for(settings) if mailer is _DEFAULT else mailer
    app.state.early_bird = early_bird or (app.state.db if isinstance(app.state.db, Database) else MemoryEarlyBird())
    if settings.auth_mode == "logto":
        keys = keys or JwksKeyHolder(JwtPolicy(settings.logto_issuer, settings.logto_audience),
                                     settings.logto_jwks_url)
        keys.load()  # no keys, no start: JwksUnavailable propagates (I-8 S1)
        app.state.keys = keys
    errors.install(app)
    app.include_router(router)
    app.include_router(comparison_router)
    app.include_router(review_router)
    app.include_router(retention_router)
    app.include_router(onboarding_router)
    app.include_router(consent_router)
    app.include_router(session_router)
    app.include_router(account_router)
    if app.state.mailer is not None:
        # No sender, no list: without one the routes are absent (`not_found`) instead of accepting
        # addresses nobody can confirm. CORS exists for this one path only.
        app.include_router(early_bird_router)
        app.add_middleware(EarlyBirdCors, origin=settings.landing_url)
    app.add_middleware(BodyLimitMiddleware, max_bytes=max_body)
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(NoStoreMiddleware)
    return app
