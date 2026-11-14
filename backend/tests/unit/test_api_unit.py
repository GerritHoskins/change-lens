"""API behaviour that needs no database: auth, problem+json, upload checks before storage."""
import uuid
from datetime import datetime, timezone
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient

from changelens.api import uploads
from changelens.api.app import create_app
from changelens.api.errors import ApiError
from changelens.config import Limits, Settings
from changelens.domain import Database
from changelens.domain.models import Comparison
from changelens.storage import MemoryObjectStore
from helpers import TOKEN_A, auth, make_pdf

LIMITS = Limits()


@pytest.fixture()
def client_store():
    settings = Settings(database_url="postgresql+psycopg://nobody@127.0.0.1:1/none", s3_endpoint="http://unused",
                        s3_access_key="x", s3_secret_key="x", s3_bucket="x", dev_tokens={TOKEN_A: uuid.uuid4()},
                        limits=Limits(max_pdf_bytes=200_000, max_pdf_pages=2, max_text_bytes=1000, max_text_words=50))
    store = MemoryObjectStore()
    # The engine never connects in these tests: every request is rejected before the database.
    app = create_app(settings, Database(settings.database_url), store)
    return TestClient(app, raise_server_exceptions=False), store


def _is_problem(r, status, code):
    assert r.status_code == status, r.text
    assert r.headers["content-type"].startswith("application/problem+json")
    assert r.json()["code"] == code


@pytest.mark.parametrize("headers", [{}, auth("wrong-token-wrong-token"), {"Authorization": "Basic " + TOKEN_A},
                                     {"Authorization": "Bearer"}])
def test_missing_or_wrong_token_is_unauthenticated(client_store, headers):
    client, _ = client_store
    for method, path in (("get", "/projects/%s" % uuid.uuid4()), ("post", "/projects"),
                         ("get", "/comparisons/%s/findings" % uuid.uuid4())):
        r = getattr(client, method)(path, headers=headers)
        _is_problem(r, 401, "unauthenticated")
        assert r.headers["www-authenticate"] == "Bearer"


def test_validation_errors_do_not_echo_input(client_store):
    client, _ = client_store
    r = client.post("/projects", json={"name": "MARKER-" + "x" * 300}, headers=auth(TOKEN_A))
    _is_problem(r, 422, "invalid_request")
    assert "MARKER" not in r.text


@pytest.mark.parametrize("extra", [
    {"MARKER-KEY-123": "MARKER-VALUE-123"},
    {"evidence_mode": {"before": "text_only", "after": "text_only", "MARKER-KEY-123": 1}},
])
def test_unknown_keys_are_not_echoed_in_validation_errors(client_store, extra):
    # The location of an extra_forbidden error is the client's own key name.
    client, _ = client_store
    body = {"action": "confirmed", "evidence_mode": {"before": "text_only", "after": "text_only"},
            "page_opened": False, **extra}
    r = client.post("/findings/%s/reviews" % uuid.uuid4(), json=body, headers=auth(TOKEN_A))
    _is_problem(r, 422, "invalid_request")
    assert "MARKER" not in r.text
    assert "<unknown field>" in r.json()["detail"]


def test_unknown_route_and_method(client_store):
    client, _ = client_store
    _is_problem(client.get("/nope"), 404, "not_found")
    _is_problem(client.delete("/projects", headers=auth(TOKEN_A)), 405, "method_not_allowed")


def _upload(client, **parts):
    files = {k: v for k, v in parts.items() if k == "file"}
    data = {k: v for k, v in parts.items() if k != "file"}
    return client.post("/projects/%s/versions" % uuid.uuid4(), files=files or None, data=data, headers=auth(TOKEN_A))


@pytest.mark.parametrize("payload,status,code", [
    (b"\x89PNG\r\n\x1a\n" + b"0" * 50, 415, "unsupported_type"),
    (b"\xff\xd8\xff\xe0 jpeg", 415, "unsupported_type"),
    (b"PK\x03\x04 docx", 415, "unsupported_type"),
    (b"text with a \x00 byte", 415, "unsupported_type"),
    (b"caf\xe9 latin-1", 415, "unsupported_type"),
    (b"word " * 60, 413, "limit_exceeded"),
])
def test_rejected_uploads_are_never_stored(client_store, payload, status, code):
    client, store = client_store
    r = _upload(client, label="v1", file=("brief.pdf", payload, "application/pdf"))
    _is_problem(r, status, code)
    assert store.objects == {}


def test_pdf_size_limit(client_store):
    client, store = client_store
    r = _upload(client, label="v1", file=("a.pdf", b"%PDF-1.7" + b"0" * 250_000, "application/pdf"))
    _is_problem(r, 413, "limit_exceeded")
    assert store.objects == {}


def test_upload_shape_errors(client_store):
    client, _ = client_store
    _is_problem(_upload(client, label="v1"), 422, "invalid_request")
    _is_problem(_upload(client, label="v1", text="a", file=("a.txt", b"a", "text/plain")), 422, "invalid_request")
    _is_problem(_upload(client, text="hello"), 422, "invalid_request")
    _is_problem(_upload(client, label="v1", text="x" * 2000), 413, "limit_exceeded")


def test_sniff_ignores_claimed_type():
    assert uploads.sniff(b"%PDF-1.4 ...") == "pdf"
    assert uploads.sniff("Plain brief, UTF-8: café".encode()) == "text"
    with pytest.raises(ApiError):
        uploads.sniff(b"")
    uploads.check_limits(make_pdf([["a"], ["b"], ["c"]]), "pdf", Limits(max_pdf_pages=1))  # pages: sandbox's job


def test_api_never_opens_pdfs():
    """Page count and malformed files are checked in the parse sandbox, not the API process (I-1)."""
    import changelens.api.app
    import changelens.api.routes
    for mod in (uploads, changelens.api.routes, changelens.api.app):
        assert "pypdfium2" not in open(mod.__file__, encoding="utf-8").read()


def test_dev_api_binds_to_localhost_unless_lan_is_asked_for():
    from changelens.api.__main__ import bind_host
    assert bind_host(False) == "127.0.0.1"
    assert bind_host(True) == "0.0.0.0"


@pytest.mark.parametrize("actual,holds,status,expected_reserved,pending", [
    ("0", {"private-ticket": "0.015"}, "complete", "0.015", True),
    ("0.3", {"private-ticket": "0.4"}, "failed", "0.4", True),
    ("0.00000006", {}, "complete", "0", False),
])
def test_comparison_separates_known_cost_from_unknown_reservations(actual, holds, status,
                                                                  expected_reserved, pending):
    from changelens.api.routes import _comparison_out

    comparison = Comparison(id=uuid.uuid4(), project_id=uuid.uuid4(), earlier_id=uuid.uuid4(),
                            later_id=uuid.uuid4(), scope_snapshot="complete", status=status,
                            pipeline_version="facts-2", model_config_id="fake", cost_ceiling=Decimal("1"),
                            cost_actual=Decimal(actual), cost_reservations=holds, warnings=[],
                            created_at=datetime.now(timezone.utc))
    result = _comparison_out(comparison)
    assert Decimal(result["cost_actual"]) == Decimal(actual)
    assert Decimal(result["cost_reserved"]) == Decimal(expected_reserved)
    assert result["cost_pending"] is pending
    assert "private-ticket" not in str(result) and "cost_reservations" not in result
