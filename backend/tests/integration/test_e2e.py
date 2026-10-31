"""End to end: API upload -> worker parse -> API compare -> worker compare -> API findings."""
from helpers import EARLIER_LINES, LATER_LINES, make_pdf


def _parsed_text(env, version_id):
    return env.sql("SELECT parsed_text FROM source_versions WHERE id = :id", id=version_id)[0][0]


def _run_pair(env, upload_a, upload_b):
    pid = env.project()
    a, b = upload_a(pid), upload_b(pid)
    assert a.status_code == b.status_code == 201, (a.text, b.text)
    assert a.json()["status"] == "uploaded"
    assert env.worker.run_until_idle() == 2
    va, vb = env.get("/versions/" + a.json()["id"]).json(), env.get("/versions/" + b.json()["id"]).json()
    assert va["status"] == vb["status"] == "parsed", (va, vb)
    r = env.compare(pid, va["id"], vb["id"], scope="complete")
    assert r.status_code == 202, r.text
    cid = r.json()["id"]
    assert env.get("/comparisons/" + cid).json()["status"] == "queued"
    assert env.worker.run_until_idle() == 1
    c = env.get("/comparisons/" + cid).json()
    assert c["status"] == "complete" and c["placeholder"] is True and c["pipeline_version"] == "placeholder-0"
    assert {"code": "placeholder_pipeline"} in c["warnings"]
    assert 0 < float(c["cost_actual"]) <= float(c["cost_ceiling"])
    f = env.get("/comparisons/%s/findings" % cid).json()
    assert f["status"] == "complete" and f["placeholder"] is True and f["findings"]
    texts = {"earlier": _parsed_text(env, va["id"]), "later": _parsed_text(env, vb["id"])}
    for finding in f["findings"]:
        assert finding["explanation"]
        for ev in finding["evidence"]:
            loc = ev["locator"]
            assert texts[ev["side"]][loc["char_start"]:loc["char_end"]] == ev["quote"]
    return f["findings"]


def test_text_versions_end_to_end(env):
    findings = _run_pair(env, lambda p: env.upload(p, label="v1", text="\n".join(EARLIER_LINES)),
                         lambda p: env.upload(p, label="v2", file=("v2.txt", "\n".join(LATER_LINES).encode(), "text/plain")))
    budget = findings[0]
    assert budget["change_type"] == "changed"
    assert [(e["side"], e["quote"]) for e in budget["evidence"]] == [
        ("earlier", "Budget: EUR 12,000"), ("later", "Budget: EUR 15,000")]


def test_pdf_versions_end_to_end(env):
    earlier = make_pdf([EARLIER_LINES[:3], EARLIER_LINES[3:]])
    later = make_pdf([LATER_LINES[:3], LATER_LINES[3:]])
    findings = _run_pair(env, lambda p: env.upload(p, label="v1", file=("a.pdf", earlier, "application/pdf")),
                         lambda p: env.upload(p, label="v2", file=("b.pdf", later, "application/octet-stream")))
    pages = {(e["side"], e["locator"]["page"]) for f in findings for e in f["evidence"]}
    assert ("earlier", 1) in pages and ("later", 2) in pages


def test_original_is_stored_under_a_tenant_prefix(env):
    pid = env.project()
    v = env.upload(pid, text="hello").json()
    key = env.sql("SELECT original_object_key FROM source_versions WHERE id = :id", id=v["id"])[0][0]
    assert key.startswith("00000000-0000-4000-8000-00000000000a/%s/" % pid)
    assert env.store.get(key) == b"hello"


def test_comparison_needs_confirmed_scope_and_parsed_versions(env):
    pid = env.project()
    a = env.upload(pid, text="one").json()["id"]
    b = env.upload(pid, text="two").json()["id"]
    r = env.compare(pid, a, b)
    assert r.status_code == 409 and r.json()["code"] == "scope_not_confirmed"
    env.worker.run_until_idle()
    for scope, earlier, later in (("everything", a, b), ("complete", a, a)):
        r = env.compare(pid, earlier, later, scope=scope)
        assert r.status_code == 422 and r.json()["code"] == "scope_not_confirmed"


def test_scanned_pdf_is_rejected_by_parse(env):
    pid = env.project()
    v = env.upload(pid, file=("scan.pdf", make_pdf([[], []]), "application/pdf")).json()
    env.worker.run_until_idle()
    got = env.get("/versions/" + v["id"]).json()
    assert got["status"] == "rejected" and got["reject_reason"] == "no_text_layer"
