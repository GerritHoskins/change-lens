"""End to end: API upload -> worker parse -> API compare -> worker compare -> API findings."""
from helpers import EARLIER_LINES, LATER_LINES, make_pdf


def _pages(env, version_id):
    return env.sql("SELECT parsed_pages FROM source_versions WHERE id = :id", id=version_id)[0][0]


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
    assert c["status"] == "complete" and c["placeholder"] is False and c["pipeline_version"] == "facts-2"
    assert 0 < float(c["cost_actual"]) <= float(c["cost_ceiling"])
    f = env.get("/comparisons/%s/findings" % cid).json()
    assert f["status"] == "complete" and f["placeholder"] is False and f["findings"]
    assert [x["priority"] for x in f["findings"]] == list(range(len(f["findings"])))
    assert f["summary"]["selected"] is True and f["withheld_count"] == 0
    pages = {"earlier": _pages(env, va["id"]), "later": _pages(env, vb["id"])}
    for finding in f["findings"]:
        assert finding["explanation"] and finding["group"] in ("prioritised", "needs_review", "other")
    # AC-9: every quote, in findings and in unexplained differences, is exact at its locator.
    for evidence in [x["evidence"] for x in f["findings"]] + [f["unexplained_differences"]]:
        for ev in evidence:
            loc = ev["locator"]
            assert pages[ev["side"]][(loc["page"] or 1) - 1][loc["char_start"]:loc["char_end"]] == ev["quote"]
    return f["findings"]


def test_text_versions_end_to_end(env):
    findings = _run_pair(env, lambda p: env.upload(p, label="v1", text="\n".join(EARLIER_LINES)),
                         lambda p: env.upload(p, label="v2", file=("v2.txt", "\n".join(LATER_LINES).encode(), "text/plain")))
    assert [(f["change_type"], [(e["side"], e["quote"]) for e in f["evidence"]]) for f in findings] == [
        ("changed", [("earlier", "Budget: EUR 12,000"), ("later", "Budget: EUR 15,000")]),
        ("changed", [("earlier", "Pages: home, about, contact"), ("later", "Pages: home, about, contact, blog")]),
        ("removed", [("earlier", "Hosting is provided by the client")]),
        ("added", [("later", "Copywriting is included")])]
    assert "does not mean it was cancelled" in findings[2]["explanation"]  # AC-2


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


def test_hidden_text_is_warned_and_never_compared(env):
    from tests_visibility_fixture import injected_pair
    pid = env.project()
    earlier, later = injected_pair()
    a = env.upload(pid, label="v1", file=("a.pdf", earlier, "application/pdf")).json()["id"]
    b = env.upload(pid, label="v2", file=("b.pdf", later, "application/pdf")).json()["id"]
    env.worker.run_until_idle()
    vb = env.get("/versions/" + b).json()
    assert vb["status"] == "parsed" and [w["code"] for w in vb["parse_warnings"]] == ["hidden_text"]
    assert vb["parse_warnings"][0]["page"] == 1 and "text" not in vb["parse_warnings"][0]
    cid = env.compare(pid, a, b).json()["id"]
    env.worker.run_until_idle()
    c = env.get("/comparisons/" + cid).json()
    assert c["status"] == "complete" and {"code": "hidden_text"} in c["warnings"]
    quotes = [e["quote"] for f in env.get("/comparisons/%s/findings" % cid).json()["findings"] for e in f["evidence"]]
    assert quotes == ["Budget: EUR 12,000", "Budget: EUR 15,000"]  # the hidden line is not a finding


def test_hostile_pdfs_are_rejected_by_the_sandboxed_parse(env):
    from helpers import text_page_pdf
    pid = env.project()
    bomb = text_page_pdf().replace(b"/Kids [3 0 R] /Count 1", b"/Kids [" + b" ".join([b"3 0 R"] * 5000) + b"] /Count 5000")
    js = text_page_pdf(catalog_extra=b"/OpenAction 6 0 R", extra_objects=[b"<< /S /JavaScript /JS (app.alert(1)) >>"])
    v1 = env.upload(pid, file=("bomb.pdf", bomb, "application/pdf")).json()["id"]
    v2 = env.upload(pid, file=("bad.pdf", b"%PDF-1.7\n" + bytes(range(256)) * 4, "application/pdf")).json()["id"]
    v3 = env.upload(pid, file=("js.pdf", js, "application/pdf")).json()["id"]
    env.worker.run_until_idle()
    got = {v: env.get("/versions/" + v).json() for v in (v1, v2, v3)}
    assert (got[v1]["status"], got[v1]["reject_reason"]) == ("rejected", "limit_exceeded_pages")
    assert (got[v2]["status"], got[v2]["reject_reason"]) == ("rejected", "malformed_pdf")
    assert got[v3]["status"] == "parsed"
    assert [w["code"] for w in got[v3]["parse_warnings"]] == ["active_content", "auto_action"]


def test_rotated_cropped_offset_pdfs_end_to_end(env):
    from geometry_fixture import geometry_pdf
    earlier, _ = geometry_pdf(0)
    later, expected = geometry_pdf(90, crop=True, offset=(100, 200))
    later = later.replace(b"(Visible line one)", b"(Visible line ONE)")
    pid = env.project()
    a = env.upload(pid, label="v1", file=("a.pdf", earlier, "application/pdf")).json()["id"]
    b = env.upload(pid, label="v2", file=("b.pdf", later, "application/pdf")).json()["id"]
    env.worker.run_until_idle()
    vb = env.get("/versions/" + b).json()
    codes = [w["code"] for w in vb["parse_warnings"]]
    assert vb["status"] == "parsed" and "visibility_unchecked" not in codes
    assert codes.count("hidden_text") == sum(expected.values())
    cid = env.compare(pid, a, b).json()["id"]
    env.worker.run_until_idle()
    c = env.get("/comparisons/" + cid).json()
    assert c["status"] == "complete" and {"code": "hidden_text"} in c["warnings"]
    got = env.get("/comparisons/%s/findings" % cid).json()
    pages = {"earlier": _pages(env, a), "later": _pages(env, b)}
    quotes = []
    for evidence in [x["evidence"] for x in got["findings"]] + [got["unexplained_differences"], got["presentation_only"]]:
        for ev in evidence:
            loc = ev["locator"]
            assert pages[ev["side"]][loc["page"] - 1][loc["char_start"]:loc["char_end"]] == ev["quote"]
            quotes.append((ev["side"], ev["quote"]))
    # What I-1c owns: the edits and the line cropped away are reported (a case-only edit is listed as
    # presentation-only), and no hidden line is ever quoted.
    assert {("earlier", "Visible line one"), ("later", "Visible line ONE"), ("earlier", "Cropped away text")} <= set(quotes)
    hidden = {k for k, v in expected.items() if v}
    assert not [q for side, q in quotes if side == "later" and q in hidden]
