"""Per-account bounds on uploads and queued work in Postgres (LR-10, launch task L33)."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
import uuid

from fastapi.testclient import TestClient

from conftest import TENANT_A
from helpers import TOKEN_A, TOKEN_B, auth


def create(env, project, n, token=TOKEN_A, client=None):
    body = {"earlier": {"label": "earlier", "text": "Budget: EUR %d." % n},
            "later": {"label": "later", "text": "Budget: EUR %d." % (n + 1000)}, "scope": "partial"}
    return (client or env.client).post(f"/projects/{project}/comparisons", json=body,
                                       headers={**auth(token), "Idempotency-Key": str(uuid.uuid4())})


def refused(response, reason):
    assert response.status_code == 429, response.text
    payload = response.json()
    assert (payload["code"], payload["detail"]) == ("account_limit_reached", reason)


def rows(env):
    return env.sql("SELECT (SELECT count(*) FROM comparisons), (SELECT count(*) FROM source_versions), "
                   "(SELECT count(*) FROM jobs), (SELECT count(*) FROM object_write_intents)")


def test_unfinished_comparisons_are_bounded_per_account_until_the_worker_is_done(env_factory):
    env = env_factory(max_unfinished_comparisons=2)
    project, other = env.project(), env.project(TOKEN_B)
    assert [create(env, project, n).status_code for n in (1, 2)] == [202, 202]
    before = rows(env)
    refused(create(env, project, 3), "unfinished_comparisons")
    assert rows(env) == before and before[0][:3] == (2, 4, 4)
    assert create(env, other, 4, TOKEN_B).status_code == 202  # the other account has its own bound
    env.worker.run_until_idle()
    assert create(env, project, 3).status_code == 202


def test_unparsed_versions_are_bounded_for_both_upload_routes(env_factory):
    env = env_factory(max_unparsed_versions=3, max_unfinished_comparisons=10)
    project = env.project()
    assert [env.upload(project, text="brief %d" % n).status_code for n in range(3)] == [201, 201, 201]
    before = rows(env)
    refused(env.upload(project, text="one more"), "unparsed_versions")
    refused(create(env, project, 1), "unparsed_versions")
    assert rows(env) == before
    env.worker.run_until_idle()
    assert env.upload(project, text="one more").status_code == 201


def test_stored_bytes_have_a_ceiling_and_count_only_this_account(env_factory):
    env = env_factory(max_stored_bytes=60)
    project, other = env.project(), env.project(TOKEN_B)
    assert env.upload(other, TOKEN_B, text="b" * 60).status_code == 201
    assert [env.upload(project, text=c * 30).status_code for c in "xy"] == [201, 201]  # exactly at the ceiling
    before = rows(env)
    refused(env.upload(project, text="z"), "stored_bytes")
    refused(create(env, project, 1), "stored_bytes")
    assert rows(env) == before
    assert env.sql("SELECT sum(size_bytes) FROM source_versions WHERE tenant_id = :t", t=TENANT_A) == [(60,)]


def test_a_deleted_project_frees_queued_work_but_its_bytes_count_while_its_rows_exist(env_factory):
    env = env_factory(max_unfinished_comparisons=1, max_unparsed_versions=2)
    waiting, project = env.project(), env.project()
    assert create(env, waiting, 1).status_code == 202
    refused(create(env, project, 2), "unfinished_comparisons")
    # Deletion requested and not yet carried out: the worker skips this project's jobs from here on.
    env.sql("UPDATE projects SET deleted_at = now() WHERE id = :p RETURNING id", p=waiting)
    assert create(env, project, 2).status_code == 202
    stored = env.sql("SELECT sum(size_bytes) FROM source_versions WHERE tenant_id = :t", t=TENANT_A)[0][0]
    full = env_factory(max_stored_bytes=int(stored), max_unparsed_versions=10, max_unfinished_comparisons=10)
    refused(full.upload(project, text="z"), "stored_bytes")


def test_two_requests_of_one_account_cannot_both_pass_on_the_same_count(env_factory):
    env = env_factory(max_unfinished_comparisons=1)
    projects, start = [env.project(), env.project()], Barrier(2)

    def submit(n):
        with TestClient(env.client.app, raise_server_exceptions=False) as client:
            start.wait(timeout=5)
            return create(env, projects[n], n, client=client)

    with ThreadPoolExecutor(max_workers=2) as pool:
        responses = list(pool.map(submit, range(2)))
    assert sorted(r.status_code for r in responses) == [202, 429], [r.text for r in responses]
    assert env.sql("SELECT count(*) FROM comparisons") == [(1,)]
    assert env.sql("SELECT count(*) FROM source_versions") == [(2,)]
