"""The `worker` process (03 §9.1): claims jobs, runs pipeline stages, persists results and cost.

Every stage that can call the model runs under a per-comparison CostMeter (AC-21). Logs carry job
IDs, kinds, statuses and error class names only (AC-23).
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Optional

from changelens import jobs
from changelens.config import Settings
from changelens.domain import Database
from changelens.domain.models import Finding
from changelens.llm import FakeLlm, LlmPort, MeteredLlm
from changelens.metering import CostMeter
from changelens.pipeline.parse import ParseRejected, parse
from changelens.pipeline.stages import ReportInterrupted, placeholder_compare, report
from changelens.pipeline.types import ParsedDocument
from changelens.storage import ObjectStore

log = logging.getLogger("changelens.worker")
TERMINAL = ("complete", "partial", "failed")


class Worker:
    def __init__(self, settings: Settings, db: Database, store: ObjectStore,
                 llm: Optional[LlmPort] = None, backoff_seconds: float = 2.0):
        self.settings, self.db, self.store = settings, db, store
        self.llm = llm or FakeLlm(settings.fake_llm_cost_eur)
        self.backoff_seconds = backoff_seconds

    # Queue loop -----------------------------------------------------------------------------
    def run_once(self) -> bool:
        """Process at most one job. Returns False when the queue had nothing ready."""
        with self.db.system_session() as s:
            for dead in jobs.reclaim_expired(s, self.settings.job_lease_seconds):
                log.warning("job %s (%s) failed: lease expired after %d attempts", dead.id, dead.kind, dead.attempts)
                self._on_final_failure(dead)
        with self.db.system_session() as s:
            job = jobs.claim(s)
        if job is None:
            return False
        log.info("job %s (%s) attempt %d/%d started", job.id, job.kind, job.attempts, job.max_attempts)
        try:
            if job.kind == "parse":
                self.handle_parse(job.tenant_id, job.ids["version_id"])
            elif job.kind == "compare":
                self.handle_compare(job.tenant_id, job.ids["comparison_id"])
            else:
                raise ValueError("unknown job kind")
        except Exception as exc:  # retried with backoff; only the class name is recorded
            with self.db.system_session() as s:
                final = jobs.retry_or_fail(s, job, type(exc).__name__, self.backoff_seconds)
            log.warning("job %s (%s) attempt %d failed: %s%s", job.id, job.kind, job.attempts,
                        type(exc).__name__, "; giving up" if final else "; will retry")
            if final:
                self._on_final_failure(job)
            return True
        with self.db.system_session() as s:
            jobs.complete(s, job.id)
        log.info("job %s (%s) done", job.id, job.kind)
        return True

    def run_until_idle(self, max_jobs: int = 1000) -> int:
        n = 0
        while n < max_jobs and self.run_once():
            n += 1
        return n

    def run_forever(self, poll_seconds: float = 1.0) -> None:
        while True:
            if not self.run_once():
                time.sleep(poll_seconds)

    def _on_final_failure(self, job: jobs.ClaimedJob) -> None:
        with self.db.tenant_scope(job.tenant_id) as repo:
            if job.kind == "parse":
                v = repo.version(job.ids["version_id"], lock=True)
                if v is not None and v.status == "uploaded":
                    v.status, v.reject_reason = "rejected", "parse_failed"
            elif job.kind == "compare":
                c = repo.comparison(job.ids["comparison_id"], lock=True)
                if c is not None and c.status not in TERMINAL:
                    c.status = "failed"
                    c.warnings = list(c.warnings) + [{"code": "job_failed"}]

    # Handlers -------------------------------------------------------------------------------
    def handle_parse(self, tenant_id: uuid.UUID, version_id: uuid.UUID) -> None:
        with self.db.tenant_scope(tenant_id) as repo:
            v = repo.version(version_id)
            if v is None or v.status != "uploaded":
                return  # another tenant's ID or already done: nothing to do (idempotent)
            key, kind = v.original_object_key, v.kind
        data = self.store.get(key)
        # Placeholder: in-process parse. I-1 moves this into the sandbox with CPU/memory caps (03 §6).
        try:
            doc, reason = parse(data, kind, self.settings.limits), None
        except ParseRejected as r:
            doc, reason = None, r.code
        with self.db.tenant_scope(tenant_id) as repo:
            v = repo.version(version_id, lock=True)
            if v is None or v.status != "uploaded":
                return
            if doc is None:
                v.status, v.reject_reason = "rejected", reason
                return
            v.parsed_text, v.blocks, v.page_count = doc.text, doc.blocks_json(), doc.page_count
            v.parse_warnings = [{"code": w.code, "page": w.page} for w in doc.warnings]
            v.status = "parsed"

    def handle_compare(self, tenant_id: uuid.UUID, comparison_id: uuid.UUID) -> None:
        with self.db.tenant_scope(tenant_id) as repo:
            c = repo.comparison(comparison_id, lock=True)
            if c is None or c.status in TERMINAL:
                return
            c.status = "running"
            e, l = repo.version(c.earlier_id), repo.version(c.later_id)
            earlier = ParsedDocument.from_stored(e.kind, e.parsed_text, e.blocks, e.page_count, e.parse_warnings)
            later = ParsedDocument.from_stored(l.kind, l.parsed_text, l.blocks, l.page_count, l.parse_warnings)
            ceiling = c.cost_ceiling
        meter = CostMeter(ceiling)
        llm = MeteredLlm(self.llm, meter)
        warnings = [{"code": "placeholder_pipeline"}]
        if earlier.warnings or later.warnings:
            warnings.append({"code": "parse_warnings"})
        drafts = placeholder_compare(earlier, later)
        try:
            done = report(drafts, llm)
            status = "partial" if len(warnings) > 1 else "complete"
        except ReportInterrupted as stop:
            done = stop.done
            warnings.append({"code": "cost_ceiling", "skipped_findings": stop.skipped})
            status = "partial" if done else "failed"
            log.warning("comparison %s stopped at the cost ceiling after %d llm calls", comparison_id, meter.calls)
        with self.db.tenant_scope(tenant_id) as repo:
            c = repo.comparison(comparison_id, lock=True)
            if c is None or c.status in TERMINAL:
                return
            rows = [Finding(comparison_id=c.id, category=f.category, change_type=f.change_type,
                            evidence=[{"side": ev.side, "quote": ev.quote,
                                       "locator": {"page": ev.locator.page, "char_start": ev.locator.char_start,
                                                   "char_end": ev.locator.char_end}} for ev in f.evidence],
                            explanation=f.explanation, priority=f.priority) for f in done]
            repo.replace_findings(c.id, rows)
            c.status, c.warnings, c.cost_actual = status, warnings, meter.total
        log.info("comparison %s %s: %d findings, cost %s of %s", comparison_id, status, len(done), meter.total, ceiling)
