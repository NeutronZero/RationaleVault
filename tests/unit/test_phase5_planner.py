"""
Tests for RationaleVault Planner Evolution (F4).

Covers PlannerPolicy, PlannerAdjustment, PlannerAdjustmentProjection,
append-only policy semantics, and serialization.
"""
from __future__ import annotations

import pytest

from rationalevault.knowledge.planner import (
    PlannerPolicy,
    PlannerAdjustment,
    PlannerAdjustmentProjection,
    AdjustmentType,
    AdjustmentStatus,
)


# =====================================================================
# PlannerPolicy
# =====================================================================

class TestPlannerPolicy:
    def test_id_generation_deterministic(self):
        config = {"min_confidence": 0.6}
        id1 = PlannerPolicy.generate_policy_id(1, config, "2026-06-26T12:00:00Z")
        id2 = PlannerPolicy.generate_policy_id(1, config, "2026-06-26T12:00:00Z")
        assert id1 == id2
        assert id1.startswith("PPOL-")

    def test_id_varies_by_version(self):
        config = {"min_confidence": 0.6}
        id1 = PlannerPolicy.generate_policy_id(1, config, "2026-06-26T12:00:00Z")
        id2 = PlannerPolicy.generate_policy_id(2, config, "2026-06-26T12:00:00Z")
        assert id1 != id2

    def test_serialization_roundtrip(self):
        policy = PlannerPolicy(
            policy_id="PPOL-TEST",
            version=1,
            config={"min_confidence": 0.6, "max_evidence": 10},
            description="Initial policy",
            superseded_by=None,
            created_at="2026-06-26T12:00:00Z",
        )
        d = policy.to_dict()
        restored = PlannerPolicy.from_dict(d)
        assert restored.policy_id == policy.policy_id
        assert restored.version == policy.version
        assert restored.config == policy.config

    def test_frozen(self):
        policy = PlannerPolicy(
            policy_id="PPOL-TEST",
            version=1,
            config={},
            description="Test",
            superseded_by=None,
            created_at="2026-06-26T12:00:00Z",
        )
        with pytest.raises(AttributeError):
            policy.version = 2

    def test_append_only_semantics(self):
        """Policies are append-only — superseded_by points to next policy."""
        p1 = PlannerPolicy(
            policy_id="PPOL-001", version=1, config={"min_confidence": 0.6},
            description="v1", superseded_by="PPOL-002", created_at="2026-06-26T12:00:00Z",
        )
        p2 = PlannerPolicy(
            policy_id="PPOL-002", version=2, config={"min_confidence": 0.7},
            description="v2", superseded_by=None, created_at="2026-06-26T13:00:00Z",
        )
        assert p1.superseded_by == "PPOL-002"
        assert p2.superseded_by is None


# =====================================================================
# PlannerAdjustment
# =====================================================================

class TestPlannerAdjustment:
    def test_id_generation_deterministic(self):
        id1 = PlannerAdjustment.generate_adjustment_id("THRESHOLD_UPDATE", "PPOL-001", "2026-06-26T12:00:00Z")
        id2 = PlannerAdjustment.generate_adjustment_id("THRESHOLD_UPDATE", "PPOL-001", "2026-06-26T12:00:00Z")
        assert id1 == id2
        assert id1.startswith("PADJ-")

    def test_serialization_roundtrip(self):
        adj = PlannerAdjustment(
            adjustment_id="PADJ-TEST",
            adjustment_type=AdjustmentType.THRESHOLD_UPDATE,
            source_policy_id="PPOL-001",
            target_policy_id="PPOL-002",
            rationale="Increase confidence threshold",
            status=AdjustmentStatus.ACCEPTED,
            created_at="2026-06-26T12:00:00Z",
        )
        d = adj.to_dict()
        restored = PlannerAdjustment.from_dict(d)
        assert restored.adjustment_id == adj.adjustment_id
        assert restored.adjustment_type == adj.adjustment_type

    def test_frozen(self):
        adj = PlannerAdjustment(
            adjustment_id="PADJ-TEST",
            adjustment_type=AdjustmentType.STRATEGY_CHANGE,
            source_policy_id=None,
            target_policy_id=None,
            rationale="Test",
            status=AdjustmentStatus.PROPOSED,
            created_at="2026-06-26T12:00:00Z",
        )
        with pytest.raises(AttributeError):
            adj.status = AdjustmentStatus.ACCEPTED


# =====================================================================
# PlannerAdjustmentProjection
# =====================================================================

class TestPlannerAdjustmentProjection:
    def test_serialization_roundtrip(self):
        p1 = PlannerPolicy(
            policy_id="PPOL-001", version=1, config={"min_confidence": 0.6},
            description="v1", superseded_by=None, created_at="2026-06-26T12:00:00Z",
        )
        adj = PlannerAdjustment(
            adjustment_id="PADJ-001",
            adjustment_type=AdjustmentType.THRESHOLD_UPDATE,
            source_policy_id=None,
            target_policy_id="PPOL-001",
            rationale="Initial policy",
            status=AdjustmentStatus.ACCEPTED,
            created_at="2026-06-26T12:00:00Z",
        )
        proj = PlannerAdjustmentProjection(
            policies=[p1],
            adjustments=[adj],
            active_policy_id="PPOL-001",
            version=1,
        )
        d = proj.to_dict()
        restored = PlannerAdjustmentProjection.from_dict(d)
        assert len(restored.policies) == 1
        assert len(restored.adjustments) == 1
        assert restored.active_policy_id == "PPOL-001"

    def test_empty_projection(self):
        proj = PlannerAdjustmentProjection(
            policies=[],
            adjustments=[],
            active_policy_id=None,
            version=0,
        )
        d = proj.to_dict()
        restored = PlannerAdjustmentProjection.from_dict(d)
        assert len(restored.policies) == 0
        assert restored.active_policy_id is None
