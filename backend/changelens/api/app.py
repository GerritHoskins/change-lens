"""FastAPI application factory for the `api` process (03 §9.1). Dev-token auth only (I-22)."""
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
from changelens.api.retention import router as retention_router
from changelens.api.routes import router
from changelens.config import Settings
from changelens.domain import Database
from changelens.storage import ObjectStore, S3ObjectStore

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


def create_app(settings: Settings, db: Optional[Database] = None, store: Optional[ObjectStore] = None) -> FastAPI:
    max_body = max(settings.limits.max_pdf_bytes, settings.limits.max_text_bytes) + _OVERHEAD
    # Uploads stay in memory: never spool document bytes to a temp file on disk (03 §9.1 `storage`).
    # The parser sees the full multipart stream before per-slot validation. Even a
    # malformed oversized part within a two-input body must never spill onto disk.
    MultiPartParser.spool_max_size = 2 * max_body
    app = FastAPI(title="ChangeLens dev API (I-22)", version="0.0.1-dev")
    app.state.settings = settings
    app.state.db = db or Database(settings.database_url)
    if store is None:
        s3 = S3ObjectStore(settings.s3_endpoint, settings.s3_access_key, settings.s3_secret_key, settings.s3_bucket)
        s3.ensure_bucket()
        store = s3
    app.state.store = store
    errors.install(app)
    app.include_router(router)
    app.include_router(comparison_router)
    app.include_router(review_router)
    app.include_router(retention_router)
    app.add_middleware(BodyLimitMiddleware, max_bytes=max_body)
    app.add_middleware(AccessLogMiddleware)
    app.add_middleware(NoStoreMiddleware)
    return app
