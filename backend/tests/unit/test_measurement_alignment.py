"""Offline regression for the two false contradictions observed on development pair P-520.

The approved diagnostic supplied unchanged resolution/duration evidence. These tests
reproduce the broad-key collision with scripted extraction; no further model calls.
"""
from dataclasses import replace

import pytest

from changelens.pipeline.align import align, key, mark_contradictions
from changelens.pipeline.compare import compare
from changelens.pipeline.types import ExtractedFact, Locator


def fact(sentence, value, ambiguity=None):
    return ExtractedFact("deliverable", sentence, value, Locator(0, len(sentence)),
                         "ambiguous" if ambiguity else "ok", 0.9, "video", ambiguity, sentence)


class NoCall:
    def structured(self, *args):
        raise AssertionError("unchanged, independently measured requirements need no judgment")


@pytest.mark.parametrize("scope", ["complete", "partial", "unknown"])
def test_same_video_resolution_and_duration_are_not_conflicting_values(scope):
    before = [fact("- Each video must be exported in 1080p.", "exported in 1080p"),
              fact("- No video may be longer than 30 seconds.", "no video may be longer than 30 seconds")]
    after = [fact("No video may be longer than 30 seconds.", "30 seconds"),
             fact("Each video must be exported in 1080p.", "1080p")]
    assert all(f.ambiguity is None for f in mark_contradictions(before))
    pairs = align(before, after, NoCall())
    assert len(pairs) == 2 and all(p.status == "matched" for p in pairs)
    assert compare(pairs, scope, NoCall()) == []


def test_same_dimension_contradiction_still_requires_review_without_polluting_other_property():
    resolution = fact("Each video must be exported in 1080p.", "1080p")
    conflicting = fact("Each video must be exported in 720p.", "720p")
    duration = fact("No video may be longer than 30 seconds.", "30 seconds")
    marked = mark_contradictions([resolution, conflicting, duration])
    assert [f.ambiguity for f in marked] == ["contradiction", "contradiction", None]
    pairs = align([resolution, duration], [resolution, conflicting, duration], NoCall())
    drafts = compare(pairs, "complete", NoCall())
    assert len(drafts) == 2
    assert all(f.change_type == "uncertain" and f.uncertainty in {"contradiction", "ambiguous_match"}
               for f in drafts)
    assert not any("30 seconds" in e.quote for f in drafts for e in f.evidence)


def test_changed_duration_is_not_hidden_by_unchanged_resolution():
    resolution = fact("Export videos in 1080p.", "1080p")
    before = [resolution, fact("Duration: 30 seconds.", "30 seconds")]
    after = [fact("Duration: 60 seconds.", "60 seconds"), resolution]
    drafts = compare(align(before, after, NoCall()), "complete", NoCall())
    assert len(drafts) == 1 and drafts[0].change_type == "changed"
    assert drafts[0].old_value == "30 seconds" and drafts[0].new_value == "60 seconds"


def test_ungrounded_or_mixed_measurement_does_not_invent_an_attribute():
    assert key(fact("Produce a video.", "1080p"))[-1] == ""
    assert key(fact("Use 1080p and 30 seconds.", "1080p and 30 seconds"))[-1] == ""


def test_unique_subject_edit_with_an_unknown_unit_keeps_deterministic_alignment():
    before = fact("Video format: 1080p.", "1080p")
    after = fact("Video format: 4K.", "4K")
    pairs = align([before], [after], NoCall())
    assert len(pairs) == 1 and pairs[0].status == "matched"
    drafts = compare(pairs, "complete", NoCall())
    assert len(drafts) == 1 and drafts[0].change_type == "changed"


def test_extraction_reported_contradiction_is_preserved():
    value = fact("Export videos in 1080p.", "1080p", "contradiction")
    assert mark_contradictions([value])[0].ambiguity == "contradiction"
    drafts = compare(align([value], [replace(value)], NoCall()), "complete", NoCall())
    assert len(drafts) == 1 and drafts[0].uncertainty == "contradiction"
