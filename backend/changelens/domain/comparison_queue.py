"""Advance a confirmed comparison only after both immutable inputs have been parsed."""
from decimal import Decimal

from changelens import jobs


def advance_comparison(repo, comparison, max_attempts: int) -> None:
    if comparison.status != "waiting_for_versions":
        return
    versions = [repo.version(comparison.earlier_id), repo.version(comparison.later_id)]
    rejected = next((v for v in versions if v is not None and v.status == "rejected"), None)
    if rejected is not None:
        comparison.status = "failed"
        comparison.cost_actual = Decimal("0")
        comparison.warnings = [{"code": "version_rejected", "version_id": str(rejected.id),
                                "reason": rejected.reject_reason or "parse_failed"}]
    elif all(v is not None and v.status == "parsed" for v in versions):
        comparison.status = "queued"
        jobs.enqueue(repo.s, repo.tenant_id, "compare", {"comparison_id": comparison.id}, max_attempts)


def resume_waiting(repo, version_id, max_attempts: int) -> None:
    for comparison in repo.waiting_for_version(version_id):
        advance_comparison(repo, comparison, max_attempts)
