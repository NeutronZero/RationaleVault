"""
RationaleVault Unit Tests — Phase F1 Reflection Engine.
"""
import pytest
from datetime import datetime, timezone
from rationalevault.schema.events import EventRecord, EventType, EventMetadata
from uuid import uuid4

from rationalevault.skill_platform.intelligence_models import (
    ExecutionLearningRecord,
    PlannerFeedback,
    PlannerRecommendation,
)
from rationalevault.skill_platform.reflection_models import (
    ReflectionReason,
    ReflectionStatus,
    ReflectionConfig,
    ReflectionCandidate,
    Reflection,
)
from rationalevault.skill_platform.reflection_engine import (
    ReflectionCandidateBuilder,
    MinSupportingRecordsRule,
    RecurrenceThresholdRule,
    ConflictingEvidenceRule,
    MinConfidenceRule,
    DuplicateSuppressionRule,
    ReflectionRuleEngine,
    ReflectionCompiler,
)
from rationalevault.projections.reflection import ReflectionStateProjection


def _make_learning_record(
    learning_id: str,
    planner_id: str,
    rationale: str,
    confidence_adjustment: float = -0.1,
    planner_recommendation: PlannerRecommendation = PlannerRecommendation.DECREASE_PRIORITY,
    skill_priority_delta: dict[str, float] | None = None,
    source_artifact_ids: list[str] | None = None,
) -> ExecutionLearningRecord:
    feedback = PlannerFeedback(
        planner_id=planner_id,
        confidence_adjustment=confidence_adjustment,
        planner_profile_hint="default-profile",
        skill_priority_delta=skill_priority_delta or {},
        planner_recommendation=planner_recommendation,
        rationale=rationale,
    )
    return ExecutionLearningRecord(
        learning_id=learning_id,
        planner_feedback=feedback,
        assessment_hash="ASS-HASH",
        analytics_hash="ANA-HASH",
        evaluation_version="1.0",
        created_at="2026-06-26T12:00:00Z",
        source_execution_ids=["SKE-1"],
        source_artifact_ids=source_artifact_ids or ["ART-1"],
    )


def test_candidate_builder_timeouts_and_failures():
    # Construct learning records: 2 timeouts for SKL-TIMEOUT, 1 success, 1 failure for SKL-FAILURE
    records = [
        _make_learning_record(
            "LEARN-1", "PLN-1", "Timeout exceeded during execution of SKL-TIMEOUT",
            skill_priority_delta={"SKL-TIMEOUT": -0.15}
        ),
        _make_learning_record(
            "LEARN-2", "PLN-1", "Performance degraded; timeout again",
            skill_priority_delta={"SKL-TIMEOUT": -0.2}
        ),
        _make_learning_record(
            "LEARN-3", "PLN-1", "Successful completion, boosting priority",
            confidence_adjustment=0.1,
            planner_recommendation=PlannerRecommendation.INCREASE_PRIORITY,
            skill_priority_delta={"SKL-TIMEOUT": 0.05}
        ),
        _make_learning_record(
            "LEARN-4", "PLN-1", "Result output mismatch",
            skill_priority_delta={"SKL-FAILURE": -0.1}
        ),
    ]

    config = ReflectionConfig(
        version="1.0",
        enabled=True,
        confidence_threshold=0.3,
        enabled_reasons=[
            ReflectionReason.PERFORMANCE_DEGRADATION,
            ReflectionReason.OUTCOME_MISMATCH,
        ],
    )

    candidates = ReflectionCandidateBuilder.build_candidates(records, config)
    assert len(candidates) == 2

    # Verify SKL-TIMEOUT candidate triggers PERFORMANCE_DEGRADATION
    cand_timeout = next(c for c in candidates if c.context["target"] == "SKL-TIMEOUT")
    assert cand_timeout.reason == ReflectionReason.PERFORMANCE_DEGRADATION
    assert cand_timeout.context["recurrence_count"] == 2
    assert cand_timeout.context["timeouts_count"] == 2
    assert len(cand_timeout.context["conflicting_record_ids"]) == 1

    # Verify SKL-FAILURE candidate triggers OUTCOME_MISMATCH
    cand_fail = next(c for c in candidates if c.context["target"] == "SKL-FAILURE")
    assert cand_fail.reason == ReflectionReason.OUTCOME_MISMATCH
    assert cand_fail.context["recurrence_count"] == 1


def test_reflection_rules():
    config = ReflectionConfig(
        version="1.0",
        enabled=True,
        confidence_threshold=0.4,
        enabled_reasons=[ReflectionReason.OUTCOME_MISMATCH],
    )

    candidate = ReflectionCandidate(
        candidate_id="RCAND-TEST",
        source_artifact_id="ART-1",
        reason=ReflectionReason.OUTCOME_MISMATCH,
        context={
            "target": "SKL-1",
            "supporting_record_ids": ["L-1", "L-2"],
            "conflicting_record_ids": ["L-3"],
            "recurrence_count": 2,
        },
        created_at="2026-06-26T12:00:00Z",
        config_version="1.0",
    )

    # 1. Min supporting records
    rule_min = MinSupportingRecordsRule(min_records=2)
    passed, msg = rule_min.evaluate(candidate, config)
    assert passed is True

    rule_min_fail = MinSupportingRecordsRule(min_records=3)
    passed, msg = rule_min_fail.evaluate(candidate, config)
    assert passed is False

    # 2. Recurrence threshold
    rule_rec = RecurrenceThresholdRule(threshold=2)
    passed, msg = rule_rec.evaluate(candidate, config)
    assert passed is True

    rule_rec_fail = RecurrenceThresholdRule(threshold=3)
    passed, msg = rule_rec_fail.evaluate(candidate, config)
    assert passed is False

    # 3. Conflicting evidence
    rule_conflict = ConflictingEvidenceRule()
    passed, msg = rule_conflict.evaluate(candidate, config)
    assert passed is True

    candidate_conflict_fail = ReflectionCandidate(
        candidate_id="RCAND-TEST2",
        source_artifact_id="ART-1",
        reason=ReflectionReason.OUTCOME_MISMATCH,
        context={
            "target": "SKL-1",
            "supporting_record_ids": ["L-1"],
            "conflicting_record_ids": ["L-2", "L-3"],
            "recurrence_count": 1,
        },
        created_at="2026-06-26T12:00:00Z",
        config_version="1.0",
    )
    passed, msg = rule_conflict.evaluate(candidate_conflict_fail, config)
    assert passed is False

    # 4. Min confidence score rule
    rule_conf = MinConfidenceRule()
    # base=0.5 + recurrence_bonus (min(0.4, (2-1)*0.1) = 0.1) - conflict_penalty (1*0.15 = 0.15) = 0.45
    # Threshold = 0.4 -> Should PASS
    passed, msg = rule_conf.evaluate(candidate, config)
    assert passed is True

    config_high = ReflectionConfig(
        version="1.0",
        enabled=True,
        confidence_threshold=0.5,
        enabled_reasons=[ReflectionReason.OUTCOME_MISMATCH],
    )
    passed, msg = rule_conf.evaluate(candidate, config_high)
    assert passed is False

    # 5. Duplicate suppression
    rule_dup = DuplicateSuppressionRule(active_targets={"SKL-1"})
    passed, msg = rule_dup.evaluate(candidate, config)
    assert passed is False

    rule_dup_pass = DuplicateSuppressionRule(active_targets={"SKL-OTHER"})
    passed, msg = rule_dup_pass.evaluate(candidate, config)
    assert passed is True


def test_rule_engine_and_compiler():
    candidate = ReflectionCandidate(
        candidate_id="RCAND-TEST",
        source_artifact_id="ART-1",
        reason=ReflectionReason.OUTCOME_MISMATCH,
        context={
            "target": "SKL-1",
            "supporting_record_ids": ["L-1", "L-2"],
            "conflicting_record_ids": [],
            "recurrence_count": 2,
            "rationales": ["rationale 1", "rationale 2"],
            "recommendations": ["DECREASE_PRIORITY"],
        },
        created_at="2026-06-26T12:00:00Z",
        config_version="1.0",
    )

    config = ReflectionConfig(
        version="1.0",
        enabled=True,
        confidence_threshold=0.4,
        enabled_reasons=[ReflectionReason.OUTCOME_MISMATCH],
    )

    rules = [
        MinSupportingRecordsRule(min_records=2),
        RecurrenceThresholdRule(threshold=2),
        ConflictingEvidenceRule(),
        MinConfidenceRule(),
        DuplicateSuppressionRule(active_targets=set()),
    ]

    engine = ReflectionRuleEngine(rules)
    assessment = engine.assess(candidate, config)

    assert assessment.approved is True
    # base=0.5 + recurrence_bonus((2-1)*0.1 = 0.1) = 0.6
    assert abs(assessment.confidence - 0.6) < 0.0001

    # Assert Rule Provenance
    assert assessment.passed_rules == [
        "MinSupportingRecordsRule",
        "RecurrenceThresholdRule",
        "ConflictingEvidenceRule",
        "MinConfidenceRule",
        "DuplicateSuppressionRule",
    ]
    assert assessment.failed_rules == []
    assert assessment.triggered_rules == [
        "MinSupportingRecordsRule",
        "RecurrenceThresholdRule",
        "ConflictingEvidenceRule",
        "MinConfidenceRule",
        "DuplicateSuppressionRule",
    ]
    assert abs(assessment.rule_scores["MinConfidenceRule"] - 0.6) < 0.0001
    assert assessment.rule_scores["MinSupportingRecordsRule"] == 1.0

    reflection = ReflectionCompiler.compile(assessment, candidate, "2026-06-26T12:30:00Z")
    assert reflection.reflection_id.startswith("REFL-")
    assert reflection.status == ReflectionStatus.COMPLETED
    assert "Target SKL-1 triggered OUTCOME_MISMATCH due to recurrent issues." in reflection.insights
    assert "Observer feedback: rationale 1" in reflection.insights
    assert "Planner Action Recommended: DECREASE_PRIORITY for target SKL-1" in reflection.actionable_guidelines


def test_reflection_state_projection():
    # 1. Prepare historical events containing a generated reflection
    meta = EventMetadata(actor="test", source="test")
    hist_reflection = Reflection(
        reflection_id="REFL-HIST1",
        candidate_id="RCAND-HIST",
        status=ReflectionStatus.COMPLETED,
        insights=["Insight hist"],
        reconstructed_rationale="Reflection triggered for target 'SKL-HIST' via candidate hist.",
        actionable_guidelines=[],
        created_at="2026-06-25T12:00:00Z",
        completed_at="2026-06-25T12:00:00Z",
    )

    events = [
        EventRecord(
            event_sequence=1,
            id=uuid4(),
            project_id=uuid4(),
            stream_id="reflection",
            version=1,
            event_type=EventType.REFLECTION_GENERATED,
            metadata=meta,
            payload=hist_reflection.to_dict(),
            parent_id=None,
            recorded_at=datetime.now(timezone.utc),
        )
    ]

    # 2. Prepare new learning records that will trigger a reflection
    # We will trigger SKL-1 outcome mismatch reflection
    learning_records = [
        _make_learning_record("L-1", "PLN-1", "Fail 1", skill_priority_delta={"SKL-1": -0.1}),
        _make_learning_record("L-2", "PLN-1", "Fail 2", skill_priority_delta={"SKL-1": -0.15}),
    ]

    config = ReflectionConfig(
        version="1.0",
        enabled=True,
        confidence_threshold=0.4,
        enabled_reasons=[ReflectionReason.OUTCOME_MISMATCH],
    )

    report, bundle = ReflectionStateProjection.project(events, learning_records, config, "2026-06-26T12:45:00Z")

    assert report.report_id.startswith("RREP-")
    assert len(report.reflections) == 2  # 1 historical, 1 new approved reflection
    assert report.summary["total_historical_reflections"] == 1
    assert report.summary["new_candidates_evaluated"] == 1
    assert report.summary["new_reflections_approved"] == 1
    assert "SKL-HIST" in report.summary["active_reflection_targets"]

    # Verify event payloads are produced
    assert len(bundle.candidate_created) == 1
    assert len(bundle.assessed) == 1
    assert len(bundle.generated) == 1
    assert len(bundle.traced) == 1
    assert bundle.candidate_created[0].schema_version == "1.0"
    assert bundle.assessed[0].approved is True
    assert bundle.generated[0].status == "COMPLETED"
    assert bundle.traced[0].approved is True
