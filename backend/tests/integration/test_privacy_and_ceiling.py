"""AC-23 (no document content in logs or job payloads) and AC-21 (the ceiling aborts runs cleanly)."""
import io
import logging
import uuid
from decimal import Decimal

from changelens.logs import configure_logging
from helpers import make_pdf


class RawRecords(logging.Handler):
    """Unfiltered capture of our own loggers: the code itself must never pass content to log()."""

    def __init__(self):
        super().__init__(logging.DEBUG)
        self.lines = []

    def emit(self, record):
        if record.name.startswith("changelens"):
            self.lines.append(record.getMessage() + (repr(record.exc_info) if record.exc_info else ""))


def test_no_document_content_in_logs_or_jobs(env):
    marker = "ZQXMARKER" + uuid.uuid4().hex
    stream, raw = io.StringIO(), RawRecords()
    handler = configure_logging(logging.DEBUG, stream)
    root = logging.getLogger()
    root.addHandler(raw)
    # Turn the chatty libraries up so the scrubber, not just their default level, is what is tested.
    chatty = ("sqlalchemy.engine", "botocore", "urllib3", "python_multipart", "psycopg")
    levels = {name: logging.getLogger(name).level for name in chatty}
    for name in chatty:
        logging.getLogger(name).setLevel(logging.DEBUG)
    try:
        pid = env.project()
        a = env.upload(pid, label="v1", text="Scope line\nBudget %s 100\nEnd" % marker).json()["id"]
        pdf = make_pdf([["Scope line", "Budget %s 200" % marker, "End"]])
        b = env.upload(pid, label="v2", file=("%s.pdf" % marker, pdf, "application/pdf")).json()["id"]
        # Rejected and invalid requests must not leak either.
        assert env.upload(pid, label="v3", file=("%s.png" % marker, b"\x89PNG" + marker.encode(), "image/png")).status_code == 415
        r = env.client.post("/projects", json={"name": marker * 20}, headers={"Authorization": "Bearer dev-token-tenant-a-0123456789"})
        assert r.status_code == 422 and marker not in r.text
        env.worker.run_until_idle()
        cid = env.compare(pid, a, b).json()["id"]
        env.worker.run_until_idle()
        findings = env.get("/comparisons/%s/findings" % cid).json()
    finally:
        root.removeHandler(raw)
        root.removeHandler(handler)
        for name, level in levels.items():
            logging.getLogger(name).setLevel(level)
    # Sanity: the marker really went through the pipeline and the logs really captured the run.
    assert any(marker in e["quote"] for f in findings["findings"] for e in f["evidence"])
    out = stream.getvalue()
    assert "POST /projects/{project_id}/versions 201" in out and "comparison %s complete" % cid in out
    assert "sqlalchemy" not in out and "botocore" not in out  # below WARNING: dropped, not just quietened
    assert marker not in out, "document content reached the logs"
    assert not [line for line in raw.lines if marker in line], "changelens code logged document content"
    for (payload, key, err) in env.sql("SELECT payload::text, idempotency_key, coalesce(last_error, '') FROM jobs"):
        assert marker not in payload + key + err
        assert set(__import__("json").loads(payload)) == {"kind", "ids"}
    keys = [k for (k,) in env.sql("SELECT original_object_key FROM source_versions")]
    assert keys and not [k for k in keys if marker in k]
    assert env.sql("SELECT count(*) FROM jobs")[0][0] == 3


def _three_change_pair(env):
    pid = env.project()
    a = env.upload(pid, text="a\nb\nc\nd\ne").json()["id"]
    b = env.upload(pid, text="x\nb\ny\nd\nz").json()["id"]  # 3 removed (templated) + 3 added (worded)
    env.worker.run_until_idle()
    return pid, a, b


def test_ceiling_stops_with_partial_results(env_factory):
    env = env_factory(cost_ceiling_eur=Decimal("1.50"), fake_llm_cost_eur=Decimal("0.60"))
    pid, a, b = _three_change_pair(env)
    cid = env.compare(pid, a, b).json()["id"]
    assert env.worker.run_until_idle() == 1
    c = env.get("/comparisons/" + cid).json()
    assert c["status"] == "partial"
    assert {"code": "cost_ceiling", "stage": "report", "templated_findings": 1} in c["warnings"]
    assert Decimal(c["cost_actual"]) == Decimal("1.20") <= Decimal(c["cost_ceiling"])
    f = env.get("/comparisons/%s/findings" % cid).json()
    # Verified findings are never dropped at the ceiling; the last one gets template wording.
    assert len(f["findings"]) == 6 and all(x["explanation"] for x in f["findings"])
    assert sum(x["explanation"].startswith("New in this version") for x in f["findings"]) == 1
    assert env.sql("SELECT status, attempts FROM jobs WHERE kind = 'compare'") == [("done", 1)]


def test_ceiling_before_first_wording_call_keeps_templated_findings(env_factory):
    env = env_factory(cost_ceiling_eur=Decimal("0.10"), fake_llm_cost_eur=Decimal("0.60"))
    pid, a, b = _three_change_pair(env)
    cid = env.compare(pid, a, b).json()["id"]
    env.worker.run_until_idle()
    c = env.get("/comparisons/" + cid).json()
    assert c["status"] == "partial" and Decimal(c["cost_actual"]) == 0
    assert {"code": "cost_ceiling", "stage": "report", "templated_findings": 3} in c["warnings"]
    assert len(env.get("/comparisons/%s/findings" % cid).json()["findings"]) == 6
    # A clean stop is not a crash: the job is done, not retried.
    assert env.sql("SELECT status, attempts FROM jobs WHERE kind = 'compare'") == [("done", 1)]
