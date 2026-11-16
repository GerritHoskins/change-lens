"""`POST /session` in Postgres (I-8 S2, §7 items 3 and 4): concurrent first calls and tenant isolation.
Dev mode: each token maps to a subject that has no user until its first session call."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from fastapi.testclient import TestClient

from changelens.api.app import create_app
from conftest import DEV_TOKENS, TOKEN_A, auth

TOKEN_C = "dev-token-new-subject-c-0123456789"
TOKEN_D = "dev-token-new-subject-d-0123456789"
TOKENS = {**DEV_TOKENS, TOKEN_C: "dev:new-c", TOKEN_D: "dev:new-d"}


def test_eight_parallel_first_calls_make_one_user_and_one_membership(env_factory):
    env = env_factory(dev_tokens=TOKENS)
    barrier = Barrier(8)

    def call(_):
        client = TestClient(create_app(env.settings, env.db, env.store), raise_server_exceptions=False)
        barrier.wait(timeout=10)
        return client.post("/session", headers=auth(TOKEN_C))

    with ThreadPoolExecutor(max_workers=8) as pool:
        responses = list(pool.map(call, range(8)))
    assert [r.status_code for r in responses] == [200] * 8
    assert all(r.json() == {"status": "active", "onboarding": {"completed": False, "step": None},
                            "consent": {"usage_events": None}} for r in responses)
    assert env.sql("SELECT count(*) FROM users WHERE idp_subject = 'dev:new-c'") == [(1,)]
    assert env.sql("SELECT count(*), count(DISTINCT tenant_id) FROM memberships m JOIN users u ON u.id = m.user_id "
                   "WHERE u.idp_subject = 'dev:new-c'") == [(1, 1)]


def test_two_new_subjects_get_separate_tenants_and_cannot_see_each_others_data(env_factory):
    env = env_factory(dev_tokens=TOKENS)
    for token in (TOKEN_C, TOKEN_D):
        assert env.client.post("/session", headers=auth(token)).status_code == 200
    tenants = env.sql("SELECT u.idp_subject, m.tenant_id FROM memberships m JOIN users u ON u.id = m.user_id "
                      "WHERE u.idp_subject IN ('dev:new-c', 'dev:new-d')")
    assert len({tenant for _, tenant in tenants}) == 2
    project = env.project(TOKEN_C)
    assert env.client.put("/me/onboarding", json={"step": 4}, headers=auth(TOKEN_C)).status_code == 200
    assert env.get("/projects", TOKEN_D).json() == {"projects": []}
    assert env.get("/projects/%s" % project, TOKEN_D).status_code == 404
    assert env.client.post("/session", headers=auth(TOKEN_D)).json()["onboarding"] == {"completed": False, "step": None}
    assert env.client.post("/session", headers=auth(TOKEN_C)).json()["onboarding"] == {"completed": False, "step": 4}


def test_a_seeded_dev_user_keeps_its_tenant(env):
    before = env.sql("SELECT count(*) FROM memberships")
    assert env.client.post("/session", headers=auth(TOKEN_A)).status_code == 200
    assert env.sql("SELECT count(*) FROM memberships") == before
