"""What the projects list says about each project's most recent comparison (home screen).

Counts follow the report (`GET /comparisons/{id}/findings`): only the current revision of each finding
counts, "shown" means the two groups the report headline counts (needs_review and prioritised), and a
finding is reviewed once any revision of it has a confirm, correct or dismiss (a note alone isn't one).
Counts exist only for a comparison with a report (complete or partial); otherwise they are null, never 0.
"""
from __future__ import annotations

from changelens.topics import topic_counts

SHOWN_GROUPS = ("needs_review", "prioritised")
WITH_REPORT = ("complete", "partial")


def summarise(comparison, labels: dict, rows: list, reviewed_ids: set) -> dict:
    """`rows` are this comparison's findings as (id, comparison_id, category, review_group, supersedes_id);
    `reviewed_ids` are finding ids with a non-note review; `labels` maps version id to its label."""
    out = {"id": str(comparison.id), "status": comparison.status,
           "earlier_label": labels.get(comparison.earlier_id), "later_label": labels.get(comparison.later_id),
           "created_at": comparison.created_at.isoformat(),
           "findings": None, "needs_review": None, "reviewed": None, "topic_counts": None}
    if comparison.status not in WITH_REPORT:
        return out
    by_id = {row.id: row for row in rows}
    superseded = {row.supersedes_id for row in rows if row.supersedes_id}
    shown, reviewed = [], 0
    for row in rows:
        if row.id in superseded or row.review_group not in SHOWN_GROUPS:
            continue
        shown.append(row)
        revision = row
        while revision is not None:
            if revision.id in reviewed_ids:
                reviewed += 1
                break
            revision = by_id.get(revision.supersedes_id) if revision.supersedes_id else None
    out.update(findings=len(shown), needs_review=sum(row.review_group == "needs_review" for row in shown),
               reviewed=reviewed, topic_counts=topic_counts(row.category for row in shown))
    return out


def latest_comparison_summaries(repo) -> dict:
    """Project id -> summary of its most recent comparison; projects never compared are absent."""
    latest = repo.latest_comparisons()
    if not latest:
        return {}
    labels = repo.version_labels({v for c in latest.values() for v in (c.earlier_id, c.later_id)})
    rows = repo.finding_summary_rows([c.id for c in latest.values() if c.status in WITH_REPORT])
    reviewed_ids = repo.reviewed_finding_ids([row.id for row in rows])
    by_comparison: dict = {}
    for row in rows:
        by_comparison.setdefault(row.comparison_id, []).append(row)
    return {project_id: summarise(c, labels, by_comparison.get(c.id, []), reviewed_ids)
            for project_id, c in latest.items()}
