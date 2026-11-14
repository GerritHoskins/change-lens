"""The `worker` process (03 §9.1): claims jobs, runs pipeline stages, persists results and cost.

Every stage that can call the model runs under a per-comparison CostMeter (AC-21). Logs carry job
IDs, kinds, statuses and error class names only (AC-23).
"""
from __future__ import annotations

import logging
import time
import uuid
from decimal import Decimal
from typing import Optional

from changelens import MODEL_CONFIG_ID, jobs
from changelens.config import Settings
from changelens.domain import Database, DbFactCache
from changelens.domain.budget import DbCostMeter
from changelens.domain.comparison_queue import resume_waiting
from changelens.domain.storage_intents import reconcile_pending_writes
from changelens.domain.models import Finding
from changelens.llm import FakeLlm, LlmPort
from changelens.pipeline.sandbox import parse_sandboxed
from changelens.pipeline.run import run_comparison
from changelens.pipeline.types import Evidence, ParsedDocument, ParseRejected, VerifyResult
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
        dead_jobs = self.db.reclaim_expired_jobs(self.settings.job_lease_seconds)
        # Never hold queue row locks while taking a project lifecycle lock: retention
        # takes the project lock before deleting the corresponding queue rows.
        for dead in dead_jobs:
            log.warning("job %s (%s) failed: lease expired after %d attempts", dead.id, dead.kind, dead.attempts)
            self._on_final_failure(dead)
        job = self.db.claim_job()
        if job is None:
            self.reconcile_uploads(limit=1)
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
            with self.db.tenant_scope(job.tenant_id) as repo:
                final = jobs.retry_or_fail(repo.s, job, type(exc).__name__, self.backoff_seconds)
            log.warning("job %s (%s) attempt %d failed: %s%s", job.id, job.kind, job.attempts,
                        type(exc).__name__, "; giving up" if final else "; will retry")
            if final:
                self._on_final_failure(job)
            return True
        with self.db.tenant_scope(job.tenant_id) as repo:
            jobs.complete(repo.s, job.id)
        log.info("job %s (%s) done", job.id, job.kind)
        return True

    def reconcile_uploads(self, limit: int = 100) -> int:
        """Maintenance hook; idle queue ticks process one intent without delaying queued jobs."""
        return reconcile_pending_writes(self.db, self.store, limit=limit)

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
                if not repo.lock_for_version(job.ids["version_id"]):
                    return
                v = repo.version(job.ids["version_id"], lock=True)
                if v is not None and v.status == "uploaded":
                    v.status, v.reject_reason = "rejected", "parse_failed"
                    repo.s.flush()
                    resume_waiting(repo, v.id, self.settings.job_max_attempts)
            elif job.kind == "compare":
                if not repo.lock_for_comparison(job.ids["comparison_id"]):
                    return
                c = repo.comparison(job.ids["comparison_id"], lock=True)
                if c is not None and c.status not in TERMINAL:
                    c.status = "failed"
                    c.warnings = list(c.warnings) + [{"code": "job_failed"}]

    # Handlers -------------------------------------------------------------------------------
    def handle_parse(self, tenant_id: uuid.UUID, version_id: uuid.UUID) -> None:
        with self.db.tenant_scope(tenant_id) as repo:
            if not repo.lock_for_version(version_id):
                return
            v = repo.version(version_id)
            if v is None or v.status != "uploaded":
                return  # another tenant's ID or already done: nothing to do (idempotent)
            key, kind = v.original_object_key, v.kind
            data = self.store.get(key)
        # PDFs are parsed in the capped sandbox child (03 §6); a breach rejects the version.
        try:
            doc, reason = parse_sandboxed(data, kind, self.settings.limits), None
        except ParseRejected as r:
            doc, reason = None, r.code
        with self.db.tenant_scope(tenant_id) as repo:
            if not repo.lock_for_version(version_id):
                return
            v = repo.version(version_id, lock=True)
            if v is None or v.status != "uploaded":
                return
            if doc is None:
                v.status, v.reject_reason = "rejected", reason
            else:
                v.parsed_pages, v.blocks, v.page_count = doc.pages, doc.blocks_json(), doc.page_count
                v.parse_warnings = doc.to_json()["warnings"]
                v.status = "parsed"
            repo.s.flush()
            resume_waiting(repo, v.id, self.settings.job_max_attempts)

    def handle_compare(self, tenant_id: uuid.UUID, comparison_id: uuid.UUID) -> None:
        with self.db.tenant_scope(tenant_id) as repo:
            if not repo.lock_for_comparison(comparison_id):
                return
            c = repo.comparison(comparison_id, lock=True)
            if c is None or c.status not in ("queued", "running"):
                return
            c.status = "running"
            e, l = repo.version(c.earlier_id), repo.version(c.later_id)
            earlier = ParsedDocument.from_stored(e.kind, e.parsed_pages, e.blocks, e.page_count, e.parse_warnings)
            later = ParsedDocument.from_stored(l.kind, l.parsed_pages, l.blocks, l.page_count, l.parse_warnings)
            sides = [(e.id, e.sha256, earlier), (l.id, l.sha256, later)]
            ceiling, scope = c.cost_ceiling, c.scope_snapshot
        config_id = getattr(self.llm, "config_id", MODEL_CONFIG_ID)
        meter = DbCostMeter(self.db, tenant_id, comparison_id, self.settings)
        out = run_comparison([(sha, doc, DbFactCache(self.db, tenant_id, vid)) for vid, sha, doc in sides],
                             scope, self.llm, ceiling, config_id, meter=meter)
        if meter.spend_cap is not None:  # a monthly cap stopped the run before a paid stage (I-8 S6)
            log.warning("comparison %s stopped: %s spend cap reached", comparison_id, meter.spend_cap)
            out.status, out.warnings = "failed", out.warnings + [{"code": "spend_cap_reached"}]
        if any(w.get("code") == "cost_ceiling" for w in out.warnings):
            log.warning("comparison %s reached the cost ceiling after %d llm calls", comparison_id, out.calls)
        self._finish(tenant_id, comparison_id, out.checked, out.status, out.warnings)
        log.info("comparison %s %s: %d findings, %d withheld, %d unexplained, cost %s of %s", comparison_id,
                 out.status, len(out.checked.findings), out.checked.withheld_count, len(out.checked.unexplained),
                 out.cost, ceiling)

    def _finish(self, tenant_id, comparison_id, checked: VerifyResult, status, warnings) -> None:
        with self.db.tenant_scope(tenant_id) as repo:
            if not repo.lock_for_comparison(comparison_id):
                return
            c = repo.comparison(comparison_id, lock=True)
            if c is None or c.status in TERMINAL:
                return
            rows = [Finding(comparison_id=c.id, category=f.category, change_type=f.change_type,
                            evidence=[_evidence_json(ev) for ev in f.evidence], explanation=f.explanation,
                            uncertainty=f.uncertainty, note=f.note, review_group=f.group, priority=f.priority)
                    for f in checked.findings]
            repo.replace_findings(c.id, rows)
            c.withheld_count = checked.withheld_count
            c.unexplained = [_evidence_json(ev) for ev in checked.unexplained]
            c.presentation_only = [_evidence_json(ev) for ev in checked.presentation_only]
            c.status, c.warnings = status, warnings
            # Model attempts already persisted actual usage and outstanding holds. A retry
            # or late worker must never replace that history with its own run's total.
            if c.cost_actual is None:
                c.cost_actual = Decimal("0")  # a fully cached run may make no requests


def _evidence_json(ev: Evidence) -> dict:
    return {"side": ev.side, "quote": ev.quote,
            "locator": {"page": ev.locator.page, "char_start": ev.locator.char_start, "char_end": ev.locator.char_end}}
