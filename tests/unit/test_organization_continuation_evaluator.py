"""Tests for I14.3 — Organization Continuation Evaluator."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pytest

from rationalevault.evaluation.organization_continuation_evaluator import (
    OrganizationContinuationEvalResult,
    OrganizationContinuationEvaluator,
    check_organization_continuation_gates,
)
from rationalevault.organization.activity import (
    OrganizationActivityProjection,
    OrganizationActivityState,
    ProjectActivity,
    OrgTransferEvent,
    OrgConflictEvent,
)
from rationalevault.organization.continuation import (
    OrganizationContinuationProjection,
    OrganizationContinuationState,
)
from rationalevault.organization.graph import OrganizationGraphProjection
from rationalevault.organization.models import (
    KnowledgeLineage,
    OrganizationState,
    CrossProjectConflict,
)


@dataclass
class FakeEvent:
    recorded_at: str

@dataclass
class FakeKnowledge:
    id: str
    title: str
    created_at: str
    updated_at: str = ""
    knowledge_type: str = "principle"


def _lineage(kid, origin, current):
    return KnowledgeLineage(
        knowledge_id=kid, origin_project=origin,
        current_projects=current, transfer_path=[origin] + current, depth=len(current),
    )

def _conflict(a_id, b_id, pa, pb, conf=0.8):
    return CrossProjectConflict(
        conflict_id=f"{pa}_{pb}", knowledge_a_id=a_id, knowledge_b_id=b_id,
        project_a=pa, project_b=pb, knowledge_a_title="A", knowledge_b_title="B",
        confidence=conf, reasons=["lexical_similarity"],
    )


class TestEvalResult:
    def test_passes_exit_gate(self) -> None:
        r = OrganizationContinuationEvalResult(
            activity_coverage=1.0, transfer_detection=1.0, conflict_detection=1.0,
            attention_accuracy=1.0, determinism=1.0, next_actions_relevance=1.0,
            activity_replayability=1.0,
        )
        passed, failures = r.passes_exit_gate()
        assert passed
        assert failures == []

    def test_fails_on_low_metric(self) -> None:
        r = OrganizationContinuationEvalResult(activity_coverage=0.1)
        passed, failures = r.passes_exit_gate()
        assert not passed
        assert "activity_coverage" in failures

    def test_to_dict(self) -> None:
        r = OrganizationContinuationEvalResult(
            activity_coverage=1.0, transfer_detection=1.0, conflict_detection=1.0,
            attention_accuracy=1.0, determinism=1.0, next_actions_relevance=1.0,
            activity_replayability=1.0,
        )
        d = r.to_dict()
        assert "org_continuation_success_rate" in d
        assert d["passed"] is True


class TestEvaluatorActivityCoverage:
    def test_half_active(self) -> None:
        org = OrganizationState(compiled_at="2025-01-01", project_ids=["a", "b"])
        activity = OrganizationActivityProjection.project(
            project_ids=["a", "b"],
            recent_events_by_project={"a": [FakeEvent(recorded_at="2025-01-01T12:00:00")]},
            recent_knowledge_by_project={},
            recent_memories_by_project={},
            org_state=org,
        )
        graph = OrganizationGraphProjection.project(org)
        cont = OrganizationContinuationProjection.project(org, graph, activity)
        eval_ = OrganizationContinuationEvaluator()
        result = eval_.evaluate(org, graph, activity, cont)
        assert result.activity_coverage == 0.5


class TestEvaluatorTransferDetection:
    def test_transfer_detected(self) -> None:
        org = OrganizationState(
            compiled_at="2025-01-01", project_ids=["a", "b"],
            active_lineages={"k1": _lineage("k1", "a", ["b"])},
        )
        activity = OrganizationActivityProjection.project(
            project_ids=["a", "b"],
            recent_events_by_project={},
            recent_knowledge_by_project={
                "b": [FakeKnowledge(id="k1", title="K1", created_at="2025-01-01T12:00:00")],
            },
            recent_memories_by_project={},
            org_state=org,
        )
        graph = OrganizationGraphProjection.project(org)
        cont = OrganizationContinuationProjection.project(org, graph, activity)
        eval_ = OrganizationContinuationEvaluator()
        result = eval_.evaluate(org, graph, activity, cont)
        assert result.transfer_detection >= 0.8


class TestEvaluatorConflictDetection:
    def test_conflict_detected(self) -> None:
        org = OrganizationState(
            compiled_at="2025-01-01", project_ids=["a", "b"],
            cross_project_conflicts=[_conflict("k1", "k2", "a", "b")],
        )
        activity = OrganizationActivityProjection.project(
            project_ids=["a", "b"],
            recent_events_by_project={},
            recent_knowledge_by_project={
                "a": [FakeKnowledge(id="k1", title="K1", created_at="2025-01-01T12:00:00")],
            },
            recent_memories_by_project={},
            org_state=org,
        )
        graph = OrganizationGraphProjection.project(org)
        cont = OrganizationContinuationProjection.project(org, graph, activity)
        eval_ = OrganizationContinuationEvaluator()
        result = eval_.evaluate(org, graph, activity, cont)
        assert result.conflict_detection >= 0.8


class TestEvaluatorAttentionAccuracy:
    def test_attention_accurate(self) -> None:
        org = OrganizationState(
            compiled_at="2025-01-01", project_ids=["a", "b"],
            cross_project_conflicts=[_conflict("k1", "k2", "a", "b")],
        )
        activity = OrganizationActivityProjection.project(
            project_ids=["a", "b"],
            recent_events_by_project={
                "a": [FakeEvent(recorded_at="2025-01-01T12:00:00")],
            },
            recent_knowledge_by_project={},
            recent_memories_by_project={},
            org_state=org,
        )
        graph = OrganizationGraphProjection.project(org)
        cont = OrganizationContinuationProjection.project(org, graph, activity)
        eval_ = OrganizationContinuationEvaluator()
        result = eval_.evaluate(org, graph, activity, cont)
        assert result.attention_accuracy >= 0.7


class TestEvaluatorNextActionsRelevance:
    def test_actions_relevant(self) -> None:
        org = OrganizationState(
            compiled_at="2025-01-01", project_ids=["a", "b"],
            cross_project_conflicts=[_conflict("k1", "k2", "a", "b")],
        )
        activity = OrganizationActivityProjection.project(
            project_ids=["a", "b"],
            recent_events_by_project={
                "a": [FakeEvent(recorded_at="2025-01-01T12:00:00")],
            },
            recent_knowledge_by_project={},
            recent_memories_by_project={},
            org_state=org,
        )
        graph = OrganizationGraphProjection.project(org)
        cont = OrganizationContinuationProjection.project(org, graph, activity)
        eval_ = OrganizationContinuationEvaluator()
        result = eval_.evaluate(org, graph, activity, cont)
        assert result.next_actions_relevance >= 0.7


class TestCheckGates:
    def test_all_pass(self) -> None:
        r = OrganizationContinuationEvalResult(
            activity_coverage=1.0, transfer_detection=1.0, conflict_detection=1.0,
            attention_accuracy=1.0, determinism=1.0, next_actions_relevance=1.0,
            activity_replayability=1.0,
        )
        passed, failures = check_organization_continuation_gates(r)
        assert passed

    def test_one_failure(self) -> None:
        r = OrganizationContinuationEvalResult(activity_coverage=0.1)
        passed, failures = check_organization_continuation_gates(r)
        assert not passed
