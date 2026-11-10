"""Persistent attempt reservations, real PostgreSQL locking and decimal precision."""
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from threading import Barrier
import uuid

import pytest

from changelens.domain.budget import DbCostMeter
from changelens.llm import FakeLlm
from changelens.llm.errors import LlmUnavailable
from changelens.metering import CeilingReached
from changelens.worker import Worker
from conftest import TENANT_A, TENANT_B


def comparison(env):
    pid = env.project()
    a = env.upload(pid, text="Budget: EUR 100").json()["id"]
    b = env.upload(pid, text="Budget: EUR 200").json()["id"]
    env.worker.run_until_idle()
    return uuid.UUID(env.compare(pid, a, b).json()["id"])


def test_database_budget_survives_new_instances_and_keeps_precision(env):
    cid = comparison(env)
    for _ in range(5):
        DbCostMeter(env.db, TENANT_A, cid).reserve(Decimal("0.0000001")).settle(Decimal("0.00000006"))
    DbCostMeter(env.db, TENANT_A, cid).reserve(Decimal("1.4"))  # abandoned request
    resumed = DbCostMeter(env.db, TENANT_A, cid)
    assert resumed.actual == Decimal("0.00000030")
    assert resumed.reserved == Decimal("1.4")
    with pytest.raises(CeilingReached):
        resumed.reserve(Decimal("0.1"))
    with pytest.raises(CeilingReached):
        DbCostMeter(env.db, TENANT_B, cid).reserve(Decimal("0.1"))


def test_concurrent_connections_cannot_reserve_the_same_budget_twice(env):
    cid = comparison(env)
    start = Barrier(2)

    def reserve():
        start.wait(timeout=5)
        try:
            return DbCostMeter(env.db, TENANT_A, cid).reserve(Decimal("0.8"))
        except CeilingReached:
            return None

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = list(pool.map(lambda _: reserve(), range(2)))
    tickets = [ticket for ticket in outcomes if ticket is not None]
    assert len(tickets) == 1
    assert DbCostMeter(env.db, TENANT_A, cid).total == Decimal("0.8")
    tickets[0].settle(Decimal("0.00000006"))
    assert DbCostMeter(env.db, TENANT_A, cid).total == Decimal("0.00000006")


def test_duplicate_late_settlement_only_consumes_its_own_hold(env):
    cid = comparison(env)
    meter = DbCostMeter(env.db, TENANT_A, cid)
    first = meter.reserve(Decimal("0.4"))
    with env.db.tenant_scope(TENANT_A) as repo:
        ticket_id = next(iter(repo.comparison(cid).cost_reservations))
    meter.reserve(Decimal("0.5"))
    env.sql("UPDATE comparisons SET status = 'failed' WHERE id = :id RETURNING id", id=cid)
    first.settle(Decimal("0.2"))
    DbCostMeter(env.db, TENANT_A, cid)._settle(ticket_id, Decimal("0.2"))
    assert meter.actual == Decimal("0.2") and meter.reserved == Decimal("0.5")
    with pytest.raises(CeilingReached):
        meter.reserve(Decimal("0"))


def test_queue_retry_in_a_new_worker_keeps_paid_usage_and_unknown_holds(env_factory):
    env = env_factory(cost_ceiling_eur=Decimal("1"))
    cid = comparison(env)

    class InterruptedModel(FakeLlm):
        def __init__(self):
            super().__init__(Decimal("0"))
            self.requests = 0

        def structured_metered(self, schema, system, data, meter):
            reservation = meter.reserve(Decimal("0.4"))
            self.requests += 1
            if self.requests == 2:
                raise LlmUnavailable("timeout")
            output, _ = super().structured(schema, system, data)
            reservation.settle(Decimal("0.3"))
            return output, Decimal("0.3")

    model = InterruptedModel()
    env.worker.llm = model
    assert env.worker.run_once()
    assert env.sql("SELECT status, attempts FROM jobs WHERE kind = 'compare'") == [("queued", 1)]
    meter = DbCostMeter(env.db, TENANT_A, cid)
    assert meter.actual == Decimal("0.3") and meter.reserved == Decimal("0.4")
    resumed = Worker(env.settings, env.db, env.store, model, backoff_seconds=0)
    assert resumed.run_once()
    assert model.requests == 2  # no additional request could fit the remaining budget
    assert env.sql("SELECT status, attempts FROM jobs WHERE kind = 'compare'") == [("done", 2)]
    result = env.get("/comparisons/" + str(cid)).json()
    assert result["status"] == "failed"
    assert {"code": "cost_ceiling", "stage": "extract"} in result["warnings"]
    assert Decimal(result["cost_actual"]) == Decimal("0.3")
    assert meter.reserved == Decimal("0.4")
