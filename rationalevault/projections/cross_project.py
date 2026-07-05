"""RationaleVault Cross-Project Projection — Knowledge transfer across boundaries.

CrossProjectState = CrossProjectProjection.project(current_project_id, current_knowledge, target_knowledge)

Discovers transferable knowledge from other projects while preserving
provenance and maintaining project isolation. Consumes KnowledgeObjects
directly (primary state), never KnowledgeStates (derived state).
"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, ClassVar
from rationalevault.projections.base import BaseProjection, ProjectionKind, SemVer

from rationalevault.knowledge.models import (
    KnowledgeObject,
    KnowledgeTransferability,
    is_transferable,
)


# ── CrossProjectKnowledge ────────────────────────────────────────────────────

@dataclass
class CrossProjectKnowledge:
    """A knowledge item transferred from another project."""
    knowledge_id: str
    source_project_id: str
    title: str
    content: str
    knowledge_type: str
    transferability: str
    confidence: float
    relevance_score: float = 0.0
    matched_terms: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)


# ── CrossProjectHealth ───────────────────────────────────────────────────────

@dataclass
class CrossProjectHealth:
    """Health metrics for cross-project transfer."""
    total_projects: int
    total_transferable: int
    reusable_count: int
    organizational_count: int
    coverage: float  # transferable / total


# ── CrossProjectState ────────────────────────────────────────────────────────

@dataclass
class CrossProjectState:
    """Compiled cross-project knowledge state.

    Built from KnowledgeObject collections by CrossProjectProjection.
    """
    project_id: str  # requesting project
    compiled_at: str
    projection_version: str = "1.0"
    source_projects: list[str] = field(default_factory=list)
    transferable_knowledge: list[CrossProjectKnowledge] = field(default_factory=list)
    knowledge_by_project: dict[str, list[str]] = field(default_factory=dict)
    provenance_map: dict[str, str] = field(default_factory=dict)  # kid -> project_id
    related_projects: dict[str, float] = field(default_factory=dict)  # project_id -> similarity
    health: Optional[CrossProjectHealth] = None

    def to_dict(self) -> dict:
        return {
            "project_id": self.project_id,
            "compiled_at": self.compiled_at,
            "projection_version": self.projection_version,
            "source_projects": self.source_projects,
            "transferable_knowledge_count": len(self.transferable_knowledge),
            "knowledge_by_project": self.knowledge_by_project,
            "provenance_map": self.provenance_map,
            "related_projects": self.related_projects,
            "health": {
                "total_projects": self.health.total_projects,
                "total_transferable": self.health.total_transferable,
                "reusable_count": self.health.reusable_count,
                "organizational_count": self.health.organizational_count,
                "coverage": round(self.health.coverage, 4),
            } if self.health else None,
        }


# ── CrossProjectProjection ───────────────────────────────────────────────────

class CrossProjectProjection(BaseProjection):
    """Builds cross-project knowledge state from KnowledgeObject collections.

    Consumes primary state (KnowledgeObjects), never derived state (KnowledgeStates).
    Deterministic: same inputs → identical output.
    """
    projection_name: ClassVar[str] = "CrossProject"
    version: ClassVar[SemVer] = SemVer(1, 0, 0)
    projection_kind: ClassVar[ProjectionKind] = ProjectionKind.DERIVED
    dependencies: ClassVar[list[type[BaseProjection]]] = []
    architectural_dependencies: ClassVar[list[str]] = []
    build_priority: ClassVar[int] = 40

    @staticmethod
    def project(
        current_project_id: str,
        current_knowledge: list[KnowledgeObject],
        target_knowledge: dict[str, list[KnowledgeObject]],
        query: str = "",
        transferability_filter: list[str] | None = None,
        reference_time: Optional[datetime] = None,
    ) -> CrossProjectState:
        """Build cross-project knowledge state.

        Args:
            current_project_id: ID of the requesting project
            current_knowledge: Knowledge from the current project (for similarity)
            target_knowledge: Knowledge from other projects {project_id: [knowledge]}
            query: Search query for relevance scoring
            transferability_filter: If set, only include these transferability levels
            reference_time: Optional reference time to run projection deterministically.

        Returns:
            CrossProjectState with transferable knowledge and metadata
        """
        from rationalevault.organization.utils import resolve_compiled_at
        now = resolve_compiled_at(reference_time)

        # 1. Collect transferable knowledge from target projects
        transferable: list[CrossProjectKnowledge] = []
        knowledge_by_project: dict[str, list[str]] = {}
        provenance_map: dict[str, str] = {}

        for proj_id, knowledge_list in target_knowledge.items():
            knowledge_by_project[proj_id] = []
            for k in knowledge_list:
                # Check transferability
                if not is_transferable(k.transferability):
                    continue

                # Apply filter if specified
                if transferability_filter and k.transferability not in transferability_filter:
                    continue

                # Score relevance
                relevance, matched = _score_relevance(k, query)

                # Build transfer record
                record = CrossProjectKnowledge(
                    knowledge_id=k.id,
                    source_project_id=proj_id,
                    title=k.title,
                    content=k.content,
                    knowledge_type=k.knowledge_type.value,
                    transferability=k.transferability,
                    confidence=k.confidence.score,
                    relevance_score=relevance,
                    matched_terms=matched,
                    reasons=_build_reasons(k, relevance, matched),
                )
                transferable.append(record)
                knowledge_by_project[proj_id].append(k.id)
                provenance_map[k.id] = proj_id

        # 2. Compute related projects (similarity based on knowledge overlap)
        related_projects = _compute_related_projects(current_knowledge, target_knowledge)

        # 3. Compute health
        total_all = sum(len(klist) for klist in target_knowledge.values())
        total_transferable = sum(
            sum(1 for k in klist if is_transferable(k.transferability))
            for klist in target_knowledge.values()
        )
        reusable_count = sum(
            1 for klist in target_knowledge.values()
            for k in klist if k.transferability == KnowledgeTransferability.REUSABLE.value
        )
        org_count = sum(
            1 for klist in target_knowledge.values()
            for k in klist if k.transferability == KnowledgeTransferability.ORGANIZATIONAL.value
        )
        coverage = total_transferable / total_all if total_all > 0 else 0.0

        health = CrossProjectHealth(
            total_projects=len(target_knowledge),
            total_transferable=total_transferable,
            reusable_count=reusable_count,
            organizational_count=org_count,
            coverage=coverage,
        )

        return CrossProjectState(
            project_id=current_project_id,
            compiled_at=now,
            source_projects=sorted(target_knowledge.keys()),
            transferable_knowledge=transferable,
            knowledge_by_project=knowledge_by_project,
            provenance_map=provenance_map,
            related_projects=related_projects,
            health=health,
        )


# ── Internal Helpers ─────────────────────────────────────────────────────────

def _score_relevance(knowledge: KnowledgeObject, query: str) -> tuple[float, list[str]]:
    """Score relevance of a knowledge item to a query.

    Returns (score, matched_terms).
    """
    if not query:
        return 0.5, []

    query_lower = query.lower()
    query_terms = set(query_lower.split())

    text = f"{knowledge.title} {knowledge.content}".lower()
    matched = [t for t in query_terms if t in text]

    if not matched:
        return 0.0, []

    # Simple term-match scoring
    score = len(matched) / len(query_terms) if query_terms else 0.0

    # Bonus for exact title match
    if query_lower in knowledge.title.lower():
        score = min(1.0, score + 0.3)

    return min(1.0, score), matched


def _build_reasons(
    knowledge: KnowledgeObject,
    relevance: float,
    matched_terms: list[str],
) -> list[str]:
    """Build human-readable reasons for transfer."""
    reasons = []

    if knowledge.transferability == KnowledgeTransferability.ORGANIZATIONAL.value:
        reasons.append("organizational_knowledge")
    elif knowledge.transferability == KnowledgeTransferability.REUSABLE.value:
        reasons.append("reusable_knowledge")

    if relevance >= 0.8:
        reasons.append("high_query_relevance")
    elif relevance >= 0.5:
        reasons.append("moderate_query_relevance")

    if matched_terms:
        reasons.append(f"matched_terms:{','.join(matched_terms)}")

    if knowledge.confidence.score >= 0.9:
        reasons.append("high_confidence")

    if not reasons:
        reasons.append("general_relevance")

    return reasons


def _compute_related_projects(
    current_knowledge: list[KnowledgeObject],
    target_knowledge: dict[str, list[KnowledgeObject]],
) -> dict[str, float]:
    """Compute similarity scores between current project and target projects."""
    if not current_knowledge:
        return {pid: 0.0 for pid in target_knowledge}

    # Build term sets from current project
    current_terms: set[str] = set()
    for k in current_knowledge:
        words = k.title.lower().split()
        current_terms.update(words)

    related: dict[str, float] = {}
    for proj_id, knowledge_list in target_knowledge.items():
        if not knowledge_list:
            related[proj_id] = 0.0
            continue

        target_terms: set[str] = set()
        for k in knowledge_list:
            words = k.title.lower().split()
            target_terms.update(words)

        if not target_terms:
            related[proj_id] = 0.0
            continue

        # Jaccard similarity
        intersection = current_terms & target_terms
        union = current_terms | target_terms
        related[proj_id] = len(intersection) / len(union) if union else 0.0

    return related
