"""Fixed category/topic vocabulary (O-14). Topics never determine review confidence."""
from collections import Counter
from collections.abc import Iterable


TOPICS = ("deadlines", "deliverables", "responsibilities", "approval_wording", "budget", "other")
CATEGORIES = ["deliverable", "quantity", "date_deadline", "responsibility_owner", "approval_wording",
              "budget", "other_material", "structure"]
CATEGORY_TOPICS = {
    "deliverable": "deliverables", "quantity": "deliverables", "date_deadline": "deadlines",
    "responsibility_owner": "responsibilities", "approval_wording": "approval_wording",
    "budget": "budget", "other_material": "other", "structure": "other",
}


def canonical_category(category: str) -> str:
    """Read historic approval rows without rewriting the immutable finding or its revisions."""
    return "approval_wording" if category == "approval" else category


def topic_for_category(category: str) -> str:
    return CATEGORY_TOPICS.get(canonical_category(category), "other")


def topic_counts(categories: Iterable[str]) -> dict[str, int]:
    counts = Counter(topic_for_category(category) for category in categories)
    return {topic: counts[topic] for topic in TOPICS}
