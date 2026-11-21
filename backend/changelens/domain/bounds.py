"""Per-account bounds on uploads and queued work (03 §6 Abuse and cost exhaustion; LR-10).

One worker serves one queue in order, and originals are kept until retention removes them. Without a bound
one account could keep everyone else waiting or fill the storage at no model cost. Both upload routes call
`bound_reached` inside the transaction that would add the rows, after `lock_account`, so two requests of one
account can't both pass on the same count.

- Unparsed versions and unfinished comparisons count rows of projects that aren't deleted: the worker skips
  a deleted project's jobs, so those rows would otherwise block the account until retention removes them.
- Stored bytes count every version row the account still has, deleted projects included, because their
  originals stay in the storage until retention removes them.
"""
from __future__ import annotations

from typing import Optional

UNFINISHED = ("waiting_for_versions", "queued", "running")


def bound_reached(repo, settings, *, new_versions: int, new_bytes: int, new_comparison: bool) -> Optional[str]:
    """'unfinished_comparisons', 'unparsed_versions', 'stored_bytes' or None. `repo` is a TenantRepo that
    holds the account lock; the request would add `new_versions` uploads of `new_bytes` in total."""
    if new_comparison and repo.unfinished_comparison_count() + 1 > settings.max_unfinished_comparisons:
        return "unfinished_comparisons"
    if new_versions and repo.unparsed_version_count() + new_versions > settings.max_unparsed_versions:
        return "unparsed_versions"
    if new_bytes and repo.stored_bytes() + new_bytes > settings.max_stored_bytes:
        return "stored_bytes"
    return None
