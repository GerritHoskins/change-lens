"""One comparison from two parsed versions to the verified, worded findings (03a), under a cost
meter (AC-21). The worker persists the outcome; the I-7 harness scores it, so both run this code.
"""
from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from changelens.llm import LlmPort, MeteredLlm
from changelens.metering import Budget, CeilingReached, CostMeter
from changelens.pipeline.align import align
from changelens.pipeline.compare import compare
from changelens.pipeline.extract import FactCache, extract_cached
from changelens.pipeline.report import report
from changelens.pipeline.types import PARTIAL_WARNINGS, ParsedDocument, VerifyResult
from changelens.pipeline.verify import verify


@dataclass
class Outcome:
    checked: VerifyResult
    status: str  # complete, partial or failed
    warnings: list
    cost: Decimal
    calls: int


def run_comparison(sides: list[tuple[str, ParsedDocument, FactCache]], scope: str, llm: LlmPort,
                   ceiling: Decimal, config_id: str, *, meter: Budget | None = None) -> Outcome:
    """`sides` is (sha256, parsed document, fact cache) for the earlier and then the newer version."""
    if meter is None:
        meter = CostMeter(ceiling)
    metered = MeteredLlm(llm, meter)
    earlier, later = sides[0][1], sides[1][1]
    warnings = []
    # Hidden blocks are never sent to the model nor diffed, and are reported; unread or
    # unchecked content makes the result partial (AC-11, AC-18).
    codes = {w.code for w in earlier.warnings + later.warnings}
    if "hidden_text" in codes:
        warnings.append({"code": "hidden_text"})
    if codes & PARTIAL_WARNINGS:
        warnings.append({"code": "parse_warnings"})
    facts, unextracted, stage = [], 0, "extract"
    try:
        for sha, doc, cache in sides:  # facts per version, cached (I-2)
            res = extract_cached(doc, sha, config_id, cache, metered)
            facts.append(res.facts)
            unextracted += len(res.unextracted)
        stage = "compare"
        drafts = compare(align(facts[0], facts[1], metered), scope, metered)  # I-3, I-4
    except CeilingReached:
        return Outcome(VerifyResult([], 0, []), "failed", warnings + [{"code": "cost_ceiling", "stage": stage}],
                       meter.total, meter.calls)
    if unextracted:
        warnings.append({"code": "unextracted", "chunks": unextracted})  # AC-11
    checked = verify(drafts, earlier, later)  # I-5: exact quotes, needs review, block cross-check
    checked.findings, templated = report(checked.findings, metered)
    if templated:  # verified findings are kept with template wording, never dropped (AC-21)
        warnings.append({"code": "cost_ceiling", "stage": "report", "templated_findings": templated})
    total = meter.total
    over_budget = total > ceiling
    if over_budget:
        # Provider usage is authoritative, even above our conservative reservation. A last
        # successful response must not hide that overage merely because no next call occurs.
        warnings.append({"code": "cost_ceiling", "stage": "report", "reason": "reported_usage_exceeded_estimate"})
    partial = {"code": "parse_warnings"} in warnings or unextracted > 0 or templated > 0 or over_budget
    return Outcome(checked, "partial" if partial else "complete", warnings, total, meter.calls)
