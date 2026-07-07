"""Unit tests for Governance projection, rules, and runtime."""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4
import pytest

from rationalevault.projection_platform.context import DependencyReader
from rationalevault.governance.projection import GovernanceProjection
from rationalevault.governance.rules import GovernanceRuleRegistry
from rationalevault.governance.runtime import (
    DefaultEvidenceProvider,
    GovernanceRuntime,
    GovernanceEvidence,
)
from rationalevault.governance.state import (
    GovernanceAction,
    GovernanceCondition,
    GovernanceRule,
    GovernanceRuleMetadata,
    GovernanceSeverity,
    GovernanceState,
    GovernanceWarning,
)
from rationalevault.recommendation.state import (
    Recommendation,
    RecommendationCategory,
    RecommendationState,
)
from rationalevault.schema.events import EventMetadata, EventRecord, EventType


def _event(event_type: EventType, payload: dict, seq: int) -> EventRecord:
    return EventRecord(
        event_sequence=seq,
        id=uuid4(),
        project_id=uuid4(),
        stream_id="governance",
        version=seq,
        event_type=event_type,
        metadata=EventMetadata(actor="test", source="test"),
        payload=payload,
        parent_id=None,
        recorded_at=datetime.now(),
    )


class TestGovernanceProjection:
    def test_metadata(self):
        proj = GovernanceProjection()
        meta = proj.metadata
        assert meta.id == "governance"
        assert EventType.GOVERNANCE_RULE_CREATED in meta.consumed_events.types
        assert len(meta.dependencies) == 1
        assert meta.dependencies[0].projection_id == "recommendation"

    def test_reduce_lifecycle(self):
        proj = GovernanceProjection()
        events = [
            _event(EventType.GOVERNANCE_RULE_CREATED, {
                "metadata": {
                    "id": "policy_a",
                    "version": 1,
                    "description": "Risk gating",
                    "severity": "critical",
                    "action": "block",
                },
                "condition": {
                    "categories": ["risk"],
                    "minimum_priority": 0.8,
                },
            }, 1),
            _event(EventType.GOVERNANCE_RULE_CREATED, {
                "metadata": {
                    "id": "policy_b",
                    "version": 2,
                    "description": "Follow up logging",
                    "severity": "info",
                    "action": "log",
                },
                "condition": {
                    "categories": ["follow_up"],
                },
            }, 2),
        ]
        state = proj.reduce(events)
        assert state.rule_count == 2
        assert state.sequence == 2
        assert state.rules[0].metadata.id == "policy_a"
        assert state.rules[1].metadata.id == "policy_b"

        # Update policy_a
        events2 = [
            _event(EventType.GOVERNANCE_RULE_UPDATED, {
                "metadata": {
                    "id": "policy_a",
                    "version": 1,
                    "description": "Risk gating updated",
                    "severity": "critical",
                    "action": "block",
                },
                "condition": {
                    "categories": ["risk"],
                    "minimum_priority": 0.5,
                },
            }, 3),
        ]
        state = proj.reduce(events2, initial_state=state)
        assert state.rule_count == 2
        assert state.rules[0].condition.minimum_priority == 0.5

        # Delete policy_b
        events3 = [
            _event(EventType.GOVERNANCE_RULE_DELETED, {
                "rule_id": "policy_b",
                "version": 2,
            }, 4),
        ]
        state = proj.reduce(events3, initial_state=state)
        assert state.rule_count == 1
        assert state.rules[0].metadata.id == "policy_a"

    def test_serialization_roundtrip(self):
        proj = GovernanceProjection()
        events = [
            _event(EventType.GOVERNANCE_RULE_CREATED, {
                "metadata": {
                    "id": "policy_a",
                    "version": 1,
                    "severity": "critical",
                    "action": "block",
                },
                "condition": {
                    "categories": ["risk"],
                    "minimum_priority": 0.8,
                },
            }, 1),
        ]
        state = proj.reduce(events)
        serialized = proj.serialize(state)
        deserialized = proj.deserialize(serialized)

        assert deserialized.rule_count == 1
        rule = deserialized.rules[0]
        assert rule.metadata.id == "policy_a"
        assert rule.metadata.severity == GovernanceSeverity.CRITICAL
        assert rule.metadata.action == GovernanceAction.BLOCK
        assert rule.condition.categories == {RecommendationCategory.RISK}
        assert rule.condition.minimum_priority == 0.8


class TestGovernanceRegistry:
    def test_registry_operations(self):
        reg = GovernanceRuleRegistry()
        rule = GovernanceRule(
            metadata=GovernanceRuleMetadata("r1", 1, "", GovernanceSeverity.INFO, GovernanceAction.LOG),
            condition=GovernanceCondition(),
        )
        reg.register(rule)
        with pytest.raises(RuntimeError):
            reg.rules()  # Not frozen yet

        reg.freeze()
        assert reg.rule_ids == ["r1"]


class TestGovernanceRuntime:
    def test_evaluate_and_warnings(self):
        # Create rule state
        rule = GovernanceRule(
            metadata=GovernanceRuleMetadata(
                id="high_risk_rule",
                version=1,
                description="Flags critical risk",
                severity=GovernanceSeverity.CRITICAL,
                action=GovernanceAction.BLOCK,
            ),
            condition=GovernanceCondition(
                categories={RecommendationCategory.RISK},
                minimum_priority=0.7,
            ),
        )
        state = GovernanceState(rules=[rule], sequence=10)

        # Mock evidence provider
        class MockProvider:
            def collect(self, rule):
                from rationalevault.recommendation.state import EvidenceReference
                return GovernanceEvidence(
                    recommendations=[
                        Recommendation(
                            id="rec1",
                            rule_id="knowledge_gap_rule",
                            rule_version=1,
                            target_entity="k1",
                            category=RecommendationCategory.RISK,
                            priority=0.85,
                            rationale="Critical knowledge gap",
                            evidence=[EvidenceReference(sequence=5)],
                            created_at=datetime.now(),
                            event_type=EventType.KNOWLEDGE_CREATED,
                        )
                    ]
                )

        runtime = GovernanceRuntime()
        evals = runtime.evaluate_rules(state, MockProvider())
        assert len(evals) == 1
        assert evals[0].matched is True
        assert evals[0].matched_entities == ["k1"]
        assert evals[0].evidence == [5]

        warnings = runtime.generate_warnings(state, evals)
        assert len(warnings) == 1
        assert warnings[0].target_entity == "k1"
        assert warnings[0].severity == GovernanceSeverity.CRITICAL
        assert warnings[0].action == GovernanceAction.BLOCK
        assert warnings[0].evidence == [5]

        # Search
        res = runtime.search(warnings, severity=GovernanceSeverity.CRITICAL)
        assert len(res) == 1
        res = runtime.search(warnings, severity=GovernanceSeverity.INFO)
        assert len(res) == 0

    def test_default_evidence_provider(self):
        from rationalevault.recommendation.state import EvidenceReference
        reader = DependencyReader()
        rec_state = RecommendationState(
            recommendations=[
                Recommendation(
                    id="rec1",
                    rule_id="r1",
                    rule_version=1,
                    target_entity="e1",
                    category=RecommendationCategory.RISK,
                    priority=0.9,
                    rationale="Risk test",
                    evidence=[EvidenceReference(sequence=1)],
                )
            ]
        )
        reader.set("recommendation", rec_state)

        provider = DefaultEvidenceProvider(reader)
        rule = GovernanceRule(
            metadata=GovernanceRuleMetadata("high_risk", 1, "", GovernanceSeverity.CRITICAL, GovernanceAction.BLOCK),
            condition=GovernanceCondition(
                categories={RecommendationCategory.RISK},
                minimum_priority=0.8,
            ),
        )
        evidence = provider.collect(rule)
        assert len(evidence.recommendations) == 1
