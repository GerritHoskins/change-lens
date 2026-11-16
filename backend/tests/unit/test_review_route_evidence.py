"""Review route validation precedes append-only writes; no services or document fixtures."""
from contextlib import contextmanager
from datetime import datetime, timezone
from types import SimpleNamespace
import uuid

import pytest

from changelens.api.errors import ApiError
from changelens.api.reviews import ReviewIn, review
from changelens.domain.identity import Principal
from changelens.domain.models import Finding, ReviewEvent


class ReviewRepository:
    def __init__(self, sides, kinds):
        self.tenant_id = uuid.uuid4()
        self.comparison_row = SimpleNamespace(id=uuid.uuid4(), status="complete",
                                             earlier_id=uuid.uuid4(), later_id=uuid.uuid4())
        self.original = Finding(id=uuid.uuid4(), tenant_id=self.tenant_id,
            comparison_id=self.comparison_row.id, category="other_material", change_type="changed",
            evidence=[{"side": side, "quote": "Synthetic term"} for side in sides],
            explanation="Synthetic change", uncertainty=None, note=None, review_group="needs_review",
            priority=0, revision=1, supersedes_id=None)
        self.rows, self.events, self.writes = [self.original], [], []
        self.versions = {vid: SimpleNamespace(kind=kind) for vid, kind in
                         zip((self.comparison_row.earlier_id, self.comparison_row.later_id), kinds)}
        self.s = SimpleNamespace(refresh=lambda _: None)

    def finding(self, identifier, lock=False):
        assert lock
        return next((row for row in self.rows if row.id == identifier), None)

    def lock_for_finding(self, identifier):
        return any(row.id == identifier for row in self.rows)

    def touch_comparison(self, row):
        row.last_used_at = datetime.now(timezone.utc)

    def findings(self, identifier):
        assert identifier == self.comparison_row.id
        return self.rows

    def comparison(self, identifier):
        assert identifier == self.comparison_row.id
        return self.comparison_row

    def version(self, identifier):
        return self.versions.get(identifier)

    def reviews(self, ids):
        return [event for event in self.events if event.finding_id in ids]

    def approvals(self, ids):
        return []

    def add(self, row):
        row.id, row.created_at = uuid.uuid4(), datetime.now(timezone.utc)
        self.writes.append(row)
        (self.events if isinstance(row, ReviewEvent) else self.rows).append(row)
        return row

    @contextmanager
    def tenant_scope(self, tenant):
        assert tenant == self.tenant_id
        yield self

    def request(self):
        return SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(db=self)))


@pytest.mark.parametrize("sides,kinds,before,after", [
    (("earlier", "later"), ("text", "text"), "pdf_highlight", "text_only"),
    (("earlier", "later"), ("pdf", "pdf"), "text_only", "pdf_highlight"),
    (("earlier", "later"), ("text", "text"), None, "text_only"),
    (("earlier",), ("text", "pdf"), "text_only", "pdf_highlight"),
    (("later",), ("text", "pdf"), "text_only", "text_fallback"),
])
def test_invalid_observation_cannot_append_a_correction_or_review(sides, kinds, before, after):
    repo = ReviewRepository(sides, kinds)
    body = ReviewIn(action="corrected", correction={"category": "budget"},
                    evidence_mode={"before": before, "after": after}, page_opened=False)
    with pytest.raises(ApiError) as error:
        review(repo.original.id, body, repo.request(), Principal(uuid.uuid4(), repo.tenant_id, "owner"))
    assert error.value.status == 422
    assert repo.writes == [] and repo.events == []
    assert repo.original.category == "other_material" and len(repo.rows) == 1


@pytest.mark.parametrize("sides,kinds,before,after,opened", [
    (("earlier",), ("pdf", "text"), "text_fallback", None, False),
    (("later",), ("text", "pdf"), None, "pdf_highlight", True),
    (("earlier", "later"), ("pdf", "pdf"), "text_fallback", "pdf_highlight", False),
])
def test_valid_device_observations_round_trip_without_recording_approval(sides, kinds, before, after, opened):
    repo = ReviewRepository(sides, kinds)
    modes = {"before": before, "after": after}
    body = ReviewIn(action="confirmed", evidence_mode=modes, page_opened=opened)
    result = review(repo.original.id, body, repo.request(), Principal(uuid.uuid4(), repo.tenant_id, "owner"))
    assert len(repo.writes) == len(repo.events) == 1 and len(repo.rows) == 1
    assert result["review"]["evidence_mode"] == modes
    assert result["review"]["page_opened"] is opened
    assert result["finding"]["client_approval_recorded"] is False
    assert result["finding"]["group"] == "needs_review"


def test_missing_tenant_resolved_source_cannot_append_a_review():
    repo = ReviewRepository(("earlier", "later"), ("text", "text"))
    del repo.versions[repo.comparison_row.later_id]
    body = ReviewIn(action="confirmed", evidence_mode={"before": "text_only", "after": "text_only"},
                    page_opened=False)
    with pytest.raises(ApiError) as error:
        review(repo.original.id, body, repo.request(), Principal(uuid.uuid4(), repo.tenant_id, "owner"))
    assert error.value.status == 404 and repo.writes == []


def _text_review(**fields):
    return ReviewIn(evidence_mode={"before": "text_only", "after": "text_only"}, page_opened=False, **fields)


@pytest.mark.parametrize("fields", [
    {"action": "dismissed"},  # no default reason
    {"action": "dismissed", "dismissal_reason": "equivalent"},  # never relabelled as equivalent
    {"action": "dismissed", "dismissal_reason": ""},
    {"action": "confirmed", "dismissal_reason": "other"},
    {"action": "note", "note": "Synthetic note", "dismissal_reason": "reworded"},
])
def test_dismissal_reason_is_required_on_dismissal_and_refused_elsewhere(fields):
    repo = ReviewRepository(("earlier", "later"), ("text", "text"))
    with pytest.raises(ApiError) as error:
        review(repo.original.id, _text_review(**fields), repo.request(),
               Principal(uuid.uuid4(), repo.tenant_id, "owner"))
    assert error.value.status == 422 and repo.writes == []


@pytest.mark.parametrize("reason", ["reworded", "wrong_passage", "irrelevant", "other"])
def test_dismissal_keeps_the_finding_and_records_its_reason(reason):
    repo = ReviewRepository(("earlier", "later"), ("text", "text"))
    result = review(repo.original.id, _text_review(action="dismissed", dismissal_reason=reason), repo.request(),
                    Principal(uuid.uuid4(), repo.tenant_id, "owner"))
    assert result["review"]["action"] == "dismissed" and result["review"]["dismissal_reason"] == reason
    assert result["finding"]["review"]["dismissal_reason"] == reason
    # The finding stays as it was: same revision and change type, no approval record (AC-12).
    assert len(repo.rows) == 1 and result["finding"]["change_type"] == "changed"
    assert result["finding"]["client_approval_recorded"] is False
