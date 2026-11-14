"""Row-level security in Postgres (I-8 S3, §8 items 1-7).

conftest runs every integration test as `changelens_app` (item 6). These tests check the policies and
grants in the catalog, direct SQL as the app role, an unfiltered query, every route and job kind across
tenants, and the `SECURITY DEFINER` functions.
"""
import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, ProgrammingError

from changelens import jobs
from changelens.domain import Database
from changelens.db import APP_ROLE, OWNER_ROLE
from conftest import TENANT_A, TENANT_B, TEST_DB, db_url
from helpers import SUBJECT_A, TOKEN_A, TOKEN_B, auth
from helpers import EARLIER_LINES, LATER_LINES
from test_reviews import _compared, _findings, _post

EXCEPTIONS = {"users", "alembic_version", "rate_limit_counters"}  # no tenant_id: only through the functions
FUNCTIONS = {  # name -> result columns (03 §6: IDs and scalar fields only)
    "session_lookup": ["user_id", "tenant_id", "member_role"],
    "session_bootstrap": ["outcome", "user_id", "tenant_id", "member_role"],
    "queue_claim": ["job_id", "tenant_id", "kind", "ids", "attempts", "max_attempts"],
    "queue_reclaim_expired": ["job_id", "tenant_id", "kind", "ids", "attempts", "max_attempts"],
    "pending_object_writes": ["tenant_id", "intent_id"],
    "maintenance_candidates": ["list", "tenant_id", "item_id"],
    "account_freeze": ["account_freeze"],  # I-8 S5
    "account_deletion_subject": ["account_deletion_subject"],
    "account_tombstone": ["account_tombstone"],
    "account_deletion_candidates": ["tenant_id", "user_id"],
    "rate_limit_hit": ["rate_limit_hit"],  # I-8 S6
    "rate_limit_prune": ["rate_limit_prune"],
    "global_spend_since": ["global_spend_since"],
}


def _tables(env):
    rows = env.sql("SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity, "
                   "EXISTS (SELECT 1 FROM information_schema.columns k WHERE k.table_schema = 'public' "
                   "        AND k.table_name = c.relname AND k.column_name = 'tenant_id') "
                   "FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace "
                   "WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p') ORDER BY 1")
    return {name: (rls, forced, tenant) for name, rls, forced, tenant in rows}


def tenant_tables(env):
    return sorted(name for name, (_, _, tenant) in _tables(env).items() if tenant)


# 1. Policy coverage ------------------------------------------------------------------------------
def test_every_table_with_tenant_id_has_a_forced_tenant_policy_and_nothing_else_is_uncovered(env):
    tables = _tables(env)
    policies = {(t, cmd): (using, check) for t, cmd, using, check in env.sql(
        "SELECT tablename, cmd, qual, with_check FROM pg_policies WHERE schemaname = 'public'")}
    covered = tenant_tables(env)
    assert len(covered) == 15
    for name, (rls, forced, tenant) in tables.items():
        if not tenant:
            assert name in EXCEPTIONS, "%s has no tenant_id and is not an explicit exception" % name
            continue
        assert rls and forced, "%s: RLS must be enabled and forced" % name
        assert [cmd for t, cmd in policies if t == name] == ["ALL"], name
        using, check = policies[(name, "ALL")]
        expected = "(tenant_id = (NULLIF(current_setting('app.tenant_id'::text, true), ''::text))::uuid)"
        assert using == expected and check == expected, name
    for name in ("users", "rate_limit_counters"):  # RLS on, no policy: nothing visible without the functions
        assert tables[name][:2] == (True, True), name
    assert not [p for p in policies if p[0] in EXCEPTIONS]


def test_the_app_role_has_only_row_rights_on_tenant_tables_and_none_on_users(env):
    grants = env.sql("SELECT table_name, string_agg(privilege_type, ',' ORDER BY privilege_type) "
                     "FROM information_schema.role_table_grants WHERE grantee = :r GROUP BY 1", r=APP_ROLE)
    assert dict(grants) == {t: "DELETE,INSERT,SELECT,UPDATE" for t in tenant_tables(env)}
    attrs = env.sql("SELECT rolname, rolsuper, rolbypassrls FROM pg_roles WHERE rolname IN (:a, :o) ORDER BY 1",
                    a=APP_ROLE, o=OWNER_ROLE)
    assert attrs == [(APP_ROLE, False, False), (OWNER_ROLE, False, True)]
    owners = env.sql("SELECT DISTINCT tableowner FROM pg_tables WHERE schemaname = 'public'")
    assert owners == [(OWNER_ROLE,)]


# 2 and 3. Direct SQL as the app role, and a deliberately unfiltered query ------------------------
def _fill_every_tenant_table(env):
    """Rows for tenants A and B in all 14 tables, through the routes and worker where they exist."""
    for token in (TOKEN_A, TOKEN_B):
        env.client.put("/me/onboarding", json={"step": 2}, headers=auth(token))
        pid = env.project(token)
        a = env.upload(pid, token, label="v1", text="\n".join(EARLIER_LINES)).json()["id"]
        b = env.upload(pid, token, label="v2", text="\n".join(LATER_LINES)).json()["id"]
        env.worker.run_until_idle()
        cid = env.compare(pid, a, b, token=token).json()["id"]
        env.worker.run_until_idle()
        finding = env.get("/comparisons/%s/findings" % cid, token).json()["findings"][0]["id"]
        sides = {item["side"] for item in env.get("/findings/" + finding, token).json()["evidence"]}
        review = {"action": "confirmed", "page_opened": False,
                  "evidence_mode": {"before": "text_only" if "earlier" in sides else None,
                                    "after": "text_only" if "later" in sides else None}}
        assert env.client.post("/findings/%s/reviews" % finding, json=review, headers=auth(token)).status_code == 201
        assert _post(env, "/findings/%s/client-approvals" % finding, {
            "evidence_text": "x", "stated_by": "y", "stated_at": "2026-10-30T09:00:00Z"}, token).status_code == 201
        doomed = env.project(token, name="Doomed")
        assert env.client.delete("/projects/" + doomed, headers=auth(token)).status_code == 204
    for subject, tenant in ((SUBJECT_A, TENANT_A), ("dev:tenant-b", TENANT_B)):  # rows no route here creates
        env.sql("INSERT INTO account_deletions (user_id, tenant_id, status, attempts) VALUES (:u, :t, 'complete', 0) "
                "RETURNING user_id", u=env.users[subject], t=tenant)
        env.sql("INSERT INTO comparison_cost_tombstones (id, tenant_id, cost_actual, cost_reservations, created_at) "
                "VALUES (gen_random_uuid(), :t, 0, '{}', now()) RETURNING id", t=tenant)
        env.sql("INSERT INTO object_purge_intents (id, tenant_id, project_id, object_key, next_attempt_at, attempts) "
                "VALUES (gen_random_uuid(), :t, gen_random_uuid(), :k, now() + interval '1 day', 0) RETURNING id", t=tenant, k="%s/x/%s" % (tenant, uuid.uuid4()))
        env.sql("INSERT INTO object_write_intents (id, tenant_id, object_key, request_lock_id, write_acknowledged, "
                "next_attempt_at, attempts, created_at) VALUES (gen_random_uuid(), :t, :k, 1, false, now() + interval '1 day', 0, now()) "
                "RETURNING id",
                t=tenant, k="%s/y/%s" % (tenant, uuid.uuid4()))


def _app(env, tenant=None):
    conn = env.db.engine.connect()
    conn.begin()
    if tenant is not None:
        conn.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(tenant)})
    return conn


def _refused(env, tenant, statement, **params):
    with _app(env, tenant) as conn:
        with pytest.raises(ProgrammingError) as error:
            conn.execute(text(statement), params)
    return "row-level security" in str(error.value.orig) or "permission denied" in str(error.value.orig)


def test_direct_sql_as_the_app_role_sees_and_writes_only_the_current_tenant(env):
    _fill_every_tenant_table(env)
    counts = "SELECT '%s', tenant_id, count(*) FROM %s GROUP BY 2"
    totals = lambda: sorted(r for t in tenant_tables(env) for r in env.sql(counts % (t, t)))
    before = totals()
    for table in tenant_tables(env):
        per_tenant = dict(env.sql("SELECT tenant_id, count(*) FROM %s GROUP BY 1" % table))
        assert per_tenant.get(TENANT_A) and per_tenant.get(TENANT_B), "%s needs rows of both tenants" % table
        with _app(env) as conn:  # no tenant set: nothing at all
            assert conn.execute(text("SELECT count(*) FROM %s" % table)).scalar_one() == 0
            assert conn.execute(text("UPDATE %s SET tenant_id = tenant_id" % table)).rowcount == 0
            assert conn.execute(text("DELETE FROM %s" % table)).rowcount == 0
        with _app(env, TENANT_A) as conn:  # an unfiltered query: only A's rows
            seen = conn.execute(text("SELECT tenant_id, count(*) FROM %s GROUP BY 1" % table)).all()
            assert seen == [(TENANT_A, per_tenant[TENANT_A])], table
        row = env.sql("SELECT row_to_json(x)::text FROM %s x WHERE tenant_id = :t LIMIT 1" % table, t=TENANT_A)[0][0]
        insert = "INSERT INTO %s SELECT * FROM json_populate_record(NULL::%s, CAST(:row AS json))" % (table, table)
        assert _refused(env, None, insert, row=row), table  # no tenant: insert refused
        assert _refused(env, TENANT_B, insert, row=row), table  # A's row while B is set: refused
        assert _refused(env, TENANT_A, "UPDATE %s SET tenant_id = :b" % table, b=TENANT_B), table
    assert totals() == before  # every refused or invisible write changed nothing
    with _app(env, TENANT_A) as conn:
        with pytest.raises(ProgrammingError) as error:
            conn.execute(text("SELECT count(*) FROM users"))
        assert "permission denied" in str(error.value.orig)


def test_an_unfiltered_orm_query_in_tenant_scope_returns_only_that_tenant(env):
    from sqlalchemy import select
    from changelens.domain.models import Membership, Project
    env.project(TOKEN_A, name="A"), env.project(TOKEN_B, name="B")
    with env.db.tenant_scope(TENANT_A) as repo:
        assert [p.name for p in repo.s.scalars(select(Project))] == ["A"]  # no tenant_id filter in the query
        assert {m.tenant_id for m in repo.s.scalars(select(Membership))} == {TENANT_A}


# 4. Every route ------------------------------------------------------------------------------------
NO_RESOURCE_ID = {("POST", "/session"), ("DELETE", "/me"), ("GET", "/projects"), ("POST", "/projects"),
                  ("GET", "/me/onboarding"), ("PUT", "/me/onboarding")}


def _requests(a, b, cid, finding):
    """Tenant B's request for each route that takes a resource ID, with a body that passes validation."""
    review = {"action": "confirmed", "evidence_mode": {"before": "text_only", "after": "text_only"},
              "page_opened": False}
    approval = {"evidence_text": "x", "stated_by": "y", "stated_at": "2026-10-30T09:00:00Z"}
    pair = {"earlier_id": a["earlier"], "later_id": a["later"], "scope": "complete"}
    return {
        ("GET", "/projects/{project_id}"): {},
        ("GET", "/projects/{project_id}/versions"): {},
        ("POST", "/projects/{project_id}/versions"): {"data": {"label": "x", "text": "x"}},
        ("GET", "/projects/{project_id}/comparisons"): {},
        ("POST", "/projects/{project_id}/comparisons"): {"json": pair, "headers": {"Idempotency-Key": str(uuid.uuid4())}},
        ("DELETE", "/projects/{project_id}"): {},
        ("GET", "/versions/{version_id}"): {},
        ("GET", "/versions/{version_id}/text"): {},
        ("GET", "/versions/{version_id}/original"): {},
        ("POST", "/versions/{version_id}/opened"): {},
        ("GET", "/comparisons/{comparison_id}"): {},
        ("GET", "/comparisons/{comparison_id}/findings"): {},
        ("POST", "/comparisons/{comparison_id}/opened"): {},
        ("GET", "/findings/{finding_id}"): {},
        ("POST", "/findings/{finding_id}/reviews"): {"json": review},
        ("POST", "/findings/{finding_id}/client-approvals"): {"json": approval},
    }


def _api_routes(env):
    """Every operation in the app's OpenAPI schema, so a new route is covered (or fails) automatically."""
    paths = env.client.app.openapi()["paths"]
    return {(method.upper(), path) for path, operations in paths.items() for method in operations}


def test_every_route_with_a_resource_id_is_not_found_for_another_tenant(env):
    earlier, later, cid = _compared(env)
    finding = _findings(env, cid)[0]["id"]
    pid = env.get("/comparisons/" + cid).json()["project_id"]
    ids = {"project_id": pid, "version_id": earlier, "comparison_id": cid, "finding_id": finding}
    requests = _requests({"earlier": earlier, "later": later}, None, cid, finding)
    routes = _api_routes(env)
    assert routes - NO_RESOURCE_ID == set(requests), "a route is missing from this test's list"
    before = env.sql("SELECT count(*) FROM review_events")[0][0], env.sql("SELECT count(*) FROM client_approvals")[0][0]
    for (method, path), kwargs in sorted(requests.items(), key=lambda item: item[0][0] == "DELETE"):
        url = path.format(**ids)
        headers = {**auth(TOKEN_B), **kwargs.get("headers", {})}
        r = env.client.request(method, url, headers=headers, **{k: v for k, v in kwargs.items() if k != "headers"})
        assert r.status_code == 404 and r.json()["code"] == "not_found", (method, path, r.status_code, r.text)
    assert env.get("/projects/" + pid).status_code == 200  # A's project survived B's DELETE
    assert env.get("/comparisons/" + cid).json()["status"] == "complete"
    after = env.sql("SELECT count(*) FROM review_events")[0][0], env.sql("SELECT count(*) FROM client_approvals")[0][0]
    assert after == before


# 5. Every job kind --------------------------------------------------------------------------------
def test_every_job_kind_with_another_tenants_ids_finds_nothing_and_changes_nothing(env):
    pid = env.project()
    a = env.upload(pid, label="v1", text="one\ntwo").json()["id"]
    b = env.upload(pid, label="v2", text="one\nthree").json()["id"]
    handlers = {
        "parse": lambda: env.worker.handle_parse(TENANT_B, uuid.UUID(a)),
        "compare": lambda: env.worker.handle_compare(TENANT_B, uuid.UUID(cid)),
    }
    assert set(handlers) == set(jobs.KINDS)
    snapshot = lambda: env.sql("SELECT id, status FROM source_versions UNION ALL SELECT id, status FROM comparisons "
                               "ORDER BY 1")
    before = snapshot()
    handlers["parse"]()
    assert snapshot() == before
    env.sql("DELETE FROM jobs RETURNING id")  # parse the versions directly so the comparison stays queued
    env.worker.handle_parse(TENANT_A, uuid.UUID(a)), env.worker.handle_parse(TENANT_A, uuid.UUID(b))
    cid = env.compare(pid, a, b).json()["id"]
    before = snapshot()
    handlers["compare"]()
    assert snapshot() == before and env.sql("SELECT count(*) FROM findings")[0][0] == 0


# 6. The processes run as the app role -------------------------------------------------------------
def test_the_suite_runs_as_the_app_role_and_other_roles_are_refused(env):
    with env.db.engine.connect() as conn:
        assert conn.execute(text("SELECT current_user")).scalar_one() == APP_ROLE
    env.db.assert_app_role()
    for url in (db_url(TEST_DB, OWNER_ROLE), db_url(TEST_DB)):
        other = Database(url)
        try:
            with pytest.raises(RuntimeError):
                other.assert_app_role()
        finally:
            other.engine.dispose(), other._intent_engine.dispose()


# 7. Functions -------------------------------------------------------------------------------------
def test_every_function_is_a_narrow_owner_owned_definer_with_a_pinned_search_path(env):
    rows = env.sql("SELECT p.proname, p.prosecdef, pg_get_userbyid(p.proowner), p.proconfig, "
                   "has_function_privilege(:app, p.oid, 'EXECUTE'), "
                   "EXISTS (SELECT 1 FROM aclexplode(p.proacl) a WHERE a.grantee = 0) "
                   "FROM pg_proc p JOIN pg_namespace n ON n.oid = p.pronamespace WHERE n.nspname = 'public'",
                   app=APP_ROLE)
    assert sorted(r[0] for r in rows) == sorted(FUNCTIONS)
    for name, definer, owner, config, app_can, public_can in rows:
        assert definer and owner == OWNER_ROLE and app_can and not public_can, name
        assert config == ["search_path=pg_catalog, pg_temp"], name


def _call(env, statement, **params):
    with _app(env) as conn:
        result = conn.execute(text(statement), params)
        return list(result.keys()), result.all()


def test_each_function_returns_only_its_listed_columns(env):
    now = datetime.now(timezone.utc)
    calls = {"session_lookup": ("session_lookup(:s)", {"s": SUBJECT_A}),
             "session_bootstrap": ("session_bootstrap(:s, false)", {"s": SUBJECT_A}),
             "queue_claim": ("queue_claim()", {}),
             "queue_reclaim_expired": ("queue_reclaim_expired(300)", {}),
             "pending_object_writes": ("pending_object_writes(:n, 10)", {"n": now}),
             "maintenance_candidates": ("maintenance_candidates(:n, 10)", {"n": now}),
             "account_freeze": ("account_freeze(:u)", {"u": uuid.uuid4()}),
             "account_deletion_subject": ("account_deletion_subject(:u)", {"u": uuid.uuid4()}),
             "account_tombstone": ("account_tombstone(:u)", {"u": uuid.uuid4()}),
             "account_deletion_candidates": ("account_deletion_candidates(:n, 10)", {"n": now}),
             "rate_limit_hit": ("rate_limit_hit(:k, date_trunc('minute', now()))", {"k": "0" * 64}),
             "rate_limit_prune": ("rate_limit_prune()", {}),
             "global_spend_since": ("global_spend_since(:n)", {"n": now})}
    for name, (call, params) in calls.items():
        columns, _ = _call(env, "SELECT * FROM " + call, **params)
        assert columns == FUNCTIONS[name], name
    _, rows = _call(env, "SELECT * FROM session_lookup(:s)", s=SUBJECT_A)
    assert rows == [(env.users[SUBJECT_A], TENANT_A, "owner")]


@pytest.mark.parametrize("call", [
    "session_bootstrap('', true)", "session_bootstrap(repeat('s', 201), true)", "session_bootstrap(NULL, true)",
    "session_bootstrap('dev:x', NULL)",
    "queue_reclaim_expired(0)", "queue_reclaim_expired(86401)", "queue_reclaim_expired(NULL)",
    "pending_object_writes(now(), 0)", "pending_object_writes(now(), 1001)", "pending_object_writes(NULL, 5)",
    "maintenance_candidates(now(), 0)", "maintenance_candidates(now(), 1001)", "maintenance_candidates(NULL, 5)",
    "account_deletion_candidates(now(), 0)", "account_deletion_candidates(NULL, 5)",
    "rate_limit_hit('not-a-hash', now())", "rate_limit_hit(repeat('a', 64), now() - interval '3 days')",
    "rate_limit_hit(repeat('a', 64), now() + interval '1 hour')", "rate_limit_hit(NULL, now())",
    "global_spend_since(NULL)",
])
def test_functions_reject_invalid_arguments(env, call):
    with pytest.raises(DBAPIError) as error:
        _call(env, "SELECT * FROM " + call)
    assert "invalid argument" in str(error.value.orig)
    assert env.sql("SELECT count(*) FROM users WHERE idp_subject IN ('', 'dev:x')")[0][0] == 0


def test_session_lookup_ignores_missing_deleted_and_membership_less_users(env):
    assert _call(env, "SELECT * FROM session_lookup('dev:nobody')")[1] == []
    assert _call(env, "SELECT * FROM session_lookup(NULL)")[1] == []
    assert _call(env, "SELECT * FROM session_bootstrap('dev:nobody', false)")[1] == [("missing", None, None, None)]
    assert env.sql("SELECT count(*) FROM users WHERE idp_subject = 'dev:nobody'")[0][0] == 0  # lookup creates nothing
    env.sql("UPDATE memberships SET status = 'inactive' WHERE tenant_id = :t RETURNING user_id", t=TENANT_B)
    env.sql("UPDATE users SET deleted_at = now() WHERE id = :u RETURNING id", u=env.users[SUBJECT_A])
    for subject, outcome in ((SUBJECT_A, "deleted"), ("dev:tenant-b", "no_membership")):
        assert _call(env, "SELECT * FROM session_lookup(:s)", s=subject)[1] == []
        assert _call(env, "SELECT * FROM session_bootstrap(:s, true)", s=subject)[1] == [(outcome, None, None, None)]
    assert env.sql("SELECT count(*) FROM memberships")[0][0] == 2  # no new tenant for either


def test_maintenance_candidates_apply_the_retention_window(env):
    pid = env.project()
    env.upload(pid, text="hello")
    env.worker.run_until_idle()
    now = datetime.now(timezone.utc)
    assert _call(env, "SELECT * FROM maintenance_candidates(:n, 10)", n=now)[1] == []
    _, rows = _call(env, "SELECT * FROM maintenance_candidates(:n, 10)", n=now + timedelta(days=31))
    assert rows == [("project", TENANT_A, uuid.UUID(pid))]
    assert json.dumps([str(v) for row in rows for v in row])  # IDs and a list name only


def test_a_pooled_connection_that_had_a_tenant_sees_nothing_once_it_is_unset(env):
    env.project()
    with env.db.engine.connect() as conn:  # one connection, two transactions
        with conn.begin():
            conn.execute(text("SELECT set_config('app.tenant_id', :t, true)"), {"t": str(TENANT_A)})
            assert conn.execute(text("SELECT count(*) FROM projects")).scalar_one() == 1
        with conn.begin():  # the setting is now '' rather than null: still no rows, and no cast error
            assert conn.execute(text("SELECT current_setting('app.tenant_id', true)")).scalar_one() == ""
            assert conn.execute(text("SELECT count(*) FROM projects")).scalar_one() == 0
