"""Unit tests for RecommendationProjection, rules, runtime, and state.

Tests the recommendation package independently of the conformance suite.
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from rationalevault.projection_platform.models import ProjectionHealth
from rationalevault.recommendation.projection import RecommendationProjection
from rationalevault.recommendation.runtime import RecommendationRuntime
from rationalevault.recommendation.rules import (
    DecisionReviewRule,
    KnowledgeDeletionRiskRule,
    KnowledgeGapRule,
    QuestionResolutionRule,
    RecommendationRuleRegistry,
    TaskFollowUpRule,
    create_default_registry,
)
from rationalevault.recommendation.state import (
    EvidenceReference,
    Recommendation,
    RecommendationCategory,
    RecommendationQueryContext,
    RecommendationRuleMetadata,
    RecommendationState,
    RankedRecommendation,
)
from rationalevault.schema.events import EventMetadata, EventRecord, EventType


# ── Helpers ──────────────────────────────────────────────────────────────────


def _event(
    event_type: EventType,
    payload: dict,
    seq: int = 1,
    project_id=None,
) -> EventRecord:
    return EventRecord(
        event_sequence=seq,
        id=uuid4(),
        project_id=project_id or uuid4(),
        stream_id="main",
        version=seq,
        event_type=event_type,
        metadata=EventMetadata(actor="test", source="test"),
        payload=payload,
        parent_id=None,
        recorded_at=None,
    )


# ── RecommendationCategory Tests ────────────────────────────────────────────


class TestRecommendationCategory:
    def test_all_values(self):
        categories = list(RecommendationCategory)
        assert len(categories) == 5
        assert RecommendationCategory.NEXT_ACTION.value == "next_action"
        assert RecommendationCategory.KNOWLEDGE_GAP.value == "knowledge_gap"
        assert RecommendationCategory.RISK.value == "risk"
        assert RecommendationCategory.OPTIMIZATION.value == "optimization"
        assert RecommendationCategory.FOLLOW_UP.value == "follow_up"


# ── EvidenceReference Tests ─────────────────────────────────────────────────


class TestEvidenceReference:
    def test_creation(self):
        e = EvidenceReference(sequence=10, reason="triggering_event")
        assert e.sequence == 10
        assert e.reason == "triggering_event"

    def test_default_reason(self):
        e = EvidenceReference(sequence=10)
        assert e.reason is None


# ── RecommendationRuleMetadata Tests ─────────────────────────────────────────


class TestRecommendationRuleMetadata:
    def test_creation(self):
        m = RecommendationRuleMetadata(
            id="test_rule",
            version=1,
            category=RecommendationCategory.RISK,
            description="A test rule",
        )
        assert m.id == "test_rule"
        assert m.version == 1
        assert m.category == RecommendationCategory.RISK


# ── Recommendation Tests ────────────────────────────────────────────────────


class TestRecommendation:
    def test_make_id_deterministic(self):
        id1 = Recommendation.make_id(1, "rule_v1", 1, "t1", 10)
        id2 = Recommendation.make_id(1, "rule_v1", 1, "t1", 10)
        assert id1 == id2
        assert len(id1) == 16

    def test_make_id_different_inputs(self):
        id1 = Recommendation.make_id(1, "rule_v1", 1, "t1", 10)
        id2 = Recommendation.make_id(1, "rule_v1", 1, "t2", 10)
        id3 = Recommendation.make_id(1, "rule_v2", 1, "t1", 10)
        id4 = Recommendation.make_id(2, "rule_v1", 1, "t1", 10)
        id5 = Recommendation.make_id(1, "rule_v1", 2, "t1", 10)
        assert len({id1, id2, id3, id4, id5}) == 5


# ── RankedRecommendation Tests ──────────────────────────────────────────────


class TestRankedRecommendation:
    def test_creation(self):
        rec = Recommendation(
            id="r1", rule_id="rule1", rule_version=1,
            target_entity="t1",
            category=RecommendationCategory.RISK,
            priority=0.5, rationale="test",
        )
        ranked = RankedRecommendation(
            recommendation=rec,
            final_score=0.7,
            semantic_similarity=0.9,
            knowledge_context={"key": "value"},
        )
        assert ranked.recommendation is rec
        assert ranked.final_score == 0.7
        assert ranked.semantic_similarity == 0.9
        assert ranked.knowledge_context == {"key": "value"}

    def test_defaults(self):
        rec = Recommendation(
            id="r1", rule_id="rule1", rule_version=1,
            target_entity="t1",
            category=RecommendationCategory.RISK,
            priority=0.5, rationale="test",
        )
        ranked = RankedRecommendation(
            recommendation=rec,
            final_score=0.5,
        )
        assert ranked.semantic_similarity == 1.0
        assert ranked.knowledge_context is None


# ── RecommendationQueryContext Tests ─────────────────────────────────────────


class TestRecommendationQueryContext:
    def test_creation(self):
        ctx = RecommendationQueryContext(
            query_time=datetime(2026, 1, 1),
            query="test",
            entity="t1",
            category=RecommendationCategory.RISK,
        )
        assert ctx.query == "test"
        assert ctx.entity == "t1"

    def test_defaults(self):
        ctx = RecommendationQueryContext(
            query_time=datetime(2026, 1, 1),
        )
        assert ctx.query is None
        assert ctx.entity is None
        assert ctx.category is None


# ── RecommendationState Tests ────────────────────────────────────────────────


class TestRecommendationState:
    def test_empty_state(self):
        state = RecommendationState()
        assert state.recommendations == []
        assert state.sequence == 0
        assert state.recommendation_count == 0
        assert state.categories == set()

    def test_properties(self):
        state = RecommendationState(
            recommendations=[
                Recommendation(
                    id="r1", rule_id="rule1", rule_version=1,
                    target_entity="t1",
                    category=RecommendationCategory.RISK,
                    priority=0.5, rationale="test",
                ),
                Recommendation(
                    id="r2", rule_id="rule2", rule_version=1,
                    target_entity="t2",
                    category=RecommendationCategory.FOLLOW_UP,
                    priority=0.7, rationale="test",
                ),
            ],
            sequence=10,
        )
        assert state.recommendation_count == 2
        assert state.categories == {
            RecommendationCategory.RISK,
            RecommendationCategory.FOLLOW_UP,
        }


# ── Rule Tests ───────────────────────────────────────────────────────────────


class TestKnowledgeGapRule:
    def test_metadata(self):
        rule = KnowledgeGapRule()
        m = rule.metadata
        assert m.id == "knowledge_gap_rule"
        assert m.version == 1
        assert m.category == RecommendationCategory.KNOWLEDGE_GAP

    def test_triggers_on_created_without_related_to(self):
        rule = KnowledgeGapRule()
        event = _event(EventType.KNOWLEDGE_CREATED, {
            "knowledge_id": "k1",
            "title": "Test",
        })
        rec = rule.apply(event, 1)
        assert rec is not None
        assert rec.rule_id == "knowledge_gap_rule"
        assert rec.rule_version == 1
        assert rec.category == RecommendationCategory.KNOWLEDGE_GAP
        assert rec.target_entity == "k1"
        assert len(rec.evidence) == 1
        assert rec.evidence[0].sequence == 1

    def test_no_trigger_with_related_to(self):
        rule = KnowledgeGapRule()
        event = _event(EventType.KNOWLEDGE_CREATED, {
            "knowledge_id": "k1",
            "title": "Test",
            "related_to": "k0",
        })
        rec = rule.apply(event, 1)
        assert rec is None

    def test_no_trigger_on_other_event_type(self):
        rule = KnowledgeGapRule()
        event = _event(EventType.TASK_COMPLETED, {"task_id": "t1"})
        rec = rule.apply(event, 1)
        assert rec is None


class TestTaskFollowUpRule:
    def test_metadata(self):
        rule = TaskFollowUpRule()
        m = rule.metadata
        assert m.id == "task_follow_up_rule"
        assert m.version == 1
        assert m.category == RecommendationCategory.FOLLOW_UP

    def test_triggers_on_task_completed(self):
        rule = TaskFollowUpRule()
        event = _event(EventType.TASK_COMPLETED, {
            "task_id": "t1",
            "title": "My task",
        })
        rec = rule.apply(event, 1)
        assert rec is not None
        assert rec.rule_id == "task_follow_up_rule"
        assert rec.rule_version == 1
        assert rec.category == RecommendationCategory.FOLLOW_UP
        assert rec.target_entity == "t1"

    def test_no_trigger_on_other_event_type(self):
        rule = TaskFollowUpRule()
        event = _event(EventType.TASK_CREATED, {"task_id": "t1"})
        rec = rule.apply(event, 1)
        assert rec is None


class TestDecisionReviewRule:
    def test_metadata(self):
        rule = DecisionReviewRule()
        m = rule.metadata
        assert m.id == "decision_review_rule"
        assert m.version == 1
        assert m.category == RecommendationCategory.OPTIMIZATION

    def test_triggers_on_decision_accepted(self):
        rule = DecisionReviewRule()
        event = _event(EventType.DECISION_ACCEPTED, {
            "decision_id": "d1",
            "title": "Use Rust",
        })
        rec = rule.apply(event, 1)
        assert rec is not None
        assert rec.rule_id == "decision_review_rule"
        assert rec.rule_version == 1
        assert rec.category == RecommendationCategory.OPTIMIZATION


class TestQuestionResolutionRule:
    def test_metadata(self):
        rule = QuestionResolutionRule()
        m = rule.metadata
        assert m.id == "question_resolution_rule"
        assert m.version == 1
        assert m.category == RecommendationCategory.NEXT_ACTION

    def test_triggers_on_question_resolved(self):
        rule = QuestionResolutionRule()
        event = _event(EventType.OPEN_QUESTION_RESOLVED, {
            "question_id": "q1",
            "question": "Should we?",
        })
        rec = rule.apply(event, 1)
        assert rec is not None
        assert rec.rule_id == "question_resolution_rule"
        assert rec.rule_version == 1
        assert rec.category == RecommendationCategory.NEXT_ACTION


class TestKnowledgeDeletionRiskRule:
    def test_metadata(self):
        rule = KnowledgeDeletionRiskRule()
        m = rule.metadata
        assert m.id == "knowledge_deletion_risk_rule"
        assert m.version == 1
        assert m.category == RecommendationCategory.RISK

    def test_triggers_on_knowledge_deleted(self):
        rule = KnowledgeDeletionRiskRule()
        event = _event(EventType.KNOWLEDGE_DELETED, {
            "knowledge_id": "k1",
        })
        rec = rule.apply(event, 1)
        assert rec is not None
        assert rec.rule_id == "knowledge_deletion_risk_rule"
        assert rec.rule_version == 1
        assert rec.category == RecommendationCategory.RISK

    def test_no_trigger_on_other_event_type(self):
        rule = KnowledgeDeletionRiskRule()
        event = _event(EventType.KNOWLEDGE_CREATED, {
            "knowledge_id": "k1",
        })
        rec = rule.apply(event, 1)
        assert rec is None


# ── RecommendationRuleRegistry Tests ─────────────────────────────────────────


class TestRecommendationRuleRegistry:
    def test_register_and_freeze(self):
        registry = RecommendationRuleRegistry()
        registry.register(KnowledgeGapRule())
        registry.register(TaskFollowUpRule())
        registry.freeze()
        assert len(registry.rules()) == 2
        ids = registry.rule_ids
        assert "knowledge_gap_rule" in ids
        assert "task_follow_up_rule" in ids

    def test_deterministic_ordering(self):
        registry = RecommendationRuleRegistry()
        registry.register(TaskFollowUpRule())
        registry.register(KnowledgeGapRule())
        registry.register(DecisionReviewRule())
        registry.freeze()
        ids = registry.rule_ids
        assert ids == sorted(ids)

    def test_cannot_register_after_freeze(self):
        registry = RecommendationRuleRegistry()
        registry.freeze()
        try:
            registry.register(KnowledgeGapRule())
            assert False, "Should have raised RuntimeError"
        except RuntimeError:
            pass

    def test_cannot_get_rules_before_freeze(self):
        registry = RecommendationRuleRegistry()
        registry.register(KnowledgeGapRule())
        try:
            registry.rules()
            assert False, "Should have raised RuntimeError"
        except RuntimeError:
            pass

    def test_duplicate_detection(self):
        registry = RecommendationRuleRegistry()
        registry.register(KnowledgeGapRule())
        try:
            registry.register(KnowledgeGapRule())
            assert False, "Should have raised ValueError"
        except ValueError:
            pass

    def test_rule_metadata(self):
        registry = create_default_registry()
        metadata = registry.rule_metadata()
        assert len(metadata) == 5
        ids = [m.id for m in metadata]
        assert ids == sorted(ids)
        for m in metadata:
            assert isinstance(m, RecommendationRuleMetadata)


# ── RecommendationProjection Tests ──────────────────────────────────────────


class TestRecommendationProjection:
    def _get_projection(self):
        return RecommendationProjection()

    def test_metadata(self):
        proj = self._get_projection()
        m = proj.metadata
        assert m.id == "recommendation"
        assert m.version == 1
        assert m.schema_version == 1
        assert m.capabilities.searchable is True
        assert m.capabilities.snapshotable is True
        assert m.capabilities.exportable is True
        assert m.capabilities.mutable is False
        assert len(m.consumed_events.types) == 6

    def test_metadata_has_dependencies(self):
        proj = self._get_projection()
        deps = proj.metadata.dependencies
        assert len(deps) == 2
        dep_ids = {d.projection_id for d in deps}
        assert "knowledge" in dep_ids
        assert "embedding" in dep_ids

    def test_health_lifecycle(self):
        proj = self._get_projection()
        assert proj.health() == ProjectionHealth.UNKNOWN

        proj.initialize(None)
        assert proj.health() == ProjectionHealth.INITIALIZING

        events = [_event(EventType.TASK_COMPLETED, {
            "task_id": "t1", "title": "Task",
        }, 1)]
        proj.reduce(events)
        assert proj.health() == ProjectionHealth.READY

        proj.shutdown()
        assert proj.health() == ProjectionHealth.SHUTDOWN

    def test_reduce_empty_events(self):
        proj = self._get_projection()
        state = proj.reduce([])
        assert state.recommendations == []
        assert state.sequence == 0

    def test_reduce_generates_recommendations(self):
        proj = self._get_projection()
        events = [
            _event(EventType.KNOWLEDGE_CREATED, {
                "knowledge_id": "k1", "title": "Test",
            }, 1),
            _event(EventType.TASK_COMPLETED, {
                "task_id": "t1", "title": "Task",
            }, 2),
        ]
        state = proj.reduce(events)
        assert len(state.recommendations) == 2
        assert state.sequence == 2

    def test_reduce_sorted_by_id(self):
        proj = self._get_projection()
        events = [
            _event(EventType.TASK_COMPLETED, {
                "task_id": "t1", "title": "Task",
            }, 2),
            _event(EventType.KNOWLEDGE_CREATED, {
                "knowledge_id": "k1", "title": "Test",
            }, 1),
        ]
        state = proj.reduce(events)
        ids = [r.id for r in state.recommendations]
        assert ids == sorted(ids)

    def test_reduce_with_initial_state(self):
        proj1 = self._get_projection()
        events1 = [_event(EventType.KNOWLEDGE_CREATED, {
            "knowledge_id": "k1", "title": "Test",
        }, 1)]
        state1 = proj1.reduce(events1)

        proj2 = self._get_projection()
        events2 = [_event(EventType.TASK_COMPLETED, {
            "task_id": "t1", "title": "Task",
        }, 2)]
        state2 = proj2.reduce(events2, initial_state=state1)

        assert len(state2.recommendations) == 2
        assert state2.sequence == 2

    def test_serialize_deterministic(self):
        proj = self._get_projection()
        events = [_event(EventType.KNOWLEDGE_CREATED, {
            "knowledge_id": "k1", "title": "Test",
        }, 1)]
        state = proj.reduce(events)
        s1 = proj.serialize(state)
        s2 = proj.serialize(state)
        assert s1 == s2

    def test_serialize_enums_are_strings(self):
        proj = self._get_projection()
        events = [_event(EventType.KNOWLEDGE_CREATED, {
            "knowledge_id": "k1", "title": "Test",
        }, 1)]
        state = proj.reduce(events)
        serialized = proj.serialize(state)
        rec = serialized["recommendations"][0]
        assert isinstance(rec["category"], str)

    def test_serialize_includes_rule_version(self):
        proj = self._get_projection()
        events = [_event(EventType.KNOWLEDGE_CREATED, {
            "knowledge_id": "k1", "title": "Test",
        }, 1)]
        state = proj.reduce(events)
        serialized = proj.serialize(state)
        rec = serialized["recommendations"][0]
        assert "rule_version" in rec
        assert rec["rule_version"] == 1

    def test_serialize_includes_evidence(self):
        proj = self._get_projection()
        events = [_event(EventType.KNOWLEDGE_CREATED, {
            "knowledge_id": "k1", "title": "Test",
        }, 1)]
        state = proj.reduce(events)
        serialized = proj.serialize(state)
        rec = serialized["recommendations"][0]
        assert "evidence" in rec
        assert len(rec["evidence"]) == 1
        assert rec["evidence"][0]["sequence"] == 1

    def test_deserialize_restores_state(self):
        proj = self._get_projection()
        events = [
            _event(EventType.KNOWLEDGE_CREATED, {
                "knowledge_id": "k1", "title": "Test",
            }, 1),
            _event(EventType.TASK_COMPLETED, {
                "task_id": "t1", "title": "Task",
            }, 2),
        ]
        state = proj.reduce(events)
        serialized = proj.serialize(state)
        restored = proj.deserialize(serialized)

        assert len(restored.recommendations) == 2
        categories = {r.category.value for r in restored.recommendations}
        assert "knowledge_gap" in categories
        assert "follow_up" in categories
        assert restored.sequence == 2

    def test_deserialize_restores_rule_version(self):
        proj = self._get_projection()
        events = [_event(EventType.KNOWLEDGE_CREATED, {
            "knowledge_id": "k1", "title": "Test",
        }, 1)]
        state = proj.reduce(events)
        serialized = proj.serialize(state)
        restored = proj.deserialize(serialized)
        assert restored.recommendations[0].rule_version == 1

    def test_deserialize_restores_evidence(self):
        proj = self._get_projection()
        events = [_event(EventType.KNOWLEDGE_CREATED, {
            "knowledge_id": "k1", "title": "Test",
        }, 1)]
        state = proj.reduce(events)
        serialized = proj.serialize(state)
        restored = proj.deserialize(serialized)
        rec = restored.recommendations[0]
        assert len(rec.evidence) == 1
        assert isinstance(rec.evidence[0], EvidenceReference)
        assert rec.evidence[0].sequence == 1

    def test_serialize_deserialize_roundtrip(self):
        proj = self._get_projection()
        events = [
            _event(EventType.KNOWLEDGE_CREATED, {
                "knowledge_id": "k1", "title": "Test",
            }, 1),
            _event(EventType.TASK_COMPLETED, {
                "task_id": "t1", "title": "Task",
            }, 2),
        ]
        state = proj.reduce(events)
        serialized = proj.serialize(state)
        restored = proj.deserialize(serialized)
        re_serialized = proj.serialize(restored)
        assert serialized == re_serialized

    def test_delta_replay(self):
        proj1 = self._get_projection()
        full_events = [
            _event(EventType.KNOWLEDGE_CREATED, {
                "knowledge_id": "k1", "title": "Test",
            }, 1),
            _event(EventType.TASK_COMPLETED, {
                "task_id": "t1", "title": "Task",
            }, 2),
            _event(EventType.DECISION_ACCEPTED, {
                "decision_id": "d1", "title": "Decision",
            }, 3),
        ]
        full_state = proj1.reduce(full_events)

        proj2 = self._get_projection()
        prefix_state = proj2.reduce(full_events[:1])

        proj3 = self._get_projection()
        delta_state = proj3.reduce(
            full_events[1:], initial_state=prefix_state,
        )

        full_ids = {r.id for r in full_state.recommendations}
        delta_ids = {r.id for r in delta_state.recommendations}
        assert full_ids == delta_ids
        assert full_state.sequence == delta_state.sequence

    def test_rule_hit_rate(self):
        proj = self._get_projection()
        events = [
            _event(EventType.KNOWLEDGE_CREATED, {
                "knowledge_id": "k1", "title": "Test",
            }, 1),
            _event(EventType.TASK_COMPLETED, {
                "task_id": "t1", "title": "Task",
            }, 2),
        ]
        proj.reduce(events)
        assert proj.rule_hit_rate > 0
        assert proj.rule_hit_rate <= 1.0

    def test_shutdown_clears_context(self):
        proj = self._get_projection()
        ctx = object()
        proj.initialize(ctx)
        assert proj._ctx is ctx
        proj.shutdown()
        assert proj._ctx is None


# ── RecommendationRuntime Tests ─────────────────────────────────────────────


class TestRecommendationRuntime:
    def _make_state(self):
        return RecommendationState(
            recommendations=[
                Recommendation(
                    id="r1", rule_id="rule1", rule_version=1,
                    target_entity="t1",
                    category=RecommendationCategory.RISK,
                    priority=0.4, rationale="risk1",
                    created_at=datetime(2026, 1, 1),
                ),
                Recommendation(
                    id="r2", rule_id="rule2", rule_version=1,
                    target_entity="t1",
                    category=RecommendationCategory.FOLLOW_UP,
                    priority=0.8, rationale="follow1",
                    created_at=datetime(2026, 1, 1),
                ),
                Recommendation(
                    id="r3", rule_id="rule3", rule_version=1,
                    target_entity="t2",
                    category=RecommendationCategory.KNOWLEDGE_GAP,
                    priority=0.6, rationale="gap1",
                    created_at=datetime(2026, 1, 1),
                ),
            ],
            sequence=10,
        )

    def test_filter_by_entity(self):
        runtime = RecommendationRuntime()
        state = self._make_state()
        result = runtime.filter(state, entity="t1")
        assert len(result) == 2
        assert all(r.target_entity == "t1" for r in result)

    def test_filter_by_category(self):
        runtime = RecommendationRuntime()
        state = self._make_state()
        result = runtime.filter(
            state, category=RecommendationCategory.RISK,
        )
        assert len(result) == 1
        assert result[0].category == RecommendationCategory.RISK

    def test_enrich_no_dependencies(self):
        runtime = RecommendationRuntime()
        state = self._make_state()
        enriched = runtime.enrich(state.recommendations)
        assert len(enriched) == 3
        assert all(isinstance(e, RankedRecommendation) for e in enriched)
        assert all(e.semantic_similarity == 1.0 for e in enriched)
        assert all(e.knowledge_context is None for e in enriched)

    def test_rank_by_priority(self):
        runtime = RecommendationRuntime()
        state = self._make_state()
        enriched = runtime.enrich(state.recommendations)
        ctx = RecommendationQueryContext(
            query_time=datetime(2026, 6, 1),
        )
        ranked = runtime.rank(enriched, context=ctx)
        scores = [r.final_score for r in ranked]
        assert scores == sorted(scores, reverse=True)

    def test_search_combined(self):
        runtime = RecommendationRuntime()
        state = self._make_state()
        ctx = RecommendationQueryContext(
            query_time=datetime(2026, 6, 1),
        )
        result = runtime.search(
            state, entity="t1", k=1, context=ctx,
        )
        assert len(result) == 1
        assert isinstance(result[0], RankedRecommendation)
        assert result[0].recommendation.target_entity == "t1"

    def test_search_no_mutation(self):
        runtime = RecommendationRuntime()
        state = self._make_state()
        original_ids = [r.id for r in state.recommendations]
        runtime.search(state, entity="t1", k=10)
        current_ids = [r.id for r in state.recommendations]
        assert original_ids == current_ids

    def test_search_returns_ranked_recommendations(self):
        runtime = RecommendationRuntime()
        state = self._make_state()
        result = runtime.search(state, k=10)
        assert all(isinstance(r, RankedRecommendation) for r in result)
        assert all(hasattr(r, "final_score") for r in result)
        assert all(hasattr(r, "semantic_similarity") for r in result)

    def test_search_with_category_filter(self):
        runtime = RecommendationRuntime()
        state = self._make_state()
        ctx = RecommendationQueryContext(
            query_time=datetime(2026, 6, 1),
        )
        result = runtime.search(
            state,
            category=RecommendationCategory.FOLLOW_UP,
            k=10,
            context=ctx,
        )
        assert len(result) == 1
        assert result[0].recommendation.category == (
            RecommendationCategory.FOLLOW_UP
        )
