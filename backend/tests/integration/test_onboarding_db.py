"""Account onboarding state in Postgres (O-23): tenant isolation, row locking and deletion scope."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
import uuid

import pytest
from sqlalchemy.exc import IntegrityError

from changelens.domain.retention import process_project_deletion, request_project_deletion
from conftest import TENANT_A, TENANT_B, TOKEN_A, TOKEN_B, auth

NOT_STARTED = {"completed": False, "step": None}
COMPLETED = {"completed": True, "step": None}


def get(env, token=TOKEN_A):
    r = env.client.get("/me/onboarding", headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


def put(env, body, token=TOKEN_A):
    r = env.client.put("/me/onboarding", json=body, headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()


def rows(env):
    return env.sql("SELECT account_id, tenant_id, onboarding_step, onboarding_completed_at IS NOT NULL "
                   "FROM account_onboarding ORDER BY tenant_id")


def test_a_tenants_state_is_invisible_to_and_unchanged_by_another(env):
    assert put(env, {"step": 4}, TOKEN_A) == {"completed": False, "step": 4}
    assert get(env, TOKEN_B) == NOT_STARTED
    assert put(env, {"step": 2}, TOKEN_B) == {"completed": False, "step": 2}
    assert put(env, {"completed": True}, TOKEN_B) == COMPLETED
    assert get(env, TOKEN_A) == {"completed": False, "step": 4}
    with env.db.tenant_scope(TENANT_B) as repo:
        assert repo.onboarding(TENANT_A) is None  # tenant-scoped repository never sees A's row
        assert repo.record_onboarding(TENANT_A, completed=True) is None  # nor writes to it
    assert get(env, TOKEN_A) == {"completed": False, "step": 4}


def test_each_tenants_first_write_creates_its_own_row(env):
    assert rows(env) == []
    assert get(env, TOKEN_A) == NOT_STARTED and get(env, TOKEN_B) == NOT_STARTED
    assert rows(env) == []  # reads create nothing
    put(env, {"step": 1}, TOKEN_A)
    assert rows(env) == [(TENANT_A, TENANT_A, 1, False)]
    put(env, {"completed": True}, TOKEN_B)
    assert rows(env) == [(TENANT_A, TENANT_A, 1, False), (TENANT_B, TENANT_B, None, True)]


def test_the_database_rejects_out_of_range_and_contradictory_rows(env):
    for values in ("33, NULL", "0, NULL", "2, now()"):
        with pytest.raises(IntegrityError):
            env.sql("INSERT INTO account_onboarding (account_id, tenant_id, onboarding_step, onboarding_completed_at, "
                    f"updated_at) VALUES (:id, :id, {values}, now())", id=uuid.uuid4())


def test_a_step_write_holding_the_row_lock_cannot_undo_a_waiting_completion(env):
    put(env, {"step": 1})
    locked, release = Event(), Event()

    def slow_step():
        with env.db.tenant_scope(TENANT_A) as repo:
            repo.record_onboarding(TENANT_A, step=5)
            locked.set()
            assert release.wait(timeout=10)

    with ThreadPoolExecutor(max_workers=2) as pool:
        stepping = pool.submit(slow_step)
        assert locked.wait(timeout=5)
        completing = pool.submit(put, env, {"completed": True})
        release.set()
        stepping.result(timeout=10)
        assert completing.result(timeout=10) == COMPLETED
    assert get(env) == COMPLETED and rows(env) == [(TENANT_A, TENANT_A, None, True)]


def test_step_writes_waiting_behind_a_completion_leave_it_completed(env):
    put(env, {"step": 2})
    locked, release = Event(), Event()

    def slow_completion():
        with env.db.tenant_scope(TENANT_A) as repo:
            repo.record_onboarding(TENANT_A, completed=True)
            locked.set()
            assert release.wait(timeout=10)

    with ThreadPoolExecutor(max_workers=5) as pool:
        completing = pool.submit(slow_completion)
        assert locked.wait(timeout=5)
        steps = [pool.submit(put, env, {"step": n}) for n in (3, 4, 5, 6)]
        release.set()
        completing.result(timeout=10)
        assert [f.result(timeout=10) for f in steps] == [COMPLETED] * 4
    assert rows(env) == [(TENANT_A, TENANT_A, None, True)]


def test_a_completion_racing_first_step_writes_ends_completed_with_a_null_step(env):
    for _ in range(5):  # repeated on a fresh row each time, including the first-insert race
        env.sql("DELETE FROM account_onboarding RETURNING account_id")
        writers = [{"step": n} for n in (1, 2, 3, 4, 5, 6, 7)] + [{"completed": True}]
        barrier = Barrier(len(writers))

        def write(body):
            barrier.wait(timeout=10)
            with env.db.tenant_scope(TENANT_A) as repo:
                repo.record_onboarding(TENANT_A, step=body.get("step"), completed=body.get("completed", False))

        with ThreadPoolExecutor(max_workers=len(writers)) as pool:
            for f in [pool.submit(write, body) for body in writers]:
                f.result(timeout=15)
        assert get(env) == COMPLETED
        assert rows(env) == [(TENANT_A, TENANT_A, None, True)]


def test_account_deletion_removes_the_row_and_project_deletion_leaves_it(env):
    put(env, {"step": 3}, TOKEN_A)
    put(env, {"completed": True}, TOKEN_B)
    project = uuid.UUID(env.project(TOKEN_A))
    request_project_deletion(env.db, TENANT_A, project)
    assert process_project_deletion(env.db, env.store, TENANT_A, project)
    assert get(env, TOKEN_A) == {"completed": False, "step": 3}  # not project data
    with env.db.tenant_scope(TENANT_A) as repo:
        assert repo.delete_onboarding(TENANT_A) == 1
    assert get(env, TOKEN_A) == NOT_STARTED
    assert rows(env) == [(TENANT_B, TENANT_B, None, True)]
