"""
Tests for RationaleVault Scheduled Cognition (F6).
"""
from __future__ import annotations

import pytest

from rationalevault.knowledge.scheduler import (
    CognitiveJob,
    JobQueue,
    ExecutionRecord,
    ExecutionHistory,
    SchedulerMetrics,
    JobType,
    ExecutionOutcome,
)


class TestCognitiveJob:
    def test_id_generation_deterministic(self):
        id1 = CognitiveJob.generate_job_id("REFLECTION", ["REFL-001"], "2026-06-26T12:00:00Z")
        id2 = CognitiveJob.generate_job_id("REFLECTION", ["REFL-001"], "2026-06-26T12:00:00Z")
        assert id1 == id2
        assert id1.startswith("CJOB-")

    def test_id_sorted_order(self):
        id1 = CognitiveJob.generate_job_id("REFLECTION", ["B", "A"], "2026-06-26T12:00:00Z")
        id2 = CognitiveJob.generate_job_id("REFLECTION", ["A", "B"], "2026-06-26T12:00:00Z")
        assert id1 == id2

    def test_serialization_roundtrip(self):
        job = CognitiveJob(
            job_id="CJOB-TEST", job_type=JobType.REFLECTION, priority=1,
            context_ids=["REFL-001", "LEARN-001"], config={"depth": 3},
            created_at="2026-06-26T12:00:00Z",
        )
        d = job.to_dict()
        restored = CognitiveJob.from_dict(d)
        assert restored.job_id == job.job_id
        assert restored.job_type == job.job_type

    def test_frozen(self):
        job = CognitiveJob("CJOB-TEST", JobType.REFLECTION, 1, [], {}, "2026-06-26T12:00:00Z")
        with pytest.raises(AttributeError):
            job.priority = 2


class TestJobQueue:
    def test_sorted_jobs(self):
        j1 = CognitiveJob("CJOB-1", JobType.REFLECTION, 10, [], {}, "2026-06-26T12:00:00Z")
        j2 = CognitiveJob("CJOB-2", JobType.REFLECTION, 1, [], {}, "2026-06-26T12:00:01Z")
        j3 = CognitiveJob("CJOB-3", JobType.REFLECTION, 5, [], {}, "2026-06-26T12:00:02Z")
        queue = JobQueue(jobs=[j1, j2, j3], version=1)
        sorted_jobs = queue.sorted_jobs()
        assert sorted_jobs[0].priority == 1
        assert sorted_jobs[1].priority == 5
        assert sorted_jobs[2].priority == 10

    def test_serialization_roundtrip(self):
        j1 = CognitiveJob("CJOB-1", JobType.REFLECTION, 1, [], {}, "2026-06-26T12:00:00Z")
        queue = JobQueue(jobs=[j1], version=1)
        d = queue.to_dict()
        restored = JobQueue.from_dict(d)
        assert len(restored.jobs) == 1


class TestExecutionRecord:
    def test_id_generation_deterministic(self):
        id1 = ExecutionRecord.generate_execution_id("CJOB-001", "SUCCESS", "2026-06-26T12:00:00Z")
        id2 = ExecutionRecord.generate_execution_id("CJOB-001", "SUCCESS", "2026-06-26T12:00:00Z")
        assert id1 == id2
        assert id1.startswith("CEXEC-")

    def test_serialization_roundtrip(self):
        record = ExecutionRecord(
            execution_id="CEXEC-TEST", job_id="CJOB-TEST",
            outcome=ExecutionOutcome.SUCCESS, duration_ms=150,
            result_summary="Reflection completed", error_message=None,
            artifacts_produced=["REFL-001", "REFL-002"],
            created_at="2026-06-26T12:00:00Z",
        )
        d = record.to_dict()
        restored = ExecutionRecord.from_dict(d)
        assert restored.execution_id == record.execution_id
        assert restored.outcome == record.outcome

    def test_frozen(self):
        record = ExecutionRecord(
            "CEXEC-TEST", "CJOB-TEST", ExecutionOutcome.SUCCESS,
            150, "Test", None, [], "2026-06-26T12:00:00Z",
        )
        with pytest.raises(AttributeError):
            record.outcome = ExecutionOutcome.FAILURE


class TestExecutionHistory:
    def test_serialization_roundtrip(self):
        r1 = ExecutionRecord(
            "CEXEC-001", "CJOB-001", ExecutionOutcome.SUCCESS,
            100, "OK", None, [], "2026-06-26T12:00:00Z",
        )
        history = ExecutionHistory(records=[r1], version=1)
        d = history.to_dict()
        restored = ExecutionHistory.from_dict(d)
        assert len(restored.records) == 1

    def test_append_only_semantics(self):
        r1 = ExecutionRecord(
            "CEXEC-001", "CJOB-001", ExecutionOutcome.SUCCESS,
            100, "OK", None, [], "2026-06-26T12:00:00Z",
        )
        r2 = ExecutionRecord(
            "CEXEC-002", "CJOB-002", ExecutionOutcome.FAILURE,
            200, "Error", "Timeout", [], "2026-06-26T13:00:00Z",
        )
        history = ExecutionHistory(records=[r1, r2], version=1)
        assert len(history.records) == 2
        assert history.records[0].outcome == ExecutionOutcome.SUCCESS
        assert history.records[1].outcome == ExecutionOutcome.FAILURE


class TestSchedulerMetrics:
    def test_serialization_roundtrip(self):
        metrics = SchedulerMetrics(
            total_jobs_planned=10, total_jobs_executed=8,
            total_jobs_succeeded=7, total_jobs_failed=1,
            average_duration_ms=150.5, success_rate=0.875,
            last_planned_at="2026-06-26T12:00:00Z",
            last_executed_at="2026-06-26T12:01:00Z",
        )
        d = metrics.to_dict()
        restored = SchedulerMetrics.from_dict(d)
        assert restored.total_jobs_planned == 10
        assert restored.success_rate == 0.875

    def test_empty_metrics(self):
        metrics = SchedulerMetrics(
            0, 0, 0, 0, 0.0, 0.0, None, None,
        )
        d = metrics.to_dict()
        restored = SchedulerMetrics.from_dict(d)
        assert restored.total_jobs_planned == 0
        assert restored.success_rate == 0.0
