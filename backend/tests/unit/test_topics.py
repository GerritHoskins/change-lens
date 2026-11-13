"""I-23 topic mapping, extraction and review revisions, using synthetic inputs only."""
from contextlib import contextmanager
from datetime import datetime, timezone
from decimal import Decimal
from types import SimpleNamespace
import uuid

import pytest

from changelens.api import reviews
from changelens.config import Limits
from changelens.domain.models import Finding, ReviewEvent
from changelens.llm import FakeLlm, MeteredLlm
from changelens.llm.schemas import FACT_LIST, SchemaError, validate
from changelens.metering import CostMeter
from changelens.pipeline.align import align
from changelens.pipeline.compare import compare
from changelens.pipeline.extract import EXTRACT_VERSION, SYSTEM, ExtractionResult, extract
from changelens.pipeline.parse import parse
from changelens.pipeline.report import report
from changelens.pipeline.types import DraftFinding, Evidence, ExtractedFact, Locator
from changelens.pipeline.verify import verify
from changelens.topics import TOPICS, topic_counts, topic_for_category
from tools import d17_score, i23_topics


@pytest.mark.parametrize("category,topic", [
    ("date_deadline", "deadlines"), ("deliverable", "deliverables"), ("quantity", "deliverables"),
    ("responsibility_owner", "responsibilities"), ("approval", "approval_wording"),
    ("approval_wording", "approval_wording"), ("budget", "budget"), ("other_material", "other"),
    ("structure", "other"), ("unknown-historical-category", "other"), (None, "other"),
])
def test_topic_is_total_and_determined_only_by_category(category, topic):
    assert topic_for_category(category) == topic
    assert DraftFinding("uncertain", category, []).topic == topic


def test_counts_include_all_six_topics_even_when_empty():
    assert topic_counts([]) == dict.fromkeys(TOPICS, 0)
    assert topic_counts(["approval", "approval_wording", "quantity", "budget"])["approval_wording"] == 2


class ExtractScript:
    def __init__(self, text, amount, date):
        self.text, self.amount, self.date = text, amount, date

    def structured(self, schema, system, data):
        assert schema == "FactList"
        assert "separate fact for each distinct topic" in system
        output = {"facts": [{"type": category, "subject": subject, "value": value, "block": 1,
                             "quote": self.text, "ambiguity": None, "confidence": "high"}
                            for category, subject, value in (("budget", "fee", self.amount),
                                                              ("date_deadline", "payment deadline", self.date))]}
        validate(output, FACT_LIST)
        return output


def test_one_sentence_with_two_topics_keeps_two_evidence_backed_findings():
    old, new = "Fee EUR 800 is payable by 12 June.", "Fee EUR 900 is payable by 15 June."
    earlier, later = (parse(text.encode(), "text", Limits()) for text in (old, new))
    a = extract(earlier, ExtractScript(old, "EUR 800", "12 June"))
    b = extract(later, ExtractScript(new, "EUR 900", "15 June"))
    llm = MeteredLlm(FakeLlm(Decimal("0")), CostMeter(Decimal("1")))
    findings = verify(compare(align(a.facts, b.facts, llm), "complete", llm), earlier, later).findings
    findings, _ = report(findings, llm)
    assert len(findings) == 2
    assert {f.topic for f in findings} == {"budget", "deadlines"}
    assert all(f.change_type == "changed" and f.group == "prioritised" for f in findings)
    assert all([ev.quote for ev in f.evidence] == [old, new] for f in findings)


def test_extract_v7_schema_and_prompt_use_canonical_categories():
    assert EXTRACT_VERSION == "extract-v7"
    types = FACT_LIST["properties"]["facts"]["items"]["properties"]["type"]["enum"]
    assert "budget" in types and "approval_wording" in types and "approval" not in types
    assert "financial budgets" in SYSTEM
    with pytest.raises(SchemaError):
        validate({"facts": [{"type": "approval"}]}, FACT_LIST)


@pytest.mark.parametrize("category", ["budget", "other_material", "approval_wording", "approval"])
def test_material_topics_are_prioritised_but_never_clear_needs_review(category):
    evidence = [Evidence("later", Locator(0, 4), "Term")]
    clear = DraftFinding("added", category, evidence)
    uncertain = DraftFinding("uncertain", category, evidence, group="needs_review")
    equivalent = DraftFinding("equivalent", category, evidence)
    llm = MeteredLlm(FakeLlm(Decimal("0")), CostMeter(Decimal("1")))
    report([clear, uncertain, equivalent], llm)
    assert clear.group == "prioritised"
    assert uncertain.group == "needs_review" and equivalent.group == "other"


def test_old_and_new_approval_names_align_without_a_model_call():
    class NoCall:
        def structured(self, *args):
            raise AssertionError("canonical aliases should align directly")
    old = ExtractedFact("approval", "Client lead signs off", "client lead", Locator(0, 21), "ok", 0.9,
                        subject="sign-off")
    new = ExtractedFact("approval_wording", "CEO signs off", "ceo", Locator(0, 13), "ok", 0.9,
                        subject="sign-off")
    result = compare(align([old], [new], NoCall()), "complete", NoCall())
    assert len(result) == 1 and result[0].category == "approval_wording" and result[0].change_type == "changed"
    restored = ExtractionResult.from_json(ExtractionResult([old]).to_json())
    assert restored.facts[0].type == "approval_wording" and old.type == "approval"


class ReviewRepo:
    def __init__(self, finding):
        self.rows, self.events = [finding], []
        self.s = SimpleNamespace(refresh=lambda _: None)
        self.comparison_row = SimpleNamespace(id=finding.comparison_id, status="complete", pipeline_version="facts-2",
            unexplained=[], presentation_only=[], withheld_count=0, warnings=[], scope_snapshot="complete",
            earlier_id=uuid.uuid4(), later_id=uuid.uuid4())

    def finding(self, fid, lock=False):
        return next((f for f in self.rows if f.id == fid), None)

    def lock_for_finding(self, fid):
        return self.finding(fid) is not None

    def lock_for_comparison(self, cid):
        return self.comparison_row.id == cid

    def touch_comparison(self, row):
        row.last_used_at = datetime.now(timezone.utc)

    def findings(self, comparison_id):
        return self.rows

    def comparison(self, cid):
        return self.comparison_row

    def version(self, vid):
        return SimpleNamespace(kind="text")

    def reviews(self, ids):
        return [event for event in self.events if event.finding_id in ids]

    def approvals(self, ids):
        return []

    def add(self, row):
        row.id = uuid.uuid4()
        if isinstance(row, ReviewEvent):
            row.created_at = datetime.now(timezone.utc)
            self.events.append(row)
        else:
            self.rows.append(row)
        return row


@pytest.fixture
def review_env():
    original = Finding(id=uuid.uuid4(), comparison_id=uuid.uuid4(), category="other_material", change_type="changed",
                       evidence=[{"side": "earlier", "quote": "EUR 800"}, {"side": "later", "quote": "EUR 900"}],
                       explanation="Fee changed.", uncertainty=None, note=None, review_group="needs_review",
                       priority=0, revision=1, supersedes_id=None)
    repo = ReviewRepo(original)
    class Db:
        @contextmanager
        def tenant_scope(self, tenant):
            yield repo
    request = SimpleNamespace(app=SimpleNamespace(state=SimpleNamespace(db=Db())))
    return original, repo, request


def correction(category):
    return reviews.ReviewIn(action="corrected", correction={"category": category},
                            evidence_mode={"before": "text_only", "after": "text_only"}, page_opened=False)


def test_correction_changes_only_new_revision_topic_and_counts_current_findings(review_env):
    original, repo, request = review_env
    result = reviews.review(original.id, correction("budget"), request, uuid.uuid4())
    updated = result["finding"]
    assert updated["topic"] == "budget" and updated["group"] == "needs_review"
    assert original.category == "other_material" and original.review_group == "needs_review"
    assert updated["client_approval_recorded"] is False
    assert result["review"]["evidence_mode"] == {"before": "text_only", "after": "text_only"}
    assert result["review"]["page_opened"] is False
    report_data = reviews.get_findings(original.comparison_id, request, uuid.uuid4())
    assert len(report_data["findings"]) == 1
    assert report_data["topic_counts"] == {**dict.fromkeys(TOPICS, 0), "budget": 1}
    history = reviews.get_finding(original.id, request, uuid.uuid4())["revisions"]
    assert [f["topic"] for f in history] == ["other", "budget"]


def test_legacy_approval_correction_is_canonical_and_does_not_record_client_approval(review_env):
    original, repo, request = review_env
    result = reviews.review(original.id, correction("approval"), request, uuid.uuid4())
    assert result["finding"]["category"] == result["finding"]["topic"] == "approval_wording"
    assert result["finding"]["client_approval_recorded"] is False
    historical = Finding(id=uuid.uuid4(), category="approval", evidence=[], change_type="added", revision=1,
                         supersedes_id=None, review_group="prioritised", priority=0)
    assert reviews._finding_out(historical, [historical], [], [])["topic"] == "approval_wording"
    assert historical.category == "approval"


def test_scoring_treats_approval_rename_as_alias_and_budget_only_as_other_material():
    side = d17_score.Side("CEO", ["CEO"])
    gold = {"category": "approval", "new_value": "CEO"}
    assert d17_score.match_score(gold, {"category": "approval_wording", "new_value": "CEO"}, side, side) > 0
    # O-14: gold labels predate the budget split, so budget scores as other_material (I-7b, 06).
    assert d17_score.match_score({"category": "other_material", "new_value": "EUR 800"},
                                {"category": "budget", "new_value": "EUR 800"}, side, side) > 0
    # ...but budget never matches an unrelated category.
    assert d17_score.match_score({"category": "deliverable", "new_value": "EUR 800"},
                                {"category": "budget", "new_value": "EUR 800"}, side, side) == 0


def test_development_topic_precision_requires_thirty_labels_across_six_topics():
    categories = ["date_deadline", "deliverable", "responsibility_owner", "approval_wording", "budget", "structure"]
    labels = [{"category": category, "expected_topic": topic_for_category(category)}
              for category in categories for _ in range(5)]
    summary = i23_topics.summarise({"split": "development", "labels": labels})
    assert summary["sample_sufficient"] and summary["labelled_findings"] == 30
    assert all(row["precision"] == 1 for row in summary["per_topic"].values())
    assert summary["other_share"] == 5 / 30
    labels[20]["expected_topic"] = "other"  # a budget prediction was labelled other
    summary = i23_topics.summarise({"split": "development", "labels": labels})
    assert summary["per_topic"]["budget"]["precision"] == 0.8
    assert not i23_topics.summarise({"split": "development", "labels": labels[:29]})["sample_sufficient"]
    with pytest.raises(ValueError, match="development_labels_required"):
        i23_topics.summarise({"split": "held_out", "labels": labels})
