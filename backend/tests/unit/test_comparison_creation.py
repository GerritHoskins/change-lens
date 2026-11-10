"""I-24 HTTP/worker regression coverage, no services, credentials or model requests."""
from decimal import Decimal
from datetime import datetime, timedelta, timezone
import json
from types import SimpleNamespace
import tempfile
import uuid

import pytest

from changelens.pipeline.types import ParseRejected
from changelens.domain.storage_intents import reconcile_pending_writes, UNKNOWN_WRITE_GRACE
from comparison_fixture import Environment
from helpers import TOKEN_A, TOKEN_B, auth, make_pdf


@pytest.fixture
def env(monkeypatch):
    environment = Environment(monkeypatch)
    yield environment
    environment.client.close()


def body():
    return {"earlier": {"label": "Earlier", "text": "Original synthetic brief"},
            "later": {"label": "Later", "text": "Updated synthetic brief"}, "scope": "partial"}


def problem(response, status, code):
    assert response.status_code == status, response.text
    assert response.headers["content-type"].startswith("application/problem+json")
    assert response.json()["code"] == code


def assert_no_writes(env):
    assert not env.versions and not env.comparisons and not env.queued and not env.store.objects


def test_two_text_slots_are_atomic_and_keep_confirmed_order_scope(env):
    comparison = env.comparison(env.post(body()))
    assert comparison.status == "waiting_for_versions" and comparison.scope_snapshot == "partial"
    assert len(env.versions) == len(env.store.objects) == len(env.queued) == 2
    earlier, later = (env.versions[v] for v in (comparison.earlier_id, comparison.later_id))
    assert (earlier.label, later.label) == ("Earlier", "Later")
    assert env.store.get(earlier.original_object_key) == b"Original synthetic brief"
    assert env.store.get(later.original_object_key) == b"Updated synthetic brief"
    assert {tuple(j["ids"].values())[0] for j in env.queued} == {earlier.id, later.id}
    assert all(j["kind"] == "parse" and j["tenant_id"] == env.tenant for j in env.queued)
    assert comparison.cost_actual is None and comparison.cost_reservations == {}


def test_two_pdf_slots_are_uploaded_in_memory_once_even_when_request_is_retried(env):
    payload = {"earlier": {"label": "PDF old", "file": True},
               "later": {"label": "PDF new", "file": True}, "scope": "complete"}
    old, new = make_pdf([["Earlier PDF"]]), make_pdf([["Later PDF"]])
    parts = [("comparison", (None, json.dumps(payload))),
             ("earlier_file", ("older.pdf", old, "application/pdf")),
             ("later_file", ("newer.pdf", new, "application/pdf"))]
    headers = {**auth(TOKEN_A), "Idempotency-Key": "pdf-comparison-test-0001"}
    path = f"/projects/{env.project_id}/comparisons"
    first = env.client.post(path, files=parts, headers=headers)
    second = env.client.post(path, files=parts, headers=headers)
    comparison = env.comparison(first)
    assert first.json() == second.json()
    assert len(env.versions) == len(env.store.objects) == len(env.queued) == 2
    assert all(v.kind == "pdf" for v in env.versions.values())
    assert env.store.get(env.versions[comparison.earlier_id].original_object_key) == old
    assert env.store.get(env.versions[comparison.later_id].original_object_key) == new


def test_idempotent_text_retry_returns_same_comparison_without_additional_writes(env):
    first, second = env.post(body()), env.post(body())
    assert first.status_code == second.status_code == 202 and first.json() == second.json()
    assert len(env.comparisons) == 1 and len(env.versions) == len(env.store.objects) == len(env.queued) == 2


def test_idempotency_keys_are_scoped_to_tenant(env):
    first = env.comparison(env.post(body()))
    second = env.comparison(env.post(body(), project=env.foreign_project, token=TOKEN_B))
    assert first.id != second.id and first.tenant_id != second.tenant_id
    assert len(env.comparisons) == 2 and len(env.versions) == len(env.store.objects) == len(env.queued) == 4


@pytest.mark.parametrize("change", ["scope", "order", "text", "label", "project"])
def test_conflicting_key_reuse_returns_409_without_side_effects(env, change):
    assert env.post(body()).status_code == 202
    altered, project = body(), None
    if change == "scope":
        altered["scope"] = "unknown"
    elif change == "order":
        altered["earlier"], altered["later"] = altered["later"], altered["earlier"]
    elif change == "project":
        project = env.other_project
    else:
        altered["later"][change] = "Changed request"
    problem(env.post(altered, project=project), 409, "idempotency_conflict")
    assert len(env.comparisons) == 1 and len(env.versions) == len(env.store.objects) == len(env.queued) == 2


@pytest.mark.parametrize("key", [None, "", "short", "invalid key 123456", "x" * 129])
def test_idempotency_key_is_required_and_bounded(env, key):
    problem(env.post(body(), key=key), 422, "idempotency_key_required")
    assert_no_writes(env)


@pytest.mark.parametrize("mutation", [
    lambda p: p.pop("scope"), lambda p: p.update(scope=None), lambda p: p.update(scope="guess"),
    lambda p: p.pop("earlier"), lambda p: p.update(later=None), lambda p: p.update(unexpected=True),
])
def test_missing_explicit_inputs_or_scope_are_rejected_before_writes(env, mutation):
    payload = body()
    mutation(payload)
    problem(env.post(payload), 422, "scope_not_confirmed")
    assert_no_writes(env)


@pytest.mark.parametrize("slot", [
    {"label": "", "text": "a"}, {"label": 42, "text": "a"}, {"label": "x", "text": 42},
    {"label": "x", "text": "a", "version_id": str(uuid.uuid4())}, {"version_id": "invalid"},
    {"label": "x", "file": True}, {"label": "x", "text": "a", "extra": "ignored?"},
])
def test_invalid_slot_shape_is_rejected_before_other_slot_is_stored(env, slot):
    payload = body()
    payload["later"] = slot
    problem(env.post(payload), 422, "invalid_request")
    assert_no_writes(env)


@pytest.mark.parametrize("text,status,code", [("", 415, "unsupported_type"),
    ("a" * 1001, 413, "limit_exceeded"), ("x " * 101, 413, "limit_exceeded")])
def test_invalid_second_document_does_not_partially_save_first(env, text, status, code):
    payload = body()
    payload["later"]["text"] = text
    problem(env.post(payload), status, code)
    assert_no_writes(env)


@pytest.mark.parametrize("where", ["top", "slot"])
def test_duplicate_json_keys_are_rejected_without_silent_selection(env, where):
    encoded = json.dumps(body())
    if where == "top":
        encoded = encoded[:-1] + ', "scope": "complete"}'
    else:
        encoded = encoded.replace('"label": "Later"', '"label": "Original label", "label": "Later"')
    headers = {**auth(TOKEN_A), "Idempotency-Key": "duplicate-json-test-01", "Content-Type": "application/json"}
    response = env.client.post(f"/projects/{env.project_id}/comparisons", content=encoded, headers=headers)
    problem(response, 422, "invalid_request")
    assert_no_writes(env)


@pytest.mark.parametrize("field", ["text", "label"])
def test_invalid_unicode_scalar_is_a_validation_error_not_server_failure(env, field):
    payload = body()
    payload["later"][field] = "\ud800"
    headers = {**auth(TOKEN_A), "Idempotency-Key": "invalid-unicode-test-01", "Content-Type": "application/json"}
    response = env.client.post(f"/projects/{env.project_id}/comparisons", content=json.dumps(payload), headers=headers)
    problem(response, 422, "invalid_request")
    assert_no_writes(env)


def test_duplicate_multipart_fields_are_rejected(env):
    fields = [("comparison", (None, json.dumps(body()))), ("comparison", (None, json.dumps(body())))]
    headers = {**auth(TOKEN_A), "Idempotency-Key": "duplicate-multipart-01"}
    response = env.client.post(f"/projects/{env.project_id}/comparisons", files=fields, headers=headers)
    problem(response, 422, "invalid_request")
    assert_no_writes(env)


def test_oversized_pair_file_is_rejected_without_spooling_to_disk(env, monkeypatch):
    rollovers = []
    original = tempfile.SpooledTemporaryFile.rollover
    def spy(file):
        rollovers.append(True)
        return original(file)
    monkeypatch.setattr(tempfile.SpooledTemporaryFile, "rollover", spy)
    payload = body()
    payload["earlier"] = {"label": "Oversized", "file": True}
    parts = [("comparison", (None, json.dumps(payload))),
             ("earlier_file", ("large.pdf", b"%PDF-1.7\n" + b"0" * 100_000, "application/pdf"))]
    headers = {**auth(TOKEN_A), "Idempotency-Key": "oversized-file-test-001"}
    response = env.client.post(f"/projects/{env.project_id}/comparisons", files=parts, headers=headers)
    problem(response, 413, "limit_exceeded")
    assert not rollovers
    assert_no_writes(env)


@pytest.mark.parametrize("project", ["missing", "foreign"])
def test_missing_and_other_tenant_projects_are_indistinguishable(env, project):
    identifier = uuid.uuid4() if project == "missing" else env.foreign_project
    problem(env.post(body(), project=identifier), 404, "not_found")
    assert_no_writes(env)


@pytest.mark.parametrize("location", ["missing", "other_project", "other_tenant"])
def test_existing_version_must_belong_to_target_tenant_and_project(env, location):
    identifier = (uuid.uuid4() if location == "missing" else
                  env.version(project=env.other_project if location == "other_project" else env.foreign_project,
                              tenant=env.other_tenant if location == "other_tenant" else env.tenant))
    before = (len(env.versions), len(env.store.objects))
    payload = body()
    payload["later"] = {"version_id": str(identifier)}
    problem(env.post(payload), 404, "not_found")
    assert (len(env.versions), len(env.store.objects)) == before
    assert not env.comparisons and not env.queued


def test_same_existing_input_cannot_be_compared_to_itself(env):
    identifier = env.version()
    payload = {"earlier_id": str(identifier), "later_id": str(identifier), "scope": "complete"}
    problem(env.post(payload), 422, "scope_not_confirmed")
    assert not env.comparisons and not env.queued


def test_existing_parsed_versions_queue_once_and_respect_reverse_order(env):
    first, second = env.version(), env.version()
    payload = {"earlier_id": str(second), "later_id": str(first), "scope": "unknown"}
    comparison = env.comparison(env.post(payload))
    assert comparison.status == "queued"
    assert (comparison.earlier_id, comparison.later_id, comparison.scope_snapshot) == (second, first, "unknown")
    assert env.post(payload).status_code == 202
    assert env.queued == [dict(tenant_id=env.tenant, kind="compare", ids={"comparison_id": comparison.id},
                              max_attempts=env.settings.job_max_attempts)]


def test_mixed_existing_and_new_input_waits_only_for_new_parse(env):
    existing = env.version()
    payload = body()
    payload["earlier"] = {"version_id": str(existing)}
    comparison = env.comparison(env.post(payload))
    assert comparison.earlier_id == existing and comparison.status == "waiting_for_versions"
    assert [j["ids"] for j in env.queued] == [{"version_id": comparison.later_id}]
    env.worker.handle_parse(env.tenant, comparison.later_id)
    retried = env.post(payload)
    assert retried.json() == {"id": str(comparison.id), "status": "queued"}
    assert len(env.versions) == len(env.store.objects) == len(env.queued) == 2


def test_existing_rejected_version_fails_comparison_without_model_cost(env):
    rejected, parsed = env.version(status="rejected"), env.version()
    comparison = env.comparison(env.post({"earlier_id": str(rejected), "later_id": str(parsed), "scope": "complete"}))
    assert comparison.status == "failed" and comparison.cost_actual == Decimal("0")
    assert comparison.warnings[0]["reason"] == "parse_failed"
    assert not env.queued and not comparison.cost_reservations


def test_both_parse_completions_queue_comparison_once(env):
    comparison = env.comparison(env.post(body()))
    env.worker.handle_parse(env.tenant, comparison.later_id)  # completion order is independent of slot order
    assert env.comparisons[comparison.id].status == "waiting_for_versions"
    env.worker.handle_parse(env.tenant, comparison.earlier_id)
    assert env.comparisons[comparison.id].status == "queued"
    env.worker.handle_parse(env.tenant, comparison.earlier_id)
    env.worker.handle_parse(env.tenant, comparison.later_id)
    assert [j["ids"] for j in env.queued if j["kind"] == "compare"] == [{"comparison_id": comparison.id}]
    assert all(v.status == "parsed" and v.parsed_pages for v in env.versions.values())


def test_parse_rejection_fails_waiter_without_model_spend(env, monkeypatch):
    comparison = env.comparison(env.post(body()))
    def reject(*args):
        raise ParseRejected("malformed_pdf")
    monkeypatch.setattr("changelens.worker.parse_sandboxed", reject)
    env.worker.handle_parse(env.tenant, comparison.later_id)
    result = env.comparisons[comparison.id]
    assert result.status == "failed" and result.cost_actual == Decimal("0")
    assert not result.cost_reservations and not [j for j in env.queued if j["kind"] == "compare"]
    assert result.warnings == [{"code": "version_rejected", "version_id": str(comparison.later_id), "reason": "malformed_pdf"}]


def test_exhausted_parse_job_fails_waiter_without_comparison_job(env):
    comparison = env.comparison(env.post(body()))
    env.worker._on_final_failure(SimpleNamespace(kind="parse", tenant_id=env.tenant,
                                               ids={"version_id": comparison.earlier_id}))
    result = env.comparisons[comparison.id]
    assert result.status == "failed" and result.cost_actual == 0
    assert result.warnings[0]["reason"] == "parse_failed"
    assert not [j for j in env.queued if j["kind"] == "compare"]


def test_storage_failure_rolls_back_every_row_and_only_cleans_attempted_leaf_keys(env, monkeypatch):
    existing = env.version()
    retained = env.versions[existing].original_object_key
    original_put, calls = env.store.put, []
    def fail_second(key, data):
        original_put(key, data)
        calls.append(key)
        if len(calls) == 2:
            raise ConnectionError("storage acknowledgement lost")
    monkeypatch.setattr(env.store, "put", fail_second)
    problem(env.post(body()), 500, "internal_error")
    assert set(env.versions) == {existing} and not env.comparisons and not env.queued
    assert set(env.store.objects) == {retained, calls[-1]}
    assert len(env.db.intents) == 1  # unknown PUT outcome stays tracked, even after deletion
    reconcile_pending_writes(env.db, env.store, now=datetime.now(timezone.utc) + UNKNOWN_WRITE_GRACE + timedelta(seconds=1))
    assert set(env.store.objects) == {retained}
    assert len(env.db.intents) == 1


def test_definite_commit_rollback_cleans_objects_and_rows(env):
    env.db.commit_failure = "before"
    problem(env.post(body()), 500, "internal_error")
    assert_no_writes(env)


def test_lost_commit_acknowledgement_preserves_referenced_originals_and_recovers_id(env):
    env.db.commit_failure = "after"
    comparison = env.comparison(env.post(body()))
    assert len(env.versions) == len(env.store.objects) == len(env.queued) == 2
    assert env.post(body()).json()["id"] == str(comparison.id)
    assert all(v.original_object_key in env.store.objects for v in env.versions.values())


def test_unknown_commit_and_failed_recovery_never_delete_possibly_committed_originals(env):
    env.db.commit_failure, env.db.recovery_unavailable = "after", True
    problem(env.post(body()), 500, "internal_error")
    assert len(env.comparisons) == 1 and len(env.versions) == len(env.store.objects) == 2
    assert all(v.original_object_key in env.store.objects for v in env.versions.values())
