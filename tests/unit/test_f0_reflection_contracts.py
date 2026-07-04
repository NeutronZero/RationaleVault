"""
RationaleVault Unit Tests — Phase F0 Reflection Contracts.
"""
import pytest
import hashlib
from rationalevault.skill_platform.reflection_models import (
    ReflectionReason,
    ReflectionStatus,
    ReflectionConfig,
    ReflectionCandidate,
    Reflection,
    ReflectionReport,
)


def test_reflection_enums():
    # Verify that the enum values match the v1.6.0 freeze spec
    assert ReflectionReason.OUTCOME_MISMATCH == "OUTCOME_MISMATCH"
    assert ReflectionReason.CONTRADICTION_DETECTED == "CONTRADICTION_DETECTED"
    assert ReflectionReason.LOW_CONFIDENCE == "LOW_CONFIDENCE"
    assert ReflectionReason.GATE_BLOCK == "GATE_BLOCK"
    assert ReflectionReason.MANUAL_TRIGGER == "MANUAL_TRIGGER"
    assert ReflectionReason.PERFORMANCE_DEGRADATION == "PERFORMANCE_DEGRADATION"

    assert ReflectionStatus.PENDING == "PENDING"
    assert ReflectionStatus.ACTIVE == "ACTIVE"
    assert ReflectionStatus.COMPLETED == "COMPLETED"
    assert ReflectionStatus.REJECTED == "REJECTED"
    assert ReflectionStatus.ABORTED == "ABORTED"


def test_reflection_config_serialization():
    config = ReflectionConfig(
        version="1.0.0",
        enabled=True,
        confidence_threshold=0.85,
        enabled_reasons=[
            ReflectionReason.OUTCOME_MISMATCH,
            ReflectionReason.PERFORMANCE_DEGRADATION,
        ],
    )

    d = config.to_dict()
    assert d["version"] == "1.0.0"
    assert d["enabled"] is True
    assert d["confidence_threshold"] == 0.85
    assert d["enabled_reasons"] == ["OUTCOME_MISMATCH", "PERFORMANCE_DEGRADATION"]

    config2 = ReflectionConfig.from_dict(d)
    assert config2 == config


def test_reflection_candidate_id_and_serialization():
    source_artifact_id = "ART-99"
    reason = ReflectionReason.GATE_BLOCK
    config_version = "v1.2"
    created_at = "2026-06-26T12:00:00Z"

    candidate_id = ReflectionCandidate.generate_candidate_id(
        source_artifact_id=source_artifact_id,
        reason=reason,
        config_version=config_version,
    )

    # Re-calculate hash manually to assert determinism
    expected_data = f"candidate_reflection:{source_artifact_id}:{reason.value}:{config_version}"
    expected_hash = hashlib.sha256(expected_data.encode("utf-8")).hexdigest()[:8].upper()
    expected_id = f"RCAND-{expected_hash}"

    assert candidate_id == expected_id
    assert candidate_id.startswith("RCAND-")

    candidate = ReflectionCandidate(
        candidate_id=candidate_id,
        source_artifact_id=source_artifact_id,
        reason=reason,
        context={"metric_score": 0.45},
        created_at=created_at,
        config_version=config_version,
    )

    d = candidate.to_dict()
    assert d["candidate_id"] == candidate_id
    assert d["source_artifact_id"] == source_artifact_id
    assert d["reason"] == "GATE_BLOCK"
    assert d["context"] == {"metric_score": 0.45}
    assert d["created_at"] == created_at
    assert d["config_version"] == config_version

    candidate2 = ReflectionCandidate.from_dict(d)
    assert candidate2 == candidate


def test_reflection_id_and_serialization():
    candidate_id = "RCAND-ABCD1234"
    created_at = "2026-06-26T12:15:00Z"

    reflection_id = Reflection.generate_reflection_id(
        candidate_id=candidate_id,
        created_at=created_at,
    )

    # Re-calculate hash manually
    expected_data = f"reflection:{candidate_id}:{created_at}"
    expected_hash = hashlib.sha256(expected_data.encode("utf-8")).hexdigest()[:8].upper()
    expected_id = f"REFL-{expected_hash}"

    assert reflection_id == expected_id
    assert reflection_id.startswith("REFL-")

    reflection = Reflection(
        reflection_id=reflection_id,
        candidate_id=candidate_id,
        status=ReflectionStatus.COMPLETED,
        insights=["Avoid loop checking without backoff"],
        reconstructed_rationale="The executor ran too fast without checking permits",
        actionable_guidelines=["Limit iterations to 5"],
        created_at=created_at,
        completed_at="2026-06-26T12:20:00Z",
    )

    d = reflection.to_dict()
    assert d["reflection_id"] == reflection_id
    assert d["candidate_id"] == candidate_id
    assert d["status"] == "COMPLETED"
    assert d["insights"] == ["Avoid loop checking without backoff"]
    assert d["reconstructed_rationale"] == "The executor ran too fast without checking permits"
    assert d["actionable_guidelines"] == ["Limit iterations to 5"]
    assert d["created_at"] == created_at
    assert d["completed_at"] == "2026-06-26T12:20:00Z"

    reflection2 = Reflection.from_dict(d)
    assert reflection2 == reflection


def test_reflection_report_id_and_serialization():
    r1 = Reflection(
        reflection_id="REFL-11111111",
        candidate_id="RCAND-11111111",
        status=ReflectionStatus.COMPLETED,
        insights=["Insight 1"],
        reconstructed_rationale="Rationale 1",
        actionable_guidelines=["Guideline 1"],
        created_at="2026-06-26T12:00:00Z",
    )
    r2 = Reflection(
        reflection_id="REFL-22222222",
        candidate_id="RCAND-22222222",
        status=ReflectionStatus.COMPLETED,
        insights=["Insight 2"],
        reconstructed_rationale="Rationale 2",
        actionable_guidelines=["Guideline 2"],
        created_at="2026-06-26T12:05:00Z",
    )
    reflections = [r2, r1]  # pass out of order to verify sorting logic in ID generation
    created_at = "2026-06-26T12:30:00Z"

    report_id = ReflectionReport.generate_report_id(reflections, created_at)

    # Re-calculate hash manually (sorted keys = REFL-11111111,REFL-22222222)
    expected_data = f"report:REFL-11111111,REFL-22222222:{created_at}"
    expected_hash = hashlib.sha256(expected_data.encode("utf-8")).hexdigest()[:8].upper()
    expected_id = f"RREP-{expected_hash}"

    assert report_id == expected_id
    assert report_id.startswith("RREP-")

    report = ReflectionReport(
        report_id=report_id,
        reflections=[r1, r2],
        summary={"total_insights": 2},
        created_at=created_at,
    )

    d = report.to_dict()
    assert d["report_id"] == report_id
    assert len(d["reflections"]) == 2
    assert d["reflections"][0]["reflection_id"] == "REFL-11111111"
    assert d["summary"] == {"total_insights": 2}
    assert d["created_at"] == created_at

    report2 = ReflectionReport.from_dict(d)
    assert report2 == report
