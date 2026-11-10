"""Device evidence metadata is explicit, content-free and independent of client approval."""
from decimal import Decimal

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
import pytest
from sqlalchemy.dialects import postgresql
from sqlalchemy.schema import CreateTable

from changelens.api.errors import ApiError, install
from changelens.api.review_evidence import ReviewTelemetryIn, review_evidence_out, validate_review_evidence
from changelens.domain import DEV_COLUMNS
from changelens.domain.models import ClientApprovalRecord, ReviewEvent


def body(before="text_only", after="text_only", page_opened=False):
    return ReviewTelemetryIn.model_validate({"evidence_mode": {"before": before, "after": after},
                                             "page_opened": page_opened})


def evidence(*sides):
    return [{"side": side, "quote": "PRIVATE-DOCUMENT-MARKER", "locator": {"char_start": 0, "char_end": 23}}
            for side in sides]


def test_text_observations_store_only_allowed_content_free_columns():
    result = validate_review_evidence(body(), evidence("earlier", "later"), {"earlier": "text", "later": "text"})
    assert result == {"evidence_mode_before": "text_only", "evidence_mode_after": "text_only", "page_opened": False}
    assert "PRIVATE-DOCUMENT-MARKER" not in str(result)
    assert not any("approv" in name for name in result)


@pytest.mark.parametrize("before,after,opened", [
    ("pdf_highlight", "text_fallback", False),
    ("text_fallback", "pdf_highlight", True),
    ("pdf_highlight", "pdf_highlight", False),
])
def test_pdf_mode_is_observed_independently_of_whether_page_was_opened(before, after, opened):
    result = validate_review_evidence(body(before, after, opened), evidence("earlier", "later"),
                                      {"earlier": "pdf", "later": "pdf"})
    assert result["evidence_mode_before"] == before and result["evidence_mode_after"] == after
    assert result["page_opened"] is opened


@pytest.mark.parametrize("side,before,after", [("earlier", "text_only", None), ("later", None, "pdf_highlight")])
def test_one_sided_finding_requires_null_only_on_the_absent_side(side, before, after):
    result = validate_review_evidence(body(before, after), evidence(side), {"earlier": "text", "later": "pdf"})
    assert result["evidence_mode_before"] == before and result["evidence_mode_after"] == after


def test_multiple_quotes_on_same_side_share_one_observation():
    result = validate_review_evidence(body("text_only", None), evidence("earlier", "earlier"), {"earlier": "text"})
    assert result["evidence_mode_before"] == "text_only"


@pytest.mark.parametrize("mode,kinds,sides", [
    ((None, "text_only"), {"earlier": "text", "later": "text"}, ("earlier", "later")),
    (("text_only", "text_only"), {"earlier": "text"}, ("earlier",)),
    (("pdf_highlight", None), {"earlier": "text"}, ("earlier",)),
    (("text_only", None), {"earlier": "pdf"}, ("earlier",)),
    (("text_fallback", None), {"earlier": "image"}, ("earlier",)),
    (("text_only", None), {}, ("earlier",)),
    ((None, None), {}, ()),
    (("text_only", None), {"earlier": "text"}, ("unknown",)),
])
def test_missing_fabricated_or_source_inconsistent_mode_is_rejected(mode, kinds, sides):
    with pytest.raises(ApiError) as exc:
        validate_review_evidence(body(*mode), evidence(*sides), kinds)
    assert exc.value.status == 422 and exc.value.code == "invalid_request"
    assert "PRIVATE-DOCUMENT-MARKER" not in exc.value.detail


@pytest.mark.parametrize("value", [None, 0, 1, "true", "false", "1", Decimal("1"), []])
def test_page_opened_must_be_an_actual_boolean(value):
    with pytest.raises(ValidationError):
        body(page_opened=value)


@pytest.mark.parametrize("payload", [
    {}, {"page_opened": False},
    {"evidence_mode": {"before": None, "after": "text_only"}},
    {"evidence_mode": {"after": "text_only"}, "page_opened": False},
    {"evidence_mode": {"before": "unknown", "after": None}, "page_opened": False},
    {"evidence_mode": {"before": "text_only", "after": None, "quote": "PRIVATE"}, "page_opened": False},
    {"evidence_mode": {"before": "text_only", "after": None}, "page_opened": False, "approved": True},
])
def test_new_payload_cannot_omit_observations_or_add_content_or_approval(payload):
    with pytest.raises(ValidationError):
        ReviewTelemetryIn.model_validate(payload)


def test_historical_row_stays_unknown_and_new_metadata_round_trips():
    old = ReviewEvent(actor="legacy", action="confirmed")
    assert review_evidence_out(old) == {"evidence_mode": {"before": None, "after": None}, "page_opened": None}
    columns = validate_review_evidence(body("text_fallback", None, True), evidence("earlier"), {"earlier": "pdf"})
    new = ReviewEvent(actor="test", action="confirmed", **columns)
    assert review_evidence_out(new) == {"evidence_mode": {"before": "text_fallback", "after": None}, "page_opened": True}
    assert not {"evidence_mode_before", "evidence_mode_after", "page_opened"} & set(ClientApprovalRecord.__table__.c.keys())


def test_schema_and_dev_upgrade_preserve_unobserved_legacy_rows():
    for name in ("evidence_mode_before", "evidence_mode_after", "page_opened"):
        column = ReviewEvent.__table__.c[name]
        assert column.nullable and column.default is None and column.server_default is None
        statements = [s for s in DEV_COLUMNS if "ADD COLUMN" in s and "review_events" in s and name in s]
        assert len(statements) == 1
        assert "IF NOT EXISTS" in statements[0] and "DEFAULT" not in statements[0] and "NOT NULL" not in statements[0]
    ddl = str(CreateTable(ReviewEvent.__table__).compile(dialect=postgresql.dialect()))
    assert "ck_review_evidence_before" in ddl and "ck_review_evidence_after" in ddl
    assert "page_opened BOOLEAN" in ddl


def test_request_error_does_not_echo_rejected_document_content():
    app = FastAPI()
    install(app)
    with pytest.raises(ValidationError) as exc:
        body("PRIVATE-DOCUMENT-MARKER", None)
    # The registered async handler contains no awaits; run it without a socket/thread bridge.
    handler = app.exception_handlers[RequestValidationError]
    result = handler(None, RequestValidationError(exc.value.errors()))
    with pytest.raises(StopIteration) as returned:
        result.send(None)
    response = returned.value.value
    assert response.status_code == 422 and b"PRIVATE-DOCUMENT-MARKER" not in response.body
