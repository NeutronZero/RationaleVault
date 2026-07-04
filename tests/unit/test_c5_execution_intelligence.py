"""
RationaleVault Unit Tests — Phase C5 Execution Intelligence.
"""
import pytest
from datetime import datetime, timezone
from rationalevault.schema.events import EventRecord, EventType
from rationalevault.projections.analytics import ExecutionAnalyticsProjection
from rationalevault.projections.intelligence import ExecutionIntelligenceProjection
from rationalevault.skill_platform.intelligence_models import (
    ExecutionAnalyticsConfig,
    RetryDecision,
    HealthStatus,
    HealthTrend,
    PlannerRecommendation,
    PlannerFeedback,
    LearningRecordBuilder,
)


import uuid
from rationalevault.schema.events import EventMetadata

def _make_executed_event(
    execution_id: str,
    skill_id: str,
    state: str,
    duration_ms: int = 100,
    error: str | None = None,
    output_hash: str = "OUT-1",
) -> EventRecord:
    meta = EventMetadata(actor="test-actor", source="test-source")
    dummy_uuid = uuid.uuid4()
    return EventRecord(
        event_sequence=1,
        id=dummy_uuid,
        project_id=dummy_uuid,
        stream_id="test",
        version=1,
        event_type=EventType.SKILL_EXECUTED,
        metadata=meta,
        payload={
            "execution_id": execution_id,
            "decision_id": "DEC-TEST",
            "skill_id": skill_id,
            "skill_name": "test-skill",
            "skill_version": "1.0.0",
            "state": state,
            "input_hash": "IN-1",
            "output_hash": output_hash,
            "error": error,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "duration_ms": duration_ms,
            "promotion_report": {
                "promoted": [{"size": 1024}],
                "rejected": [],
                "gate_result": {"violations": []},
                "evaluation": {"score": 0.95},
            },
        },
        parent_id=None,
        recorded_at=datetime.now(timezone.utc),
    )


def test_execution_analytics_calculations():
    # Construct historical events: 4 completed, 1 timeout, 1 validation failure
    events = [
        _make_executed_event("SKE-1", "SKL-1", "COMPLETED", duration_ms=100),
        _make_executed_event("SKE-2", "SKL-1", "COMPLETED", duration_ms=120),
        _make_executed_event("SKE-3", "SKL-1", "COMPLETED", duration_ms=80),
        _make_executed_event("SKE-4", "SKL-1", "COMPLETED", duration_ms=90),
        _make_executed_event("SKE-5", "SKL-1", "TIMEOUT", duration_ms=5000),
        _make_executed_event("SKE-6", "SKL-1", "FAILED", error="Output validation failed: missing key", duration_ms=50),
    ]

    config = ExecutionAnalyticsConfig(window_size=5)
    analytics_state = ExecutionAnalyticsProjection.project(events, config)

    assert analytics_state.version == "1.0.0"
    assert analytics_state.analytics_hash != ""

    analytics = analytics_state.analytics
    assert "SKL-1" in analytics.skills
    stats = analytics.skills["SKL-1"]

    assert stats.total_executions == 6
    assert abs(stats.success_rate - (4 / 6)) < 0.01
    
    # Rolling success rate (last 5 runs of the 6 events)
    # The last 5 runs are SKE-2 (COMPLETED), SKE-3 (COMPLETED), SKE-4 (COMPLETED), SKE-5 (TIMEOUT), SKE-6 (FAILED)
    # Success counts in window = 3 out of 5 = 0.60
    assert abs(stats.rolling_success_rate - 0.60) < 0.01
    assert stats.timeouts == 1
    assert stats.schema_failures == 1

    # Promotion statistics
    assert analytics.promotions.candidate_count == 6
    assert analytics.promotions.promoted_count == 6
    assert abs(analytics.promotions.average_gate_score - 0.95) < 0.001


def test_execution_intelligence_interpretation():
    # Build healthy event stream vs unhealthy/degrading event stream
    events = [
        # Skill 1 is healthy and stable
        _make_executed_event("SKE-1", "SKL-HEALTHY", "COMPLETED", duration_ms=100),
        _make_executed_event("SKE-2", "SKL-HEALTHY", "COMPLETED", duration_ms=110),
        _make_executed_event("SKE-3", "SKL-HEALTHY", "COMPLETED", duration_ms=100),
        
        # Skill 2 is degraded and timeout failure
        _make_executed_event("SKE-4", "SKL-DEGRADED", "COMPLETED", duration_ms=150),
        _make_executed_event("SKE-5", "SKL-DEGRADED", "TIMEOUT", duration_ms=6000),
    ]

    report = ExecutionIntelligenceProjection.project(events)
    assert report.version == "1.0.0"

    assessment = report.assessment
    assert "SKL-HEALTHY" in assessment.skill_health
    assert assessment.skill_health["SKL-HEALTHY"] == HealthStatus.HEALTHY
    assert assessment.skill_health["SKL-DEGRADED"] == HealthStatus.UNHEALTHY

    # Verify score breakdown
    assert assessment.scores.overall_score >= 0.0
    assert assessment.scores.reliability_score > 0.0

    # Retry recommendations
    intelligence = report.intelligence
    assert len(intelligence.retry_recommendations) == 1
    rec = intelligence.retry_recommendations[0]
    assert rec.execution_id == "SKE-5"
    assert rec.decision == RetryDecision.BACKOFF
    assert rec.recommended_backoff_seconds == 10


def test_learning_record_builder():
    feedback = PlannerFeedback(
        planner_id="PLN-1",
        confidence_adjustment=-0.1,
        planner_profile_hint="degraded-profile",
        skill_priority_delta={"SKL-1": -0.2},
        planner_recommendation=PlannerRecommendation.DECREASE_PRIORITY,
        rationale="degraded rolling success rate on SKL-1",
    )

    record = LearningRecordBuilder.build(
        planner_feedback=feedback,
        assessment_hash="ASSESSMENT-1",
        analytics_hash="ANALYTICS-1",
        evaluation_version="1.0",
        created_at="2026-01-01T00:00:00Z",
        source_execution_ids=["SKE-1"],
        source_artifact_ids=["ART-1"],
    )

    assert record.learning_id.startswith("LEARN-")
    assert record.planner_feedback.planner_id == "PLN-1"
    assert record.assessment_hash == "ASSESSMENT-1"
    assert record.analytics_hash == "ANALYTICS-1"
    assert record.source_execution_ids == ["SKE-1"]
