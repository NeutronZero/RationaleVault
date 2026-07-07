"""Recommendation rules — deterministic analytical fact generation.

Each rule examines an event and may produce a Recommendation.
Rules are registered in a RecommendationRuleRegistry, which ensures
deterministic ordering by (rule_id, rule_version) during replay.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

from rationalevault.recommendation.state import (
    EvidenceReference,
    Recommendation,
    RecommendationCategory,
    RecommendationRuleMetadata,
)
from rationalevault.schema.events import EventRecord, EventType


class RecommendationRule(ABC):
    """Abstract base for deterministic recommendation rules.

    Subclass this and implement apply() to define new rules.
    The metadata provides stable identification and versioning.
    """

    @property
    @abstractmethod
    def metadata(self) -> RecommendationRuleMetadata:
        """Rule metadata (id, version, category, description)."""

    @abstractmethod
    def apply(
        self,
        event: EventRecord,
        projection_version: int,
    ) -> Optional[Recommendation]:
        """Return a Recommendation or None if rule does not apply."""


class RecommendationRuleRegistry:
    """Deterministic registry for recommendation rules.

    Rules are keyed by (id, version) and sorted deterministically
    before replay to ensure reproducible generation.
    """

    def __init__(self) -> None:
        self._rules: dict[tuple[str, int], RecommendationRule] = {}
        self._frozen = False

    def register(self, rule: RecommendationRule) -> None:
        """Register a rule. Raises if frozen or duplicate."""
        if self._frozen:
            raise RuntimeError("Registry is frozen")
        key = (rule.metadata.id, rule.metadata.version)
        if key in self._rules:
            raise ValueError(f"Rule {key} already registered")
        self._rules[key] = rule

    def freeze(self) -> None:
        """Freeze the registry."""
        self._frozen = True

    def rules(self) -> list[RecommendationRule]:
        """Return rules in deterministic order. Must be frozen."""
        if not self._frozen:
            raise RuntimeError("Registry must be frozen before use")
        return [self._rules[k] for k in sorted(self._rules.keys())]

    def rule_metadata(self) -> list[RecommendationRuleMetadata]:
        """Return rule metadata in deterministic order."""
        return [r.metadata for r in self.rules()]

    @property
    def rule_ids(self) -> list[str]:
        """Return rule IDs in deterministic order."""
        return [m.id for m in self.rule_metadata()]


# ── Concrete Rules ───────────────────────────────────────────────────────────


class KnowledgeGapRule(RecommendationRule):
    """Detects when knowledge is created without cross-referencing.

    Rule: If a KNOWLEDGE_CREATED event has no 'related_to' field,
    recommend reviewing existing knowledge for overlap.
    """

    @property
    def metadata(self) -> RecommendationRuleMetadata:
        return RecommendationRuleMetadata(
            id="knowledge_gap_rule",
            version=1,
            category=RecommendationCategory.KNOWLEDGE_GAP,
            description=(
                "Detects knowledge created without cross-references"
            ),
        )

    def apply(
        self,
        event: EventRecord,
        projection_version: int,
    ) -> Optional[Recommendation]:
        if event.event_type != EventType.KNOWLEDGE_CREATED:
            return None

        if event.payload.get("related_to"):
            return None

        knowledge_id = event.payload.get(
            "knowledge_id", event.payload.get("id", ""),
        )
        title = event.payload.get("title", "untitled")

        return Recommendation(
            id=Recommendation.make_id(
                projection_version,
                self.metadata.id,
                self.metadata.version,
                knowledge_id,
                event.event_sequence,
            ),
            rule_id=self.metadata.id,
            rule_version=self.metadata.version,
            target_entity=knowledge_id,
            category=self.metadata.category,
            priority=0.85,
            rationale=(
                f"Knowledge '{title}' created without "
                "cross-references. Review existing knowledge "
                "for overlap."
            ),
            evidence=[
                EvidenceReference(
                    sequence=event.event_sequence,
                    reason="triggering_event",
                ),
            ],
            created_at=event.recorded_at,
            event_type=event.event_type,
        )


class TaskFollowUpRule(RecommendationRule):
    """Recommends follow-up when a task is completed.

    Rule: If a TASK_COMPLETED event is recorded, suggest review
    or next steps.
    """

    @property
    def metadata(self) -> RecommendationRuleMetadata:
        return RecommendationRuleMetadata(
            id="task_follow_up_rule",
            version=1,
            category=RecommendationCategory.FOLLOW_UP,
            description=(
                "Recommends follow-up when a task is completed"
            ),
        )

    def apply(
        self,
        event: EventRecord,
        projection_version: int,
    ) -> Optional[Recommendation]:
        if event.event_type != EventType.TASK_COMPLETED:
            return None

        task_id = event.payload.get("task_id", "")
        title = event.payload.get("title", "untitled")

        return Recommendation(
            id=Recommendation.make_id(
                projection_version,
                self.metadata.id,
                self.metadata.version,
                task_id,
                event.event_sequence,
            ),
            rule_id=self.metadata.id,
            rule_version=self.metadata.version,
            target_entity=task_id,
            category=self.metadata.category,
            priority=0.65,
            rationale=(
                f"Task '{title}' completed. "
                "Consider review or follow-up actions."
            ),
            evidence=[
                EvidenceReference(
                    sequence=event.event_sequence,
                    reason="triggering_event",
                ),
            ],
            created_at=event.recorded_at,
            event_type=event.event_type,
        )


class DecisionReviewRule(RecommendationRule):
    """Recommends review when a decision is accepted.

    Rule: If a DECISION_ACCEPTED event is recorded, suggest
    documenting the rationale.
    """

    @property
    def metadata(self) -> RecommendationRuleMetadata:
        return RecommendationRuleMetadata(
            id="decision_review_rule",
            version=1,
            category=RecommendationCategory.OPTIMIZATION,
            description=(
                "Recommends review when a decision is accepted"
            ),
        )

    def apply(
        self,
        event: EventRecord,
        projection_version: int,
    ) -> Optional[Recommendation]:
        if event.event_type != EventType.DECISION_ACCEPTED:
            return None

        decision_id = event.payload.get("decision_id", "")
        title = event.payload.get("title", "untitled")

        return Recommendation(
            id=Recommendation.make_id(
                projection_version,
                self.metadata.id,
                self.metadata.version,
                decision_id,
                event.event_sequence,
            ),
            rule_id=self.metadata.id,
            rule_version=self.metadata.version,
            target_entity=decision_id,
            category=self.metadata.category,
            priority=0.55,
            rationale=(
                f"Decision '{title}' accepted. "
                "Document rationale for future reference."
            ),
            evidence=[
                EvidenceReference(
                    sequence=event.event_sequence,
                    reason="triggering_event",
                ),
            ],
            created_at=event.recorded_at,
            event_type=event.event_type,
        )


class QuestionResolutionRule(RecommendationRule):
    """Recommends knowledge capture when a question is resolved.

    Rule: If OPEN_QUESTION_RESOLVED is recorded, suggest
    converting the resolution to knowledge.
    """

    @property
    def metadata(self) -> RecommendationRuleMetadata:
        return RecommendationRuleMetadata(
            id="question_resolution_rule",
            version=1,
            category=RecommendationCategory.NEXT_ACTION,
            description=(
                "Recommends knowledge capture on question resolution"
            ),
        )

    def apply(
        self,
        event: EventRecord,
        projection_version: int,
    ) -> Optional[Recommendation]:
        if event.event_type != EventType.OPEN_QUESTION_RESOLVED:
            return None

        question_id = event.payload.get("question_id", "")
        question = event.payload.get("question", "")

        return Recommendation(
            id=Recommendation.make_id(
                projection_version,
                self.metadata.id,
                self.metadata.version,
                question_id,
                event.event_sequence,
            ),
            rule_id=self.metadata.id,
            rule_version=self.metadata.version,
            target_entity=question_id,
            category=self.metadata.category,
            priority=0.75,
            rationale=(
                f"Question '{question}' resolved. "
                "Consider converting resolution to knowledge."
            ),
            evidence=[
                EvidenceReference(
                    sequence=event.event_sequence,
                    reason="triggering_event",
                ),
            ],
            created_at=event.recorded_at,
            event_type=event.event_type,
        )


class KnowledgeDeletionRiskRule(RecommendationRule):
    """Flags risk when knowledge is deleted.

    Rule: If KNOWLEDGE_DELETED is recorded, flag as risk
    (potential knowledge loss).
    """

    @property
    def metadata(self) -> RecommendationRuleMetadata:
        return RecommendationRuleMetadata(
            id="knowledge_deletion_risk_rule",
            version=1,
            category=RecommendationCategory.RISK,
            description=(
                "Flags risk when knowledge is deleted"
            ),
        )

    def apply(
        self,
        event: EventRecord,
        projection_version: int,
    ) -> Optional[Recommendation]:
        if event.event_type != EventType.KNOWLEDGE_DELETED:
            return None

        knowledge_id = event.payload.get(
            "knowledge_id", event.payload.get("id", ""),
        )

        return Recommendation(
            id=Recommendation.make_id(
                projection_version,
                self.metadata.id,
                self.metadata.version,
                knowledge_id,
                event.event_sequence,
            ),
            rule_id=self.metadata.id,
            rule_version=self.metadata.version,
            target_entity=knowledge_id,
            category=self.metadata.category,
            priority=0.45,
            rationale=(
                f"Knowledge '{knowledge_id}' deleted. "
                "Review for potential knowledge loss."
            ),
            evidence=[
                EvidenceReference(
                    sequence=event.event_sequence,
                    reason="triggering_event",
                ),
            ],
            created_at=event.recorded_at,
            event_type=event.event_type,
        )


def create_default_registry() -> RecommendationRuleRegistry:
    """Create a registry with all default rules registered and frozen."""
    registry = RecommendationRuleRegistry()
    registry.register(KnowledgeGapRule())
    registry.register(TaskFollowUpRule())
    registry.register(DecisionReviewRule())
    registry.register(QuestionResolutionRule())
    registry.register(KnowledgeDeletionRiskRule())
    registry.freeze()
    return registry
