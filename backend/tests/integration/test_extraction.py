"""I-2 in the worker: facts are extracted once per version and cached; failures make it partial."""
from __future__ import annotations

from decimal import Decimal

from changelens.llm import FakeLlm
from changelens.llm.errors import LlmOutputInvalid
from helpers import EARLIER_LINES, LATER_LINES


class FactLlm(FakeLlm):
    """Fake that answers FactList with one budget fact per chunk, or fails if told to."""
    config_id = "fact-llm-test"

    def __init__(self, fail: bool = False):
        super().__init__(Decimal("0.01"))
        self.fail = fail
        self.fact_calls = 0

    def structured(self, schema, system, data):
        if schema != "FactList":
            return super().structured(schema, system, data)
        self.fact_calls += 1
        if self.fail:
            raise LlmOutputInvalid("output_invalid_after_retry", Decimal("0.02"))
        n = next(i for i, line in enumerate(data[0].splitlines(), 1) if "Budget" in line)
        return {"facts": [{"type": "quantity", "subject": "Budget", "value": "x", "block": n,
                           "quote": "Budget", "ambiguity": None, "confidence": "high"}]}, Decimal("0.01")


def _versions(env, *texts):
    pid = env.project()
    ids = [env.upload(pid, label="v%d" % i, text=t).json()["id"] for i, t in enumerate(texts)]
    assert env.worker.run_until_idle() == len(ids)
    return pid, ids


def test_facts_are_extracted_once_per_version_and_reused(env):
    env.worker.llm = llm = FactLlm()
    pid, (a, b, c) = _versions(env, "\n".join(EARLIER_LINES), "\n".join(LATER_LINES),
                               "\n".join(LATER_LINES + ["Hosting by us"]))
    first = env.compare(pid, a, b).json()["id"]
    env.worker.run_until_idle()
    assert llm.fact_calls == 2
    second = env.compare(pid, b, c).json()["id"]
    env.worker.run_until_idle()
    assert llm.fact_calls == 3  # b came from the cache; only c was extracted
    rows = env.sql("SELECT source_version_id::text, result FROM fact_cache ORDER BY created_at")
    assert [r[0] for r in rows] == [a, b, c]
    for _, result in rows:
        assert [f["raw_text"] for f in result["facts"]] == ["Budget"] and result["unextracted"] == []
    for cid in (first, second):
        cmp = env.get("/comparisons/" + cid).json()
        assert cmp["status"] == "complete" and not [w for w in cmp["warnings"] if w["code"] == "unextracted"]


def test_unextracted_makes_the_comparison_partial_and_is_not_cached(env):
    env.worker.llm = llm = FactLlm(fail=True)
    pid, (a, b) = _versions(env, "\n".join(EARLIER_LINES), "\n".join(LATER_LINES))
    cid = env.compare(pid, a, b).json()["id"]
    env.worker.run_until_idle()
    c = env.get("/comparisons/" + cid).json()
    assert c["status"] == "partial"
    assert {"code": "unextracted", "chunks": 2} in c["warnings"]
    assert Decimal(c["cost_actual"]) >= Decimal("0.04")  # failed extraction calls are still counted
    assert env.sql("SELECT count(*) FROM fact_cache")[0][0] == 0


def test_ceiling_during_extraction_fails_cleanly(env_factory):
    env = env_factory(cost_ceiling_eur=Decimal("0.001"))
    env.worker.llm = llm = FactLlm()
    llm.estimate_cost = lambda schema, data: Decimal("0.01")
    pid, (a, b) = _versions(env, "\n".join(EARLIER_LINES), "\n".join(LATER_LINES))
    cid = env.compare(pid, a, b).json()["id"]
    env.worker.run_until_idle()
    c = env.get("/comparisons/" + cid).json()
    assert c["status"] == "failed" and {"code": "cost_ceiling", "stage": "extract"} in c["warnings"]
    assert llm.fact_calls == 0
    assert env.sql("SELECT status FROM jobs WHERE kind = 'compare'") == [("done",)]
