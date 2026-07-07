"""Recommendation projection state — data model and state container."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from rationalevault.schema.events import EventType


class RecommendationCategory(Enum):
    """Category of recommendation."""

    NEXT_ACTION = "next_action"
    KNOWLEDGE_GAP = "knowledge_gap"
    RISK = "risk"
    OPTIMIZATION = "optimization"
    FOLLOW_UP = "follow_up"


@dataclass(frozen=True)
class EvidenceReference:
    """Typed evidence linking a recommendation to supporting events.

    Attributes:
        sequence: event sequence number
        reason: optional semantic role (e.g., "supporting", "contradicting")
    """

    sequence: int
    reason: str | None = None


@dataclass(frozen=True)
class RecommendationRuleMetadata:
    """Metadata for a recommendation rule.

    Attributes:
        id: stable rule identifier (e.g., "knowledge_gap_rule")
        version: rule version (allows evolution without changing projection)
        category: category of recommendations this rule produces
        description: human-readable description
    """

    id: str
    version: int
    category: RecommendationCategory
    description: str


@dataclass(frozen=True)
class Recommendation:
    """A deterministic analytical fact derived from events.

    Attributes:
        id: deterministic hash (sha256 of projection_version + rule_id
            + rule_version + target_entity + triggering_sequence)
        rule_id: stable identifier of the rule that generated this
        rule_version: version of the rule that generated this
        target_entity: task_id, decision_id, knowledge_id, etc.
        category: recommendation category
        priority: intrinsic priority (0-1), part of deterministic state
        rationale: human-readable justification
        evidence: supporting event sequences (typed EvidenceReference)
        created_at: when the recommendation was generated
        event_type: the event type that triggered this recommendation
    """

    id: str
    rule_id: str
    rule_version: int
    target_entity: str
    category: RecommendationCategory
    priority: float
    rationale: str
    evidence: list[EvidenceReference] = field(default_factory=list)
    created_at: datetime | None = None
    event_type: EventType | None = None

    @staticmethod
    def make_id(
        projection_version: int,
        rule_id: str,
        rule_version: int,
        target_entity: str,
        triggering_sequence: int,
    ) -> str:
        """Generate a deterministic recommendation ID."""
        raw = (
            f"{projection_version}:{rule_id}:"
            f"{rule_version}:{target_entity}:"
            f"{triggering_sequence}"
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class RankedRecommendation:
    """Enriched recommendation with runtime scoring.

    Returned by RecommendationRuntime.search(). Preserves
    enrichment data so CLI/MCP/Governance can render as needed.

    Attributes:
        recommendation: the base deterministic recommendation
        final_score: combined score after enrichment
        semantic_similarity: similarity score from embedding (1.0 if unavailable)
        knowledge_context: knowledge state context (None if unavailable)
    """

    recommendation: Recommendation
    final_score: float
    semantic_similarity: float = 1.0
    knowledge_context: Any | None = None


@dataclass(frozen=True)
class RecommendationQueryContext:
    """Deterministic query context for runtime ranking.

    Injecting this ensures: same state + same context → same answer.

    Attributes:
        query_time: when the query was made
        query: optional search query
        entity: optional entity filter
        category: optional category filter
    """

    query_time: datetime
    query: str | None = None
    entity: str | None = None
    category: RecommendationCategory | None = None


@dataclass
class RecommendationState:
    """Projection state — sorted list of recommendations.

    Attributes:
        recommendations: sorted by id (stable ordering)
        sequence: max processed event sequence
    """

    recommendations: list[Recommendation] = field(default_factory=list)
    sequence: int = 0

    @property
    def recommendation_count(self) -> int:
        """Number of recommendations."""
        return len(self.recommendations)

    @property
    def categories(self) -> set[RecommendationCategory]:
        """Set of categories present."""
        return {r.category for r in self.recommendations}
