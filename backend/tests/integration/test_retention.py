"""Synthetic primary-store lifecycle tests, including PostgreSQL locks and late paid usage."""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from threading import Event
import uuid

import pytest

from changelens.db import upgrade
from changelens.domain import DbFactCache, used_at
from changelens.domain.budget import DbCostMeter
from changelens.domain.models import ObjectWriteIntent
from changelens.domain.retention import (
    expire_project_resources, process_project_deletion, request_project_deletion, run_maintenance,
)
from changelens.metering import CeilingReached
from changelens.pipeline.types import VerifyResult
from conftest import TENANT_A, TOKEN_A, TOKEN_B, auth


def pair(env, *, run=True):
    project = env.project()
    earlier = env.upload(project, text="Budget: EUR 100").json()["id"]
    later = env.upload(project, text="Budget: EUR 200").json()["id"]
    env.worker.run_until_idle()
    comparison = env.compare(project, earlier, later).json()["id"]
    if run:
        env.worker.run_until_idle()
    return tuple(uuid.UUID(value) for value in (project, earlier, later, comparison))


def age(env, project, instant):
    for table in ("source_versions", "comparisons"):
        env.sql(f"UPDATE {table} SET last_used_at = :instant WHERE project_id = :id RETURNING id",
                instant=instant, id=project)


def clocks(env, project):
    return {row[0]: row[1] for row in env.sql(
        "SELECT id,last_used_at FROM source_versions WHERE project_id=:id "
        "UNION ALL SELECT id,last_used_at FROM comparisons WHERE project_id=:id", id=project)}


def post_open(env, kind, identifier, token=TOKEN_A):
    return env.client.post(f"/{kind}/{identifier}/opened", headers=auth(token))


def test_polling_never_touches_but_explicit_open_touches_only_selected_graph(env):
    project, earlier, later, comparison = pair(env)
    old = datetime.now(timezone.utc) - timedelta(days=31)
    age(env, project, old)
    finding = env.get(f"/comparisons/{comparison}/findings").json()["findings"][0]["id"]
    for path in ("/projects", f"/projects/{project}", f"/projects/{project}/versions",
                 f"/projects/{project}/comparisons", f"/comparisons/{comparison}",
                 f"/comparisons/{comparison}/findings", f"/findings/{finding}",
                 f"/versions/{earlier}", f"/versions/{earlier}/text", f"/versions/{earlier}/original"):
        assert env.get(path).status_code == 200
    assert set(clocks(env, project).values()) == {old}
    assert post_open(env, "versions", earlier, TOKEN_B).status_code == 404
    assert post_open(env, "comparisons", comparison, TOKEN_B).status_code == 404
    assert set(clocks(env, project).values()) == {old}
    assert post_open(env, "versions", earlier).status_code == 204
    after = clocks(env, project)
    assert after[earlier] > old and after[later] == after[comparison] == old
    assert post_open(env, "comparisons", comparison).status_code == 204
    assert all(value > old for value in clocks(env, project).values())


def test_valid_review_touches_inputs_but_invalid_review_does_not(env):
    project, _, _, comparison = pair(env)
    old = datetime.now(timezone.utc) - timedelta(days=31)
    age(env, project, old)
    finding = env.get(f"/comparisons/{comparison}/findings").json()["findings"][0]
    path = f"/findings/{finding['id']}/reviews"
    sides = {e["side"] for e in finding["evidence"]}
    body = {"action": "confirmed", "page_opened": False, "evidence_mode": {
        "before": "text_only" if "earlier" in sides else None,
        "after": "text_only" if "later" in sides else None}}
    assert env.client.post(path, json={**body, "action": "approved"}, headers=auth(TOKEN_A)).status_code == 422
    assert set(clocks(env, project).values()) == {old}
    assert env.client.post(path, json=body, headers=auth(TOKEN_A)).status_code == 201
    assert all(value > old for value in clocks(env, project).values())


@pytest.mark.parametrize("status", ["queued", "running", "waiting_for_versions", "complete", "partial", "failed"])
def test_exact_thirty_day_expiry_in_every_state_preserves_project_and_late_cost(env, status):
    project, earlier, later, comparison = pair(env, run=False)
    meter = DbCostMeter(env.db, TENANT_A, comparison)
    charge = meter.reserve(Decimal("0.2"))
    meter.reserve(Decimal("0.3"))  # unknown outcome must remain accounted after content expiry
    env.sql("UPDATE comparisons SET status=:status WHERE id=:id RETURNING id", status=status, id=comparison)
    now = datetime.now(timezone.utc)
    age(env, project, now - timedelta(days=30))
    keys = [row[0] for row in env.sql("SELECT original_object_key FROM source_versions WHERE project_id=:id", id=project)]
    assert expire_project_resources(env.db, TENANT_A, project, now=now-timedelta(microseconds=1)) == (0, 0)
    result = run_maintenance(env.db, env.store, now=now, execute=True)
    assert result["expired_comparisons"] == 1 and result["expired_sources"] == 2
    assert result["completed_object_purges"] == 2
    assert env.get(f"/projects/{project}").status_code == 200
    assert env.get(f"/comparisons/{comparison}").status_code == 404
    assert env.get(f"/versions/{earlier}/original").status_code == 404
    for table in ("source_versions", "comparisons", "findings", "fact_cache", "jobs"):
        assert env.sql(f"SELECT count(*) FROM {table}")[0][0] == 0
    for key in keys:
        assert env.store.delete_prefix(key) == 0
    charge.settle(Decimal("0.12"))
    charge.settle(Decimal("0.12"))
    assert meter.actual == Decimal("0.12") and meter.reserved == Decimal("0.3")
    with pytest.raises(CeilingReached):
        meter.reserve(Decimal("0"))
    DbFactCache(env.db, TENANT_A, earlier).put("f" * 64, {"content": "must not return"})
    env.worker._finish(TENANT_A, comparison, VerifyResult([], 0, []), "complete", [])
    assert env.sql("SELECT count(*) FROM fact_cache")[0][0] == 0
    assert env.sql("SELECT count(*) FROM findings")[0][0] == 0


def test_retained_comparison_protects_shared_sources_and_dry_run_is_read_only(env):
    project, earlier, later, expired = pair(env)
    retained = uuid.UUID(env.compare(str(project), str(earlier), str(later)).json()["id"])
    now = datetime.now(timezone.utc)
    age(env, project, now-timedelta(days=31))
    env.sql("UPDATE comparisons SET last_used_at=:now WHERE id=:id RETURNING id", now=now, id=retained)
    preview = run_maintenance(env.db, env.store, now=now)
    assert preview["candidate_projects"] == 1 and not preview["execute"]
    assert env.get(f"/comparisons/{expired}").status_code == 200
    assert expire_project_resources(env.db, TENANT_A, project, now=now) == (1, 0)
    assert env.get(f"/versions/{earlier}").status_code == 200
    assert env.get(f"/comparisons/{retained}").status_code == 200


def test_explicit_project_deletion_is_idempotent_tenant_scoped_and_purges_all_content(env):
    project, earlier, _, comparison = pair(env)
    other = env.project(TOKEN_B)
    other_source = env.upload(other, token=TOKEN_B, text="Neighbor tenant content").json()["id"]
    findings = env.get(f"/comparisons/{comparison}/findings").json()["findings"]
    fid = findings[0]["id"]
    assert env.client.post(f"/findings/{fid}/client-approvals", headers=auth(TOKEN_A), json={
        "evidence_text": "Synthetic approval", "stated_by": "Synthetic author",
        "stated_at": datetime.now(timezone.utc).isoformat()}).status_code == 201
    assert env.client.delete(f"/projects/{project}", headers=auth(TOKEN_B)).status_code == 404
    for _ in range(2):
        assert env.client.delete(f"/projects/{project}", headers=auth(TOKEN_A)).status_code == 204
    for path in (f"/projects/{project}", f"/versions/{earlier}/original", f"/versions/{earlier}/text",
                 f"/comparisons/{comparison}/findings", f"/findings/{fid}"):
        assert env.get(path).status_code == 404
    assert post_open(env, "comparisons", comparison).status_code == 404
    assert env.upload(str(project), text="Cannot revive").status_code == 404
    for table in ("client_approvals", "review_events", "findings", "fact_cache", "comparisons", "source_versions", "jobs", "projects"):
        assert env.sql(f"SELECT count(*) FROM {table} WHERE tenant_id=:tenant", tenant=TENANT_A)[0][0] == 0
    assert env.get(f"/versions/{other_source}/original", TOKEN_B).content == b"Neighbor tenant content"
    assert env.store.delete_prefix(f"{TENANT_A}/{project}") == 0


def test_deletion_freezes_immediately_while_existing_writer_holds_project_lock(env):
    project, earlier, _, comparison = pair(env, run=False)
    locked, release = Event(), Event()

    def writer():
        with env.db.tenant_scope(TENANT_A) as repo:
            repo.lock_project(project)
            locked.set()
            assert release.wait(timeout=10)

    with ThreadPoolExecutor(max_workers=1) as pool:
        task = pool.submit(writer)
        assert locked.wait(timeout=5)
        try:
            response = env.client.delete(f"/projects/{project}", headers=auth(TOKEN_A))
            assert response.status_code == 202
            assert env.get(f"/projects/{project}").status_code == 404
            with pytest.raises(CeilingReached):
                DbCostMeter(env.db, TENANT_A, comparison).reserve(Decimal("0"))
        finally:
            release.set()
        task.result(timeout=5)
    assert process_project_deletion(env.db, env.store, TENANT_A, project)
    assert env.get(f"/versions/{earlier}").status_code == 404


def test_failed_object_purge_is_durable_and_retry_completes(env, monkeypatch):
    project, _, _, _ = pair(env)
    original = env.store.delete_prefix
    calls = []

    def fail(prefix):
        calls.append(prefix)
        raise RuntimeError("synthetic storage failure")

    monkeypatch.setattr(env.store, "delete_prefix", fail)
    assert env.client.delete(f"/projects/{project}", headers=auth(TOKEN_A)).status_code == 202
    assert env.get(f"/projects/{project}").status_code == 404
    assert env.sql("SELECT count(*) FROM source_versions")[0][0] == 0
    assert env.sql("SELECT count(*) FROM object_purge_intents")[0][0] == 2
    assert calls == [f"{TENANT_A}/{project}/"]
    monkeypatch.setattr(env.store, "delete_prefix", original)
    future = datetime.now(timezone.utc)+timedelta(hours=2)
    assert process_project_deletion(env.db, env.store, TENANT_A, project, now=future)
    assert env.sql("SELECT count(*) FROM object_purge_intents")[0][0] == 0


def test_unknown_upload_cannot_be_reported_as_completed_project_erasure(env):
    project = uuid.UUID(env.project())
    now = datetime.now(timezone.utc)
    key = f"{TENANT_A}/{project}/{uuid.uuid4()}"
    with env.db.tenant_scope(TENANT_A) as repo:
        repo.add(ObjectWriteIntent(object_key=key, request_lock_id=123, next_attempt_at=now,
                                   write_acknowledged=False, attempts=0))
    request_project_deletion(env.db, TENANT_A, project, now=now)
    assert not process_project_deletion(env.db, env.store, TENANT_A, project, now=now)
    env.store.put(key, b"delayed synthetic PUT")
    assert not process_project_deletion(env.db, env.store, TENANT_A, project, now=now+timedelta(hours=2))
    assert env.store.delete_prefix(key) == 0
    assert env.sql("SELECT status FROM project_deletions") == [("pending",)]
    assert env.sql("SELECT count(*) FROM object_write_intents")[0][0] == 1


def test_in_flight_model_response_settles_after_deletion_without_more_calls_or_content(env):
    from changelens.llm import FakeLlm

    project, _, _, comparison = pair(env, run=False)

    class DeleteDuringModel(FakeLlm):
        requests = 0

        def structured_metered(self, schema, system, data, meter):
            ticket = meter.reserve(Decimal("0.1"))
            self.requests += 1
            result, _ = super().structured(schema, system, data)
            request_project_deletion(env.db, TENANT_A, project)
            assert process_project_deletion(env.db, env.store, TENANT_A, project)
            ticket.settle(Decimal("0.04"))
            return result, Decimal("0.04")

    model = DeleteDuringModel(Decimal("0"))
    env.worker.llm = model
    env.worker.run_until_idle()
    assert model.requests == 1
    assert DbCostMeter(env.db, TENANT_A, comparison).actual == Decimal("0.04")
    assert env.sql("SELECT count(*) FROM findings")[0][0] == 0
    assert env.sql("SELECT count(*) FROM fact_cache")[0][0] == 0
    assert env.sql("SELECT count(*) FROM jobs")[0][0] == 0


def test_repeated_migration_and_clock_rollback_do_not_extend_or_shorten_observed_use(env):
    # The create_schema bootstrap and its NULL backfill are gone (I-8 S1); `upgrade head` at head is a no-op.
    project, _, _, _ = pair(env)
    old = datetime.now(timezone.utc)-timedelta(days=4)
    age(env, project, old)
    before = clocks(env, project)
    upgrade(env.db.engine.url.render_as_string(hide_password=False))
    assert clocks(env, project) == before
    assert used_at(old, old-timedelta(days=1)) == old
