"""Local job lifecycle model for heavyweight analysis work."""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal

from src.persistent_cache import PersistentJsonCache, repo_state_cache, utc_now_iso

JobStatus = Literal["queued", "running", "succeeded", "failed", "partial", "cancelled"]

ANALYSIS_JOBS_NAMESPACE = "analysis_jobs"
_NO_EXPIRY_SECONDS = 60 * 60 * 24 * 365 * 100


@dataclass
class AnalysisJob:
    """Persisted lifecycle state for one local analysis job."""

    job_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    job_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: JobStatus = "queued"
    attempts: int = 0
    max_retries: int = 0
    timeout_seconds: int | None = None
    result: dict[str, Any] = field(default_factory=dict)
    error: str = ""
    warnings: list[str] = field(default_factory=list)
    last_successful_cache: str = ""
    created_at: str = field(default_factory=utc_now_iso)
    updated_at: str = field(default_factory=utc_now_iso)
    history: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_mapping(cls, value: dict[str, Any]) -> AnalysisJob:
        return cls(
            job_id=str(value.get("job_id") or uuid.uuid4()),
            job_type=str(value.get("job_type") or ""),
            payload=dict(value.get("payload") or {}),
            status=_coerce_status(value.get("status")),
            attempts=int(value.get("attempts") or 0),
            max_retries=int(value.get("max_retries") or 0),
            timeout_seconds=value.get("timeout_seconds"),
            result=dict(value.get("result") or {}),
            error=str(value.get("error") or ""),
            warnings=list(value.get("warnings") or []),
            last_successful_cache=str(value.get("last_successful_cache") or ""),
            created_at=str(value.get("created_at") or utc_now_iso()),
            updated_at=str(value.get("updated_at") or utc_now_iso()),
            history=list(value.get("history") or []),
        )


class AnalysisJobStore:
    """Small JSON-backed store for queued local analysis jobs."""

    def __init__(self, cache: PersistentJsonCache | None = None) -> None:
        self.cache = cache or repo_state_cache(ANALYSIS_JOBS_NAMESPACE)

    def enqueue(
        self,
        job_type: str,
        payload: dict[str, Any],
        *,
        job_id: str | None = None,
        max_retries: int = 0,
        timeout_seconds: int | None = None,
    ) -> AnalysisJob:
        job = AnalysisJob(
            job_id=job_id or str(uuid.uuid4()),
            job_type=job_type,
            payload=payload,
            max_retries=max_retries,
            timeout_seconds=timeout_seconds,
        )
        job.history.append(_event("queued"))
        return self.save(job)

    def start(self, job_id: str) -> AnalysisJob:
        job = self.get(job_id)
        if job.status not in {"queued", "running"}:
            raise ValueError(f"Cannot start job in status {job.status}")
        job.status = "running"
        job.attempts += 1
        job.error = ""
        job.history.append(_event("running"))
        return self.save(job)

    def succeed(
        self,
        job_id: str,
        result: dict[str, Any],
        *,
        warnings: list[str] | None = None,
        last_successful_cache: str = "",
        partial: bool = False,
    ) -> AnalysisJob:
        job = self.get(job_id)
        job.status = "partial" if partial else "succeeded"
        job.result = result
        job.warnings = list(warnings or [])
        job.error = ""
        job.last_successful_cache = last_successful_cache
        job.history.append(_event(job.status))
        return self.save(job)

    def fail(self, job_id: str, error: str) -> AnalysisJob:
        job = self.get(job_id)
        job.error = error
        if job.attempts <= job.max_retries:
            job.status = "queued"
            job.history.append(_event("queued", f"retry after failure: {error}"))
        else:
            job.status = "failed"
            job.history.append(_event("failed", error))
        return self.save(job)

    def mark_timed_out(self, job_id: str) -> AnalysisJob:
        job = self.get(job_id)
        seconds = job.timeout_seconds or 0
        job.status = "failed"
        job.error = f"Job timed out after {seconds} seconds."
        job.history.append(_event("failed", job.error))
        return self.save(job)

    def cancel(self, job_id: str) -> AnalysisJob:
        job = self.get(job_id)
        if job.status in {"succeeded", "failed", "partial"}:
            raise ValueError(f"Cannot cancel terminal job {job_id}")
        job.status = "cancelled"
        job.history.append(_event("cancelled"))
        return self.save(job)

    def get(self, job_id: str) -> AnalysisJob:
        read = self.cache.read(job_id, fresh_seconds=_NO_EXPIRY_SECONDS)
        if not read.is_available:
            raise KeyError(job_id)
        return AnalysisJob.from_mapping(read.payload)

    def list_jobs(self) -> list[AnalysisJob]:
        root: Path = self.cache.root
        if not root.exists():
            return []
        jobs = []
        for path in sorted(root.glob("*.json")):
            read = self.cache.read_path(
                path,
                path.stem,
                fresh_seconds=_NO_EXPIRY_SECONDS,
            )
            if read.is_available:
                jobs.append(AnalysisJob.from_mapping(read.payload))
        return jobs

    def save(self, job: AnalysisJob) -> AnalysisJob:
        job.updated_at = utc_now_iso()
        self.cache.write(job.job_id, job.to_dict(), fetched_at=job.updated_at)
        return job


def repo_analysis_job_store() -> AnalysisJobStore:
    return AnalysisJobStore()


def _event(status: str, message: str = "") -> dict[str, str]:
    return {"status": status, "message": message, "at": utc_now_iso()}


def _coerce_status(value: Any) -> JobStatus:
    if value in {"queued", "running", "succeeded", "failed", "partial", "cancelled"}:
        return value
    return "queued"
