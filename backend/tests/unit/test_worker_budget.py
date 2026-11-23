"""Durable budget/worker behaviour with transactional tenant repositories, without services.

The fixture commits detached row copies and rolls back on failure. PostgreSQL row locking
and numeric storage are covered separately by integration/test_budget.py.
"""
from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal
from threading import RLock
from types import SimpleNamespace
import uuid

import pytest

from changelens.config import Limits, Settings
from changelens.domain.budget import DbCostMeter
from changelens.llm import FakeLlm
from changelens.llm.errors import LlmUnavailable
from changelens.metering import CeilingReached
from changelens.pipeline.parse import parse
from changelens.pipeline.run import Outcome
from changelens.pipeline.types import VerifyResult
from changelens.storage import MemoryObjectStore
from changelens.worker import Worker


class TransactionalDb:
    def __init__(self):
        self.tenant = uuid.uuid4()
        self.cid, earlier_id, later_id = (uuid.uuid4() for _ in range(3))
        comparison = SimpleNamespace(id=self.cid, tenant_id=self.tenant, earlier_id=earlier_id,
                                     later_id=later_id, status="queued", scope_snapshot="complete",
                                     cost_ceiling=Decimal("1"), cost_actual=None, cost_reservations={},
                                     created_at=datetime.now(timezone.utc),
                                     warnings=[], withheld_count=0, unexplained=[], presentation_only=[])
        versions = {}
        for vid, raw in ((earlier_id, b"Budget: EUR 100"), (later_id, b"Budget: EUR 200")):
            doc = parse(raw, "text", Limits())
            versions[vid] = SimpleNamespace(id=vid, tenant_id=self.tenant, kind="text", sha256=str(vid),
                                            parsed_pages=doc.pages, blocks=doc.blocks_json(),
                                            page_count=doc.page_count, parse_warnings=[])
        self.state = {"comparisons": {self.cid: comparison}, "versions": versions, "cache": {}, "findings": []}
        self.lock = RLock()

    @contextmanager
    def tenant_scope(self, tenant_id):
        with self.lock:
            pending = deepcopy(self.state)
            yield TenantRepo(pending, tenant_id)
            self.state = pending

    def meter(self, tenant=None):
        return DbCostMeter(self, tenant or self.tenant, self.cid)

    @property
    def comparison(self):
        return self.state["comparisons"][self.cid]


class TenantRepo:
    def __init__(self, state, tenant_id):
        self.state, self.tenant_id = state, tenant_id

    def month_spend(self, since):
        return Decimal("0")  # spend caps (I-8 S6) are covered by the integration tests

    def global_month_spend(self, since):
        return Decimal("0")

    def _get(self, collection, id_):
        row = self.state[collection].get(id_)
        return row if row is not None and row.tenant_id == self.tenant_id else None

    def comparison(self, id_, lock=False):
        return self._get("comparisons", id_)

    def comparison_ledger(self, id_, lock=False):
        return self.comparison(id_, lock)

    def comparison_cost_tombstone(self, id_, lock=False):
        return None

    def version(self, id_, lock=False):
        return self._get("versions", id_)

    def lock_for_version(self, id_):
        return self.version(id_) is not None

    def lock_for_comparison(self, id_):
        return self.comparison(id_) is not None

    def cached_facts(self, key):
        return self.state["cache"].get((self.tenant_id, key))

    def cache_facts(self, version_id, key, value):
        self.state["cache"][(self.tenant_id, key)] = value

    def record_demo_comparison(self, comparison_id, now=None):
        self.state.setdefault("demo", []).append(comparison_id)

    def replace_findings(self, comparison_id, findings):
        self.state["findings"] = findings


@pytest.fixture
def db():
    return TransactionalDb()


def test_new_meter_retains_paid_cost_and_abandoned_request(db):
    first = db.meter()
    first.reserve(Decimal("0.4")).settle(Decimal("0.3"))
    first.reserve(Decimal("0.4"))  # process dies with no usage response
    resumed = db.meter()
    assert resumed.actual == Decimal("0.3")
    assert resumed.reserved == Decimal("0.4")
    assert resumed.total == Decimal("0.7")
    with pytest.raises(CeilingReached):
        resumed.reserve(Decimal("0.4"))
    assert first.calls == 2 and resumed.calls == 0
    assert len(db.comparison.cost_reservations) == 1


def test_reservation_is_committed_before_it_is_returned(db):
    meter = db.meter()
    ticket = meter.reserve(Decimal("0.6"))
    assert db.meter().total == Decimal("0.6")
    with pytest.raises(CeilingReached):
        db.meter().reserve(Decimal("0.5"))
    ticket.settle(Decimal("0.2"))
    assert db.meter().total == Decimal("0.2")


def test_settlement_is_durable_idempotent_and_cannot_consume_another_ticket(db):
    first = db.meter()
    ticket = first.reserve(Decimal("0.4"))
    ticket_id = next(iter(db.comparison.cost_reservations))
    db.meter().reserve(Decimal("0.5"))
    ticket.settle(Decimal("0.2"))
    db.meter()._settle(ticket_id, Decimal("0.2"))  # replay after uncertain commit
    assert db.meter().actual == Decimal("0.2")
    assert db.meter().reserved == Decimal("0.5")
    assert len(db.comparison.cost_reservations) == 1


def test_late_response_settles_after_terminal_status_without_reopening_budget(db):
    meter = db.meter()
    ticket = meter.reserve(Decimal("0.4"))
    with db.tenant_scope(db.tenant) as repo:
        repo.comparison(db.cid).status = "failed"
    ticket.settle(Decimal("0.12345678"))
    assert db.meter().actual == Decimal("0.12345678")
    assert db.meter().reserved == 0
    with pytest.raises(CeilingReached):
        meter.reserve(Decimal("0"))


def test_provider_overage_is_recorded_truthfully_and_blocks_further_calls(db):
    meter = db.meter()
    meter.reserve(Decimal("0.9")).settle(Decimal("1.00000001"))
    assert db.meter().total == Decimal("1.00000001")
    with pytest.raises(CeilingReached):
        db.meter().reserve(Decimal("0"))


def test_small_charges_keep_precision_across_new_meters(db):
    for _ in range(5):
        db.meter().reserve(Decimal("0.0000001")).settle(Decimal("0.00000006"))
    assert db.meter().actual == Decimal("0.00000030")


@pytest.mark.parametrize("status", ["complete", "partial", "failed"])
def test_terminal_comparison_refuses_new_spend(db, status):
    with db.tenant_scope(db.tenant) as repo:
        repo.comparison(db.cid).status = status
    with pytest.raises(CeilingReached):
        db.meter().reserve(Decimal("0.1"))
    assert not db.comparison.cost_reservations


def test_other_tenant_and_missing_comparison_cannot_reserve(db):
    with pytest.raises(CeilingReached):
        db.meter(uuid.uuid4()).reserve(Decimal("0.1"))
    with pytest.raises(CeilingReached):
        DbCostMeter(db, db.tenant, uuid.uuid4()).reserve(Decimal("0.1"))
    assert db.comparison.cost_actual is None and not db.comparison.cost_reservations


def test_a_run_after_the_month_turned_is_held_to_the_month_it_was_created_in(db, monkeypatch):
    """LR-2: its cost is booked to the old month, which no check looked at any more."""
    created = datetime(2026, 10, 31, 23, 59, tzinfo=timezone.utc)
    db.comparison.created_at = created
    asked = []

    def month_spend(self, since):
        asked.append(since)
        return Decimal("5") if since == datetime(2026, 10, 1, tzinfo=timezone.utc) else Decimal("0")

    monkeypatch.setattr(TenantRepo, "month_spend", month_spend)
    settings = Settings(database_url="unused", s3_endpoint="unused", s3_access_key="unused",
                        s3_secret_key="unused", s3_bucket="unused")
    meter = DbCostMeter(db, db.tenant, db.cid, settings)
    with pytest.raises(CeilingReached):
        meter.reserve(Decimal("0.10"))
    assert meter.spend_cap == "tenant" and datetime(2026, 10, 1, tzinfo=timezone.utc) in asked
    assert db.comparison.cost_reservations == {}

    db.comparison.created_at = datetime.now(timezone.utc)  # created this month: only this month counts
    meter = DbCostMeter(db, db.tenant, db.cid, settings)
    meter.reserve(Decimal("0.10"))
    assert meter.spend_cap is None


class InterruptedModel(FakeLlm):
    """A paid first extraction and an interrupted second request, then a worker restart."""
    def __init__(self):
        super().__init__(Decimal("0"))
        self.requests = 0

    def structured_metered(self, schema, system, data, meter):
        reservation = meter.reserve(Decimal("0.4"))
        self.requests += 1
        if self.requests == 2:
            raise LlmUnavailable("timeout")  # no known usage: retain the committed hold
        out, _ = super().structured(schema, system, data)
        reservation.settle(Decimal("0.3"))
        return out, Decimal("0.3")


def test_new_worker_reuses_durable_budget_and_finish_does_not_replace_actual(db):
    settings = Settings(database_url="unused", s3_endpoint="unused", s3_access_key="unused",
                        s3_secret_key="unused", s3_bucket="unused")
    model, store = InterruptedModel(), MemoryObjectStore()
    with pytest.raises(LlmUnavailable):
        Worker(settings, db, store, model).handle_compare(db.tenant, db.cid)
    assert model.requests == 2
    assert db.comparison.status == "running"
    assert db.meter().actual == Decimal("0.3") and db.meter().reserved == Decimal("0.4")
    # The earlier extraction was cached. A new process still cannot afford the second.
    Worker(settings, db, store, model).handle_compare(db.tenant, db.cid)
    assert model.requests == 2
    assert db.comparison.status == "failed"
    assert {"code": "cost_ceiling", "stage": "extract"} in db.comparison.warnings
    assert db.comparison.cost_actual == Decimal("0.3")  # not the effective €0.7 budget
    assert db.meter().reserved == Decimal("0.4")


def test_comparison_with_no_model_requests_reports_zero_cost(db, monkeypatch):
    import changelens.worker as worker_module
    monkeypatch.setattr(worker_module, "run_comparison", lambda *args, **kwargs:
                        Outcome(VerifyResult([], 0, []), "complete", [], Decimal("0"), 0))
    settings = Settings(database_url="unused", s3_endpoint="unused", s3_access_key="unused",
                        s3_secret_key="unused", s3_bucket="unused")
    Worker(settings, db, MemoryObjectStore()).handle_compare(db.tenant, db.cid)
    assert db.comparison.status == "complete"
    assert db.comparison.cost_actual == Decimal("0")
    assert not db.comparison.cost_reservations
