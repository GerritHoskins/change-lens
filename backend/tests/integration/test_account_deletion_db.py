"""`DELETE /me` in Postgres and MinIO (I-8 S5, §6 items 1-3 and 5-7).

The IdP is a fake that records calls and can fail. The Apple step (item 4) needs S4's token column and
revoke function, so it is not built or tested here.
"""
import logging
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient

from changelens.api.app import create_app
from changelens.domain import TenantRepo
from changelens.domain.accounts import run_account_deletions
from changelens.domain.retention import run_maintenance
from conftest import TENANT_A, TENANT_B
from helpers import EARLIER_LINES, LATER_LINES, SUBJECT_A, SUBJECT_B, TOKEN_A, TOKEN_B, auth

TENANT_TABLES = ("projects", "source_versions", "comparisons", "findings", "fact_cache", "jobs", "review_events",
                 "client_approvals", "object_write_intents", "object_purge_intents", "project_deletions",
                 "account_onboarding", "consent_events", "demo_comparisons", "demo_feedback", "memberships")


class FakeIdp:
    def __init__(self, failures=0):
        self.calls, self.failures = [], failures

    def delete_user(self, subject):
        self.calls.append(subject)
        if self.failures:
            self.failures -= 1
            raise ConnectionError("idp down")


def _account(env, token, name):
    """Two projects with versions, a comparison (counted for the demo limit), a review, an onboarding row, a
    consent answer and the demo feedback with both text fields."""
    assert env.client.put("/me/onboarding", json={"step": 3}, headers=auth(token)).status_code == 200
    consent = {"usage_events": {"granted": True, "policy_version": "2026-11-13"}}
    assert env.client.put("/me/consent", json=consent, headers=auth(token)).status_code == 200
    feedback = {"missing": "other", "missing_other": "A synthetic wish, long enough.", "anything_else": "Nothing.",
                "price": "eur_5"}
    assert env.client.post("/me/demo-feedback", json=feedback, headers=auth(token)).status_code == 201
    projects = []
    for n in range(2):
        pid = env.project(token, name="%s %d" % (name, n))
        a = env.upload(pid, token, label="v1", text="\n".join(EARLIER_LINES)).json()["id"]
        b = env.upload(pid, token, label="v2", text="\n".join(LATER_LINES)).json()["id"]
        env.worker.run_until_idle()
        projects.append((pid, a, b))
    pid, a, b = projects[0]
    cid = env.compare(pid, a, b, token=token).json()["id"]
    env.worker.run_until_idle()
    finding = env.get("/comparisons/%s/findings" % cid, token).json()["findings"][0]
    sides = {item["side"] for item in env.get("/findings/" + finding["id"], token).json()["evidence"]}
    review = {"action": "confirmed", "page_opened": False,
              "evidence_mode": {"before": "text_only" if "earlier" in sides else None,
                                "after": "text_only" if "later" in sides else None}}
    assert env.client.post("/findings/%s/reviews" % finding["id"], json=review, headers=auth(token)).status_code == 201
    return projects


def _client(env, idp):
    return TestClient(create_app(env.settings, env.db, env.store, idp=idp), raise_server_exceptions=False)


def _objects(env, tenant, projects):
    """Object versions under this test's projects (the shared test bucket keeps other tests' objects)."""
    n = 0
    for pid, _, _ in projects:
        page = env.store.client.list_object_versions(Bucket=env.store.bucket, Prefix="%s/%s/" % (tenant, pid))
        n += len(page.get("Versions", [])) + len(page.get("DeleteMarkers", []))
    return n


def _rows(env, tenant):
    return {t: env.sql("SELECT count(*) FROM %s WHERE tenant_id = :t" % t, t=tenant)[0][0] for t in TENANT_TABLES}


def _user(env, subject_or_id):
    return env.sql("SELECT idp_subject, deleted_at FROM users WHERE id = :u", u=subject_or_id)


def test_deleting_an_account_removes_its_tenant_and_leaves_a_tombstone(env, caplog):
    pa, pb = _account(env, TOKEN_A, "A"), _account(env, TOKEN_B, "B")
    b_rows, b_objects = _rows(env, TENANT_B), _objects(env, TENANT_B, pb)
    assert _objects(env, TENANT_A, pa) > 0 and all(b_rows[t] for t in ("projects", "review_events", "account_onboarding",
                                                                              "consent_events", "demo_comparisons",
                                                                              "demo_feedback"))
    idp = FakeIdp()
    with caplog.at_level(logging.DEBUG):
        r = _client(env, idp).delete("/me", headers=auth(TOKEN_A))
    assert r.status_code == 204 and r.content == b""
    assert _rows(env, TENANT_A) == {t: 0 for t in TENANT_TABLES} and _objects(env, TENANT_A, pa) == 0
    assert idp.calls == [SUBJECT_A]  # the Logto user, deleted once
    user_a = env.users[SUBJECT_A]
    [(subject, deleted_at)] = _user(env, user_a)  # the tombstone: ID and timestamps only
    assert subject is None and deleted_at is not None
    receipt = env.sql("SELECT status, idp_deleted_at IS NOT NULL, completed_at IS NOT NULL FROM account_deletions "
                      "WHERE user_id = :u", u=user_a)
    assert receipt == [("complete", True, True)]
    # Item 5: the other tenant is untouched.
    assert _rows(env, TENANT_B) == b_rows and _objects(env, TENANT_B, pb) == b_objects > 0
    assert _user(env, env.users[SUBJECT_B])[0] == (SUBJECT_B, None)
    assert env.get("/projects", TOKEN_B).status_code == 200
    # Item 7: no subject or token in responses, logs or the receipt.
    logs = "\n".join(rec.getMessage() for rec in caplog.records if rec.name.startswith("changelens"))
    for secret in (SUBJECT_A, TOKEN_A):
        assert secret not in logs and secret not in r.text
    assert SUBJECT_A not in str(env.sql("SELECT * FROM account_deletions"))


class ForgetfulIdp(FakeIdp):
    """Like Logto: a deleted user is unknown afterwards."""

    def __init__(self):
        super().__init__()
        self.known = {SUBJECT_A, SUBJECT_B}

    def delete_user(self, subject):
        super().delete_user(subject)
        self.known.discard(subject)

    def user(self, subject):
        return {"id": subject} if subject in self.known else None


def test_a_token_from_before_the_deletion_cannot_create_the_account_again(env):
    """LR-3: the tombstone has no subject, and the token stays valid for up to 15 minutes."""
    _account(env, TOKEN_A, "A")
    client = _client(env, ForgetfulIdp())
    assert client.delete("/me", headers=auth(TOKEN_A)).status_code == 204
    users, memberships = env.sql("SELECT count(*) FROM users"), env.sql("SELECT count(*) FROM memberships")
    r = client.post("/session", headers=auth(TOKEN_A))
    assert r.status_code == 401 and r.json()["code"] == "unauthenticated"
    assert env.sql("SELECT count(*) FROM users") == users
    assert env.sql("SELECT count(*) FROM memberships") == memberships
    assert env.sql("SELECT count(*) FROM users WHERE idp_subject = :s", s=SUBJECT_A) == [(0,)]
    assert client.post("/session", headers=auth(TOKEN_B)).status_code == 200  # another account still signs in


def test_the_account_is_locked_out_right_after_the_freeze(env, monkeypatch):
    _account(env, TOKEN_A, "A")
    monkeypatch.setattr(env.store, "delete_prefix", lambda prefix: (_ for _ in ()).throw(ConnectionError("down")))
    client = _client(env, FakeIdp())
    assert client.delete("/me", headers=auth(TOKEN_A)).status_code == 202
    for method, path in (("GET", "/projects"), ("GET", "/me/onboarding"), ("PUT", "/me/onboarding"),
                         ("POST", "/projects"), ("DELETE", "/me")):
        r = client.request(method, path, headers=auth(TOKEN_A), json={"step": 1} if method == "PUT" else None)
        assert r.status_code == 401 and r.json()["code"] == "unauthenticated", (method, path)
    r = client.post("/session", headers=auth(TOKEN_A))  # no re-registration under the deleted user
    assert r.status_code == 401
    assert env.sql("SELECT count(*) FROM memberships WHERE status = 'active' AND tenant_id = :t", t=TENANT_A) == [(0,)]
    assert env.get("/projects", TOKEN_B).status_code == 200


def _fail_once_at(step, env, monkeypatch, idp):
    if step == "projects":
        real = env.store.delete_prefix
        state = {"failed": False}

        def flaky(prefix):
            if not state["failed"]:
                state["failed"] = True
                raise ConnectionError("down")
            return real(prefix)
        monkeypatch.setattr(env.store, "delete_prefix", flaky)
    elif step == "account_rows":
        real = TenantRepo.delete_onboarding
        state = {"failed": False}

        def flaky(self, account_id):
            if not state["failed"]:
                state["failed"] = True
                raise ConnectionError("db blip")
            return real(self, account_id)
        monkeypatch.setattr(TenantRepo, "delete_onboarding", flaky)
    else:
        idp.failures = 1


@pytest.mark.parametrize("step", ["projects", "account_rows", "idp"])
def test_a_failure_at_any_step_returns_202_and_maintenance_finishes_it(env, monkeypatch, step):
    pa = _account(env, TOKEN_A, "A")
    idp = FakeIdp()
    _fail_once_at(step, env, monkeypatch, idp)
    assert _client(env, idp).delete("/me", headers=auth(TOKEN_A)).status_code == 202
    user_a = env.users[SUBJECT_A]
    assert env.sql("SELECT status FROM account_deletions WHERE user_id = :u", u=user_a) == [("pending",)]
    assert _user(env, user_a)[0][0] == SUBJECT_A  # not a tombstone yet
    assert run_account_deletions(env.db, env.store, idp) == (0, 0)  # backed off: not due yet
    later = datetime.now(timezone.utc) + timedelta(hours=2)
    summary = run_maintenance(env.db, env.store, now=later, execute=True, idp=idp)
    assert (summary["completed_account_deletions"], summary["pending_account_deletions"]) == (1, 0)
    assert _rows(env, TENANT_A) == {t: 0 for t in TENANT_TABLES} and _objects(env, TENANT_A, pa) == 0
    assert _user(env, user_a)[0][0] is None
    # The Logto deletion ran once, plus one retry only where it was the step that failed.
    assert idp.calls == [SUBJECT_A] * (2 if step == "idp" else 1)
    run_maintenance(env.db, env.store, now=later + timedelta(hours=2), execute=True, idp=idp)
    assert len(idp.calls) == (2 if step == "idp" else 1)  # a complete receipt never calls again


def test_without_a_configured_idp_the_deletion_stays_pending(env):
    _account(env, TOKEN_A, "A")
    assert _client(env, None).delete("/me", headers=auth(TOKEN_A)).status_code == 202
    later = datetime.now(timezone.utc) + timedelta(hours=2)
    assert run_account_deletions(env.db, env.store, None, now=later) == (0, 1)
    user_a = env.users[SUBJECT_A]
    assert env.sql("SELECT status, idp_deleted_at FROM account_deletions WHERE user_id = :u", u=user_a) == [
        ("pending", None)]
    assert _rows(env, TENANT_A)["projects"] == 0  # everything before the IdP step is done
    assert run_account_deletions(env.db, env.store, FakeIdp(), now=later + timedelta(hours=2)) == (1, 0)


def test_the_functions_refuse_another_tenants_user(env):
    """A receipt the app writes in its own tenant can't reach a user of another tenant."""
    user_b = env.users[SUBJECT_B]
    with env.db.tenant_scope(TENANT_A) as repo:
        from sqlalchemy import text
        repo.s.execute(text("INSERT INTO account_deletions (user_id, tenant_id, status, attempts) "
                            "VALUES (:u, :t, 'pending', 0)"), {"u": user_b, "t": TENANT_A})
        for fn in ("account_freeze", "account_tombstone"):
            assert repo.s.execute(text("SELECT %s(:u)" % fn), {"u": user_b}).scalar_one() is False
        assert repo.s.execute(text("SELECT account_deletion_subject(:u)"), {"u": user_b}).scalar_one() is None
        repo.s.rollback()
    assert _user(env, user_b)[0] == (SUBJECT_B, None)
