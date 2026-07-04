"""
RationaleVault Scheduled Cognition — Planner → JobQueue → Executor → ExecutionHistory.

Architecture:
  Planner (deterministic job planning)
      ↓
  JobQueue (ordered pending jobs)
      ↓
  Executor (runs jobs)
      ↓
  ExecutionHistory (records what happened)
      +
  SchedulerMetrics (tracks performance)

Design rules:
  - CJOB-[hash] for cognitive jobs.
  - CEXEC-[hash] for execution history records.
  - Planner is stateless, consumes PlannerAdjustmentProjection.
  - Jobs are deterministic — same input produces same job plan.
  - ExecutionHistory is append-only.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from enum import Enum
from typing import Any


# =====================================================================
# Enums
# =====================================================================

class JobType(str, Enum):
    """Types of cognitive jobs."""
    REFLECTION = "REFLECTION"
    KNOWLEDGE_PROMOTION = "KNOWLEDGE_PROMOTION"
    KNOWLEDGE_VALIDATION = "KNOWLEDGE_VALIDATION"
    MEMORY_LIFECYCLE = "MEMORY_LIFECYCLE"
    ADVISORY = "ADVISORY"


class JobStatus(str, Enum):
    """Status of a cognitive job."""
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class ExecutionOutcome(str, Enum):
    """Outcome of a job execution."""
    SUCCESS = "SUCCESS"
    PARTIAL = "PARTIAL"
    FAILURE = "FAILURE"
    TIMEOUT = "TIMEOUT"


# =====================================================================
# Domain Models
# =====================================================================

@dataclass(frozen=True)
class CognitiveJob:
    """
    A deterministic cognitive job to be executed.

    CJOB-[hash] — immutable, append-only.
    """
    job_id: str                     # CJOB-[hash]
    job_type: JobType
    priority: int                   # Lower = higher priority
    context_ids: list[str]          # IDs of objects this job operates on
    config: dict[str, Any]
    created_at: str

    @staticmethod
    def generate_job_id(job_type: str, context_ids: list[str], created_at: str) -> str:
        sorted_ids = ",".join(sorted(context_ids))
        data = f"cognitive_job:{job_type}:{sorted_ids}:{created_at}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"CJOB-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "job_type": self.job_type.value,
            "priority": self.priority,
            "context_ids": self.context_ids,
            "config": self.config,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CognitiveJob:
        return cls(
            job_id=d["job_id"],
            job_type=JobType(d["job_type"]),
            priority=d.get("priority", 100),
            context_ids=d.get("context_ids", []),
            config=d.get("config", {}),
            created_at=d["created_at"],
        )


@dataclass(frozen=True)
class JobQueue:
    """
    Ordered queue of pending cognitive jobs.

    Deterministic ordering by priority then creation time.
    """
    jobs: list[CognitiveJob]
    version: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "jobs": [j.to_dict() for j in self.jobs],
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> JobQueue:
        return cls(
            jobs=[CognitiveJob.from_dict(j) for j in d.get("jobs", [])],
            version=d.get("version", 1),
        )

    def sorted_jobs(self) -> list[CognitiveJob]:
        """Return jobs sorted by priority (ascending) then created_at."""
        return sorted(self.jobs, key=lambda j: (j.priority, j.created_at))


@dataclass(frozen=True)
class ExecutionRecord:
    """
    Record of a job execution.

    CEXEC-[hash] — immutable, append-only.
    """
    execution_id: str               # CEXEC-[hash]
    job_id: str                     # CJOB-[hash]
    outcome: ExecutionOutcome
    duration_ms: int
    result_summary: str
    error_message: str | None
    artifacts_produced: list[str]   # IDs of artifacts produced
    created_at: str

    @staticmethod
    def generate_execution_id(job_id: str, outcome: str, created_at: str) -> str:
        data = f"execution:{job_id}:{outcome}:{created_at}"
        h = hashlib.sha256(data.encode("utf-8")).hexdigest()[:8].upper()
        return f"CEXEC-{h}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_id": self.execution_id,
            "job_id": self.job_id,
            "outcome": self.outcome.value,
            "duration_ms": self.duration_ms,
            "result_summary": self.result_summary,
            "error_message": self.error_message,
            "artifacts_produced": self.artifacts_produced,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ExecutionRecord:
        return cls(
            execution_id=d["execution_id"],
            job_id=d["job_id"],
            outcome=ExecutionOutcome(d["outcome"]),
            duration_ms=d.get("duration_ms", 0),
            result_summary=d.get("result_summary", ""),
            error_message=d.get("error_message"),
            artifacts_produced=d.get("artifacts_produced", []),
            created_at=d["created_at"],
        )


@dataclass(frozen=True)
class ExecutionHistory:
    """
    Append-only history of all job executions.
    """
    records: list[ExecutionRecord]
    version: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "records": [r.to_dict() for r in self.records],
            "version": self.version,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ExecutionHistory:
        return cls(
            records=[ExecutionRecord.from_dict(r) for r in d.get("records", [])],
            version=d.get("version", 1),
        )


@dataclass(frozen=True)
class SchedulerMetrics:
    """
    Metrics for scheduling performance.
    """
    total_jobs_planned: int
    total_jobs_executed: int
    total_jobs_succeeded: int
    total_jobs_failed: int
    average_duration_ms: float
    success_rate: float
    last_planned_at: str | None
    last_executed_at: str | None

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_jobs_planned": self.total_jobs_planned,
            "total_jobs_executed": self.total_jobs_executed,
            "total_jobs_succeeded": self.total_jobs_succeeded,
            "total_jobs_failed": self.total_jobs_failed,
            "average_duration_ms": round(self.average_duration_ms, 2),
            "success_rate": round(self.success_rate, 4),
            "last_planned_at": self.last_planned_at,
            "last_executed_at": self.last_executed_at,
        }

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> SchedulerMetrics:
        return cls(
            total_jobs_planned=d.get("total_jobs_planned", 0),
            total_jobs_executed=d.get("total_jobs_executed", 0),
            total_jobs_succeeded=d.get("total_jobs_succeeded", 0),
            total_jobs_failed=d.get("total_jobs_failed", 0),
            average_duration_ms=d.get("average_duration_ms", 0.0),
            success_rate=d.get("success_rate", 0.0),
            last_planned_at=d.get("last_planned_at"),
            last_executed_at=d.get("last_executed_at"),
        )
