"""I-10 review, client approval and evidence routes: AC-12 (separate states) and AC-15 (revisions)."""
from conftest import TOKEN_A, TOKEN_B, auth
from helpers import EARLIER_LINES, LATER_LINES, make_pdf


def _compared(env, earlier=None, later=None):
    pid = env.project()
    a = env.upload(pid, label="v1", text=earlier or "\n".join(EARLIER_LINES)).json()["id"]
    b = env.upload(pid, label="v2", text=later or "\n".join(LATER_LINES)).json()["id"]
    env.worker.run_until_idle()
    cid = env.compare(pid, a, b).json()["id"]
    env.worker.run_until_idle()
    return a, b, cid


def _post(env, path, body, token=TOKEN_A):
    if path.endswith("/reviews"):
        # These fixtures use pasted text. Derive absent sides from the actual finding so
        # the request represents this test client's evidence view, not production defaults.
        finding = env.get(path.removesuffix("/reviews")).json()
        sides = {item["side"] for item in finding["evidence"]}
        body = {**body, "evidence_mode": {"before": "text_only" if "earlier" in sides else None,
                                         "after": "text_only" if "later" in sides else None},
                "page_opened": False}
    return env.client.post(path, json=body, headers=auth(token))


def _findings(env, cid):
    return env.get("/comparisons/%s/findings" % cid).json()["findings"]


def test_confirm_and_dismiss_are_reviews_never_approvals(env):
    _, _, cid = _compared(env)
    first, second = _findings(env, cid)[:2]
    assert first["review"] is None and first["client_approval_recorded"] is False
    r = _post(env, "/findings/%s/reviews" % first["id"], {"action": "confirmed"})
    assert r.status_code == 201 and r.json()["finding"]["review"]["action"] == "confirmed"
    assert r.json()["review"]["page_opened"] is False
    # WP-C: a dismissal needs its reason, and only a dismissal takes one.
    assert _post(env, "/findings/%s/reviews" % second["id"], {"action": "dismissed"}).status_code == 422
    assert _post(env, "/findings/%s/reviews" % second["id"],
                 {"action": "confirmed", "dismissal_reason": "other"}).status_code == 422
    assert _post(env, "/findings/%s/reviews" % second["id"],
                 {"action": "dismissed", "note": "not relevant", "dismissal_reason": "irrelevant"}).status_code == 201
    got = {f["id"]: f for f in _findings(env, cid)}
    assert got[first["id"]]["review"]["action"] == "confirmed" and got[second["id"]]["review"]["action"] == "dismissed"
    assert got[second["id"]]["review"]["dismissal_reason"] == "irrelevant"
    assert got[first["id"]]["review"]["dismissal_reason"] is None
    assert all(f["client_approval_recorded"] is False for f in got.values())  # AC-12
    assert env.sql("SELECT count(*) FROM client_approvals")[0][0] == 0
    assert "approved" not in str(got[first["id"]]).lower()


def test_a_correction_creates_a_revision_and_keeps_the_ai_finding(env):
    _, _, cid = _compared(env)
    original = _findings(env, cid)[0]
    before = env.sql("SELECT change_type, category, explanation, evidence::text FROM findings WHERE id = :id",
                     id=original["id"])
    r = _post(env, "/findings/%s/reviews" % original["id"],
              {"action": "corrected", "note": "it is a fee", "correction": {"category": "other_material"}})
    assert r.status_code == 201, r.text
    new = r.json()["finding"]
    assert new["id"] != original["id"] and new["revision"] == 2 and new["supersedes_id"] == original["id"]
    assert new["category"] == "other_material" and new["evidence"] == original["evidence"]
    assert new["review"]["action"] == "corrected"
    # AC-15: the AI output is untouched, and the list shows only the current revision.
    assert env.sql("SELECT change_type, category, explanation, evidence::text FROM findings WHERE id = :id",
                   id=original["id"]) == before
    ids = [f["id"] for f in _findings(env, cid)]
    assert new["id"] in ids and original["id"] not in ids
    detail = env.get("/findings/%s" % new["id"]).json()
    assert [(x["revision"], x["category"]) for x in detail["revisions"]] == [
        (1, original["category"]), (2, "other_material")]
    assert [x["action"] for x in detail["reviews"]] == ["corrected"]
    # The superseded revision cannot be reviewed again.
    r = _post(env, "/findings/%s/reviews" % original["id"], {"action": "confirmed"})
    assert r.status_code == 409 and r.json()["code"] == "finding_superseded"


def test_client_approval_is_a_separate_record_and_no_review(env):
    _, _, cid = _compared(env)
    f = _findings(env, cid)[0]
    body = {"evidence_text": "Mail from the client: fine by us.", "stated_by": "Client contact",
            "stated_at": "2026-10-30T09:00:00+00:00"}
    r = _post(env, "/findings/%s/client-approvals" % f["id"], body)
    assert r.status_code == 201, r.text
    assert r.json()["label"] == "Client approval recorded (not verified by ChangeLens)"
    got = next(x for x in _findings(env, cid) if x["id"] == f["id"])
    assert got["client_approval_recorded"] is True and got["review"] is None  # AC-12: no review implied
    assert env.sql("SELECT count(*) FROM review_events")[0][0] == 0
    detail = env.get("/findings/%s" % f["id"]).json()
    assert [a["stated_by"] for a in detail["client_approvals"]] == ["Client contact"] and detail["reviews"] == []


def test_review_input_is_checked_and_tenant_scoped(env):
    _, _, cid = _compared(env)
    fid = _findings(env, cid)[0]["id"]
    for body in ({"action": "approved"}, {"action": "note"}, {"action": "corrected"},
                 {"action": "confirmed", "correction": {"category": "deliverable"}},
                 {"action": "corrected", "correction": {"change_type": "cancelled"}},
                 {"action": "corrected", "correction": {}}):
        r = _post(env, "/findings/%s/reviews" % fid, body)
        assert r.status_code == 422, (body, r.text)
    assert _post(env, "/findings/%s/reviews" % fid, {"action": "confirmed"}, TOKEN_B).status_code == 404
    assert env.get("/findings/%s" % fid, TOKEN_B).status_code == 404
    assert _post(env, "/findings/%s/client-approvals" % fid,
                 {"evidence_text": "x", "stated_by": "y", "stated_at": "2026-10-30T09:00:00Z"}, TOKEN_B).status_code == 404
    assert env.sql("SELECT count(*) FROM review_events")[0][0] == 0


def test_version_text_and_original_for_the_evidence_view(env):
    pid = env.project()
    pdf = make_pdf([EARLIER_LINES[:3], EARLIER_LINES[3:]])
    v = env.upload(pid, label="v1", file=("a.pdf", pdf, "application/pdf")).json()["id"]
    assert env.get("/versions/%s/text" % v).status_code == 409  # not parsed yet
    env.worker.run_until_idle()
    t = env.get("/versions/%s/text" % v).json()
    assert t["kind"] == "pdf" and len(t["pages"]) == 2 and t["blocks"][0]["locator"]["page"] == 1
    r = env.get("/versions/%s/original" % v)
    assert r.status_code == 200 and r.content == pdf and r.headers["content-type"] == "application/pdf"
    assert r.headers["cache-control"] == "no-store"
    assert env.get("/versions/%s/original" % v, TOKEN_B).status_code == 404
    assert env.get("/versions/%s/text" % v, TOKEN_B).status_code == 404


def test_projects_list_summarises_each_projects_latest_comparison(env):
    """Home screen: the list's counts equal the report's, follow reviews, and stay inside the tenant."""
    idle = env.project(name="Never compared")
    _, _, cid = _compared(env)
    report = env.get("/comparisons/%s/findings" % cid).json()
    shown = [f for f in report["findings"] if f["group"] in ("needs_review", "prioritised")]
    assert shown, "the fixture pair must produce findings the report shows"
    by_id = {p["id"]: p for p in env.get("/projects").json()["projects"]}
    assert by_id[idle]["latest_comparison"] is None
    latest = next(p for p in by_id.values() if p["id"] != idle)["latest_comparison"]
    assert (latest["id"], latest["earlier_label"], latest["later_label"]) == (cid, "v1", "v2")
    assert latest["status"] == report["status"]
    assert latest["findings"] == len(shown) and latest["reviewed"] == 0
    assert latest["needs_review"] == sum(f["group"] == "needs_review" for f in shown)
    assert sum(latest["topic_counts"].values()) == len(shown)
    for topic, count in latest["topic_counts"].items():
        assert count == sum(f["topic"] == topic for f in shown)
    # A note is not a review; a confirm is; a correction keeps the finding counted once.
    assert _post(env, "/findings/%s/reviews" % shown[0]["id"], {"action": "note", "note": "ask"}).status_code == 201
    noted = next(p for p in env.get("/projects").json()["projects"] if p["id"] != idle)["latest_comparison"]
    assert noted["reviewed"] == 0
    assert _post(env, "/findings/%s/reviews" % shown[0]["id"],
                 {"action": "corrected", "correction": {"explanation": "Reworded."}}).status_code == 201
    after = next(p for p in env.get("/projects").json()["projects"] if p["id"] != idle)["latest_comparison"]
    assert (after["findings"], after["reviewed"]) == (len(shown), 1)
    assert env.get("/projects", TOKEN_B).json()["projects"] == []


def test_projects_list_reports_a_newer_unfinished_comparison_without_counts(env):
    a, b, _ = _compared(env)
    pid = env.get("/projects").json()["projects"][0]["id"]
    c = env.upload(pid, label="v3", text="\n".join(LATER_LINES + ["Launch: 1 May"])).json()["id"]
    env.worker.run_until_idle()
    newer = env.compare(pid, b, c).json()["id"]
    latest = env.get("/projects").json()["projects"][0]["latest_comparison"]
    assert (latest["id"], latest["status"], latest["earlier_label"], latest["later_label"]) == (newer, "queued", "v2", "v3")
    assert [latest[k] for k in ("findings", "needs_review", "reviewed", "topic_counts")] == [None] * 4
