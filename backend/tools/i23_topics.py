"""Summarise explicitly labelled DEVELOPMENT findings for I-23, without model calls.

Input JSON: {"split": "development", "labels": [{"category": "budget",
"expected_topic": "budget"}, ...]}. Each row labels one shown prediction; expected_topic
is null for an unsupported finding. Budget/other labels must be reviewed explicitly rather
than inferred from the prediction. No held-out labels are accepted. Output contains counts
only; a sufficient annotation sample is not a claim that the live I-7 gates passed.

Usage: python -m tools.i23_topics --labels /private/development-topic-labels.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from changelens.topics import CATEGORIES, TOPICS, canonical_category, topic_for_category


def summarise(document: dict) -> dict:
    if not isinstance(document, dict) or document.get("split") != "development":
        raise ValueError("development_labels_required")
    labels = document.get("labels")
    if not isinstance(labels, list):
        raise ValueError("labels_must_be_a_list")
    counts = {topic: {"predicted": 0, "correct": 0} for topic in TOPICS}
    covered = set()
    for row in labels:
        if not isinstance(row, dict) or set(row) != {"category", "expected_topic"}:
            raise ValueError("invalid_topic_label")
        category, expected = row["category"], row["expected_topic"]
        if not isinstance(category, str) or canonical_category(category) not in CATEGORIES:
            raise ValueError("invalid_prediction_category")
        if expected is not None and expected not in TOPICS:
            raise ValueError("invalid_expected_topic")
        topic = topic_for_category(category)
        counts[topic]["predicted"] += 1
        counts[topic]["correct"] += int(expected == topic)
        if expected is not None:
            covered.add(expected)
    for values in counts.values():
        values["precision"] = values["correct"] / values["predicted"] if values["predicted"] else None
    other_share = counts["other"]["predicted"] / len(labels) if labels else None
    return {"split": "development", "labelled_findings": len(labels), "per_topic": counts,
            "labelled_topics": [topic for topic in TOPICS if topic in covered],
            "sample_sufficient": len(labels) >= 30 and covered == set(TOPICS),
            "other_share": other_share,
            "review_topic_list": other_share is not None and other_share > 0.20}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--labels", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        result = summarise(json.loads(args.labels.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError):
        parser.exit(2, "Invalid development topic labels; no report produced.\n")
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
