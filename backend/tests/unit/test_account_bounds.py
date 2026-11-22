"""Per-account bounds on uploads and queued work (LR-10, launch task L33). No services."""
from dataclasses import replace
from datetime import datetime, timezone
import uuid

import pytest

from changelens.api.limits import UploadSlots
from changelens.config import Settings
from comparison_fixture import Environment
from helpers import TOKEN_A, TOKEN_B, auth


@pytest.fixture
def env(monkeypatch):
    environment = Environment(monkeypatch)
    yield environment
    environment.client.close()


def bounded(env, **limits):
    env.client.app.state.settings = replace(env.settings, **limits)


def body(n=0):
    return {"earlier": {"label": "Earlier", "text": "Original synthetic brief %d" % n},
            "later": {"label": "Later", "text": "Updated synthetic brief %d" % n}, "scope": "partial"}


def post(env, n, **kwargs):
    return env.post(body(n), key="account-bounds-key-%04d" % n, **kwargs)


def upload(env, text="Standalone synthetic brief", project=None, token=TOKEN_A):
    return env.client.post(f"/projects/{project or env.project_id}/versions",
                           data={"label": "Standalone", "text": text}, headers=auth(token))


def refused(response, reason):
    assert response.status_code == 429, response.text
    assert response.headers["content-type"].startswith("application/problem+json")
    payload = response.json()
    assert (payload["code"], payload["detail"]) == ("account_limit_reached", reason)


def written(env):
    return len(env.versions), len(env.comparisons), len(env.queued), len(env.store.objects)


def test_unfinished_comparisons_are_bounded_and_free_up_when_one_finishes(env):
    bounded(env, max_unfinished_comparisons=2)
    first = env.comparison(post(env, 1)).id
    env.comparison(post(env, 2))
    before = written(env)
    refused(post(env, 3), "unfinished_comparisons")
    assert written(env) == before == (4, 2, 4, 4)
    env.comparisons[first].status = "complete"
    assert post(env, 3).status_code == 202


@pytest.mark.parametrize("status", ["waiting_for_versions", "queued", "running"])
def test_every_unfinished_status_counts(env, status):
    bounded(env, max_unfinished_comparisons=1)
    env.comparison(post(env, 1)).status = status
    refused(post(env, 2), "unfinished_comparisons")


def test_a_replay_of_an_accepted_request_is_still_answered_at_the_limit(env):
    bounded(env, max_unfinished_comparisons=1)
    first = post(env, 1)
    again = post(env, 1)
    assert (first.status_code, again.status_code) == (202, 202)
    assert first.json()["id"] == again.json()["id"]
    assert written(env) == (2, 1, 2, 2)


def test_unparsed_versions_are_bounded_for_both_upload_routes(env):
    bounded(env, max_unparsed_versions=3, max_unfinished_comparisons=10)
    env.comparison(post(env, 1))  # two unparsed versions
    before = written(env)
    refused(post(env, 2), "unparsed_versions")  # two more would make four
    assert written(env) == before
    assert upload(env).status_code == 201  # the third
    before = written(env)
    refused(upload(env, "Another synthetic brief"), "unparsed_versions")
    assert written(env) == before
    # Comparing two versions that are already there adds no upload.
    earlier, later = env.version(), env.version()
    existing = {"earlier": {"version_id": str(earlier)}, "later": {"version_id": str(later)}, "scope": "complete"}
    assert env.post(existing, key="account-bounds-existing-1").status_code == 202
    # Parsed or rejected versions no longer count.
    for version in env.versions.values():
        if version.status == "uploaded":
            version.status = "rejected"
    assert upload(env, "Another synthetic brief").status_code == 201


def test_stored_bytes_have_a_ceiling_per_account(env):
    for _ in range(3):
        env.version()  # 24 bytes each
    bounded(env, max_stored_bytes=100)
    before = written(env)
    refused(post(env, 1), "stored_bytes")  # 72 + 26 + 25 bytes
    assert written(env) == before
    assert upload(env, "x" * 28).status_code == 201  # exactly at the ceiling
    before = written(env)
    refused(upload(env, "y"), "stored_bytes")
    assert written(env) == before
    # Comparing versions that are already stored adds no bytes.
    ids = [str(v) for v in list(env.versions)[:2]]
    existing = {"earlier": {"version_id": ids[0]}, "later": {"version_id": ids[1]}, "scope": "complete"}
    assert env.post(existing, key="account-bounds-existing-2").status_code == 202


def test_bounds_count_this_account_only(env):
    bounded(env, max_unfinished_comparisons=1, max_unparsed_versions=2, max_stored_bytes=200)
    for _ in range(4):
        env.version(status="uploaded", project=env.foreign_project, tenant=env.other_tenant)
    assert post(env, 1, project=env.foreign_project, token=TOKEN_B).status_code == 429  # the other account is full
    assert post(env, 2).status_code == 202


def test_a_deleted_project_frees_queued_work_but_its_bytes_count_until_they_are_removed(env):
    bounded(env, max_unfinished_comparisons=1, max_unparsed_versions=2)
    env.comparison(post(env, 1, project=env.other_project))
    refused(post(env, 2), "unfinished_comparisons")
    with env.db.tenant_scope(env.tenant) as repo:
        repo.state["projects"][env.other_project].deleted_at = datetime.now(timezone.utc)
    assert post(env, 2).status_code == 202
    stored = sum(v.size_bytes for v in env.versions.values())
    bounded(env, max_unfinished_comparisons=10, max_unparsed_versions=10, max_stored_bytes=stored)
    refused(upload(env, "z"), "stored_bytes")


def test_upload_slots_bound_the_process_and_each_account():
    slots, a, b, c = UploadSlots(4), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    assert slots.per_account == 2
    assert [slots.take(a), slots.take(a), slots.take(a)] == [True, True, False]  # one account: half the slots
    assert [slots.take(b), slots.take(b), slots.take(c)] == [True, True, False]  # the process is full
    slots.release(a)
    assert slots.take(c) and not slots.take(b)
    for tenant in (a, b, b, c):
        slots.release(tenant)
    assert slots.used == 0 and not slots.by_account
    assert UploadSlots(1).per_account == 1


def test_an_upload_beyond_the_slots_is_refused_before_its_body_is_stored(env):
    slots = env.client.app.state.upload_slots
    assert slots.limit == env.settings.max_concurrent_uploads
    while slots.take(uuid.uuid4()):
        pass
    for response in (post(env, 1), upload(env)):
        assert response.status_code == 429, response.text
        assert response.json()["code"] == "rate_limited" and int(response.headers["Retry-After"]) >= 1
    assert written(env) == (0, 0, 0, 0)


def test_one_account_cannot_take_every_slot(env):
    slots = env.client.app.state.upload_slots
    for _ in range(slots.per_account):
        assert slots.take(env.tenant)
    assert post(env, 1).status_code == 429
    assert post(env, 2, project=env.foreign_project, token=TOKEN_B).status_code == 202


def test_a_slot_is_given_back_after_success_refusal_and_failure(env):
    slots = env.client.app.state.upload_slots
    assert post(env, 1).status_code == 202 and slots.used == 0
    assert env.post({"scope": "partial"}, key="account-bounds-invalid-1").status_code == 422 and slots.used == 0
    assert upload(env).status_code == 201 and slots.used == 0
    assert upload(env, project=uuid.uuid4()).status_code == 404 and slots.used == 0
    assert env.client.post(f"/projects/{env.project_id}/versions", data={"label": "x", "text": "y"}).status_code == 401
    assert slots.used == 0 and not slots.by_account


BOUNDS = {"max_unparsed_versions": "CHANGELENS_MAX_UNPARSED_VERSIONS",
          "max_unfinished_comparisons": "CHANGELENS_MAX_UNFINISHED_COMPARISONS",
          "max_stored_bytes": "CHANGELENS_MAX_STORED_BYTES",
          "max_concurrent_uploads": "CHANGELENS_MAX_CONCURRENT_UPLOADS"}


def test_bounds_come_from_the_environment(monkeypatch):
    monkeypatch.setenv("CHANGELENS_AUTH_MODE", "dev")
    monkeypatch.setenv("CHANGELENS_ENV", "local")
    monkeypatch.setenv("CHANGELENS_DEV_TOKEN", "t" * 16)
    for name in BOUNDS.values():
        monkeypatch.delenv(name, raising=False)
    defaults = Settings.from_env()
    assert all(isinstance(getattr(defaults, field), int) and getattr(defaults, field) >= 1 for field in BOUNDS)
    assert defaults.max_unparsed_versions >= 2 * defaults.max_unfinished_comparisons
    for value, name in enumerate(BOUNDS.values(), 5):
        monkeypatch.setenv(name, str(value))
    assert [getattr(Settings.from_env(), field) for field in BOUNDS] == [5, 6, 7, 8]
    monkeypatch.setenv("CHANGELENS_MAX_STORED_BYTES", "many")
    with pytest.raises(RuntimeError):
        Settings.from_env()


@pytest.mark.parametrize("field, value", [("max_unparsed_versions", 1), ("max_unfinished_comparisons", 0),
                                          ("max_stored_bytes", 0), ("max_concurrent_uploads", 0),
                                          ("max_stored_bytes", 1.5), ("max_concurrent_uploads", True)])
def test_bounds_must_be_positive_whole_numbers(env, field, value):
    with pytest.raises(ValueError):
        replace(env.settings, **{field: value})
