"""Tests for Phase 1.1: Reflection event hierarchy and identifier registry."""
from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from uuid import uuid4

from rationalevault.schema.identifier_registry import (
    IdentifierPrefix,
    IDENTIFIER_REGISTRY,
    get_spec,
    list_prefixes,
)
from rationalevault.skill_platform.reflection_events import (
    ReflectionCandidateCreatedPayload,
    ReflectionAssessedPayload,
    ReflectionGeneratedPayload,
    ReflectionTracedPayload,
    RuleResultPayload,
    RuleTracePayload,
    generate_reflection_trace_id,
    generate_assessment_id,
    SCHEMA_VERSION,
)
from rationalevault.skill_platform.reflection_engine import (
    ReflectionCandidateBuilder,
    ReflectionCompiler,
    MinSupportingRecordsRule,
    ReflectionRuleEngine,
)
from rationalevault.skill_platform.reflection_models import (
    ReflectionReason,
    ReflectionConfig,
    ReflectionCandidate,
)
from rationalevault.skill_platform.intelligence_models import (
    ExecutionLearningRecord,
    PlannerFeedback,
    PlannerRecommendation,
    LearningRecordBuilder,
)
from rationalevault.projections.reflection import (
    ReflectionStateProjection,
    ReflectionEventBundle,
)


# =====================================================================
# Identifier Registry Tests
# =====================================================================

class TestIdentifierRegistry:
    def test_all_expected_prefixes_registered(self):
        """Every prefix used in the codebase must be registered."""
        expected = {
            "BEL", "SYN", "DEC",
            "SKE", "SRT", "ART", "ACAND", "SKL",
            "LEARN",
            "RCAND", "REFL", "RREP", "RTRC",
            "PROMO", "PASSMT", "PGATE", "PD", "PREP", "KCAN", "KNOW",
            "KVAL",
            "ADVC",
            "PADJ", "PPOL",
            "MTRANS",
            "CJOB", "CEXEC",
            "WS", "WSSNP", "WSSSN", "WSCTX", "WSPKG",
            "AGNT", "AGS", "AGCAP", "RTC", "WSB", "SSSN", "AGPRF",
            "TMNF", "TNAG", "TSSN",
            "VMNF",
            "MCPT", "MCPB", "MCPM",
            "MQRY", "MRES", "MCTX", "MWRT", "MWRS",
            "MPOL",
            "TELE", "ARUL", "APOL",
            "PSIM",
            "RSES",
        }
        assert expected == set(list_prefixes())

    def test_registry_has_57_entries(self):
        """Ensure no accidental additions or removals."""
        assert len(IDENTIFIER_REGISTRY) == 57

    def test_get_spec_returns_valid(self):
        spec = get_spec("REFL")
        assert spec.prefix == "REFL"
        assert "reflection" in spec.description.lower()

    def test_get_spec_unknown_raises(self):
        import pytest
        with pytest.raises(ValueError, match="Unknown identifier prefix"):
            get_spec("UNKNOWN")

    def test_ephemeral_flags(self):
        """Candidates should be marked ephemeral."""
        assert get_spec("ACAND").ephemeral is True
        assert get_spec("RCAND").ephemeral is True
        assert get_spec("KCAN").ephemeral is True
        assert get_spec("REFL").ephemeral is False
        assert get_spec("KNOW").ephemeral is False

    def test_all_specs_have_hash_template(self):
        for prefix, spec in IDENTIFIER_REGISTRY.items():
            assert spec.hash_input_template, f"{prefix} missing hash_input_template"
            assert "://" not in spec.hash_input_template, f"{prefix} hash template looks like a URL"


# =====================================================================
# Reflection Event Payload Tests
# =====================================================================

class TestReflectionCandidateCreatedPayload:
    def test_serialization_roundtrip(self):
        payload = ReflectionCandidateCreatedPayload(
            schema_version="1.0",
            candidate_id="RCAND-ABC12345",
            source_artifact_id="ART-XYZ99999",
            reason="OUTCOME_MISMATCH",
            context={"target": "SKL-1", "recurrence_count": 3},
            created_at="2026-06-26T12:00:00Z",
            config_version="1.0",
        )
        d = payload.to_dict()
        restored = ReflectionCandidateCreatedPayload.from_dict(d)
        assert restored == payload
        assert restored.schema_version == "1.0"

    def test_schema_version_required(self):
        payload = ReflectionCandidateCreatedPayload(
            candidate_id="RCAND-TEST",
            source_artifact_id="ART-TEST",
            reason="OUTCOME_MISMATCH",
            created_at="2026-06-26T12:00:00Z",
            config_version="1.0",
        )
        assert payload.schema_version == SCHEMA_VERSION


class TestReflectionAssessedPayload:
    def test_serialization_roundtrip(self):
        payload = ReflectionAssessedPayload(
            schema_version="1.0",
            assessment_id="RASSMT-ABC12345",
            candidate_id="RCAND-ABC12345",
            approved=True,
            confidence=0.75,
            base_confidence=0.5,
            recurrence_score=0.3,
            contradiction_penalty=0.0,
            duplicate_suppressed=False,
            rules_evaluated=[
                RuleResultPayload(rule_name="MinSupportingRecordsRule", passed=True, reason="Met threshold"),
                RuleResultPayload(rule_name="MinConfidenceRule", passed=True, reason="Score 0.75 >= 0.4"),
            ],
            supporting_record_ids=["LEARN-001", "LEARN-002"],
            created_at="2026-06-26T12:00:00Z",
        )
        d = payload.to_dict()
        restored = ReflectionAssessedPayload.from_dict(d)
        assert restored == payload
        assert len(restored.rules_evaluated) == 2
        assert restored.rules_evaluated[0].passed is True


class TestReflectionGeneratedPayload:
    def test_serialization_roundtrip(self):
        payload = ReflectionGeneratedPayload(
            schema_version="1.0",
            reflection_id="REFL-ABC12345",
            candidate_id="RCAND-ABC12345",
            status="COMPLETED",
            insights=["Target SKL-1 triggered OUTCOME_MISMATCH"],
            reconstructed_rationale="Reflection triggered for target 'SKL-1'",
            actionable_guidelines=["Planner Action Recommended: DECREASE_PRIORITY for target SKL-1"],
            source_learning_record_ids=["LEARN-001", "LEARN-002"],
            created_at="2026-06-26T12:00:00Z",
        )
        d = payload.to_dict()
        restored = ReflectionGeneratedPayload.from_dict(d)
        assert restored == payload
        assert restored.reflection_id == "REFL-ABC12345"


class TestReflectionTracedPayload:
    def test_serialization_roundtrip(self):
        payload = ReflectionTracedPayload(
            schema_version="1.0",
            trace_id="RTRC-ABC12345",
            reflection_id="REFL-ABC12345",
            candidate_id="RCAND-ABC12345",
            approved=True,
            confidence=0.75,
            rules_fired=[
                RuleTracePayload(rule_name="MinConfidenceRule", passed=True, reason="Score 0.75 >= 0.4", inputs={"confidence": 0.75}),
            ],
            contributing_learning_records=["LEARN-001"],
            ignored_learning_records=["LEARN-003"],
            duplicate_suppressed=False,
            conflict_resolution=None,
            created_at="2026-06-26T12:00:00Z",
        )
        d = payload.to_dict()
        restored = ReflectionTracedPayload.from_dict(d)
        assert restored == payload
        assert restored.trace_id == "RTRC-ABC12345"


# =====================================================================
# ID Generation Tests
# =====================================================================

class TestIDGeneration:
    def test_generate_reflection_trace_id_deterministic(self):
        id1 = generate_reflection_trace_id("REFL-001", "RCAND-001", "2026-06-26T12:00:00Z")
        id2 = generate_reflection_trace_id("REFL-001", "RCAND-001", "2026-06-26T12:00:00Z")
        assert id1 == id2
        assert id1.startswith("RTRC-")

    def test_generate_reflection_trace_id_unique(self):
        id1 = generate_reflection_trace_id("REFL-001", "RCAND-001", "2026-06-26T12:00:00Z")
        id2 = generate_reflection_trace_id("REFL-002", "RCAND-001", "2026-06-26T12:00:00Z")
        assert id1 != id2

    def test_generate_assessment_id_deterministic(self):
        id1 = generate_assessment_id("RCAND-001", "2026-06-26T12:00:00Z")
        id2 = generate_assessment_id("RCAND-001", "2026-06-26T12:00:00Z")
        assert id1 == id2
        assert id1.startswith("RASSMT-")


# =====================================================================
# Domain → Payload Conversion Tests
# =====================================================================

class TestDomainToPayload:
    def _make_learning_record(self, lr_id: str, planner_id: str, rationale: str, skill_priority_delta: dict | None = None):
        fb = PlannerFeedback(
            planner_id=planner_id,
            confidence_adjustment=-0.1,
            planner_profile_hint="default",
            skill_priority_delta=skill_priority_delta or {},
            planner_recommendation=PlannerRecommendation.DECREASE_PRIORITY,
            rationale=rationale,
        )
        return LearningRecordBuilder.build(
            planner_feedback=fb,
            assessment_hash="HASH1234",
            analytics_hash="HASH5678",
            evaluation_version="1.0",
            created_at="2026-06-26T12:00:00Z",
            source_execution_ids=["SKE-001"],
            source_artifact_ids=["ART-001"],
        )

    def test_candidate_builder_produces_payloads(self):
        records = [
            self._make_learning_record("L-1", "PLN-1", "Fail 1", skill_priority_delta={"SKL-1": -0.1}),
            self._make_learning_record("L-2", "PLN-1", "Fail 2", skill_priority_delta={"SKL-1": -0.15}),
        ]
        config = ReflectionConfig(
            version="1.0",
            enabled=True,
            confidence_threshold=0.4,
            enabled_reasons=[ReflectionReason.OUTCOME_MISMATCH],
        )
        candidates = ReflectionCandidateBuilder.build_candidates(records, config, "2026-06-26T12:00:00Z")
        payloads = ReflectionCandidateBuilder.build_payloads(candidates, "2026-06-26T12:00:00Z")

        assert len(payloads) == 1
        assert payloads[0].schema_version == "1.0"
        assert payloads[0].candidate_id.startswith("RCAND-")
        assert payloads[0].reason == "OUTCOME_MISMATCH"

    def test_assessment_to_payload(self):
        from rationalevault.skill_platform.reflection_engine import ReflectionAssessment
        assessment = ReflectionAssessment(
            candidate_id="RCAND-TEST",
            approved=True,
            confidence=0.75,
            base_confidence=0.5,
            recurrence_score=0.3,
            contradiction_penalty=0.0,
            duplicate_suppressed=False,
            reasons_for_decision=["MinConfidenceRule: PASSED - Score 0.75 >= 0.4"],
            supporting_record_ids=["LEARN-001", "LEARN-002"],
            passed_rules=["MinConfidenceRule"],
            failed_rules=[],
            triggered_rules=["MinConfidenceRule"],
            rule_scores={"MinConfidenceRule": 0.75},
        )
        payload = assessment.to_payload("2026-06-26T12:00:00Z")
        assert payload.schema_version == "1.0"
        assert payload.assessment_id.startswith("RASSMT-")
        assert payload.approved is True
        assert len(payload.rules_evaluated) == 1
        assert payload.rules_evaluated[0].rule_name == "MinConfidenceRule"
        assert payload.rules_evaluated[0].passed is True

    def test_compiler_produces_generated_payload(self):
        from rationalevault.skill_platform.reflection_models import Reflection, ReflectionStatus
        reflection = Reflection(
            reflection_id="REFL-TEST",
            candidate_id="RCAND-TEST",
            status=ReflectionStatus.COMPLETED,
            insights=["Test insight"],
            reconstructed_rationale="Test rationale",
            actionable_guidelines=["Test guideline"],
            created_at="2026-06-26T12:00:00Z",
        )
        payload = ReflectionCompiler.compile_generated_payload(
            reflection, ["LEARN-001", "LEARN-002"], "2026-06-26T12:00:00Z"
        )
        assert payload.schema_version == "1.0"
        assert payload.reflection_id == "REFL-TEST"
        assert payload.status == "COMPLETED"
        assert len(payload.source_learning_record_ids) == 2

    def test_compiler_produces_traced_payload(self):
        from rationalevault.skill_platform.reflection_engine import ReflectionAssessment
        assessment = ReflectionAssessment(
            candidate_id="RCAND-TEST",
            approved=True,
            confidence=0.75,
            base_confidence=0.5,
            recurrence_score=0.3,
            contradiction_penalty=0.0,
            duplicate_suppressed=False,
            reasons_for_decision=["MinConfidenceRule: PASSED - Score 0.75 >= 0.4"],
            supporting_record_ids=["LEARN-001"],
            passed_rules=["MinConfidenceRule"],
            failed_rules=[],
            triggered_rules=["MinConfidenceRule"],
            rule_scores={"MinConfidenceRule": 0.75},
        )
        candidate = ReflectionCandidate(
            candidate_id="RCAND-TEST",
            source_artifact_id="ART-TEST",
            reason=ReflectionReason.OUTCOME_MISMATCH,
            context={"target": "SKL-1", "supporting_record_ids": ["LEARN-001"], "conflicting_record_ids": []},
            created_at="2026-06-26T12:00:00Z",
            config_version="1.0",
        )
        payload = ReflectionCompiler.compile_traced_payload(
            assessment, "REFL-TEST", candidate, "2026-06-26T12:00:00Z"
        )
        assert payload.schema_version == "1.0"
        assert payload.trace_id.startswith("RTRC-")
        assert payload.approved is True
        assert len(payload.rules_fired) == 1
        assert len(payload.contributing_learning_records) == 1


# =====================================================================
# ReflectionStateProjection Integration Tests
# =====================================================================

class TestReflectionEventBundle:
    def _make_learning_record(self, lr_id: str, planner_id: str, rationale: str, skill_priority_delta: dict | None = None):
        fb = PlannerFeedback(
            planner_id=planner_id,
            confidence_adjustment=-0.1,
            planner_profile_hint="default",
            skill_priority_delta=skill_priority_delta or {},
            planner_recommendation=PlannerRecommendation.DECREASE_PRIORITY,
            rationale=rationale,
        )
        return LearningRecordBuilder.build(
            planner_feedback=fb,
            assessment_hash="HASH1234",
            analytics_hash="HASH5678",
            evaluation_version="1.0",
            created_at="2026-06-26T12:00:00Z",
            source_execution_ids=["SKE-001"],
            source_artifact_ids=["ART-001"],
        )

    def test_projection_produces_bundle(self):
        """Verify ReflectionStateProjection produces both report and event bundle."""
        meta = {"actor": "test", "source": "test"}
        from rationalevault.schema.events import EventRecord, EventType
        events = []
        learning_records = [
            self._make_learning_record("L-1", "PLN-1", "Fail 1", skill_priority_delta={"SKL-1": -0.1}),
            self._make_learning_record("L-2", "PLN-1", "Fail 2", skill_priority_delta={"SKL-1": -0.15}),
        ]
        config = ReflectionConfig(
            version="1.0",
            enabled=True,
            confidence_threshold=0.4,
            enabled_reasons=[ReflectionReason.OUTCOME_MISMATCH],
        )
        report, bundle = ReflectionStateProjection.project(
            events, learning_records, config, "2026-06-26T12:00:00Z"
        )

        # Report is correct
        assert report.report_id.startswith("RREP-")
        assert len(report.reflections) == 1

        # Bundle contains all four event types
        assert len(bundle.candidate_created) == 1
        assert len(bundle.assessed) == 1
        assert len(bundle.generated) == 1
        assert len(bundle.traced) == 1

        # All payloads have correct schema version
        for p in bundle.candidate_created:
            assert p.schema_version == "1.0"
        for p in bundle.assessed:
            assert p.schema_version == "1.0"
        for p in bundle.generated:
            assert p.schema_version == "1.0"
        for p in bundle.traced:
            assert p.schema_version == "1.0"

        # Bundle is serializable
        bundle_dict = bundle.to_dict()
        assert "candidate_created" in bundle_dict
        assert "assessed" in bundle_dict
        assert "generated" in bundle_dict
        assert "traced" in bundle_dict
