"""problem+json errors with the stable codes of 03 §9.4. Error bodies never echo request input."""
from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

log = logging.getLogger("changelens.api")

TITLES = {
    "limit_exceeded": "Input exceeds a limit",
    "unsupported_type": "Unsupported document type",
    "scope_not_confirmed": "Order and scope not confirmed",
    "not_found": "Not found",
    "unauthenticated": "Authentication required",
    "spend_cap_reached": "Monthly spend cap reached",
    "rate_limited": "Too many requests",
    "provider_unavailable": "Sign-in provider unavailable",  # I-8 S4: Google, Apple or Logto failed; retry
    "policy_version_stale": "Privacy policy version is not current",  # D-18 consent: re-read and ask again
    # Codes added by I-22 for cases 03 §9.4 does not list (see 06, I-22 row):
    "invalid_request": "Request is malformed",
    "method_not_allowed": "Method not allowed",
    "internal_error": "Internal error",
}


class ApiError(Exception):
    def __init__(self, status: int, code: str, detail: str = "", headers=None):
        super().__init__(code)
        self.status, self.code, self.detail, self.headers = status, code, detail, headers


def problem(status: int, code: str, detail: str = "", headers=None) -> JSONResponse:
    body = {"type": "urn:changelens:problem:" + code, "title": TITLES.get(code, code),
            "status": status, "code": code}
    if detail:
        body["detail"] = detail
    response = JSONResponse(body, status_code=status, media_type="application/problem+json", headers=headers)
    # Unhandled errors are rendered by Starlette's outer error middleware, outside the
    # ordinary response middleware. Apply the same cache policy at that boundary too.
    response.headers["Cache-Control"] = "no-store"
    return response


def not_found() -> ApiError:
    return ApiError(404, "not_found")


def install(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(request: Request, exc: ApiError):
        headers = dict(exc.headers or {})
        if exc.code == "unauthenticated":
            headers["WWW-Authenticate"] = "Bearer"
        return problem(exc.status, exc.code, exc.detail, headers or None)

    @app.exception_handler(RequestValidationError)
    async def _validation(request: Request, exc: RequestValidationError):
        # Field locations only; FastAPI's default body would echo the submitted input.
        fields = sorted({_location(e) for e in exc.errors()})
        return problem(422, "invalid_request", "invalid fields: " + ", ".join(fields))

    @app.exception_handler(StarletteHTTPException)
    async def _http(request: Request, exc: StarletteHTTPException):
        if exc.status_code == 404:
            return problem(404, "not_found")
        if exc.status_code == 405:
            return problem(405, "method_not_allowed")
        return problem(exc.status_code, "invalid_request")

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):
        log.error("unhandled error on %s %s: %s", request.method, _route(request), type(exc).__name__)
        return problem(500, "internal_error")


def _location(error: dict) -> str:
    """An unknown key's location is the client's own key name, so it is never echoed."""
    loc = tuple(error.get("loc", ()))
    if error.get("type") == "extra_forbidden" and loc:
        loc = loc[:-1] + ("<unknown field>",)
    return ".".join(str(p) for p in loc)


def _route(request: Request) -> str:
    route = request.scope.get("route")
    return getattr(route, "path", "<unmatched>")
