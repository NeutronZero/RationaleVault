"""
End-to-end integration tests for the complete Program F cognitive loop.

Exercises the full flow:
    Reflection → Promotion → Knowledge Materialization → Validation → Evolution

These tests verify that the entire cognitive loop works as an integrated system,
not just as individual modules.
"""
from __future__ import annotations

import pytest

from rationalevault.skill_platform.reflection_models import (
    ReflectionCandidate,
    ReflectionStatus,
)
from rationalevault.skill_platform.reflection_events import (
    ReflectionCandidateCreatedPayload,
    ReflectionAssessedPayload,
    ReflectionGeneratedPayload,
    ReflectionTracedPayload,
)
from rationalevault.knowledge.promotion_models import (
    PromotionCandidate,
    PromotionType,
    PromotionDecisionType,
    PromotionGatePolicy,
)
from rationalevault.knowledge.promotion_pipeline import PromotionPipeline
from rationalevault.knowledge.promotion_materializer import KnowledgeMaterializer
from rationalevault.knowledge.models import (
    KnowledgeType,
    KnowledgeDomain,
    KnowledgeTransferability,
    KnowledgeObject,
    KnowledgeConfidence,
    ProvenanceChain,
    EpistemicStatus,
)
from rationalevault.knowledge.validation import (
    KnowledgeValidator,
    EvidenceItem,
    ValidationStatus,
)
from rationalevault.knowledge.planner import (
    PlannerPolicy,
    PlannerAdjustment,
    PlannerAdjustmentProjection,
    AdjustmentType,
    AdjustmentStatus,
)
from rationalevault.knowledge.memory_lifecycle import (
    MemoryEvidence,
    MemoryPromotionPolicy,
    MemoryTransition,
    MemoryState,
    TransitionType,
)
from rationalevault.knowledge.scheduler import (
    CognitiveJob,
    JobQueue,
    ExecutionRecord,
    ExecutionHistory,
    SchedulerMetrics,
    JobType,
    ExecutionOutcome,
)
from rationalevault.knowledge.system_lineage import (
    LineageNode,
    LineageEdge,
    SystemLineageProjection,
    EdgeType,
    NodeSubsystem,
)


# =====================================================================
# Full Cognitive Loop Integration
# =====================================================================

class TestFullCognitiveLoop:
    """
    Integration test: Reflection → Promotion → Materialization → Validation.
    """

    def test_reflection_to_knowledge_lifecycle(self):
        """
        Complete lifecycle: reflection produces a promotion candidate,
        which becomes knowledge, which is then validated.
        """
        # Step 1: Create a PromotionCandidate (simulating reflection output)
        candidate = PromotionCandidate(
            candidate_id="PROMO-LOOP-001",
            source_reflection_ids=["REFL-001", "REFL-002"],
            promotion_type=PromotionType.LESSON_TO_INVARIANT,
            knowledge_type=KnowledgeType.LESSON,
            knowledge_domain=KnowledgeDomain.PROCESS,
            title="Always validate inputs",
            content="Input validation prevents downstream failures in cognitive pipelines",
            confidence=0.85,
            supporting_evidence=["LEARN-001", "LEARN-002", "LEARN-003"],
            contradicting_evidence=[],
            created_at="2026-06-26T12:00:00Z",
        )

        # Step 2: Run the promotion pipeline
        policy = PromotionGatePolicy(min_confidence=0.6, min_supporting_evidence=2)
        report = PromotionPipeline.run(candidate, policy, "2026-06-26T12:01:00Z")

        assert report.gate_result.decision == PromotionDecisionType.APPROVE
        assert report.knowledge_candidate is not None

        # Step 3: Materialize into KnowledgeObject
        knowledge = KnowledgeMaterializer.materialize(
            report.knowledge_candidate, report.decision, "project-1"
        )

        assert len(knowledge.id) == 64  # Full SHA-256 hash
        assert knowledge.knowledge_type == KnowledgeType.LESSON
        assert knowledge.epistemic_status in (EpistemicStatus.VALIDATED, EpistemicStatus.PROPOSED)

        # Step 4: Validate the knowledge against new evidence
        evidence = [
            EvidenceItem("LEARN-100", "Input validation is critical for reliability", "learning_record", 0.9, "supporting", "2026-06-26T13:00:00Z"),
            EvidenceItem("LEARN-101", "Input validation adds overhead", "learning_record", 0.6, "supporting", "2026-06-26T13:00:01Z"),
            EvidenceItem("LEARN-102", "Input validation is slow", "learning_record", 0.5, "contradicting", "2026-06-26T13:00:02Z"),
        ]
        val_report, evolution = KnowledgeValidator.validate(knowledge, evidence, "2026-06-26T14:00:00Z")

        # Should be EVOLVED (2 supporting > 1 contradicting)
        assert val_report.validation_status == ValidationStatus.EVOLVED
        assert evolution is not None
        assert evolution.source_knowledge_id == knowledge.id

    def test_rejection_does_not_produce_knowledge(self):
        """Rejected candidates should not produce knowledge."""
        candidate = PromotionCandidate(
            candidate_id="PROMO-REJECT-001",
            source_reflection_ids=["REFL-001"],
            promotion_type=PromotionType.LESSON_TO_INVARIANT,
            knowledge_type=KnowledgeType.LESSON,
            knowledge_domain=KnowledgeDomain.PROCESS,
            title="Weak claim",
            content="Barely any evidence",
            confidence=0.3,
            supporting_evidence=["LEARN-001"],
            contradicting_evidence=[],
            created_at="2026-06-26T12:00:00Z",
        )

        policy = PromotionGatePolicy(min_confidence=0.6, min_supporting_evidence=2)
        report = PromotionPipeline.run(candidate, policy, "2026-06-26T12:01:00Z")

        assert report.gate_result.decision == PromotionDecisionType.REJECT
        assert report.knowledge_candidate is None

    def test_evolution_candidate_re_enters_pipeline(self):
        """
        Knowledge validation produces evolution candidate,
        which re-enters the promotion pipeline.
        """
        # Original knowledge
        knowledge = KnowledgeObject(
            id="KNOW-EVOL-001", version=1,
            title="Type hints optional",
            content="Type hints are optional in Python",
            knowledge_type=KnowledgeType.LESSON,
            knowledge_domain=KnowledgeDomain.PROCESS,
            confidence=KnowledgeConfidence(3, 2, 0, 0.7, 0.75),
            importance="medium",
            provenance=ProvenanceChain(
                knowledge_id="KNOW-EVOL-001",
                source_memory_ids=["LEARN-001"],
                source_event_ids=["REFL-001"],
                synthesis_event_id="PD-001",
                confidence=KnowledgeConfidence(3, 2, 0, 0.7, 0.75),
                evidence_count=3,
            ),
        )

        # New evidence: two supporting, one contradicting → EVOLVED
        evidence = [
            EvidenceItem("LEARN-200", "Type hints are essential for large codebases", "learning_record", 0.9, "contradicting", "2026-06-26T13:00:00Z"),
            EvidenceItem("LEARN-201", "Type hints are helpful for small scripts too", "learning_record", 0.7, "supporting", "2026-06-26T13:00:01Z"),
            EvidenceItem("LEARN-202", "Type hints catch errors at compile time", "learning_record", 0.8, "supporting", "2026-06-26T13:00:02Z"),
        ]
        val_report, evolution = KnowledgeValidator.validate(knowledge, evidence, "2026-06-26T14:00:00Z")

        assert val_report.validation_status == ValidationStatus.EVOLVED
        assert evolution is not None

        # Evolution candidate re-enters promotion pipeline
        new_candidate = PromotionCandidate(
            candidate_id=evolution.candidate_id,
            source_reflection_ids=["REFL-001"],
            promotion_type=evolution.promotion_type,
            knowledge_type=evolution.knowledge_type,
            knowledge_domain=evolution.knowledge_domain,
            title=evolution.title,
            content=evolution.content,
            confidence=evolution.confidence,
            supporting_evidence=evolution.supporting_evidence,
            contradicting_evidence=evolution.contradicting_evidence,
            created_at=evolution.created_at,
        )

        policy = PromotionGatePolicy(min_confidence=0.3, min_supporting_evidence=1, require_no_contradictions=False, max_contradicting_evidence=5)
        new_report = PromotionPipeline.run(new_candidate, policy, "2026-06-26T15:00:00Z")

        # The evolved knowledge should pass with updated confidence
        assert new_report.gate_result.decision == PromotionDecisionType.APPROVE
        assert new_report.knowledge_candidate is not None


# =====================================================================
# Cross-Subsystem Integration
# =====================================================================

class TestCrossSubsystemIntegration:
    """
    Integration tests spanning multiple Program F subsystems.
    """

    def test_planner_consumes_projection(self):
        """PlannerAdjustmentProjection can be consumed by the planner."""
        policy = PlannerPolicy(
            policy_id="PPOL-001", version=1,
            config={"min_confidence": 0.6, "max_evidence": 10},
            description="Initial policy", superseded_by=None,
            created_at="2026-06-26T12:00:00Z",
        )
        adj = PlannerAdjustment(
            adjustment_id="PADJ-001",
            adjustment_type=AdjustmentType.THRESHOLD_UPDATE,
            source_policy_id=None,
            target_policy_id="PPOL-001",
            rationale="Initial setup",
            status=AdjustmentStatus.ACCEPTED,
            created_at="2026-06-26T12:00:00Z",
        )
        projection = PlannerAdjustmentProjection(
            policies=[policy], adjustments=[adj],
            active_policy_id="PPOL-001", version=1,
        )

        # Verify the projection is serializable (simulates planner consumption)
        d = projection.to_dict()
        restored = PlannerAdjustmentProjection.from_dict(d)
        assert restored.active_policy_id == "PPOL-001"
        assert len(restored.policies) == 1

    def test_memory_evidence_driven_promotion(self):
        """Memory promotion is driven by evidence metrics."""
        evidence = MemoryEvidence(
            memory_id="MEM-001", reference_count=5,
            reference_velocity=0.3, reflection_count=2,
            promotion_count=0, last_referenced_at="2026-06-26T12:00:00Z",
            created_at="2026-06-20T12:00:00Z",
        )
        policy = MemoryPromotionPolicy()

        # Check eligibility
        eligible = (
            evidence.reference_count >= policy.min_reference_count
            and evidence.reference_velocity >= policy.min_reference_velocity
            and evidence.reflection_count >= policy.min_reflection_count
            and evidence.promotion_count < policy.max_promotion_count
        )
        assert eligible is True

    def test_scheduler_job_execution_history(self):
        """Scheduler creates jobs, executes them, records history."""
        job = CognitiveJob(
            job_id="CJOB-001", job_type=JobType.KNOWLEDGE_PROMOTION,
            priority=1, context_ids=["PROMO-001"],
            config={}, created_at="2026-06-26T12:00:00Z",
        )
        queue = JobQueue(jobs=[job], version=1)
        assert len(queue.sorted_jobs()) == 1

        # Simulate execution
        record = ExecutionRecord(
            execution_id="CEXEC-001", job_id=job.job_id,
            outcome=ExecutionOutcome.SUCCESS, duration_ms=150,
            result_summary="Knowledge promoted",
            error_message=None, artifacts_produced=["KNOW-001"],
            created_at="2026-06-26T12:01:00Z",
        )
        history = ExecutionHistory(records=[record], version=1)
        assert len(history.records) == 1
        assert history.records[0].outcome == ExecutionOutcome.SUCCESS


# =====================================================================
# Lineage Integration
# =====================================================================

class TestLineageIntegration:
    """
    Integration tests verifying the SystemLineageProjection
    connects all Program F subsystems.
    """

    def test_full_lineage_chain(self):
        """Verify a complete lineage chain from Event to Knowledge."""
        nodes = [
            LineageNode("N1", "EVT-001", NodeSubsystem.EVENT, "Event", "2026-06-26T12:00:00Z"),
            LineageNode("N2", "BEL-001", NodeSubsystem.BELIEF, "Belief", "2026-06-26T12:00:01Z"),
            LineageNode("N3", "DEC-001", NodeSubsystem.DECISION, "Decision", "2026-06-26T12:00:02Z"),
            LineageNode("N4", "SKE-001", NodeSubsystem.EXECUTION, "Execution", "2026-06-26T12:00:03Z"),
            LineageNode("N5", "ART-001", NodeSubsystem.ARTIFACT, "Artifact", "2026-06-26T12:00:04Z"),
            LineageNode("N6", "LEARN-001", NodeSubsystem.LEARNING, "Learning", "2026-06-26T12:00:05Z"),
            LineageNode("N7", "REFL-001", NodeSubsystem.REFLECTION, "Reflection", "2026-06-26T12:00:06Z"),
            LineageNode("N8", "PROMO-001", NodeSubsystem.PROMOTION, "Promotion", "2026-06-26T12:00:07Z"),
            LineageNode("N9", "KNOW-001", NodeSubsystem.KNOWLEDGE, "Knowledge", "2026-06-26T12:00:08Z"),
            LineageNode("N10", "PPOL-001", NodeSubsystem.PLANNER, "Planner Policy", "2026-06-26T12:00:09Z"),
            LineageNode("N11", "MEM-001", NodeSubsystem.MEMORY, "Memory", "2026-06-26T12:00:10Z"),
            LineageNode("N12", "CJOB-001", NodeSubsystem.SCHEDULER, "Cognitive Job", "2026-06-26T12:00:11Z"),
        ]
        edges = [
            LineageEdge("E1", "N1", "N2", EdgeType.DERIVED_FROM, "2026-06-26T12:00:01Z"),
            LineageEdge("E2", "N2", "N3", EdgeType.DERIVED_FROM, "2026-06-26T12:00:02Z"),
            LineageEdge("E3", "N3", "N4", EdgeType.EXECUTED_FOR, "2026-06-26T12:00:03Z"),
            LineageEdge("E4", "N4", "N5", EdgeType.GENERATED_BY, "2026-06-26T12:00:04Z"),
            LineageEdge("E5", "N5", "N6", EdgeType.DERIVED_FROM, "2026-06-26T12:00:05Z"),
            LineageEdge("E6", "N6", "N7", EdgeType.REFLECTED_IN, "2026-06-26T12:00:06Z"),
            LineageEdge("E7", "N7", "N8", EdgeType.PROMOTED_FROM, "2026-06-26T12:00:07Z"),
            LineageEdge("E8", "N8", "N9", EdgeType.PROMOTED_FROM, "2026-06-26T12:00:08Z"),
            LineageEdge("E9", "N9", "N10", EdgeType.ADJUSTED_BY, "2026-06-26T12:00:09Z"),
            LineageEdge("E10", "N10", "N11", EdgeType.TRANSITIONED_VIA, "2026-06-26T12:00:10Z"),
            LineageEdge("E11", "N11", "N12", EdgeType.SCHEDULED_BY, "2026-06-26T12:00:11Z"),
        ]
        proj = SystemLineageProjection(nodes=nodes, edges=edges, version=1)

        # Knowledge can answer "Why do I exist?"
        reasons = proj.why_exists("KNOW-001")
        assert "EVT-001" in reasons
        assert "BEL-001" in reasons
        assert "DEC-001" in reasons
        assert "REFL-001" in reasons

        # Full lineage path includes all upstream objects
        path = proj.full_lineage_path("KNOW-001")
        assert path[0] == "KNOW-001"
        assert "EVT-001" in path
        assert len(path) >= 8  # At least 8 objects in the chain

    def test_knowledge_to_scheduler_lineage(self):
        """Verify lineage from Knowledge through Planner to Scheduler."""
        nodes = [
            LineageNode("N1", "KNOW-001", NodeSubsystem.KNOWLEDGE, "Knowledge", "2026-06-26T12:00:00Z"),
            LineageNode("N2", "PPOL-001", NodeSubsystem.PLANNER, "Policy", "2026-06-26T12:00:01Z"),
            LineageNode("N3", "CJOB-001", NodeSubsystem.SCHEDULER, "Job", "2026-06-26T12:00:02Z"),
            LineageNode("N4", "CEXEC-001", NodeSubsystem.SCHEDULER, "Execution", "2026-06-26T12:00:03Z"),
        ]
        edges = [
            LineageEdge("E1", "N1", "N2", EdgeType.ADJUSTED_BY, "2026-06-26T12:00:01Z"),
            LineageEdge("E2", "N2", "N3", EdgeType.SCHEDULED_BY, "2026-06-26T12:00:02Z"),
            LineageEdge("E3", "N3", "N4", EdgeType.EXECUTED_FOR, "2026-06-26T12:00:03Z"),
        ]
        proj = SystemLineageProjection(nodes=nodes, edges=edges, version=1)

        # CEXEC-001 should trace back to KNOW-001
        reasons = proj.why_exists("CEXEC-001")
        assert "KNOW-001" in reasons
        assert "PPOL-001" in reasons
        assert "CJOB-001" in reasons
