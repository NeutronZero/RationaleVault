"""
Tests for RationaleVault Memory Lifecycle (F5).

Covers MemoryEvidence, MemoryPromotionPolicy, MemoryTransition,
MemoryPromotionReport, and serialization roundtrips.
"""
from __future__ import annotations

import pytest

from rationalevault.knowledge.memory_lifecycle import (
    MemoryEvidence,
    MemoryPromotionPolicy,
    MemoryTransition,
    MemoryPromotionReport,
    MemoryState,
    TransitionType,
)


# =====================================================================
# MemoryEvidence
# =====================================================================

class TestMemoryEvidence:
    def test_serialization_roundtrip(self):
        evidence = MemoryEvidence(
            memory_id="MEM-001",
            reference_count=5,
            reference_velocity=0.3,
            reflection_count=2,
            promotion_count=1,
            last_referenced_at="2026-06-26T12:00:00Z",
            created_at="2026-06-20T12:00:00Z",
        )
        d = evidence.to_dict()
        restored = MemoryEvidence.from_dict(d)
        assert restored.memory_id == evidence.memory_id
        assert restored.reference_count == evidence.reference_count
        assert restored.reference_velocity == evidence.reference_velocity

    def test_frozen(self):
        evidence = MemoryEvidence(
            memory_id="MEM-001",
            reference_count=5,
            reference_velocity=0.3,
            reflection_count=2,
            promotion_count=1,
            last_referenced_at=None,
            created_at="2026-06-20T12:00:00Z",
        )
        with pytest.raises(AttributeError):
            evidence.reference_count = 10


# =====================================================================
# MemoryPromotionPolicy
# =====================================================================

class TestMemoryPromotionPolicy:
    def test_default_values(self):
        policy = MemoryPromotionPolicy()
        assert policy.min_reference_count == 3
        assert policy.min_reference_velocity == 0.1
        assert policy.min_reflection_count == 1
        assert policy.max_promotion_count == 5
        assert policy.require_reflection is True

    def test_serialization_roundtrip(self):
        policy = MemoryPromotionPolicy(
            version="2.0",
            min_reference_count=5,
            min_reference_velocity=0.2,
            min_reflection_count=2,
            max_promotion_count=3,
            require_reflection=False,
        )
        d = policy.to_dict()
        restored = MemoryPromotionPolicy.from_dict(d)
        assert restored.version == "2.0"
        assert restored.min_reference_count == 5
        assert restored.require_reflection is False


# =====================================================================
# MemoryTransition
# =====================================================================

class TestMemoryTransition:
    def test_id_generation_deterministic(self):
        evidence = MemoryEvidence(
            memory_id="MEM-001", reference_count=5, reference_velocity=0.3,
            reflection_count=2, promotion_count=0, last_referenced_at=None, created_at="2026-06-20T12:00:00Z",
        )
        id1 = MemoryTransition.generate_transition_id("MEM-001", "CANDIDATE", "ACTIVE", "2026-06-26T12:00:00Z")
        id2 = MemoryTransition.generate_transition_id("MEM-001", "CANDIDATE", "ACTIVE", "2026-06-26T12:00:00Z")
        assert id1 == id2
        assert id1.startswith("MTRANS-")

    def test_serialization_roundtrip(self):
        evidence = MemoryEvidence(
            memory_id="MEM-001", reference_count=5, reference_velocity=0.3,
            reflection_count=2, promotion_count=0, last_referenced_at=None, created_at="2026-06-20T12:00:00Z",
        )
        transition = MemoryTransition(
            transition_id="MTRANS-TEST",
            memory_id="MEM-001",
            from_state=MemoryState.CANDIDATE,
            to_state=MemoryState.ACTIVE,
            transition_type=TransitionType.ACTIVATED,
            rationale="Met activation thresholds",
            evidence=evidence,
            created_at="2026-06-26T12:00:00Z",
        )
        d = transition.to_dict()
        restored = MemoryTransition.from_dict(d)
        assert restored.transition_id == transition.transition_id
        assert restored.from_state == transition.from_state
        assert restored.to_state == transition.to_state

    def test_frozen(self):
        evidence = MemoryEvidence(
            memory_id="MEM-001", reference_count=5, reference_velocity=0.3,
            reflection_count=2, promotion_count=0, last_referenced_at=None, created_at="2026-06-20T12:00:00Z",
        )
        transition = MemoryTransition(
            transition_id="MTRANS-TEST",
            memory_id="MEM-001",
            from_state=MemoryState.CANDIDATE,
            to_state=MemoryState.ACTIVE,
            transition_type=TransitionType.ACTIVATED,
            rationale="Test",
            evidence=evidence,
            created_at="2026-06-26T12:00:00Z",
        )
        with pytest.raises(AttributeError):
            transition.rationale = "Modified"


# =====================================================================
# MemoryPromotionReport
# =====================================================================

class TestMemoryPromotionReport:
    def test_serialization_roundtrip(self):
        evidence = MemoryEvidence(
            memory_id="MEM-001", reference_count=5, reference_velocity=0.3,
            reflection_count=2, promotion_count=0, last_referenced_at=None, created_at="2026-06-20T12:00:00Z",
        )
        transition = MemoryTransition(
            transition_id="MTRANS-TEST",
            memory_id="MEM-001",
            from_state=MemoryState.CANDIDATE,
            to_state=MemoryState.ACTIVE,
            transition_type=TransitionType.ACTIVATED,
            rationale="Met thresholds",
            evidence=evidence,
            created_at="2026-06-26T12:00:00Z",
        )
        report = MemoryPromotionReport(
            report_id="MREP-TEST",
            memory_id="MEM-001",
            current_state=MemoryState.CANDIDATE,
            proposed_state=MemoryState.ACTIVE,
            eligible=True,
            evidence=evidence,
            transition=transition,
            findings=["Memory meets activation criteria"],
            warnings=[],
            created_at="2026-06-26T12:00:00Z",
        )
        d = report.to_dict()
        restored = MemoryPromotionReport.from_dict(d)
        assert restored.report_id == report.report_id
        assert restored.eligible is True
        assert restored.transition is not None

    def test_report_without_transition(self):
        """Rejection reports have no transition."""
        evidence = MemoryEvidence(
            memory_id="MEM-001", reference_count=1, reference_velocity=0.01,
            reflection_count=0, promotion_count=0, last_referenced_at=None, created_at="2026-06-20T12:00:00Z",
        )
        report = MemoryPromotionReport(
            report_id="MREP-TEST",
            memory_id="MEM-001",
            current_state=MemoryState.CANDIDATE,
            proposed_state=MemoryState.ACTIVE,
            eligible=False,
            evidence=evidence,
            transition=None,
            findings=["Insufficient evidence"],
            warnings=["Low reference count"],
            created_at="2026-06-26T12:00:00Z",
        )
        d = report.to_dict()
        restored = MemoryPromotionReport.from_dict(d)
        assert restored.eligible is False
        assert restored.transition is None
