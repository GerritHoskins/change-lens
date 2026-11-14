"""Deleting primary data must not leave a cacheable API response behind."""

import pytest
from fastapi.responses import JSONResponse, Response
from fastapi.testclient import TestClient

from changelens.api.app import create_app
from changelens.config import Settings
from changelens.storage import MemoryObjectStore


@pytest.fixture
def client():
    # No database/model/network calls. Test-only routes exercise real application middleware.
    settings = Settings(database_url="unused", s3_endpoint="unused", s3_access_key="unused",
                        s3_secret_key="unused", s3_bucket="unused", dev_tokens={"test-token-test-token": "dev:test"})
    app = create_app(settings, db=object(), store=MemoryObjectStore())

    @app.get("/test/report")
    def report():
        return JSONResponse({"quote": "synthetic content"}, headers={"Cache-Control": "public, max-age=3600"})

    @app.get("/test/text")
    def text():
        return {"pages": ["synthetic content"]}

    @app.get("/test/original")
    def original():
        return Response(b"synthetic content", media_type="application/octet-stream")

    @app.post("/test/opened", status_code=204)
    def opened():
        return Response(status_code=204)

    @app.get("/test/failure")
    def failure():
        raise RuntimeError("synthetic private exception")

    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.mark.parametrize("method,path,status", [
    ("get", "/test/report", 200), ("get", "/test/text", 200),
    ("get", "/test/original", 200), ("post", "/test/opened", 204),
    ("get", "/projects", 401), ("get", "/missing", 404),
    ("get", "/test/failure", 500),
])
def test_all_success_and_error_responses_are_not_cacheable(client, method, path, status):
    response = getattr(client, method)(path)
    assert response.status_code == status
    assert response.headers.get_list("cache-control") == ["no-store"]
    if status == 401:
        assert response.headers["www-authenticate"] == "Bearer"
    if status == 500:
        assert "synthetic private exception" not in response.text


def test_oversized_request_rejected_by_outer_middleware_is_not_cacheable(client):
    response = client.post("/projects", content=b"", headers={"Content-Length": str(100 * 1024 * 1024)})
    assert response.status_code == 413
    assert response.headers["cache-control"] == "no-store"
