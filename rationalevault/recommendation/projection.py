"""Recommendation projection — pure event-to-state transformer.

Applies registered recommendation rules to produce a deterministic set of
recommendations stored in sorted ID order.
"""

from __future__ import annotations

from typing import Any, Optional

from rationalevault.projection_platform.models import (
    DependencyKind,
    EventSelector,
    ProjectionCapabilities,
    ProjectionDependency,
    ProjectionHealth,
    ProjectionMetadata,
)
from rationalevault.recommendation.rules import (
    RecommendationRuleRegistry,
    create_default_registry,
)
from rationalevault.recommendation.state import (
    Recommendation,
    RecommendationCategory,
    RecommendationState,
)
from rationalevault.schema.events import EventRecord, EventType


class RecommendationProjection:
    """Recommendation projection — derives deterministic analytical facts from event history.

    Archetype: Compose & Recommend
    """

    VERSION = 1
    SCHEMA_VERSION = 1

    def __init__(
        self,
        registry: Optional[RecommendationRuleRegistry] = None,
    ) -> None:
        self._health = ProjectionHealth.UNKNOWN
        self._ctx: Any = None
        self._registry = registry or create_default_registry()
        # Ensure frozen
        if not self._registry._frozen:
            self._registry.freeze()
        self._evaluations = 0
        self._hits = 0

    @property
    def rule_hit_rate(self) -> float:
        """Calculate the proportion of rule evaluations that generated a recommendation."""
        if self._evaluations == 0:
            return 0.0
        return self._hits / self._evaluations

    @property
    def metadata(self) -> ProjectionMetadata:
        # Define all consumed events across all rules
        consumed_types = {
            EventType.KNOWLEDGE_CREATED,
            EventType.KNOWLEDGE_UPDATED,
            EventType.KNOWLEDGE_DELETED,
            EventType.DECISION_ACCEPTED,
            EventType.TASK_COMPLETED,
            EventType.OPEN_QUESTION_RESOLVED,
        }
        return ProjectionMetadata(
            id="recommendation",
            version=self.VERSION,
            schema_version=self.SCHEMA_VERSION,
            consumed_events=EventSelector(types=frozenset(consumed_types)),
            capabilities=ProjectionCapabilities(
                searchable=True,
                snapshotable=True,
                observable=True,
                exportable=True,
                mutable=False,
            ),
            dependencies=(
                ProjectionDependency(
                    projection_id="knowledge",
                    kind=DependencyKind.STATE,
                ),
                ProjectionDependency(
                    projection_id="embedding",
                    kind=DependencyKind.SEARCH,
                    optional=True,
                ),
            ),
            description="Derived recommendations from event history",
        )

    def initialize(self, ctx: Any) -> None:
        """Called once when registered with the platform."""
        self._ctx = ctx
        self._health = ProjectionHealth.INITIALIZING

    def reduce(
        self,
        events: list[EventRecord],
        initial_state: Optional[RecommendationState] = None,
    ) -> RecommendationState:
        """Pure event-to-state transformer.

        Runs each event against the deterministic set of rules.
        """
        state = (
            initial_state
            if initial_state is not None
            else RecommendationState(recommendations=[], sequence=0)
        )

        self._health = ProjectionHealth.BUILDING

        # Put existing recommendations in a dict for fast updates/de-duplication
        # Since we use deterministic ID, we can overwrite or add new ones
        recs_by_id = {r.id: r for r in state.recommendations}

        rules = self._registry.rules()

        for event in events:
            for rule in rules:
                self._evaluations += 1
                rec = rule.apply(event, self.VERSION)
                if rec is not None:
                    self._hits += 1
                    recs_by_id[rec.id] = rec
            state.sequence = max(state.sequence, event.event_sequence)

        # Ensure stored sorted by ID for stable/deterministic order
        state.recommendations = sorted(recs_by_id.values(), key=lambda r: r.id)

        self._health = ProjectionHealth.READY
        return state

    def serialize(self, state: RecommendationState) -> dict:
        """Snapshot state to a dict."""
        return {
            "recommendations": [
                {
                    "id": r.id,
                    "rule_id": r.rule_id,
                    "rule_version": r.rule_version,
                    "target_entity": r.target_entity,
                    "category": r.category.value,
                    "priority": r.priority,
                    "rationale": r.rationale,
                    "evidence": [
                        {"sequence": ev.sequence, "reason": ev.reason}
                        for ev in r.evidence
                    ],
                    "created_at": (
                        r.created_at.isoformat() if r.created_at else None
                    ),
                    "event_type": r.event_type.value if r.event_type else None,
                }
                for r in state.recommendations
            ],
            "sequence": state.sequence,
            "schema_version": self.SCHEMA_VERSION,
        }

    def deserialize(self, payload: dict) -> RecommendationState:
        """Restore state from a dict."""
        from datetime import datetime
        from rationalevault.schema.events import EventType
        from rationalevault.recommendation.state import EvidenceReference

        recs = []
        for r in payload.get("recommendations", []):
            created_at = r.get("created_at")
            if created_at and isinstance(created_at, str):
                created_at = datetime.fromisoformat(created_at)

            event_type = r.get("event_type")
            if event_type:
                event_type = EventType(event_type)

            evidence = []
            for ev in r.get("evidence", []):
                evidence.append(
                    EvidenceReference(
                        sequence=ev["sequence"],
                        reason=ev.get("reason"),
                    )
                )

            recs.append(
                Recommendation(
                    id=r["id"],
                    rule_id=r["rule_id"],
                    rule_version=r.get("rule_version", 1),
                    target_entity=r["target_entity"],
                    category=RecommendationCategory(r["category"]),
                    priority=r["priority"],
                    rationale=r["rationale"],
                    evidence=evidence,
                    created_at=created_at,
                    event_type=event_type,
                )
            )

        # Keep sorted by id
        recs.sort(key=lambda r: r.id)

        return RecommendationState(
            recommendations=recs,
            sequence=payload.get("sequence", 0),
        )

    def health(self) -> ProjectionHealth:
        """Current health state."""
        return self._health

    def shutdown(self) -> None:
        """Clean teardown."""
        self._health = ProjectionHealth.SHUTDOWN
        self._ctx = None
