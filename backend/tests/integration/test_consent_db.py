"""Usage-events consent in Postgres (D-18 tier B): tenant isolation and append-only answers.
Route behaviour without services is in tests/unit/test_consent.py; RLS coverage in test_rls_db.py."""
from conftest import SUBJECT_A, TENANT_A, TENANT_B, TOKEN_A, TOKEN_B, auth

CURRENT = "2026-11-13"


def put(env, granted, token=TOKEN_A):
    r = env.client.put("/me/consent", json={"usage_events": {"granted": granted, "policy_version": CURRENT}},
                       headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()["usage_events"]


def get(env, token=TOKEN_A):
    r = env.client.get("/me/consent", headers=auth(token))
    assert r.status_code == 200, r.text
    return r.json()["usage_events"]


def test_answers_are_appended_and_the_newest_wins_with_a_utc_timestamp(env):
    put(env, True)
    latest = put(env, False)
    assert get(env) == latest and latest["granted"] is False and latest["decided_at"].endswith("+00:00")
    assert env.sql("SELECT granted FROM consent_events ORDER BY decided_at") == [(True,), (False,)]


def test_a_tenants_answer_is_invisible_to_another(env):
    put(env, True, TOKEN_A)
    assert get(env, TOKEN_B)["granted"] is None
    with env.db.tenant_scope(TENANT_B) as repo:
        assert repo.consent(env.users[SUBJECT_A], "usage_events") is None
    with env.db.tenant_scope(TENANT_A) as repo:
        assert repo.consent(env.users[SUBJECT_A], "usage_events").granted is True
