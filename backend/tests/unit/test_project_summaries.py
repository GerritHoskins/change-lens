"""The projects list's latest-comparison summary: counts follow the report, and are null without one."""
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from changelens.api.project_summaries import latest_comparison_summaries, summarise
from changelens.topics import TOPICS

V1, V2 = uuid.uuid4(), uuid.uuid4()
LABELS = {V1: "v1", V2: "v2"}


def _comparison(status="complete", project_id=None):
    return SimpleNamespace(id=uuid.uuid4(), project_id=project_id or uuid.uuid4(), status=status, earlier_id=V1,
                           later_id=V2, created_at=datetime(2026, 11, 21, 9, 0, tzinfo=timezone.utc))


def _row(comparison, category, group, supersedes=None):
    return SimpleNamespace(id=uuid.uuid4(), comparison_id=comparison.id, category=category, review_group=group,
                           supersedes_id=supersedes)


def test_counts_only_the_findings_the_report_headline_counts():
    c = _comparison()
    rows = [_row(c, "date_deadline", "prioritised"), _row(c, "deliverable", "prioritised"),
            _row(c, "quantity", "prioritised"), _row(c, "responsibility_owner", "needs_review"),
            _row(c, "structure", "other"), _row(c, "approval", "needs_review")]
    out = summarise(c, LABELS, rows, {rows[0].id, rows[4].id})
    assert (out["earlier_label"], out["later_label"], out["status"]) == ("v1", "v2", "complete")
    assert (out["findings"], out["needs_review"], out["reviewed"]) == (5, 2, 1)  # the "other" row never counts
    assert out["topic_counts"] == {**dict.fromkeys(TOPICS, 0), "deadlines": 1, "deliverables": 2,
                                   "responsibilities": 1, "approval_wording": 1}
    assert sum(out["topic_counts"].values()) == out["findings"]
    assert out["created_at"] == "2026-11-21T09:00:00+00:00" and out["id"] == str(c.id)


def test_a_correction_counts_once_and_stays_reviewed():
    c = _comparison("partial")
    original = _row(c, "budget", "prioritised")
    revision = _row(c, "other_material", "prioritised", supersedes=original.id)
    untouched = _row(c, "budget", "prioritised")
    out = summarise(c, LABELS, [original, revision, untouched], {original.id})  # the review sits on revision 1
    assert (out["findings"], out["reviewed"]) == (2, 1)
    assert out["topic_counts"]["other"] == 1 and out["topic_counts"]["budget"] == 1  # the current category


@pytest.mark.parametrize("status", ["waiting_for_versions", "queued", "running", "failed"])
def test_without_a_report_the_counts_are_null_not_zero(status):
    c = _comparison(status)
    out = summarise(c, LABELS, [_row(c, "budget", "prioritised")], set())
    assert out["status"] == status and out["later_label"] == "v2"
    assert [out[k] for k in ("findings", "needs_review", "reviewed", "topic_counts")] == [None] * 4


def test_a_report_with_nothing_to_show_is_zero_not_null():
    out = summarise(_comparison(), LABELS, [], set())
    assert (out["findings"], out["needs_review"], out["reviewed"]) == (0, 0, 0)


class _Repo:
    def __init__(self, comparisons, rows, reviewed):
        self.comparisons, self.rows, self.reviewed, self.asked = comparisons, rows, reviewed, None

    def latest_comparisons(self):
        return {c.project_id: c for c in self.comparisons}

    def version_labels(self, ids):
        return {i: LABELS[i] for i in ids}

    def finding_summary_rows(self, comparison_ids):
        self.asked = list(comparison_ids)
        return [r for r in self.rows if r.comparison_id in comparison_ids]

    def reviewed_finding_ids(self, finding_ids):
        return self.reviewed & set(finding_ids)


def test_summaries_are_per_project_and_read_findings_only_for_reports():
    done, running = _comparison(), _comparison("running")
    rows = [_row(done, "budget", "prioritised"), _row(done, "budget", "needs_review")]
    repo = _Repo([done, running], rows, {rows[1].id})
    got = latest_comparison_summaries(repo)
    assert repo.asked == [done.id]
    assert (got[done.project_id]["findings"], got[done.project_id]["reviewed"]) == (2, 1)
    assert got[running.project_id]["findings"] is None
    assert latest_comparison_summaries(_Repo([], [], set())) == {}
